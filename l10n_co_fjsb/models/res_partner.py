# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_co_fjsb_document_type = fields.Selection([('rut', 'NIT'),
                                              ('id_document', 'Cédula'),
                                              ('id_card', 'Tarjeta de Identidad'),
                                              ('passport', 'Pasaporte'),
                                              ('foreign_id_card', 'Cédula Extranjera'),
                                              ('external_id', 'ID del Exterior'),
                                              ('diplomatic_card', 'Carné Diplomatico'),
                                              ('residence_document', 'Salvoconducto de Permanencia'),
                                              ('civil_registration', 'Registro Civil'),
                                              ('national_citizen_id', 'Cédula de ciudadanía')], string='Document Type',
                                             help='Indicates to what document the information in here belongs to.')
    l10n_co_fjsb_verification_code = fields.Char(compute='_compute_verification_code', string='VC',  # todo remove this field in master
                                            help='Redundancy check to verify the vat number has been typed in correctly.')

    @api.depends('vat')
    def _compute_verification_code(self):
        multiplication_factors = [71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

        for partner in self:
            if partner.vat and partner.country_id == self.env.ref('base.co') and len(partner.vat) <= len(multiplication_factors):
                number = 0
                padded_vat = partner.vat

                while len(padded_vat) < len(multiplication_factors):
                    padded_vat = '0' + padded_vat

                # if there is a single non-integer in vat the verification code should be False
                try:
                    for index, vat_number in enumerate(padded_vat):
                        number += int(vat_number) * multiplication_factors[index]

                    number %= 11

                    if number < 2:
                        partner.l10n_co_fjsb_verification_code = number
                    else:
                        partner.l10n_co_fjsb_verification_code = 11 - number
                except ValueError:
                    partner.l10n_co_fjsb_verification_code = False
            else:
                partner.l10n_co_fjsb_verification_code = False

    @api.constrains('vat', 'country_id', 'l10n_co_fjsb_document_type')
    def check_vat(self):
        # check_vat is implemented by base_vat which this localization
        # doesn't directly depend on. It is however automatically
        # installed for Colombia.
        if self.sudo().env.ref('base.module_base_vat').state == 'installed':
            # don't check Colombian partners unless they have RUT (= Colombian VAT) set as document type
            self = self.filtered(lambda partner: partner.country_id != self.env.ref('base.co') or\
                                                 partner.l10n_co_fjsb_document_type == 'rut')
            return super(ResPartner, self).check_vat()
        else:
            return True


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _load(self, sale_tax_rate, purchase_tax_rate, company):
        res = super(AccountChartTemplate, self)._load(sale_tax_rate, purchase_tax_rate, company)

        # by default, anglo-saxon companies should have totals
        # displayed below sections in their reports
        company.totals_below_sections = True

        #set a default misc journal for the tax closure
        company.account_tax_periodicity_journal_id = company._get_default_misc_journal()

        company.account_tax_periodicity_reminder_day = 3

        company.use_anglo_saxon = True


        # create the recurring entry
        vals = {
            'company_id': company,
            'account_tax_periodicity': company.account_tax_periodicity,
            'account_tax_periodicity_journal_id': company.account_tax_periodicity_journal_id,
            'account_tax_periodicity_reminder_day': company.account_tax_periodicity_reminder_day,
            'use_anglo_saxon': company.use_anglo_saxon,
            'totals_below_sections': company.totals_below_sections,
        }
        config_settings = self.env['res.config.settings'].with_context(company=company)
        config_settings._create_edit_tax_reminder(vals)

        config_settings.group_analytic_accounting = True
        config_settings.group_analytic_accounting = True
        config_settings.group_analytic_tags = True
        config_settings.module_account_budget = True
        config_settings.module_product_margin = True
        config_settings.use_anglo_saxon = True

        config_settings.account_tax_periodicity_reminder_day = 3

        company.account_tax_original_periodicity_reminder_day = company.account_tax_periodicity_reminder_day

        return res
