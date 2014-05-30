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
import time
from lxml import etree
import openerp.addons.decimal_precision as dp
import openerp.exceptions
import socket 
import textwrap
import errno
import string, types 
import unicodedata

from openerp import netsvc
from openerp import pooler
from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

FS = chr(28)
PORT=1600
BUFFER=1024
HOST= 'localhost'

def send_message(HOST, PORT, BUFFER, INDATA):
    try: 
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((HOST, PORT))
        s.send(INDATA)
        data = s.recv(BUFFER)
        s.close()
    except socket.timeout:
        data = ['00099','PRINTER TIMEOUT']
    except socket.error as serr:
        data = ['00099','NO COMMUNICATION']
    return data

def verify_tcp(HOST, PORT, BUFFER):
    try: 
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((HOST, PORT))
        s.close()
        data = ['00000','COMMUNICATION OK']
    except socket.timeout:
        data = ['00099','PRINTER TIMEOUT']
    except socket.error as serr:
        data = ['00099','NO COMMUNICATION']
    return data

def get_fields(dataline):
    fields = dataline.strip().split(FS)
    return fields

def fis_getstatus(HOST, PORT, BUFFER):
    resp=send_message(HOST, PORT, BUFFER, "*")
    ret=get_fields(resp)
    return ret

def fis_getserial(HOST, PORT, BUFFER):
    resp=send_message(HOST, PORT, BUFFER, chr(128))
    #resp=send_message(HOST, PORT, BUFFER, "Ç")
    ret=get_fields(resp)
    return ret    

def fis_getdatetime(HOST, PORT, BUFFER):
    resp=send_message(HOST, PORT, BUFFER, "Y")
    ret=get_fields(resp)
    return ret
    
def fis_closeday(HOST, PORT, BUFFER, FS, close_type, printer_ok):
    resp=send_message(HOST, PORT, BUFFER, "9" + FS + close_type + FS + printer_ok)
    ret=get_fields(resp)
    return ret
    
class account_invoice(osv.osv):

     _inherit = "account.invoice"

     _columns = {
        'fiscalized': fields.boolean('Fiscalized', readonly=True ),
        'to_printfiscal': fields.boolean('Send to Printer', readonly=True ),
        'original_invoice': fields.char('Original Invoice', size=64, readonly=True, help="Original Fiscal Invoice for Return.", ),
        'original_date': fields.date('Original Date', readonly=True, help="Original Fiscal Invoice Date for Return." ),
        'original_time': fields.char('Original Time', size=14, readonly=True, help="Original Fiscal Invoice Time for Return." ),
        'fiscal_invoice': fields.char('Fiscal Invoice', size=64, readonly=True, help="Fiscal Invoice"),
        'fiscal_status': fields.char('Fiscal Status', size=64, readonly=True, help="Fiscal Invoice Status"),
        'fprinter_id': fields.related('pos_ar_id','fprinter_id',readonly=True, type='many2one',relation='fiscal.printers', string="Fiscal Printer", store=True),
     }

     _defaults ={
        'fiscalized': False,
        'original_invoice': '',
        'fiscal_status': '',
     }

     def action_fiscal_print(self, cr, uid, ids, context):
         if context is None:
            context ={}
         for invoice in self.browse(cr, uid, context['active_ids'], context=context):
             _logger.info("invoice %s",invoice)
             if invoice.fiscalized == False:         
                self.write(cr, uid, [invoice.id], {'to_printfiscal': True})
         return True

account_invoice()


class pos_ar(osv.osv):
     _inherit = "pos.ar"
     _columns = {
                 'fprinter_id': fields.many2one('fiscal.printers', 'Fiscal Printers', ondelete='cascade'),
     }
 
pos_ar()

class fiscal_printers(osv.osv):

     _name = 'fiscal.printers'
     _description = 'Fiscal Printers'   

     def _get_printerstatus(self, cr, uid, ids, field_name, arg, context={}):
         result = {}
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res = verify_tcp(HOST, PORT, BUFFER)			
             if res[0] == '00000': 
				 if r.state in ['connected','disconnected']:
					result[r.id] = 'Connected'
					self.write(cr, uid, ids, {'state': 'connected'})
				 else:
					result[r.id] = 'Inactive'
             else:
				 if r.state in ['connected','disconnected']:
					result[r.id] = 'Disconnected'
					self.write(cr, uid, ids, {'state': 'disconnected'})
				 else:
					result[r.id] = 'Inactive'				
         return result

     def action_enable_print(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res = verify_tcp(HOST, PORT, BUFFER)			
             if res[0] == '00000': 
				 if r.state in ['inactive','connected','disconnected']:
					estado = 'connected'
				 else:
					estado = 'inactive'
             else:
				 if r.state in ['inactive','connected','disconnected']:
					estado = 'disconnected'
				 else:
					estado = 'inactive'
         return self.write(cr, uid, ids, {'state': estado})
		 		
     def action_disable_print(self, cr, uid, ids, context=None):
         return self.write(cr, uid, ids, {'state': 'inactive'})

     _columns = {
        'name': fields.char('Printer Id', size=14, help="Fiscal Printer Id", ),
        'fiscal_model': fields.char('Model', size=25, help="Supported Model Printer", ),
        'fiscal_separator': fields.integer('Separator', size=25,help="Supported in number Printer scape"),
        'fiscal_widthtext': fields.integer('Widthtext',  size=25,help="Supported number Width Printer"),
        'fiscal_brand': fields.char('Brand', size=35,help="Supported Brand Printer"),
        'fiscal_hostname': fields.char('Hostname/IP Address', help='Device Hostname in Fiscal Printer', size=64, ),
        'fiscal_port': fields.integer('Port', help="Device Port in Fiscal Printer", ),
        'fiscal_buffer': fields.integer('Buffer', help="Device Buffer in Fiscal Printer", ),
        'fiscal_device': fields.char('Serial Device', help='Serial Device in Fiscal Printer', size=64, ),
        'state': fields.selection([('inactive','Inactive'), ('disconnected','Disconnected'), ('connected','Connected')], 'Status'),
        'printerstat': fields.function(_get_printerstatus, type='char', method=True, size=26, string='Communication'),

        'fisqueue_ids': fields.one2many('account.invoice', 'fprinter_id', 'Fiscal Invoices', ondelete='cascade',
               domain=[('state','in', ['open', 'paid', 'cancel']), ('fiscalized','=', False),
                                  ('type','in', ['out_invoice', 'out_refund']), ('to_printfiscal','=', True)]),
        'fisprint_ids': fields.one2many('account.invoice', 'fprinter_id', 'Fiscal Invoices', ondelete='cascade',
               domain=[('state','in', ['open', 'paid', 'cancel']), ('fiscalized','=', False),
                                  ('type','in', ['out_invoice', 'out_refund']), ('to_printfiscal','=', False)]),
     }
 
     _defaults ={
        'fiscal_port': 1600,
        'fiscal_hostname': 'localhost',
        'fiscal_buffer': 1024,
        'fiscal_device': 'ttyUSB0',
        'fiscal_widthtext': 50,
        'fiscal_separator': 28,
        'state': 'inactive',
     }

     def send_verify(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res = verify_tcp(HOST, PORT, BUFFER)			
             if res[0] == '00000': 
				 if r.state in ['connected','disconnected']:
					estado = 'connected'
				 else:
					estado = 'inactive'
             else:
				 if r.state in ['connected','disconnected']:
					estado = 'disconnected'
				 else:
					estado = 'inactive'
         return self.write(cr, uid, ids, {'state': estado})

     def send_closeX(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             FS     = chr(r.fiscal_separator)
             res=fis_closeday(HOST, PORT, BUFFER, FS, "X", "")
             if res[0] == '00099':
                raise osv.except_osv(_('ERROR!'), _(res[1])) 
             else:  
                raise osv.except_osv(_(res), _('Close "X" completed!'))
         return True

     def send_closeZ(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             FS     = chr(r.fiscal_separator)
             res=fis_closeday(HOST, PORT, BUFFER, FS, "Z", "")
             if res[0] == '00099':
                raise osv.except_osv(_('ERROR!'), _(res[1:])) 
             else:  
                raise osv.except_osv(_(res), _('Close "Z" completed!'))
         return True

     def get_status(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res=fis_getstatus(HOST, PORT, BUFFER)
             if res[0] == '00099':
                raise osv.except_osv(_('ERROR!'), _(res[1])) 
             elif res[0] == '0000':  
                raise osv.except_osv(_('PRINTER STATUS'), _(res[2:]))
             else:
                raise osv.except_osv(_('STATUS ' + res[0]), _(res[1:]))				 
         return True

     def get_serial(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res=fis_getserial(HOST, PORT, BUFFER)
             if res[0] == '00099':
                raise osv.except_osv(_('ERROR!'), _(res[1])) 
             elif res[0] == '0000':  
                raise osv.except_osv(_('PRINTER SERIAL'), _(res[2:]))
             else:
                raise osv.except_osv(_('STATUS ' + res[0]), _(res[1]))				 
         return True

     def get_datetime(self, cr, uid, ids, context=None):
         estado = ''
         for r in self.browse(cr, uid, ids, context=context):
             HOST   = r.fiscal_hostname
             BUFFER = r.fiscal_buffer
             PORT   = r.fiscal_port
             res=fis_getdatetime(HOST, PORT, BUFFER)
             if res[0] == '00099':
                raise osv.except_osv(_('ERROR!'), _(res[1])) 
             elif res[0] == '0000':  
                raise osv.except_osv(_('FISCAL DATE/TIME'), _(res[2:]))
             else:
                raise osv.except_osv(_('STATUS ' + res[0]), _(res[1:]))				 
         return True
fiscal_printers()

class model_printers(osv.osv):

     _name = 'fiscal.model.printers'
     _description = 'Fiscal Printer Models'    

     _columns = {
        'name': fields.char('Model', size=14, help="Fiscal Printer Model", ),
        'fiscal_brand': fields.char('Brand', size=14, help="Brand for this printer", ),
        'fiscal_separator': fields.integer('Separator', help="Field Separator in Fiscal Printer", ),
        'fiscal_widthtext': fields.integer('Width', help="Width Text in Fiscal Printer", ),
     }
 
     _defaults ={
        'fiscal_brand': 'HASSAR',
        'fiscal_separator': 28,
        'fiscal_widthtext': 50,
     }

model_printers()
