# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    fel_usuario = fields.Char('Prefijo WS')
    fel_llave_pre_firma = fields.Char('Token Signer')
    fel_llave_firma = fields.Char('Llave WS')
    feel_frase = fields.Char('Tipo de frase Feel')
    fel_frase_ids = fields.One2many('infilefel.frase','company_id','Frases')
    fel_codigo_exportador = fields.Char('Codigo exportador')
    certificador = fields.Char('Certificador', default="INFILE")
    fel_logo = fields.Binary('Logo fel')
    fel_texto_logo = fields.Char('Texto logo fel')
    fel_numero_abonos_fc = fields.Integer('Numero de abonos FCAM')
    fel_monto_factura_fc = fields.Boolean('Abono fijo por monto de FCAM')
    fel_fecha_vencimiento_fc = fields.Boolean('Fecha vencimiento factura para FCAM')
    unidad_medida = fields.Boolean('Unidad de medida odoo')
    adenda_extra = fields.Text('Adenda extra')
