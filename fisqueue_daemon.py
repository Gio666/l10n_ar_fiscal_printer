#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import psycopg2 as dbdrive
import logging
import socket
import textwrap
import errno
import xmlrpclib
import string, types 
import unicodedata
from time import sleep
from ConfigParser import SafeConfigParser

# VARIABLES DE CONEXION A OPENERP
UID=1
DBUSER='admin'
DBNAME='TEST_FE'
DB='localhost'
PWD='admin'
DBDRIVEUSER='postgres'

def get_num(x): return float(''.join(ele for ele in x if ele.isdigit() or ele == '.'))

def _convert_ref(ref,denomination):
		return "CI " + denomination + ref

def formatText(text):
	res = unicodedata.normalize('NFKD', unicode(text)).encode('ASCII', 'ignore')
	return res    

def send_message(INDATA):
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((HOST, PORT))
		s.send(INDATA)
                sleep(2)
		data = s.recv(BUFFER)
		s.close()
                return data
	except socket.error as serr:
		data = "FALLO_COMUNICACION"
		return data

def get_fields(dataline):
    fields = dataline.strip().split(FS)
    return fields       

def fis_getstatus():
    resp=send_message('*')
    ret=get_fields(resp)
    return ret

def fis_getserial():
    resp = send_message(chr(128))
    #resp = send_message('Ç')
    ret = get_fields(resp)
    return ret    

def fis_barcode(ean13code, print_number):
    resp=send_message('Z' + FS + "1" + FS + ean13code + FS + print_number)
    ret=get_fields(resp)
    return ret

def fis_openfiscal(doctype,value):
    resp = send_message('@' + FS + doctype + FS + value) 
    ret=get_fields(resp)
    return ret

def fis_printline(desc,cant,punit,iva,imputacion,impuestos,display,calificador):
    resp = send_message('B' + FS + desc + FS + cant + FS + punit + FS + iva + FS + imputacion + FS + impuestos + FS + display + FS + calificador) 
    ret=get_fields(resp)
    return ret

def fis_senditems(partner_data):
    commdata='B'
    for infield in partner_data:
        commdata=commdata + FS + infield
    resp=send_message(commdata)
    ret=get_fields(resp)
    return ret  

def fis_subtotal(imp, locked, display):
    resp=send_message('C' + FS + imp + FS + locked + FS + display)
    ret=get_fields(resp)
    return ret
    
def fis_paymment(desc,monto,tipo,display,desc_adic):
    resp=send_message('D' + FS + desc + FS + monto + FS + tipo + FS + display + FS + desc_adic) 
    ret=get_fields(resp)
    return ret

def fis_closefiscal(n_copias):
    resp=send_message('E' + FS + n_copias)
    ret=get_fields(resp)
    return ret

def fis_cancel():
    #resp=send_message('ÿ')
    resp=send_message(chr(152))
    ret=get_fields(resp)
    return ret

def fis_buyerdata(nombre,cuit,iva,tipodni,street):
    commdata = "b" + FS + nombre + FS + cuit + FS + iva + FS + tipodni + FS + street
    resp = send_message(commdata)
    ret = get_fields(resp)
    return ret

def hasar_invoice():

	#CREO LA CONEXION AL OPENERP CON XMLRPC
	sock = xmlrpclib.ServerProxy('http://localhost:8069/xmlrpc/object')
	
	#BUSCO EN EL OPENERP LAS FACTURAS A IMPRIMIR .
	args = [('type', '=', 'out_invoice'), 
			('state', 'in', ['open','paid']), 
			('fiscalized', '=', False), 
			('to_printfiscal', '=', True)]
	invoice_ids = sock.execute(DBNAME, UID, PWD, 'account.invoice', 'search', args)
	if not invoice_ids:
		logging.info('NO HAY FACTURAS PARA IMPRIMIR')
		return 1

	print "FACTURAS ENCONTRADAS PARA IMPRESION: ",invoice_ids

	#RECORRO LAS FACTURAS QUE TRAIGO DEL OPEN
	for records in invoice_ids:

                #INICIALIZO VARIABLES EN VALORES DEFAULT
                global FS
                global PORT
                global HOST
                global BUFFER
                global WIDTHTEXT
                FS = chr(28)
                PORT = 1600
                HOST = 'localhost'
                BUFFER = 1024
                WIDTHTEXT = 50

		print "SE INTENTARA PROCESAR LA FACTURA: ",records

		invoice_fields= ['denomination_id','partner_id','number', 'type', 'internal_number', 'state', 'name',
		'invoice_line', 'tax_line', 'company_id', 'amount_total','payment_ids','move_id','pos_ar_id']

		#OBTENGO DATOS DE LA FACTURA
		invoice_data=sock.execute(DBNAME, UID, PWD, 'account.invoice', 'read', records, invoice_fields)

		#OBTENGO DATOS DEL PUNTO DE VENTA DONDE SE HIZO LA FACTURA
		pos_fields= ['name','fprinter_id']
		pos_data=sock.execute(DBNAME, UID, PWD, 'pos.ar', 'read', invoice_data['pos_ar_id'][0], pos_fields)

                #OBTENGO DATOS DEL IMPRESOR FISCAL
                printer_fields = ['fiscal_hostname','fiscal_port','fiscal_buffer','fiscal_widthtext','fiscal_separator']
                printer_data=sock.execute(DBNAME, UID, PWD, 'fiscal.printers', 'read', pos_data['fprinter_id'][0], printer_fields)
                
                FS= chr(printer_data['fiscal_separator'])
                PORT= int(printer_data['fiscal_port'])
                HOST= printer_data['fiscal_hostname']
                BUFFER= int(printer_data['fiscal_buffer'])
                WIDTHTEXT = int(printer_data['fiscal_widthtext'])

		#PREGUNTO ESTADO DE IMPRESORA FISCAL
                resp = fis_getstatus()
                print "CONSULTO ESTADO DE LA IMPRESORA FISCAL: ",resp
                if resp == ['FALLO_COMUNICACION']:
			print "    FALLO COMUNICACION, SE SALTEA OPERACION"
			continue
                # SI EL ESTADO ES MALO TENDRIA QUE PASAR AL SIGUIENTE RECORD.

                #OBTENGO DATOS DEL PARTNER DE LA FACTURA
		partner_fields= ['name','vat','property_account_position','document_type_id','street']
		partner_data=sock.execute(DBNAME, UID, PWD, 'res.partner', 'read', invoice_data['partner_id'][0], partner_fields)

		#PASO A LA IMPRESORA FISCAL DATOS DEL PARTNER
		if partner_data['vat'] == False :
			partner_data['vat'] = ''
		if partner_data['street'] == False :
			partner_data['street'] = 'Domicilio...'


		#CASE DE RESPONSABILIDAD FISCAL
		if partner_data['property_account_position'] == False:
			responsability = 'T'
		else:
			if partner_data['property_account_position'][1] == 'RI':
				responsability = 'I'
			if partner_data['property_account_position'][1] == 'Monotributo':
				responsability = 'M'
			if partner_data['property_account_position'][1] == 'Exento':
				responsability = 'E'
			if partner_data['property_account_position'][1] == 'Consumidor Final':
				responsability = 'C'

		#CASE DE TIPO DE DOCUMENTO
		if partner_data['document_type_id'] == False:
			doc_type = ' '
		else:
                        if partner_data['document_type_id'][1] == 'CUIT':
				doc_type = 'C'
			if partner_data['document_type_id'][1] == 'CUIL':
				doc_type = 'L'
			if partner_data['document_type_id'][1] == 'LE':
				doc_type = '0'
			if partner_data['document_type_id'][1] == 'LC':
				doc_type = '1'
			if partner_data['document_type_id'][1] == 'DNI':
				doc_type = '2'
			if partner_data['document_type_id'][1] == 'Pasaporte':
				doc_type = '3'
			if partner_data['document_type_id'][1] == 'CI Policia Federal':
				doc_type = '4'

		resp = fis_buyerdata( partner_data['name'], partner_data['vat'], str(responsability) , doc_type , partner_data['street'])
		print "    RESPUESTA CUSTOMER DATA: ",resp

		#PASO A LA IMPRESORA FISCAL TIPO DE FACTURA EJ: A , B , C
		#PASO EN DURO T
		resp = fis_openfiscal( invoice_data['denomination_id'][1] , 'T')
		if resp == ['FALLO_COMUNICACION']:
                        print "    FALLO COMUNICACION, SE SALTEA OPERACION"
                        continue
		print "    RESPUESTA ABRIR ARCHIVO FISCAL: ",resp

		#RECORRO LAS LINEAS DE FACTURACION
		for line in invoice_data['invoice_line']:
			invoice_line_fields= ['name','quantity','price_unit','invoice_line_tax_id','']
			invoice_line_data=sock.execute(DBNAME, UID, PWD, 'account.invoice.line', 'read', line, invoice_line_fields)

			tax_data= {}
			tax_data['amount'] = 0.0
			if invoice_line_data['invoice_line_tax_id']:
				tax_fields= ['amount']
				tax_data=sock.execute(DBNAME, UID, PWD, 'account.tax', 'read', invoice_line_data['invoice_line_tax_id'][0], tax_fields)

			#def fis_printline(desc,cant,punit,iva,imputacion,impuestos,display,calificado)
			resp = fis_printline( invoice_line_data['name'] , str(invoice_line_data['quantity']) , str(invoice_line_data['price_unit']) ,str(tax_data['amount'] * 100),'M','0.0','','T')
	                if resp == ['FALLO_COMUNICACION']:
        	                print "    FALLO COMUNICACION, SE SALTEA OPERACION"
                	        continue
			print "    RESPUESTA IMPRESION LINEA: ",resp

		#PASO EL SUBTOTAL DE LA FACTURA
		#def fis_subtotal(imp, locked, display):
		resp = fis_subtotal('P','Subtotal: ','')
                if resp == ['FALLO_COMUNICACION']:
                        print "    FALLO COMUNICACION, SE SALTEA OPERACION"
                        continue
		print "    REPUESTA SUBTOTAL: ",resp

		
		#PASO EL PAGO DE LA FACTURA
		#def fis_paymment(desc,monto,tipo,display,desc_adic)

		if not invoice_data['payment_ids']:
			logging.info('NO HAY PAGOS')
		else :
			dbconn = dbdrive.connect(database=DBNAME,host=DB,user=DBDRIVEUSER)
			cursor = dbconn.cursor()
			cursor.execute("""SELECT a.name as name, a.amount as amount FROM payment_mode_receipt_line as a, account_voucher as b, account_move_line as c WHERE a.voucher_id = b.id AND b.move_id = c.move_id AND c.id = ANY(%s) UNION ALL SELECT 'CH N: ' || trim(a.number) || '|' || substring(trim(d.name) from 1 for 12) || '|' || to_char(a.issue_date, 'DD/MM/YYYY') || '|' || coalesce(to_char(a.payment_date, 'DD/MM/YYYY'),''), a.amount as amount FROM account_third_check as a, account_voucher as b, account_move_line as c, res_bank d WHERE a.source_voucher_id = b.id AND b.move_id = c.move_id AND a.bank_id = d.id AND c.id = ANY(%s)""",(invoice_data['payment_ids'],invoice_data['payment_ids'],))
                        
			payment_mode_receipt = cursor.fetchall()

			if len(payment_mode_receipt) <= 3:

				for payment in payment_mode_receipt:
					resp = fis_paymment(payment[0],str(payment[1]),'T','','')
					if resp == ['FALLO_COMUNICACION']:
						print "    FALLO COMUNICACION, SE SALTEA OPERACION"
						continue
					print "RESPUESTA PAGO: ",resp
			else :
				logging.info('MAS DE 3 LINEAS DE PAGO, NO IMPRIME EN FACTURA')

		#MANDO COMANDO DE CIERRE FISCAL
		#def fis_closefiscal(n_copias)
		resp = fis_closefiscal('1')
		if resp == ['FALLO_COMUNICACION']:
			print "    FALLO COMUNICACION, SE SALTEA OPERACION"
			continue
		print "    RESPUESTA CIERRE FISCAL: ",resp

		#NO TOMO resp[0] PORQUE PUEDE VENIR CON RUIDO
                #if resp[0] == 'C080' and resp[1] == '0600':
		if resp[1] == '0600':
			
			numero = str(pos_data['name'])+'-'+resp[2].zfill(8)
                        print "    ULTIMO NUMERO DE FACTURA: ",numero

			#COPIO ULTIMO NUMERO A OPEN
			values = {'to_printfiscal': False, 'fiscalized': True,
						'fiscal_invoice': 'FISCALIZADA',
						'fiscal_status': 'FISCALIZADA', 'internal_number': numero }
			results = sock.execute(DBNAME, UID, PWD, 'account.invoice', 'write', records, values)


			move_id = invoice_data['move_id'][0]
			ref = _convert_ref(numero, invoice_data['denomination_id'][1])
			
			#CONEXION A LA BASE DE DATOS PARA ACTUALIZAR CAMPOS DE REFERENCIA.
			#SOBRE ACCOUNT_MOVE, ACCOUNT_MOVE_LINE y ACCOUNT_ANALYTIC_LINE
			dbconn = dbdrive.connect(database=DBNAME,host=DB,user=DBDRIVEUSER)
			cursor = dbconn.cursor()
			cursor.execute("""UPDATE account_move SET ref = %s WHERE id = %s""",(ref,move_id))
			cursor.execute("""UPDATE account_move_line SET ref = %s WHERE move_id = %s""",(ref,move_id))
			cursor.execute("""UPDATE account_analytic_line SET ref = %s WHERE move_id = %s""",(ref,move_id))

		else:
			values = {'fiscal_status': 'ERROR - ' + resp[1], 'fiscal_invoice': 'ERROR - '+ resp[1]}
			results = sock.execute(DBNAME, UID, PWD, 'account.invoice', 'write', records, values)
			fis_cancel()

	return 0

def main():
    taskEND, FirsTime = True, True
    while taskEND:
    		if not FirsTime:
			sleep(15)
		FirsTime = False
                print " == NUEVA RECORRIDA =="
                hasar_invoice()
    return 

if __name__ == "__main__":
    main()    
