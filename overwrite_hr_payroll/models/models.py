from odoo import models, fields, api
from odoo.tools import date_utils
from datetime import date, datetime, time
from odoo.tools import float_compare, float_is_zero
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict


class overwrite_payroll_contract(models.Model):
    _inherit = 'hr.contract'
    tipo_de_contrato = fields.Selection(
        selection=[('1','Contrato a término indefinido'),
        ('2', 'Contrato integral'),
        ('3', 'Contrato a término fijo'),
        ('4', 'Contrato a término fijo SNH'),
        ('5', 'Contrato de aprendizaje'),
        ('6', 'Contrato de Obra o labor'),
        ('7', 'Contrato de relevantes'),
        ('8', 'Contrato de jornada tiempo parcial')]
    )

    eps = fields.Char(
        string='EPS',
        help='Ingrese la EPS',
        required=True,
    )

    caja_compensacion = fields.Char(
        string='Caja de compensación',
        help='Aquí se debe ingresar la caja de compensación',
        required=True,
    )

    fondo_pension = fields.Char(
        string='Fondo de pensiones',
        help='Aquí se debe ingresar la caja de compensación',
        required=True,
    )

    aseguradora_riesgo = fields.Char(
        string='Nombre de aseguradora ARL',
        help='Aquí se debe diligenciar el nombre de la aseguradora',
        required=True,
    )

    clase_riesgo = fields.Selection(
        string='Clase de riesgo',
        selection=[('1', 'Tipo I'),
                   ('2', 'Tipo II'),
                   ('3', 'Tipo III'),
                   ('4', 'Tipo IV'),
                   ('5', 'Tipo V')],
        required=True,
    )




class overwrite_payroll_employee(models.Model):
    _inherit = 'hr.employee'
#informacion personal
    ciudad_de_nacimiento = fields.Char()
    ciudad_actual = fields.Char()
    casa_propia = fields.Boolean(string='¿tiene casa propia?')
    carro_propio = fields.Boolean(string='¿tiene carro?')
    placas_carro =fields.Integer()

#informacion de documento
    tipo_de_documento = fields.Selection(
        string='Tipo de documento',
        selection=[('1', 'Cédula de ciudadanía'),
                   ('2', 'Cédula de extranjería'),
                   ('3', 'Pasaporte'),]
    )
    ciudad_de_expedicion = fields.Char()

#informacion de salud
    fuma = fields.Boolean(string='¿fuma?')
    estatura = fields.Integer(string="estatura en centimetros")
    anteojos = fields.Boolean(string='¿usa anteojos?')
    factor_rh = fields.Selection(
        string='Factor RH',
        selection=[('1', 'positivo'),
                   ('2', 'negativo'),]
    )
    grupo_sanguineo = fields.Selection(
        string='Grupo Sanguineo',
        selection=[('1', 'O'),
                   ('2', 'A'),
                   ('3', 'B'),
                   ('4', 'AB')]
    )
    embarazo = fields.Boolean(string='¿se encuentra en estado de embarazo?')

#informacion judicial
    libreta_militar = fields.Boolean(string='¿tiene libreta militar?')
    certificado_judicial = fields.Boolean()


class overwrite_payroll_payslip(models.Model):
    _inherit = 'hr.payslip'
    state = fields.Selection(selection_add=[('Descuento contable', 'Descuento contable')])
    sepa_journal_id = fields.Many2one(
        string='Bank Journal', comodel_name='account.journal', required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'bank')], limit=1))
    paid_move_id = fields.Many2one('account.move', 'asiento contable pago', readonly=True, copy=False)

    def _get_worked_day_lines(self):
        """
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        res = []
        # fill only if the contract as a working schedule linked
        self.ensure_one()
        contract = self.contract_id
        if contract.resource_calendar_id:
            paid_amount = self._get_contract_wage()
            unpaid_work_entry_types = self.struct_id.unpaid_work_entry_type_ids.ids

            work_hours = contract._get_work_hours(self.date_from, self.date_to)
            total_hours = sum(work_hours.values()) or 1
            total_days = 30.0
            total_days_work = 30.0
            work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
            biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
            add_days_rounding = 0
            for work_entry_type_id, hours in work_hours_ordered:
                work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
                is_paid = work_entry_type_id not in unpaid_work_entry_types
                calendar = contract.resource_calendar_id
                days = round(hours / calendar.hours_per_day, 0) if calendar.hours_per_day else 0
                if work_entry_type_id == biggest_work:
                    if((self.date_to.day == 30 or self.date_to.day == 31 
                    or ((self.date_to.day == 28 or self.date_to.day == 29) and self.date_to.month == 2))):
                        days  = total_days_work
                    days += add_days_rounding
                else:
                    total_days_work = total_days_work - days
                day_rounded = self._round_days(work_entry_type, days)
                add_days_rounding += (days - day_rounded)
                attendance_line = {
                    'sequence': work_entry_type.sequence,
                    'work_entry_type_id': work_entry_type_id,
                    'number_of_days': day_rounded,
                    'number_of_hours': hours,
                    'amount': day_rounded * paid_amount / total_days if is_paid else 0,
                }
                res.append(attendance_line)
        return res
    
    def action_payslip_paid_account(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))

        precision = self.env['decimal.precision'].precision_get('Payroll')

        # payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # payslip_runs = (self - payslips_to_post).mapped('payslip_run_id')
        # for run in payslip_runs:
        #     if run._are_payslips_ready():
        #         payslips_to_post |= run.slip_ids

        payslips_to_post = self.filtered(lambda slip: slip.state == 'paid' and slip.move_id)

        journal_id_slip = self.sepa_journal_id
        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contract for these payslips has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no account journal defined on it.'))    
        # Map all payslips by structure journal and pay slips month.
        # {'journal_id': {'month': [slip_ids]}}
        slip_mapped_data = {slip.struct_id.journal_id.id: {fields.Date().end_of(slip.date_to, 'month'): self.env['hr.payslip']} for slip in payslips_to_post}
        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][fields.Date().end_of(slip.date_to, 'month')] |= slip
        for journal_id in slip_mapped_data: # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]: # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                date = slip_date
                move_dict = {
                    'narration': '',
                    'ref': date.strftime('%B %Y'),
                    'journal_id': journal_id_slip.id,
                    'date': date,
                }

                for slip in slip_mapped_data[journal_id][slip_date]:
                    move_dict['narration'] += slip.number or '' + ' - ' + slip.employee_id.name or ''
                    move_dict['narration'] += '\n'
                    for line in slip.line_ids.filtered(lambda line: line.category_id):
                        amount = -line.total if slip.credit_note else line.total
                        if float_is_zero(amount, precision_digits=precision):
                            continue
                        if line.code == 'NET':
                            print("Entre al devengado")
                            debit_account_id = line.salary_rule_id.account_credit.id
                            credit_account_id =  journal_id_slip.default_debit_account_id.id

                            if debit_account_id: # If the rule has a debit account.
                                debit = amount if amount > 0.0 else 0.0
                                credit = -amount if amount < 0.0 else 0.0

                                existing_debit_lines = (
                                    line_id for line_id in line_ids if
                                    line_id['name'] == line.name
                                    and line_id['account_id'] == debit_account_id
                                    and line_id['analytic_account_id'] == (line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id)
                                    and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0)))
                                debit_line = next(existing_debit_lines, False)

                                if not debit_line:
                                    debit_line = {
                                        'name': line.name,
                                        'partner_id': line.partner_id.id,
                                        'account_id': debit_account_id,
                                        'journal_id': journal_id_slip.id,
                                        'date': date,
                                        'debit': debit,
                                        'credit': credit,
                                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                    }
                                    line_ids.append(debit_line)
                                else:
                                    debit_line['debit'] += debit
                                    debit_line['credit'] += credit
                            
                            if credit_account_id: # If the rule has a credit account.
                                debit = -amount if amount < 0.0 else 0.0
                                credit = amount if amount > 0.0 else 0.0
                                existing_credit_line = (
                                    line_id for line_id in line_ids if
                                    line_id['name'] == line.name
                                    and line_id['account_id'] == credit_account_id
                                    and line_id['analytic_account_id'] == (line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id)
                                    and ((line_id['debit'] > 0 and credit <= 0) or (line_id['credit'] > 0 and debit <= 0))
                                )
                                credit_line = next(existing_credit_line, False)

                                if not credit_line:
                                    credit_line = {
                                        'name': line.name,
                                        'partner_id': line.partner_id.id,
                                        'account_id': credit_account_id,
                                        'journal_id': journal_id_slip.id,
                                        'date': date,
                                        'debit': debit,
                                        'credit': credit,
                                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                                    }
                                    line_ids.append(credit_line)
                                else:
                                    credit_line['debit'] += debit
                                    credit_line['credit'] += credit

                for line_id in line_ids: # Get the debit and credit sum.
                    debit_sum += line_id['debit']
                    credit_sum += line_id['credit']

                # Add accounting lines in the move
                move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in line_ids]
                move = self.env['account.move'].create(move_dict)
                for slip in slip_mapped_data[journal_id][slip_date]:
                    print("entre al for de los asientos")
                    slip.write({'paid_move_id': move.id, 'date': date})
                    self.filtered(lambda slip: slip.state == 'paid').write({'state': 'Descuento contable'})


class overwrite_hr_payslip_employees(models.TransientModel):
    _inherit = 'hr.payslip.employees'
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees',
                                    default=None, required=True)

class overwrite_hr_payslip_sepa_wizard(models.TransientModel):
    _inherit = 'hr.payslip.sepa.wizard'

    def generate_sepa_xml_file(self):
        payslip_ids = self.env['hr.payslip'].browse(self.env.context['active_ids'])
        payslip_ids.sepa_journal_id = self.journal_id
        print(payslip_ids.sepa_journal_id.name)
        payslip_ids._create_xml_file(self.journal_id)

class overwrite_payroll_payslip_run(models.Model):
    _inherit = 'hr.payslip.run'
    state = fields.Selection(selection_add=[('Descuento contable', 'Descuento contable')])

    def action_desc(self):
        self.write({'state' : 'Descuento contable'})

    def action_validate_paid(self):
        self.mapped('slip_ids').filtered(lambda slip: slip.state != 'cancel').action_payslip_paid_account()
        self.action_desc()