# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fel_tipo_dte = fields.Selection([
            ('FACT', 'Factura'),
            ('FCAM', 'Factura cambiaria'),
            ('FPEQ', 'Factura pequeño contribuyente'),
            ('FCAP', 'Factura cambiaria pequeño contribuyente'),
            ('FESP', 'Factura especial'),
            ('NABN','Nota de abono'),
            ('RDON','Recibo de doanción'),
            ('RECI','Recibo'),
            ('NDEB','Nota de Débito'),
            ('NCRE','Nota de Crédito'),
            ('FACA','Factura Contribuyente Agropecuario'),
            ('FCCA','Factura Cambiaria Contribuyente Agropecuario'),
            ('FAPE','Factura Pequeño contribuyente Regimen Elctrónico'),
            ('FCPE','Factura Cambiaria Pequeño contribuyente Regimen Elctrónico'),
            ('FAAE','Factura Contribuyente Agropecuario Régimen Electrónico especial'),
            ('FCAE','Factura Cambiaria Contribuyente Agropecuario Régimen Electrónico especial'),
        ],string="Tipo DTE",
        help="Tipo de DTE (documento para feel)")
    fel_codigo_establecimiento = fields.Char('Codigo de establecimiento')
    fel_nombre_comercial = fields.Char('Nombre comercial')
    direccion_id = fields.Many2one('res.partner','Dirección')
    producto_descripcion = fields.Boolean('Producto + descripcion')
    descripcion_factura = fields.Boolean('Descripcion factura')
    columna_extra_fel_py = fields.Text('Columna extra py linea')
    factura_exportacion = fields.Boolean('Factura exportación')
    frase_py = fields.Text('Frases')
    # direccion_sucursal = fields.Char('Dirección sucursal')
    # telefono = fields.Char('Teléfono')
