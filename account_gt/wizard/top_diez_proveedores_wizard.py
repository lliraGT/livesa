# -*- coding: utf-8 -*-

from odoo import models, fields, api
import xlsxwriter
import base64
import io
import logging

class ReporteTopDiezWizard(models.TransientModel):
    _name ="account_gt.top_diez_proveedores.wizard"
    _description ="Wizard creado para top diez proveedores"

    fecha_inicio = fields.Date('Fecha inicio: ')
    fecha_fin = fields.Date('Fecha final: ')
    name = fields.Char('Nombre archivo: ', size=32)
    archivo = fields.Binary('Archivo ', filters='.xls')

    def print_report(self):
        data = {
            'ids':[],
            'model': 'account_gt.top_diez_proveedores.wizard',
            'form': self.read()[0]
        }
        return self.env.ref('account_gt.reporte_top_diez').report_action([], data=data)


    def print_report_excel(self):
        logging.warning('Estamos funcionando bien :D')
        for w in self:
            f = io.BytesIO()
            libro = xlsxwriter.Workbook(f)
            hoja = libro.add_worksheet('Reporte Resumen top 10 proveedores')

            hoja.write(0, 0, 'Resumen de 10 proveedores')

            hoja.write(2, 0, 'Proveedor')
            hoja.write(2, 1, 'Base')
            hoja.write(2, 2, 'IVA')
            hoja.write(2, 3, 'Total')

            proveedores = self.env['account.move'].search([('invoice_date', '>=', w.fecha_inicio), ('invoice_date', '<=', w.fecha_fin), ('move_type', '=', 'in_invoice'), ('state', '=', 'posted')])
            dicc_proveedores={}
            contador=0
            positivo=0
            positivo_base=0
            for proveedor in proveedores:
                if proveedor.journal_id.tipo_factura != False:
                    if proveedor.partner_id.id not in dicc_proveedores:
                        dicc_proveedores[proveedor.partner_id.id]={
                        'nombre_proveedor': proveedor.partner_id.name,
                        'base':0,
                        'iva':0,
                        'total':0,
                        }
                        contador+=1
                    if proveedor.partner_id.id in dicc_proveedores and proveedor.tipo_factura != 'factura_especial':
                        positivo = proveedor.amount_total_signed * -1
                        positivo_base = proveedor.amount_untaxed_signed * -1
                        dicc_proveedores[proveedor.partner_id.id]['base']+=positivo_base
                        dicc_proveedores[proveedor.partner_id.id]['total']+=positivo
                        iva = dicc_proveedores[proveedor.partner_id.id]['total'] - dicc_proveedores[proveedor.partner_id.id]['base']
                        dicc_proveedores[proveedor.partner_id.id]['iva']+=iva
                    if proveedor.partner_id.id in dicc_proveedores and proveedor.tipo_factura == 'factura_especial':
                        for lineas_proveedor in proveedor.invoice_line_ids:
                            total_base += lineas_proveedor.quantity * lineas_proveedor.price_unit;
                        dicc_proveedores[proveedor.partner_id.id]['base'] = total_base;
                        dicc_proveedores[proveedor.partner_id.id]['iva'] = total_base - (proveedor.amount_untaxed_signed*-1)
                        dicc_proveedores[proveedor.partner_id.id]['total'] = dicc_proveedores[proveedor.partner_id.id]['base'] + dicc_proveedores[proveedor.partner_id.id]['iva']

            logging.warning('')
            logging.warning('')
            logging.warning('Diccionario proveedores')
            logging.warning(dicc_proveedores)
            logging.warning(len(dicc_proveedores))

            list_total = []
            posicion = 0
            reemplazo =0
            for id in dicc_proveedores:
                list_total.append(dicc_proveedores[id]['total'])

            for recorrido in range(1, len(list_total)):
                for posicion in range(len(list_total) - recorrido):
                    if list_total[posicion] < list_total[posicion + 1]:
                        temp = list_total[posicion]
                        list_total[posicion] = list_total[posicion+1]
                        list_total[posicion+1]= temp


            logging.warning(list_total)

            fila=3
            contador = 0
            lista_id=[]
            for x_monto in list_total:
                if contador < 10:
                    for id in dicc_proveedores:
                        if x_monto == dicc_proveedores[id]['total'] and id not in lista_id:
                            logging.warning(dicc_proveedores[id]['nombre_proveedor']+' :'+str(x_monto))
                            hoja.write(fila, 0, dicc_proveedores[id]['nombre_proveedor'])
                            hoja.write(fila, 1, dicc_proveedores[id]['base'])
                            hoja.write(fila, 2, dicc_proveedores[id]['iva'])
                            hoja.write(fila, 3, dicc_proveedores[id]['total'])
                            fila+=1
                            lista_id.append(id)
                contador+=1
            libro.close()
            datos = base64.b64encode(f.getvalue())
            self.write({'archivo':datos, 'name':'Reporte_top_diez.xlsx'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account_gt.top_diez_proveedores.wizard',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
