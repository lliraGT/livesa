# -*- coding: utf-8 -*-
from odoo import api, Command, fields, models, _
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo.addons.base.models.res_bank import sanitize_account_number
from odoo.tools import remove_accents
import logging
import re
import warnings

_logger = logging.getLogger(__name__)

class AccountJournal(models.Model):
    _inherit = "account.journal"
    _description = " Agregando campo extra "

    tipo_factura = fields.Selection([('FACT', 'FACT'),
    ('FCAM', 'FCAM'),
    ('FPEQ', 'FPEQ'),
    ('FCAP', 'FCAP'),
    ('FESP', 'FESP'),
    ('NABN', 'NABN'),
    ('RDON', 'RDON'),
    ('RECI', 'RECI'),
    ('NDEB', 'NDEB'),
    ('NCRE', 'NCRE'),
    ('DUCA', 'DUCA')], 'Tipo de Documento FEL', copy=False)
#     lineas_ids = fields.One2many('account.journal.lineas_extras','linea_id', 'Lineas')
#
# class AccountJournalLineas(models.Model):
#     _name = "account.journal.lineas_extras"
#     _description = "Agregando algunas cosas extras"
#
#      linea_id = fields.Many2one('account.journal', 'Linea')
#      empleados = fields.Many2one('res.users', string='Usuarios')
#      porcentaje = fields.Float('Porcentaje')
