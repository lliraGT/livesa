# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.tools.misc import format_date, DEFAULT_SERVER_DATE_FORMAT
from datetime import timedelta
import logging

class AccountGeneralLedgerReport(models.AbstractModel):
    _inherit = "account.general.ledger"

    @api.model
    def _get_columns_name(self, options):
        res = super(AccountGeneralLedgerReport, self)._get_columns_name(options)
        for c in res:
            logging.warning('C NAME')
            logging.warning(c['name'])
            if c['name'] == '':
                c['name'] = 'Cuenta'
            if c['name'] == 'Comunicación':
                c['name'] = 'Descripción'
            if c['name'] == 'Balance':
                c['name'] = 'Saldo Final'
            if c['name'] == 'Crédito':
                c['name'] = 'Haber'
        return res
    
    def _get_query_amls_select_clause(self):
        select_str = super(AccountGeneralLedgerReport, self)._get_query_amls_select_clause()
        select_str += '''
            ,account_payment.descripcion
        '''
        return select_str
        
        
    def _get_query_amls_from_clause(self):
        from_str = super(AccountGeneralLedgerReport, self)._get_query_amls_from_clause()
        from_str += """
            LEFT JOIN account_payment account_payment ON account_payment.id = account_move_line.payment_id \
        """
        return from_str
    
    @api.model
    def _get_aml_line(self, options, account, aml, cumulated_balance):
        res = super(AccountGeneralLedgerReport, self)._get_aml_line(options, account, aml, cumulated_balance)
        if aml['payment_id'] and 'columns' in res and len(res['columns']) > 1:
            if 'name' in res['columns'][1] and res['columns'][1]['name'] and aml['descripcion']:
                res['columns'][1]['name'] += ", "+ aml['descripcion']
        return res
