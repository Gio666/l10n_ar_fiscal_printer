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

from osv import osv, fields
from tools.translate import _

class invoice(osv.osv):
    _name = "account.invoice"
    _inherit = "account.invoice"

    # MODIFICO LA FUNCION PARA QUE SOLO LEVANTE EL ULTIMO NUMERO DE FACTURA NO FISCALIZADO.
    # ESTO PUEDE GENERAR PROBLEMAS PARA LAS PRIMERAS FACTURAS SI NO SON ENVIADAS DIRECTAMENTE A FISCALIZAR
    # PERO RESUELVE EL PROBLEMA DE DE DUPLICACION CUANDO SE SIGUE LA MISMA SECUENCIA DE FISCALIZACION
    # Y UNA FACTURA CONTIENE SUFICIENTES ELEMENTOS COMO PARA CONSUMIR MAS DE UN NUMERO.
    def get_next_invoice_number(self, cr, uid, invoice, context=None):

        cr.execute("SELECT max(to_number(substring(internal_number from '[0-9]{8}$'), '99999999')) FROM account_invoice WHERE internal_number ~ '^[0-9]{4}-[0-9]{8}$' and pos_ar_id=%s and state in %s and type=%s and is_debit_note=%s and fiscalized = False", (invoice.pos_ar_id.id, ('open', 'paid', 'cancel',), invoice.type, invoice.is_debit_note))
        last_number = cr.fetchone()

        if not last_number or not last_number[0]:
            next_number = 1
        else:
            next_number = last_number[0] + 1

        return next_number
invoice()
