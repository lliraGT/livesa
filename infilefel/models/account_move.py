# -*- coding: utf-8 -*-

import time
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import requests
import logging
import base64
from lxml import etree
from lxml.builder import ElementMaker
import xml.etree.ElementTree as ET
import datetime

class AccountMove(models.Model):
    _inherit = "account.move"

    fel_numero_abonos_fc = fields.Integer('Número de abonos FCAM', default=1)
    fel_fecha_vencimiento_fc = fields.Date('Fecha vencimiento FCAM')
    fel_monto_abonos_fc = fields.Float('Monto de aboons FCAM')
    fel_numero_autorizacion = fields.Char('Número de autorización', copy=False, tracking=True)
    fel_serie = fields.Char('Serie', copy=False, tracking=True)
    fel_numero = fields.Char('Número', copy=False, tracking=True)
    fel_documento_certificado = fields.Char('Documento Feel', copy=False, tracking=True)
    fel_incoterm = fields.Selection([
            ('EXW', 'En fábrica'),
            ('FCA', 'Libre transportista'),
            ('FAS', 'Libre al costado del buque'),
            ('FOB', 'Libre a bordo'),
            ('CFR', 'Costo y flete'),
            ('CIF','Costo, seguro y flete'),
            ('CPT','Flete pagado hasta'),
            ('CIP','Flete y seguro pagado hasta'),
            ('DDP','Entregado en destino con derechos pagados'),
            ('DAP','Entregada en lugar'),
            ('DAT','Entregada en terminal'),
            ('ZZZ','Otros')
        ],string="Incoterm",default="EXW",
        help="Termino de entrega")
    tipo_factura = fields.Selection([('venta','Venta'),('compra', 'Compra o Bien'), ('servicio', 'Servicio'),('varios','Varios'), ('combustible', 'Combustible'),('importacion', 'Importación'),('exportacion','Exportación')],
        string="Tipo de factura")
    fel_no_enviar_tel = fields.Boolean('No enviar telefono fel')

    def fecha_hora_factura(self, fecha):
        fecha_convertida = datetime.datetime.strptime(str(fecha), '%Y-%m-%d').date().strftime('%Y-%m-%d')
        hora = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
        fecha_hora_emision = str(fecha_convertida)+'T'+str(hora)
        return fecha_hora_emision


    def verificar_lineas_sin_impuestos(self, lineas):
        linea_sin_impuesto = False
        for linea in lineas:
            if len(linea.tax_ids) == 0:
                linea_sin_impuesto = True
            else:
                if linea.tax_ids[0].amount <= 0:
                    linea_sin_impuesto = True
        return linea_sin_impuesto

    def obtener_numero_identificacion(self, partner_id):
        nit_partner = {'id_receptor': "CF",'tipo_especial': False}
        if partner_id.vat:
            if '-' in partner_id.vat:
                nit_partner['id_receptor'] = str(partner_id.vat.replace('-',''))
            else:
                nit_partner['id_receptor'] = str(partner_id.vat)

        if partner_id.documento_personal_identificacion == False and (nit_partner['id_receptor']== "CF" or nit_partner['id_receptor']== "C/F"):
            nit_partner['id_receptor'] = "CF"

        if (nit_partner['id_receptor'] == "CF" or nit_partner['id_receptor'] == "C/F") and partner_id.documento_personal_identificacion:
            nit_partner['id_receptor'] = str(partner_id.documento_personal_identificacion)
            nit_partner['tipo_especial'] = "CUI"
        if partner_id.numero_documento_extranjero:
            nit_partner['id_receptor'] = str(partner_id.numero_documento_extranjero)
            nit_partner['tipo_especial'] = "EXT"
        return nit_partner

    def _post(self,soft=True):
        for factura in self:
            if factura.fel_serie and factura.fel_numero_autorizacion and factura.journal_id.fel_tipo_dte:
                raise UserError(str('NO PUEDE VALIDAR FACTURA DE NUEVO POR QUE YA FUE CERTIFICADA UNA VEZ'))

            if factura.journal_id and factura.journal_id.fel_tipo_dte and factura.move_type in ["out_invoice","out_refund","in_invoice","in_refund"]:
                logging.warn(factura)
                # Definimos SHEMALOCATION
                lista_impuestos = []

                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.2.0}"
                # Nuevo SMAP
                NSMAP = {
                    "ds": "http://www.w3.org/2000/09/xmldsig#",
                    "dte": "http://www.sat.gob.gt/dte/fel/0.2.0",
                    "xsi": "http://www.w3.org/2001/XMLSchema-instance"
                }

                if factura.invoice_date == False:
                    factura.invoice_date = fields.Date.context_today(self)

                moneda = str(factura.currency_id.name)
                fecha = datetime.datetime.strptime(str(factura.invoice_date), '%Y-%m-%d').date().strftime('%Y-%m-%d')
                hora = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
                fecha_hora_emision = self.fecha_hora_factura(factura.invoice_date)
                tipo = factura.journal_id.fel_tipo_dte
                existe_complemento = False

                motivo_nc = ''
                factura_original_id = False
                if tipo == 'NCRE' or tipo == 'NABN':
                    logging.warning('split factura')
                    logging.warning(factura.ref.split(':'))
                    factura_original_id = self.env['account.move'].search([('name','=',factura.ref.split(':')[1].split()[0].replace(",", "")  )])
                    if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                        tipo == 'NCRE'
                        factura.ref.split(':')[1].split().pop(0)
                        motivo_nc =  " ".join(factura.ref.split(':')[1].split()) if len(factura.ref.split(':')[1].split()) >= 1 else 'Nota de credito'
                        logging.warn('si es nota credito')
                    else:
                        raise UserError(str('NOTA DE CREDITO DEBE DE SER CON LA MISMA MONEDA QUE LA FACTURA ORIGINAL'))

                datos_generales = {
                    "CodigoMoneda": moneda,
                    "FechaHoraEmision":fecha_hora_emision,
                    "NumeroAcceso": str(100000000),
                    "Tipo":tipo
                    }
                if factura.journal_id.factura_exportacion:
                    datos_generales['Exp'] = "SI"

                nit_company = "CF"
                if '-' in factura.company_id.vat:
                    nit_company = factura.company_id.vat.replace('-','')
                else:
                    nit_company = factura.company_id.vat

                datos_emisor = {
                    "AfiliacionIVA":"GEN",
                    "CodigoEstablecimiento": str(factura.journal_id.fel_codigo_establecimiento) or "",
                    "CorreoEmisor": str(factura.company_id.email) or "",
                    "NITEmisor": str(nit_company),
                    "NombreComercial": factura.journal_id.direccion_id.name or "",
                    "NombreEmisor": factura.company_id.name or ""
                }

                nit_partner = self.obtener_numero_identificacion(factura.partner_id)

                if factura.amount_total > 2500 and factura.journal_id.factura_exportacion == False:
                    if (nit_partner['id_receptor'] == "CF" or nit_partner['id_receptor'] == "C/F") and factura.partner_id.documento_personal_identificacion == False:
                        raise UserError('EL cliente debe de tener NIT O DPI para poder emitir la factura')

                datos_receptor = {
                    "CorreoReceptor": factura.partner_id.email or "",
                    "NombreReceptor": factura.partner_id.parent_id.name if factura.partner_id.parent_id else factura.partner_id.name,
                    "IDReceptor": nit_partner['id_receptor'],
                }

                if nit_partner['tipo_especial'] != False:
                    datos_receptor['TipoEspecial'] = nit_partner['tipo_especial']

                if tipo in ['FACT','FCAM'] and factura.journal_id.factura_exportacion:
                    datos_receptor['IDReceptor'] = nit_partner['id_receptor']
                    datos_receptor['TipoEspecial'] = "EXT"

                # Creamos los TAGS necesarios
                GTDocumento = etree.Element(DTE_NS+"GTDocumento", {attr_qname: 'http://www.sat.gob.gt/dte/fel/0.1.0'}, Version="0.1", nsmap=NSMAP)
                TagSAT = etree.SubElement(GTDocumento,DTE_NS+"SAT",ClaseDocumento="dte")
                TagDTE = etree.SubElement(TagSAT,DTE_NS+"DTE",ID="DatosCertificados")
                TagDatosEmision = etree.SubElement(TagDTE,DTE_NS+"DatosEmision",ID="DatosEmision")
                TagDatosGenerales = etree.SubElement(TagDatosEmision,DTE_NS+"DatosGenerales",datos_generales)
                # Datos de emisor
                TagEmisor = etree.SubElement(TagDatosEmision,DTE_NS+"Emisor",datos_emisor)
                TagDireccionEmisor = etree.SubElement(TagEmisor,DTE_NS+"DireccionEmisor",{})
                TagDireccion = etree.SubElement(TagDireccionEmisor,DTE_NS+"Direccion",{})
                TagDireccion.text = str(factura.journal_id.direccion_id.street)+(" "+str(factura.journal_id.direccion_id.street2) if factura.journal_id.direccion_id.street2 else "" )
                TagCodigoPostal = etree.SubElement(TagDireccionEmisor,DTE_NS+"CodigoPostal",{})
                TagCodigoPostal.text = str(factura.journal_id.direccion_id.zip)
                TagMunicipio = etree.SubElement(TagDireccionEmisor,DTE_NS+"Municipio",{})
                TagMunicipio.text = str(factura.journal_id.direccion_id.city) if factura.journal_id.direccion_id.city else "Guatemala"
                TagDepartamento = etree.SubElement(TagDireccionEmisor,DTE_NS+"Departamento",{})
                TagDepartamento.text = str(factura.journal_id.direccion_id.state_id.name) if factura.journal_id.direccion_id.state_id else "Guatemala"
                TagPais = etree.SubElement(TagDireccionEmisor,DTE_NS+"Pais",{})
                TagPais.text = "GT"
                # Datos de receptor
                TagReceptor = etree.SubElement(TagDatosEmision,DTE_NS+"Receptor",datos_receptor)
                TagDireccionReceptor = etree.SubElement(TagReceptor,DTE_NS+"DireccionReceptor",{})
                TagReceptorDireccion = etree.SubElement(TagDireccionReceptor,DTE_NS+"Direccion",{})
                TagReceptorDireccion.text = (factura.partner_id.street or "Ciudad")+" "+(factura.partner_id.street2 or "")
                TagReceptorCodigoPostal = etree.SubElement(TagDireccionReceptor,DTE_NS+"CodigoPostal",{})
                TagReceptorCodigoPostal.text = factura.partner_id.zip or '01001'
                TagReceptorMunicipio = etree.SubElement(TagDireccionReceptor,DTE_NS+"Municipio",{})
                TagReceptorMunicipio.text = factura.partner_id.city or 'Guatemala'
                TagReceptorDepartamento = etree.SubElement(TagDireccionReceptor,DTE_NS+"Departamento",{})
                TagReceptorDepartamento.text = factura.partner_id.state_id.name or 'Guatemala'
                TagReceptorPais = etree.SubElement(TagDireccionReceptor,DTE_NS+"Pais",{})
                TagReceptorPais.text = "GT"
                # Frases

                data_frase = {"xmlns:dte": "http://www.sat.gob.gt/dte/fel/0.2.0"}
                NSMAPFRASE = {"dte": "http://www.sat.gob.gt/dte/fel/0.2.0"}

                lineas_sin_impuestos = self.verificar_lineas_sin_impuestos(factura.invoice_line_ids)
                logging.warning('lineas_sin_impuestos')
                logging.warning(lineas_sin_impuestos)
                #segun fel Versión 1.7.3 no es necesaio frases ni codigos para FESP
                if tipo == 'FESP':
                    TagFrases = etree.SubElement(TagDatosEmision,DTE_NS+"Frases", {},nsmap=NSMAPFRASE)
                    if factura.journal_id.frase_py:
                       exec(factura.journal_id.frase_py)
                    else:
                        logging.warning('LA FRASE')
                        logging.warning(factura.company_id.fel_frase_ids[0].frase)
                        frases_datos = {"CodigoEscenario": factura.company_id.fel_frase_ids[1].codigo,"TipoFrase":factura.company_id.fel_frase_ids[1].frase}
                        TagFrase = etree.SubElement(TagFrases,DTE_NS+"Frase",frases_datos)

                #validamos tipo de documento para saber que tipo de frases se agregan
                #segun fel Versión 1.7.3 es necesario frase 2 y frase 1
                if (tipo in ['FACT','NCRE','NDEB', 'FCAM']):
                    TagFrases = etree.SubElement(TagDatosEmision,DTE_NS+"Frases", {},nsmap=NSMAPFRASE)
                    if factura.journal_id.frase_py:
                        exec(factura.journal_id.frase_py)
                    else:
                        if factura.company_id.fel_frase_ids[0].frase != 5:
                            frases_datos = {"CodigoEscenario": factura.company_id.fel_frase_ids[0].codigo,"TipoFrase":factura.company_id.fel_frase_ids[0].frase}
                        logging.warning('FRASES 1')
                        logging.warning(frases_datos)
                        TagFrase = etree.SubElement(TagFrases,DTE_NS+"Frase",frases_datos)
    
                        if len(factura.company_id.fel_frase_ids) > 1:
                            if int(factura.company_id.fel_frase_ids[1].frase) != 5 and int(factura.company_id.fel_frase_ids[1].frase) != 4 and lineas_sin_impuestos==False:
                                frases_datos2 = {"CodigoEscenario": factura.company_id.fel_frase_ids[1].codigo,"TipoFrase":factura.company_id.fel_frase_ids[1].frase}
                                TagFrase2 = etree.SubElement(TagFrases,DTE_NS+"Frase",frases_datos2)
    
                            if lineas_sin_impuestos == True and int(factura.company_id.fel_frase_ids[1].frase) == 4 and tipo != "NCRE":
                                frases_datos2 = {"CodigoEscenario": factura.company_id.fel_frase_ids[1].codigo,"TipoFrase":factura.company_id.fel_frase_ids[1].frase}
                                TagFrase2 = etree.SubElement(TagFrases,DTE_NS+"Frase",frases_datos2)

                # Items
                TagItems = etree.SubElement(TagDatosEmision,DTE_NS+"Items",{})

                impuestos_dic = {'IVA': 0}
                tax_iva = False
                # monto_gravable_iva = 0
                # monto_impuesto_iva = 0
                total_factura_general = 0
                total_retencion_iva = 0
                total_retencion_isr_fesp = 0
                logging.warning('total_retencion_isr_fesp 0')
                logging.warning(total_retencion_isr_fesp)
                total_retencion_isr = 0
                for linea in factura.invoice_line_ids:
                    iva_fespecial = 0
                    if linea.product_id:
                        tax_ids = linea.tax_ids
                        numero_linea = 1
                        bien_servicio = "S" if linea.product_id.type == 'service' else "B"
                        linea_datos = {
                            "BienOServicio": bien_servicio,
                            'NumeroLinea': str(numero_linea)
                        }
                        numero_linea += 1
                        TagItem =  etree.SubElement(TagItems,DTE_NS+"Item",linea_datos)
                        cantidad = linea.quantity
                        unidad_medida = ("UNI" if linea.product_uom_id.name == "Unidades" else str(linea.product_uom_id.name) ) if factura.company_id.unidad_medida else "UNI"
                        descripcion = linea.product_id.name
                        if factura.journal_id.descripcion_factura:
                            descripcion = linea.name
                        if factura.journal_id.producto_descripcion:
                            descripcion = str(linea.product_id.name) + ' ' +str(linea.name)

                        # precio_unitario = (linea.price_unit * (1 - (linea.discount) / 100.0)) if linea.discount > 0 else linea.price_unit
                        precio_unitario = linea.price_unit
                        precio = linea.price_unit * linea.quantity
                        total_factura_general += precio
                        descuento = ((linea.quantity * linea.price_unit) - linea.price_total) if linea.discount > 0 else 0
                        precio_subtotal = '{:.6f}'.format(linea.price_subtotal)
                        TagCantidad = etree.SubElement(TagItem,DTE_NS+"Cantidad",{})
                        TagCantidad.text ='{:.6f}'.format(cantidad)
                        # TagCantidad.text = str(cantidad)
                        TagUnidadMedida = etree.SubElement(TagItem,DTE_NS+"UnidadMedida",{})
                        TagUnidadMedida.text = str(unidad_medida)
                        TagDescripcion = etree.SubElement(TagItem,DTE_NS+"Descripcion",{})
                        if factura.journal_id.columna_extra_fel_py:
                            logging.warning('si hay py')
                            exec(factura.journal_id.columna_extra_fel_py)
                        else:
                            TagDescripcion.text = (str(linea.product_id.name) +'|'+ str(linea.product_id.default_code)) if linea.product_id.default_code else descripcion
                        TagPrecioUnitario = etree.SubElement(TagItem,DTE_NS+"PrecioUnitario",{})
                        TagPrecioUnitario.text = '{:.6f}'.format(precio_unitario)
                        TagPrecio = etree.SubElement(TagItem,DTE_NS+"Precio",{})
                        TagPrecio.text =  '{:.6f}'.format(precio)
                        TagDescuento = etree.SubElement(TagItem,DTE_NS+"Descuento",{})
                        TagDescuento.text =  str('{:.6f}'.format(descuento))

                        if tipo != 'NABN':
                            logging.warn('IMPUESTOS')
                            currency = linea.move_id.currency_id
                            logging.warn(precio_unitario)
                            if linea.tax_ids:
                                if linea.tax_ids[0].amount <= 0:
                                    TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                                    TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                                    TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                                    TagNombreCorto.text = "IVA"
                                    TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                                    TagCodigoUnidadGravable.text = "2"
                                    TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                                    TagMontoGravable.text = str(precio_subtotal)
                                    TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                                    TagMontoImpuesto.text = "0.00"
                                else:
                                    TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                                    taxes = tax_ids.compute_all(precio_unitario-(descuento/linea.quantity), currency, linea.quantity, linea.product_id, linea.move_id.partner_id)
                                    logging.warning(taxes)
                                    for impuesto in taxes['taxes']:
                                        #nombre_impuesto = impuesto['name']
                                        #valor_impuesto = impuesto['amount']
                                        logging.warning("IMPUESTO ABC")
                                        logging.warning(impuesto)
                                        if impuesto['name'] == 'ISR Factura Especial':
                                            total_retencion_isr_fesp += impuesto['amount']
                                            logging.warning('sumando total_retencion_isr_fesp')
                                            logging.warning(impuesto)
                                            logging.warning(total_retencion_isr_fesp)
                                        if impuesto['name'] == '12%' or impuesto['name'] == 'IVA por Pagar' or impuesto['name'] == 'IVA POR PAGAR' or impuesto['name'] == 'IVA por Cobrar':
                                            nombre_impuesto = impuesto['name']
                                            valor_impuesto = impuesto['amount']
                                            nombre_impuesto = "IVA"
                                            tax_iva = True
                                            lista_impuestos.append({'nombre': nombre_impuesto, 'monto': valor_impuesto})


                                            TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                                            TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                                            TagNombreCorto.text = nombre_impuesto
                                            TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                                            TagCodigoUnidadGravable.text = "1"
                                            TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                                            TagMontoGravable.text = str(precio_subtotal)
                                            TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                                            TagMontoImpuesto.text = '{:.6f}'.format(valor_impuesto)
                                            iva_fespecial += valor_impuesto
                                            total_retencion_iva += valor_impuesto
                                        # monto_gravable_iva += precio_subtotal
                                        # monto_impuesto_iva += valor_impuesto
                            else:
                                if factura.journal_id.factura_exportacion == False:
                                    TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                                    TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                                    TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                                    TagNombreCorto.text = "IVA"
                                    TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                                    TagCodigoUnidadGravable.text = "2"
                                    TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                                    TagMontoGravable.text = str(precio_subtotal)
                                    TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                                    TagMontoImpuesto.text = "0.00"

                        # if (tipo in ['FACT','NCRE']) and factura.currency_id !=  factura.company_id.currency_id and len(linea.tax_ids) == 0:
                        #     TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                        #     TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                        #     TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                        #     TagNombreCorto.text = "IVA"
                        #     TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                        #     TagCodigoUnidadGravable.text = "2"
                        #     TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                        #     TagMontoGravable.text = str(precio_subtotal)
                        #     TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                        #     TagMontoImpuesto.text = "0.00"

                        if factura.journal_id.factura_exportacion:
                            TagImpuestos = etree.SubElement(TagItem,DTE_NS+"Impuestos",{})
                            TagImpuesto = etree.SubElement(TagImpuestos,DTE_NS+"Impuesto",{})
                            TagNombreCorto = etree.SubElement(TagImpuesto,DTE_NS+"NombreCorto",{})
                            TagNombreCorto.text = "IVA"
                            TagCodigoUnidadGravable = etree.SubElement(TagImpuesto,DTE_NS+"CodigoUnidadGravable",{})
                            TagCodigoUnidadGravable.text = "2"
                            TagMontoGravable = etree.SubElement(TagImpuesto,DTE_NS+"MontoGravable",{})
                            TagMontoGravable.text = str(precio_subtotal)
                            TagMontoImpuesto = etree.SubElement(TagImpuesto,DTE_NS+"MontoImpuesto",{})
                            TagMontoImpuesto.text = "0.00"


                        #logging.warn(taxes)
                        TagTotal = etree.SubElement(TagItem,DTE_NS+"Total",{})
                        if tipo == 'FESP':
                             TagTotal.text = '{:.6f}'.format(linea.price_subtotal+iva_fespecial)
                        else:
                            TagTotal.text = '{:.6f}'.format(linea.price_total)
                        # TagTotal.text =  str(linea.price_total)


                TagTotales = etree.SubElement(TagDatosEmision,DTE_NS+"Totales",{})
                #if tipo != 'NABN': nota de abono sin impuesto
                if tipo != 'NABN':
                    TagTotalImpuestos = etree.SubElement(TagTotales,DTE_NS+"TotalImpuestos",{})
                    logging.warning('lista impuestos')
                    logging.warning(lista_impuestos)
                    if len(lista_impuestos) > 0:
                        if lista_impuestos[0]['monto'] <= 0:
                            dato_impuesto = {'NombreCorto': "IVA",'TotalMontoImpuesto': "0.00"}
                            TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
                        else:
                            total_impuesto = 0
                            logging.warn('EL IMPUESTO')
                            for i in lista_impuestos:
                                logging.warn(i)
                                total_impuesto += float(i['monto'])
                            dato_impuesto = {'NombreCorto': lista_impuestos[0]['nombre'],'TotalMontoImpuesto': str('{:.6f}'.format(total_impuesto))}
                            TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
                            TagTotalImpuestos.append(TagTotalImpuesto)
                    else:
                        dato_impuesto = {'NombreCorto': "IVA",'TotalMontoImpuesto': "0.00"}
                        TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)

                TagGranTotal = etree.SubElement(TagTotales,DTE_NS+"GranTotal",{})
                if tipo == 'FESP':
                    TagGranTotal.text = '{:.6f}'.format(factura.currency_id.round(total_factura_general))
                else:
                    TagGranTotal.text = '{:.6f}'.format(factura.currency_id.round(factura.amount_total))

                if factura.journal_id.factura_exportacion and factura.move_type == 'out_invoice':
                    dato_impuesto = {'NombreCorto': "IVA",'TotalMontoImpuesto': str(0.00)}
                    #TagTotalImpuesto = etree.SubElement(TagTotalImpuestos,DTE_NS+"TotalImpuesto",dato_impuesto)
                    TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                    datos_complementos = {
                        "IDComplemento": "EXPORTACION",
                        "NombreComplemento": "EXPORTACION",
                        "URIComplemento": "EXPORTACION"
                    }
                    TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complementos)
                    existe_complemento = True
                    NSMAP = {
                        "cex": "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0"
                    }
                    cex = "{http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0}"

                    TagExportacion = etree.SubElement(TagComplemento,cex+"Exportacion",{},Version="1",nsmap=NSMAP)
                    TagNombreConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"NombreConsignatarioODestinatario",{})
                    TagNombreConsignatarioODestinatario.text = str(factura.consignatario_destinatario_id.name) if factura.consignatario_destinatario_id else str(factura.partner_id.name)
                    TagDireccionConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"DireccionConsignatarioODestinatario",{})
                    direccion_consignatario = str(factura.partner_id.street) + (str(factura.partner_id.street2) if factura.partner_id.street2 else "")
                    TagDireccionConsignatarioODestinatario.text = str(factura.consignatario_destinatario_id.street) if factura.consignatario_destinatario_id else direccion_consignatario
                    TagCodigoConsignatarioODestinatario = etree.SubElement(TagExportacion,cex+"CodigoConsignatarioODestinatario",{})
                    TagCodigoConsignatarioODestinatario.text = str(factura.partner_id.codigo_destinatario)  if factura.partner_id.codigo_destinatario else "-"
                    TagNombreComprador = etree.SubElement(TagExportacion,cex+"NombreComprador",{})
                    TagNombreComprador.text = str(factura.comprador_id.name) if factura.comprador_id else str(factura.partner_id.name)
                    direccion_comprador = str(factura.partner_id.street) + (str(factura.partner_id.street2) if factura.partner_id.street2 else "")
                    TagDireccionComprador = etree.SubElement(TagExportacion,cex+"DireccionComprador",{})
                    TagDireccionComprador.text = str(factura.direccion_comprador) if factura.direccion_comprador else direccion_comprador
                    TagCodigoComprador = etree.SubElement(TagExportacion,cex+"CodigoComprador",{})
                    TagCodigoComprador.text = str(factura.comprador_id.ref) if factura.comprador_id.ref else "-"
                    TagOtraReferencia = etree.SubElement(TagExportacion,cex+"OtraReferencia",{})
                    TagOtraReferencia.text = str(factura.otra_referencia) if factura.otra_referencia else str(factura.name)
                    if factura.incoterm_exp:
                        TagINCOTERM = etree.SubElement(TagExportacion,cex+"INCOTERM",{})
                        TagINCOTERM.text = str(factura.incoterm_exp) if factura.incoterm_exp else ""
                    TagNombreExportador = etree.SubElement(TagExportacion,cex+"NombreExportador",{})
                    TagNombreExportador.text = str(factura.exportador_id.name) if factura.exportador_id else ""
                    TagCodigoExportador = etree.SubElement(TagExportacion,cex+"CodigoExportador",{})
                    TagCodigoExportador.text = str(factura.exportador_id.ref) if factura.exportador_id.ref else "-"


                if tipo == 'NDEB':
                    #ANTES
                    #factura_original_id = self.env['account.move'].search([('name','=',factura.ref.split(':')[1].split()  )])
                    #DESPUES
                    factura_original_str = factura.ref.split(':')[1].split()[0].split(',')[0]
                    factura_original_id = self.env['account.move'].search([('name','=', factura_original_str  )])
                    logging.warning('factura_original_id')
                    logging.warning(factura_original_id)



                    logging.warning('--------------------------------------')
                    logging.warning(factura.ref.split(':')[1].split()[0].split(','))
                    logging.warning(factura.ref.split(':')[1].split()[1])
                    factura_original_str = factura.ref.split(':')[1].split()[0].split(',')[0]
                    factura_original_id = self.env['account.move'].search([('name','=', factura_original_str )])
                    logging.warning('si es NC FACTURA ORIGIN')
                    logging.warning(factura_original_id)
                    referencia_lista = factura.ref.split(':')[1].split()
                    del referencia_lista[0]
                    logging.warning('referencia lista')
                    logging.warning(referencia_lista)
                    motivo_nc = " ".join(referencia_lista)
                    logging.warning('MOTIVO NC')
                    logging.warning(motivo_nc)
                    
                    if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                        logging.warn('si')
                        if existe_complemento == False:
                            TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                        cno = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
                        NSMAP_REF = {"cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"}
                        datos_complemento = {'IDComplemento': 'ReferenciasNota', 'NombreComplemento':'Nota de Debito','URIComplemento':'text'}
                        TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                        datos_referencias = {
                            'FechaEmisionDocumentoOrigen': str(factura_original_id.invoice_date),
                            'MotivoAjuste': motivo_nc,
                            'NumeroAutorizacionDocumentoOrigen': str(factura_original_id.fel_numero_autorizacion),
                            'NumeroDocumentoOrigen': str(factura_original_id.fel_numero),
                            'SerieDocumentoOrigen': str(factura_original_id.fel_serie),
                            'Version': '0.0'
                        }
                        TagReferenciasNota = etree.SubElement(TagComplemento,cno+"ReferenciasNota",datos_referencias,nsmap=NSMAP_REF)


                if tipo == 'NCRE':
                    logging.warning('--------------------------------------')
                    logging.warning(factura.ref.split(':')[1].split()[0].split(','))
                    logging.warning(factura.ref.split(':')[1].split()[1])
                    factura_original_str = factura.ref.split(':')[1].split()[0].split(',')[0]
                    factura_original_id = self.env['account.move'].search([('name','=', factura_original_str )])
                    logging.warning('si es NC FACTURA ORIGIN')
                    logging.warning(factura_original_id)
                    referencia_lista = factura.ref.split(':')[1].split()
                    del referencia_lista[0]
                    logging.warning('referencia lista')
                    logging.warning(referencia_lista)
                    motivo_nc = " ".join(referencia_lista)
                    logging.warning('MOTIVO NC')
                    logging.warning(motivo_nc)
                    if factura_original_id and factura.currency_id.id == factura_original_id.currency_id.id:
                        logging.warn('si')
                        if existe_complemento == False:
                            TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                        cno = "{http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0}"
                        NSMAP_REF = {"cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"}
                        datos_complemento = {'IDComplemento': 'Notas', 'NombreComplemento':'Notas','URIComplemento':'text'}
                        #datos_complemento = {'IDComplemento': 'ReferenciasNota', 'NombreComplemento':'Nota de Debito','URIComplemento':'text'}
                        TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                        datos_referencias = {
                            'FechaEmisionDocumentoOrigen': str(factura_original_id.invoice_date),
                            'MotivoAjuste': motivo_nc,
                            'NumeroAutorizacionDocumentoOrigen': str(factura_original_id.fel_numero_autorizacion),
                            'NumeroDocumentoOrigen': str(factura_original_id.fel_numero),
                            'SerieDocumentoOrigen': str(factura_original_id.fel_serie),
                            'Version': '0.0'
                        }
                        TagReferenciasNota = etree.SubElement(TagComplemento,cno+"ReferenciasNota",datos_referencias,nsmap=NSMAP_REF)

                if tipo == 'FCAM':
                    NSMAPFCAM = {
                        "cfc": "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0"
                    }
                    DTE_NS_CFCAM = "{http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0}"
                    if existe_complemento == False:
                        TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                    #TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                    datos_complemento = {'IDComplemento': 'Cambiaria', 'NombreComplemento':'Cambiaria','URIComplemento':'http://www.sat.gob.gt/fel/cambiaria.xsd'}
                    TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                    tag_datos_factura_cambiaria = {
                        'Version': '1'
                    }
                    TagAbonosFacturaCambiaria = etree.SubElement(TagComplemento,DTE_NS_CFCAM+"AbonosFacturaCambiaria",tag_datos_factura_cambiaria,nsmap=NSMAPFCAM)
                    TagAbono = etree.SubElement(TagAbonosFacturaCambiaria,DTE_NS_CFCAM+"Abono")
                    TagNumeroAbono = etree.SubElement(TagAbono,DTE_NS_CFCAM+"NumeroAbono")
                    logging.warning('numero abonos')
                    logging.warning(factura.fel_numero_abonos_fc)
                    TagNumeroAbono.text = str(factura.fel_numero_abonos_fc) if factura.fel_numero_abonos_fc > 0 else str(factura.company_id.fel_numero_abonos_fc)
                    TagFechaVencimiento = etree.SubElement(TagAbono,DTE_NS_CFCAM+"FechaVencimiento")
                    fecha_fcam = False
                    if factura.fel_fecha_vencimiento_fc:
                        fecha_fcam = datetime.datetime.strftime(factura.fel_fecha_vencimiento_fc, "%Y-%m-%d")
                    else:
                        fecha_fcam = datetime.datetime.strftime(factura.invoice_date_due, "%Y-%m-%d")

                    TagFechaVencimiento.text = fecha_fcam
                    TagMontoAbono = etree.SubElement(TagAbono,DTE_NS_CFCAM+"MontoAbono")
                    TagMontoAbono.text = str(factura.fel_monto_abonos_fc) if factura.fel_monto_abonos_fc > 0 else str(factura.amount_total)


                if tipo == 'FESP':
                    NSMAPFRASECFC = {
                        "cfe": "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0"
                    }
                    DTE_NS_CFC = "{http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0}"
                    if existe_complemento == False:
                        TagComplementos = etree.SubElement(TagDatosEmision,DTE_NS+"Complementos",{})
                    #NSMAP_REF = {"cno": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0"}
                    datos_complemento = {'IDComplemento': 'FacturaEspecial', 'NombreComplemento':'FacturaEspecial','URIComplemento':'http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0'}
                    TagComplemento = etree.SubElement(TagComplementos,DTE_NS+"Complemento",datos_complemento)
                    tag_datos_factura_especial = {
                        'Version': '1'
                    }

                    TagRetencionFacturaEspecial = etree.SubElement(TagComplemento,DTE_NS_CFC+"RetencionesFacturaEspecial",tag_datos_factura_especial,nsmap=NSMAPFRASECFC)
                    TagRetencionISR = etree.SubElement(TagRetencionFacturaEspecial,DTE_NS_CFC+"RetencionISR")
                    # tomamos en cuenta IVA Factura Especial para total_retencion_iva
                    logging.warning("TOTAL total_retencion_isr_fesp")
                    logging.warning(total_retencion_isr_fesp)
                    TagRetencionISR.text = '{:.6f}'.format(abs(total_retencion_isr_fesp))
                    TagRetencionIVA = etree.SubElement(TagRetencionFacturaEspecial,DTE_NS_CFC+"RetencionIVA")
                    TagRetencionIVA.text = '{:.6f}'.format(total_retencion_iva)
                    TagTotalMenosRetenciones = etree.SubElement(TagRetencionFacturaEspecial,DTE_NS_CFC+"TotalMenosRetenciones")
                    TagTotalMenosRetenciones.text = '{:.6f}'.format(factura.amount_total_signed*-1)

                # if factura.currency_id.id != factura.company_id.currency_id.id:
                #     TagAdenda = etree.SubElement(TagSAT,DTE_NS+"Adenda",{})
                #     if factura.comment:
                #         TagComentario = etree.SubElement(TagAdenda, DTE_NS+"Comentario",{})
                #         TagComentario.text = factura.comment
                #     if factura.currency_id.id != factura.company_id.currency_id.id:
                #         TagNitCliente = etree.SubElement(TagAdenda, DTE_NS+"NitCliente",{})
                #         if factura.partner_id.vat:
                #             if '-' in factura.partner_id.vat:
                #                 TagNitCliente.text = factura.partner_id.vat.replace('-','')
                #             else:
                #                 TagNitCliente.text = factura.partner_id.vat

                if tipo in ['FACT','NCRE','NDEB','NABN','FESP','FCAM']:
                    if factura.name == False or factura.name == "/" or factura.name in ["Borrador", "Draft"]:
                        factura._set_next_sequence()
                    TagAdenda = etree.SubElement(TagSAT,DTE_NS+"Adenda",{})
                    TagNint = etree.SubElement(TagAdenda,DTE_NS+"NInt",{})
                    logging.warning('numero interno')
                    logging.warning(factura.name)
                    TagNint.text = factura.name
                    if factura.company_id.adenda_extra:
                        exec(factura.company_id.adenda_extra)
                # if factura.narration:
                #     TagAdenda = etree.SubElement(TagDTE, DTE_NS+"Adenda",{})
                #     TagDECER = etree.SubElement(TagAdenda,"DECertificador",{})
                #     TagDECER.text = str(factura.narration)

                # if factura.narration:
                #     TagAdenda = etree.SubElement(TagSAT,DTE_NS+"Adenda",{})
                #     TagComentario = etree.SubElement(TagAdenda, DTE_NS+"Comentario",{})
                #     TagComentario.text = factura.narration

                xmls = etree.tostring(GTDocumento, encoding="UTF-8")
                xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                xmls_base64 = base64.b64encode(xmls)
                logging.warn(xmls)


                url = "https://signer-emisores.feel.com.gt/sign_solicitud_firmas/firma_xml"

                nit_company = "CF"
                if '-' in factura.company_id.vat:
                    nit_company = factura.company_id.vat.replace('-','')
                else:
                    nit_company = factura.company_id.vat


                nuevo_json = {
                    'llave': str(factura.company_id.fel_llave_pre_firma),
                    'codigo': str(nit_company),
                    'alias': str(factura.company_id.fel_usuario),
                    'es_anulacion': 'N',
                    'archivo': xmls_base64.decode("utf-8")
                }

                nuevos_headers = {"content-type": "application/json"}
                response = requests.post(url, json = nuevo_json, headers = nuevos_headers)

                respone_json=response.json()
                logging.warning('respuesta autentic')
                logging.warning(nuevo_json)
                logging.warning(respone_json)

                if respone_json['resultado']:
                        headers = {
                            "USUARIO": str(factura.company_id.fel_usuario),
                            "LLAVE": str(factura.company_id.fel_llave_firma),
                            "IDENTIFICADOR": str(factura.journal_id.name)+'/'+str(factura.payment_reference) if factura.payment_reference else str(factura.journal_id.name)+'/'+str(factura.id),
                            "Content-Type": "application/json",
                        }

                        logging.warning('VALIDADO')
                        logging.warning(headers)

                        nit_company = "CF"
                        if '-' in factura.company_id.vat:
                            nit_company = factura.company_id.vat.replace('-','')
                        else:
                            nit_company = factura.company_id.vat
                        data = {
                            "nit_emisor": str(nit_company),
                            "correo_copia": str(factura.company_id.email),
                            "xml_dte": respone_json["archivo"]
                        }

                        r = requests.post("https://certificador.feel.com.gt/fel/certificacion/v2/dte/", json=data, headers=headers)
                        retorno_certificacion_json = r.json()
                        logging.warn(retorno_certificacion_json)
                        if retorno_certificacion_json['resultado']:
                            factura.fel_numero_autorizacion = retorno_certificacion_json["uuid"]
                            # factura.name = str(retorno_certificacion_json["serie"])+"/"+str(retorno_certificacion_json["numero"])
                            factura.fel_serie = retorno_certificacion_json["serie"]
                            factura.fel_numero = retorno_certificacion_json["numero"]
                            factura.fel_documento_certificado = "https://report.feel.com.gt/ingfacereport/ingfacereport_documento?uuid="+retorno_certificacion_json["uuid"]
                        else:
                            raise UserError(str(retorno_certificacion_json))
                else:
                    raise UserError(str(respone_json))

        return super(AccountMove, self)._post()


    def button_draft(self):
        for factura in self:
            if factura.journal_id.fel_tipo_dte and factura.fel_serie and factura.fel_numero and factura.fel_numero_autorizacion and factura.company_id.fel_llave_firma:
                attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
                DTE_NS = "{http://www.sat.gob.gt/dte/fel/0.1.0}"
                # Nuevo SMAP
                NSMAP = {
                    "ds": "http://www.w3.org/2000/09/xmldsig#",
                    "dte": "http://www.sat.gob.gt/dte/fel/0.1.0",
                    "xsi": "http://www.w3.org/2001/XMLSchema-instance"
                }
                tipo = factura.journal_id.fel_tipo_dte
                GTAnulacionDocumento = etree.Element(DTE_NS+"GTAnulacionDocumento", {attr_qname: 'http://www.sat.gob.gt/dte/fel/0.1.0'}, Version="0.1", nsmap=NSMAP)
                datos_sat = {'ClaseDocumento': 'dte'}
                TagSAT = etree.SubElement(GTAnulacionDocumento,DTE_NS+"SAT",{})
                # dato_anulacion = {'ID': 'DatosCertificados'}
                dato_anulacion = {"ID": "DatosCertificados"}
                TagAnulacionDTE = etree.SubElement(TagSAT,DTE_NS+"AnulacionDTE",dato_anulacion)
                fecha_factura = self.fecha_hora_factura(factura.invoice_date)
                fecha_anulacion = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%Y-%m-%d")
                hora_anulacion = datetime.datetime.strftime(fields.Datetime.context_timestamp(self, datetime.datetime.now()), "%H:%M:%S")
                fecha_anulacion = str(fecha_anulacion)+'T'+str(hora_anulacion)
                nit_partner = self.obtener_numero_identificacion(factura.partner_id)

                nit_company = "CF"
                if factura.journal_id.direccion_id.vat and ('-' in factura.journal_id.direccion_id.vat):
                    nit_company = factura.company_id.vat.replace('-','')
                else:
                    nit_company = factura.company_id.vat

                datos_generales = {
                    "ID": "DatosAnulacion",
                    "NumeroDocumentoAAnular": str(factura.fel_numero_autorizacion),
                    "NITEmisor": str(nit_company),
                    "FechaEmisionDocumentoAnular": fecha_factura,
                    "FechaHoraAnulacion": fecha_anulacion,
                    "MotivoAnulacion": "Anulacion factura",
                    "IDReceptor": nit_partner["id_receptor"]
                }

                #if tipo == 'FACT' and (factura.currency_id.id !=  factura.company_id.currency_id.id):
                #    datos_generales['IDReceptor'] = "CF"
                TagDatosGenerales = etree.SubElement(TagAnulacionDTE,DTE_NS+"DatosGenerales",datos_generales)


                xmls = etree.tostring(GTAnulacionDocumento, encoding="UTF-8")
                logging.warn('xmls')
                logging.warn(xmls)
                xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
                xmls_base64 = base64.b64encode(xmls)
                logging.warn(xmls_base64)
                logging.warn('BASE 64')
                logging.warn(xmls_base64.decode("utf-8"))


                url = "https://signer-emisores.feel.com.gt/sign_solicitud_firmas/firma_xml"

                nuevo_json = {
                    "llave": factura.company_id.fel_llave_pre_firma,
                    "archivo": xmls_base64.decode("utf-8"),
                    "codigo": str(factura.company_id.vat),
                    "alias": str(factura.company_id.fel_usuario),
                    "es_anulacion": "S"
                }
                logging.warn('NUEVO JSON ARCHIVO')
                logging.warn(xmls_base64.decode("utf-8"))

                nuevos_headers = {"content-type": "application/json"}
                response = requests.post(url, json = nuevo_json, headers = nuevos_headers)
                respone_json=response.json()
                logging.warn('RESPONSE JSON')
                logging.warn(respone_json)
                if respone_json['resultado']:


                    headers = {
                        "USUARIO": str(factura.company_id.fel_usuario),
                        "LLAVE": factura.company_id.fel_llave_firma,
                        "IDENTIFICADOR": str(factura.journal_id.name)+'/'+str(factura.id)+'/'+'ANULACION',
                        "Content-Type": "application/json",
                    }
                    data = {
                        "nit_emisor": factura.company_id.vat,
                        "correo_copia": factura.company_id.email,
                        "xml_dte": respone_json["archivo"]
                    }

                    r = requests.post("https://certificador.feel.com.gt/fel/anulacion/v2/dte/", json=data, headers=headers)
                    logging.warn(r.json())
                    retorno_certificacion_json = r.json()
                    logging.warn('si anuló')
                    if not retorno_certificacion_json['resultado']:
                        raise UserError(str('ERROR AL ANULAR'))
                else:
                    raise UserError(str('ERROR AL ANULAR'))

        return super(AccountMove, self).button_draft()
