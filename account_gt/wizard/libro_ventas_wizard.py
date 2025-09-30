# -*- coding: utf-8 -*-

from odoo import models, fields, api
import xlsxwriter
import base64
import io
import logging

class LibroVentasWizard(models.TransientModel):
    _name = 'account_gt.libro_ventas.wizard'
    _description = "Wizard para libro de ventas"

    fecha_inicio = fields.Date('Fecha inicio')
    fecha_fin = fields.Date('Fecha fin')
    diarios_ids = fields.Many2many('account.journal', string='Diarios')
    name = fields.Char('Nombre archivo', size=32)
    archivo = fields.Binary('Archivo', filters='.xls')

    def print_report(self):
        data = {
             'ids': [],
             'model': 'account_gt.libro_ventas.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('account_gt.action_libro_ventas').report_action([], data=data)

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_inicio'] = w.fecha_inicio
            dict['fecha_fin'] = w.fecha_fin
            # dict['impuesto_id'] = [w.impuesto_id.id, w.impuesto_id.name]
            dict['diarios_ids'] =w.diarios_ids.ids

            res = self.env['report.account_gt.reporte_libro_ventas']._get_ventas(dict)

            f = io.BytesIO()
            libro = xlsxwriter.Workbook(f)
            hoja = libro.add_worksheet('Reporte ventas')

            hoja.write(0, 0, 'LIBRO DE VENTAS Y SERVICIOS')
            nombre_libro = ''
            if w.diarios_ids:
                nombre_libro= w.diarios_ids[0].fel_nombre_comercial
            hoja.write(1, 4, nombre_libro)
            hoja.write(2, 0, 'NUMERO DE IDENTIFICACION TRIBUTARIA')
            hoja.write(2, 1, self.env.company.vat)
            hoja.write(3, 0, 'NOMBRE COMERCIAL')
            hoja.write(3, 1,  self.env.company.name)
#             hoja.write(2, 3, 'DOMICILIO FISCAL')
#             hoja.write(2, 4,  self.env.company.street)
            hoja.write(3, 3, 'REGISTRO DEL')
            hoja.write(3, 4, str(w.fecha_inicio) + ' al ' + str(w.fecha_fin))



            hoja.write(5, 0, 'Fecha')
#             hoja.write(5, 1, 'Documento')
            hoja.write(5, 1, 'Serie')
            hoja.write(5, 2, 'Numero de factura')
            hoja.write(5, 3, 'Tipo de documento')
            hoja.write(5, 4, 'NIT')
            hoja.write(5, 5, 'Cliente')
            hoja.write(5, 6, 'Estado de la factura')
            hoja.write(5, 7, 'Bien')
            hoja.write(5, 8, 'Ventas exentas')
            hoja.write(5, 9, 'Servicios')
            hoja.write(5, 10, 'Servicios exentos')
            hoja.write(5, 11, 'Exportación')
            hoja.write(5, 12, 'IVA')
            hoja.write(5, 13, 'Total')
            hoja.write(5, 14, 'Reten IVA')
#             hoja.write(5, 15, 'Correlativo interno')
            hoja.write(5, 15, 'País destino')
            hoja.write(5, 16, 'Correlativo interno')

            fila = 6
            for compra in res['compras_lista']:
                hoja.write(fila, 0, compra['fecha'])
#                 hoja.write(fila, 1, compra['documento'])
                hoja.write(fila, 1, compra['serie'])
                hoja.write(fila, 2, compra['numero_factura'])
                hoja.write(fila, 3, compra['tipo_doc'])
                hoja.write(fila, 4, compra['nit'])
                hoja.write(fila, 5, compra['proveedor'])
                hoja.write(fila, 6, compra['estado_factura'])
                hoja.write(fila, 7, compra['compra'])
                hoja.write(fila, 8, compra['compra_exento'])
                hoja.write(fila, 9, compra['servicio'])
                hoja.write(fila, 10, compra['servicio_exento'])
                hoja.write(fila, 11, compra['importacion'])
                hoja.write(fila, 12, compra['iva'])
                hoja.write(fila, 13, compra['total'])
                hoja.write(fila, 14, compra['reten_iva'])
#                 hoja.write(fila, 15, compra['correlativo_interno'])
                hoja.write(fila, 15, compra['pais_destino'])
                hoja.write(fila, 16, compra['observaciones'])

                fila += 1
            hoja.write(fila, 5, 'Total')
#             if res['total']['compra'] < 0:
#                 res['total']['compra'] = (res['total']['compra'] *-1)
#                 hoja.write(fila, 7, res['total']['compra'])
#             else:
            hoja.write(fila, 7, res['total']['compra'])
#             if res['total']['compra_exento'] < 0:
#                 res['total']['compra_exento'] = (res['total']['compra_exento'] * -1)
#                 hoja.write(fila, 8, res['total']['compra_exento'])
#             else:
            hoja.write(fila, 8, res['total']['compra_exento'])
#             if res['total']['servicio'] < 0:
#                 res['total']['servicio'] = (res['total']['servicio']*-1)
#                 hoja.write(fila, 9, res['total']['servicio'])
#             else:
            hoja.write(fila, 9, res['total']['servicio'])
#             if res['total']['servicio_exento'] < 0:
#                 res['total']['servicio_exento'] = (res['total']['servicio_exento'] * -1)
#                 hoja.write(fila, 10, res['total']['servicio_exento'])
#             else:
            hoja.write(fila, 10, res['total']['servicio_exento'])
#             if res['total']['importacion'] < 0:
#                 res['total']['importacion'] = res['total']['importacion'] * -1
#                 hoja.write(fila, 11, res['total']['importacion'])
#             else:
            hoja.write(fila, 11, res['total']['importacion'])
#             if res['total']['iva'] < 0:
#                 res['total']['iva'] = res['total']['iva'] * -1
#                 hoja.write(fila, 12, res['total']['iva'])
#             else:
            hoja.write(fila, 12, res['total']['iva'])
#             if res['total']['total'] < 0:
#                 res['total']['total'] = res['total']['total'] * -1
#                 hoja.write(fila, 13, res['total']['total'])
#             else:
            hoja.write(fila, 13, res['total']['total'])
#             if res['total']['reten_iva'] < 0:
#                 res['total']['reten_iva'] = res['total']['reten_iva'] * -1
#                 hoja.write(fila, 14, res['total']['reten_iva'])
#             else:
            hoja.write(fila, 14, res['total']['reten_iva'])

            fila += 1


            libro.close()
            datos = base64.b64encode(f.getvalue())
            self.write({'archivo':datos, 'name':'libro_ventas.xlsx'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account_gt.libro_ventas.wizard',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
