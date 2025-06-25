from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Requisicion  # asumiendo un modelo llamado Requisicion

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/reporte_requisiciones')
@login_required
def reporte_requisiciones():
    if not current_user.superadmin:
        return "Acceso no autorizado", 403

    # Obtener las requisiciones, agrupadas por estado y luego por departamento
    requisiciones = Requisicion.query.all()
    datos_reporte = {}

    for requi in requisiciones:
        estado = requi.estado
        departamento = requi.departamento
        if estado not in datos_reporte:
            datos_reporte[estado] = {}
        if departamento not in datos_reporte[estado]:
            datos_reporte[estado][departamento] = []
        datos_reporte[estado][departamento].append(requi)
    
    # Ordenar requisiciones por fecha descendente dentro de cada grupo
    for estado in datos_reporte:
        for departamento in datos_reporte[estado]:
            datos_reporte[estado][departamento].sort(key=lambda x: x.fecha, reverse=True)

    return render_template('reportes/reporte_requisiciones.html', datos_reporte=datos_reporte)
