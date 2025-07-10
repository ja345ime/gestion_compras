from flask import current_app as app
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, make_response, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
import pytz
from urllib.parse import urlparse, urljoin

from . import (
    db,
    ESTADO_INICIAL_REQUISICION, # Usado en servicio y potencialmente en rutas para lógica de permisos
    ESTADOS_REQUISICION, # Usado en servicio
    ESTADOS_REQUISICION_DICT, # Usado en servicio y rutas (templates)
    ESTADOS_HISTORICOS, # Usado en servicio
    UNIDADES_DE_MEDIDA_SUGERENCIAS, # Usado en templates (pasado desde rutas)
    TIEMPO_LIMITE_EDICION_REQUISICION, # Usado en servicio y rutas (templates)
    DURACION_SESION,
)

from .utils import (
    registrar_intento,
    exceso_intentos,
    admin_required,
    superadmin_required,
    obtener_sugerencias_productos, # Usado en rutas para pasar a templates
    generar_pdf_requisicion, # Usado en ruta de imprimir
    registrar_accion, # Usado en servicio y otras rutas
)

from .models import (
    Rol,
    Usuario,
    Departamento,
    Requisicion, # Usado para queries directas en rutas (ej. dashboard) o pasado a servicio
    AdminVirtual,
    AuditoriaAcciones, # Usado en dashboard
)

from .forms import (
    LoginForm,
    UserForm,
    EditUserForm,
    ConfirmarEliminarUsuarioForm,
    RequisicionForm,
    CambiarEstadoForm,  # <--- Importar el formulario necesario
    ConfirmarEliminarForm
)

from .services.requisicion_service import requisicion_service
from .services.usuario_service import usuario_service

main = Blueprint('main', __name__)

def is_safe_url(target):
    """
    Validates that a redirect URL is safe to prevent open redirect vulnerabilities.
    """
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    ip_addr = request.remote_addr

    from .models import Usuario

    if form.validate_on_submit():
        if exceso_intentos(ip_addr, form.username.data):
            flash('Demasiados intentos de inicio de sesión. Por favor, inténtalo más tarde.', 'danger')
            return render_template('login.html', title='Iniciar Sesión', form=form)

        admin_password = os.environ.get("ADMIN_PASSWORD")
        if form.username.data == "admin" and admin_password and form.password.data == admin_password:
            admin_user = AdminVirtual()
            admin_user.session_token = os.urandom(24).hex()
            session['session_token'] = admin_user.session_token
            login_user(admin_user, duration=DURACION_SESION)
            registrar_intento(ip_addr, "admin", True)
            flash("Inicio de sesión como Administrador exitoso.", "success")
            app.logger.info("Usuario 'admin' (virtual) ha iniciado sesión.")
            # FIXED: Safe URL validation for redirect
            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("main.index"))

        user = Usuario.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if user.activo:
                previous_login = user.ultimo_login
                user.session_token = os.urandom(24).hex()
                user.ultimo_login = datetime.now(pytz.UTC)
                db.session.commit()
                login_user(user, duration=DURACION_SESION)
                session['session_token'] = user.session_token
                session['prev_login'] = previous_login.isoformat() if previous_login else None
                registrar_intento(ip_addr, user.username, True)
                # FIXED: Safe URL validation for redirect
                next_page = request.args.get('next')
                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                flash('Inicio de sesión exitoso.', 'success')
                app.logger.info(f"Usuario '{user.username}' inició sesión.")
                return redirect(url_for('main.index'))
            else:
                flash('Esta cuenta de usuario está desactivada.', 'danger')
                app.logger.warning(f"Intento de login de usuario desactivado: {form.username.data}")
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            registrar_intento(ip_addr, form.username.data, False)
    return render_template('login.html', title='Iniciar Sesión', form=form)

@main.route('/requisiciones/nueva', methods=['GET', 'POST'])
@login_required
def crear_requisicion():
    form = RequisicionForm()
    from .models import Departamento

    departamentos = Departamento.query.all()
    form.departamento_nombre.choices = [(d.nombre, d.nombre) for d in departamentos]

    if form.validate_on_submit():
        requisicion = Requisicion(
            nombre_solicitante=form.nombre_solicitante.data,
            cedula_solicitante=form.cedula_solicitante.data,
            correo_solicitante=form.correo_solicitante.data,
            departamento_nombre=form.departamento_nombre.data,
            prioridad=form.prioridad.data,
            observaciones=form.observaciones.data
        )
        # Obtener y agregrar detalles
        for detalle_form in form.detalles:
            detalle = DetalleRequisicion(
                producto=detalle_form.producto.data,
                cantidad=detalle_form.cantidad.data,
                unidad_medida=detalle_form.unidad_medida.data
            )
            requisicion.detalles.append(detalle)
        db.session.add(requisicion)
        db.session.commit()
        flash('Requisición creada con éxito.', 'success')
        return redirect(url_for('main.ver_requisiciones'))
    return render_template('requisiciones/crear_requisicion.html', form=form)
