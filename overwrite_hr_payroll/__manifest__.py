# -*- coding: utf-8 -*-
{
    'name': "Overwrite Hr_payroll",

    'summary': """
        Overwrite hr_payroll module for use Colombian configuration""",

    'description': """
        Overwrite hr_payroll module for use Colombian configuration
    """,

    'author': "Xphera SAS",
    'website': "http://xphera.co",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','hr','hr_payroll', 'hr_contract', 'hr_payroll_account_sepa'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'data/data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
