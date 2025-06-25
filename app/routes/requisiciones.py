from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
from .models import Requisicion
from .utils.auditoria import generar_pdf_requisicion

requisiciones_bp = Blueprint('requisiciones', __name__)

@requisiciones_bp.route('/requisiciones')
@login_required
def ver_requisiciones():
    requisiciones = Requisicion.query.all()
    return render_template('requisiciones.html', requisiciones=requisiciones)

@requisiciones_bp.route('/requisiciones/<int:requisicion_id>/imprimir')
@login_required
def imprimir_requisicion(requisicion_id):
    generar_pdf_requisicion(requisicion_id)
    return redirect(url_for('requisiciones.ver_requisiciones'))
