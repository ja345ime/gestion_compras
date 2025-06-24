from flask import current_app as app
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, make_response, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
import pytz

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
    # agregar_producto_al_catalogo, # Movido o usado dentro del servicio
    obtener_sugerencias_productos, # Usado en rutas para pasar a templates
    # enviar_correo, # Usado dentro del servicio
    # enviar_correos_por_rol, # Usado dentro del servicio
    # generar_mensaje_correo, # Usado dentro del servicio
    # cambiar_estado_requisicion, # Lógica ahora en servicio
    # guardar_pdf_requisicion, # Usado dentro del servicio
    # limpiar_requisiciones_viejas, # Lógica ahora en servicio
    generar_pdf_requisicion, # Usado en ruta de imprimir
    registrar_accion, # Usado en servicio y otras rutas
)

from .models import (
    Rol,
    Usuario,
    Departamento,
    Requisicion, # Usado para queries directas en rutas (ej. dashboard) o pasado a servicio
    # DetalleRequisicion, # Manejado por el servicio
    # ProductoCatalogo, # Manejado por el servicio
    AdminVirtual,
    AuditoriaAcciones, # Usado en dashboard
)

from .forms import (
    LoginForm,
    UserForm,
    EditUserForm,
    RequisicionForm,
    CambiarEstadoForm,
    ConfirmarEliminarForm,
    ConfirmarEliminarUsuarioForm,
)

from .services.requisicion_service import requisicion_service
from .services.usuario_service import usuario_service

main = Blueprint('main', __name__)
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    ip_addr = request.remote_addr

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
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))

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
                next_page = request.args.get('next')
                flash('Inicio de sesión exitoso.', 'success')
                app.logger.info(f"Usuario '{user.username}' inició sesión.")
                return redirect(next_page or url_for('main.index'))
            else:
                flash('Esta cuenta de usuario está desactivada.', 'danger')
                app.logger.warning(f"Intento de login de usuario desactivado: {form.username.data}")
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            registrar_intento(ip_addr, form.username.data, False)
            app.logger.warning(f"Intento de login fallido para usuario: {form.username.data}")
    return render_template('login.html', title='Iniciar Sesión', form=form)
@main.route('/logout')
@login_required
def logout():
    app.logger.info(f"Usuario '{current_user.username}' cerró sesión.")
    current_user.session_token = None
    if getattr(current_user, "id", None) != 0:
        db.session.commit()
    session.pop('session_token', None)
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('main.login'))
@main.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    page = request.args.get('page', 1, type=int)
    per_page = app.config.get('PER_PAGE', 10) # Usar config si está disponible
    usuarios_paginados = usuario_service.listar_usuarios_paginados(page=page, per_page=per_page)
    return render_template('admin/listar_usuarios.html', usuarios_paginados=usuarios_paginados, title="Gestión de Usuarios")

@main.route('/admin/usuarios/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def crear_usuario():
    form = UserForm()
    # Poblar choices del formulario usando el servicio o directamente si es simple
    # El servicio puede encapsular la lógica de qué roles/deptos puede ver/asignar el current_user
    roles_disponibles = usuario_service.get_roles_para_formulario(current_user)
    departamentos_disponibles = usuario_service.get_departamentos_para_formulario(current_user)

    form.rol_id.choices = [(r.id, r.nombre) for r in roles_disponibles]
    form.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + \
                                  [(str(d.id), d.nombre) for d in departamentos_disponibles]

    if form.validate_on_submit():
        nuevo_usuario = usuario_service.crear_nuevo_usuario(form, current_user)
        if nuevo_usuario:
            # El servicio ya maneja el flash de éxito y el registro de acción
            return redirect(url_for('main.listar_usuarios'))
        # Si hay error, el servicio ya flasheó y/o añadió errores al form.
        # Se re-renderiza el template con el form que contiene los errores.
            
    return render_template(
        'admin/crear_usuario.html',
        form=form,
        # Ya no es necesario pasar roles y departamentos directamente si el form los carga bien.
        # Sin embargo, si el template los usa para algo más, se pueden mantener.
        # roles=roles_disponibles,
        # departamentos=departamentos_disponibles,
        title="Crear Nuevo Usuario"
    )

@main.route('/admin/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    usuario = usuario_service.obtener_usuario_por_id(usuario_id) # get_or_404

    # Lógica de permiso: Un admin no puede editar un superadmin a menos que él mismo sea superadmin.
    if usuario.superadmin and not current_user.superadmin:
        flash('No tiene permisos para editar a un superadministrador.', 'danger')
        return redirect(url_for('main.listar_usuarios'))

    form = EditUserForm(obj=usuario if request.method == 'GET' else None)

    # Poblar choices para roles y departamentos
    roles_disponibles = usuario_service.get_roles_para_formulario(current_user)
    departamentos_disponibles = usuario_service.get_departamentos_para_formulario(current_user) # Podría ser todos los deptos

    form.rol_id.choices = [(r.id, r.nombre) for r in roles_disponibles]
    form.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + \
                                  [(str(d.id), d.nombre) for d in departamentos_disponibles]

    # Si es superadmin, puede cambiar el rol. Si no, el campo rol_id debería estar deshabilitado o no mostrarse.
    # El UserForm/EditUserForm podría manejar esto internamente o aquí explícitamente.
    if not current_user.superadmin:
        form.rol_id.render_kw = {'disabled': 'disabled'} # Deshabilitar si no es superadmin
        # O filtrar el rol actual del usuario para que no pueda cambiarlo si no es superadmin
        # form.rol_id.data = usuario.rol_id # Asegurar que el valor no cambie si está disabled


    if request.method == 'GET':
        form.departamento_id.data = str(usuario.departamento_id) if usuario.departamento_id else '0'
        form.password.data = '' # Limpiar campo de contraseña
        form.confirm_password.data = ''
        if not current_user.superadmin: # Si no es superadmin, mostrar el rol actual
            form.rol_id.data = usuario.rol_id


    if form.validate_on_submit():
        # Si no es superadmin y el rol_id fue alterado (ej. por habilitar el campo desde el browser)
        if not current_user.superadmin and form.rol_id.data != usuario.rol_id:
             flash("No tiene permisos para cambiar el rol del usuario.", "warning")
             form.rol_id.data = usuario.rol_id # Reestablecer al rol original

        usuario_actualizado = usuario_service.actualizar_usuario(usuario_id, form, current_user)
        if usuario_actualizado:
            return redirect(url_for('main.listar_usuarios'))
        # Si hay error, el servicio ya flasheó. Re-renderizar.

    # Para el template, pasar los roles y departamentos completos si el form no los filtra internamente
    # o si el template los necesita para algo más que el select.
    all_roles = Rol.query.order_by(Rol.nombre).all()
    all_departamentos = Departamento.query.order_by(Departamento.nombre).all()

    return render_template('admin/editar_usuario.html', form=form,
                           usuario_id=usuario.id, # o usuario=usuario
                           # Pasar todos los roles/deptos para el selector si el form no los limita
                           roles=all_roles,
                           departamentos=all_departamentos,
                           title="Editar Usuario")


@main.route('/admin/usuarios/<int:usuario_id>/confirmar_eliminar')
@login_required
@admin_required # Un admin puede llegar aquí, pero la acción de eliminar es @superadmin_required
def confirmar_eliminar_usuario(usuario_id):
    usuario = usuario_service.obtener_usuario_por_id(usuario_id)
    if usuario.id == current_user.id:
        flash('No puede eliminar su propio usuario.', 'danger')
        # Redirigir a editar o listar, ya que no puede proceder.
        return redirect(url_for('main.editar_usuario', usuario_id=usuario_id))

    # Un Admin no puede eliminar a un Superadmin. Solo Superadmin puede.
    if usuario.superadmin and not current_user.superadmin:
        flash('No tiene permisos para eliminar a un Superadministrador.', 'danger')
        return redirect(url_for('main.listar_usuarios'))

    form = ConfirmarEliminarUsuarioForm() # Simple form para CSRF token
    return render_template('admin/confirmar_eliminar_usuario.html',
                           usuario=usuario,
                           form=form,
                           title=f"Confirmar Eliminación: {usuario.username}")


@main.route('/admin/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
@superadmin_required # Solo superadmin puede ejecutar esta acción.
def eliminar_usuario_post(usuario_id):
    form = ConfirmarEliminarUsuarioForm() # Para validación CSRF
    if not form.validate_on_submit():
        flash('Petición inválida o error de CSRF.', 'danger')
        # Redirigir a la confirmación de nuevo o a listar usuarios
        return redirect(url_for('main.confirmar_eliminar_usuario', usuario_id=usuario_id))

    # El servicio ya maneja la lógica de si el usuario puede ser eliminado (ej. no a sí mismo, no al último superadmin)
    # y también si el current_user tiene permiso (aunque el decorador ya lo hizo).
    if usuario_service.eliminar_usuario(usuario_id, current_user):
        # El servicio ya flasheó el mensaje de éxito
        pass
    else:
        # El servicio ya flasheó el mensaje de error.
        # Podríamos querer redirigir a la página de edición si la eliminación falla por una razón recuperable.
        # Pero si es por permisos o "último superadmin", listar_usuarios es mejor.
        # Si el usuario ya no existe (eliminado por otro request), get_or_404 en el servicio lo manejaría.
        return redirect(url_for('main.listar_usuarios')) # O a editar_usuario si es apropiado

    return redirect(url_for('main.listar_usuarios'))

@main.route('/admin/limpiar_requisiciones_viejas')
@login_required
@admin_required # Se mantiene el decorador de la ruta para control de acceso general
def limpiar_requisiciones_viejas_route():
    """Limpia requisiciones finalizadas antiguas."""
    dias = request.args.get('dias', 15, type=int)
    # La lógica de limpieza y registro de acción se mueve al servicio
    eliminadas = requisicion_service.limpiar_requisiciones_antiguas(dias, current_user.id)
    if eliminadas >= 0: # El servicio devuelve -1 o similar en error, o lanza excepción
        flash(f'Se eliminaron {eliminadas} requisiciones antiguas.', 'success')
    else:
        flash('Ocurrió un error durante la limpieza de requisiciones antiguas.', 'danger')
    return redirect(url_for('main.historial_requisiciones'))

@main.route('/')
@login_required
def index():
    nuevas = 0
    roles_notificados = ['Almacen', 'Compras', 'Admin']
    if current_user.rol_asignado and current_user.rol_asignado.nombre in roles_notificados:
        prev_login_str = session.pop('prev_login', None)
        last_login = None
        if prev_login_str:
            try:
                last_login = datetime.fromisoformat(prev_login_str)
            except ValueError:
                last_login = None
        if last_login:
            nuevas = Requisicion.query.filter(Requisicion.fecha_creacion > last_login).count()
    if nuevas > 0:
        flash(f'🔔 Tienes {nuevas} requisiciones nuevas desde tu última sesión.', 'info')
    return render_template('inicio.html', title="Inicio", usuario=current_user)
@main.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_requisiciones = Requisicion.query.count()
    promedio_dias = db.session.query(
        db.func.avg(db.func.extract('epoch', Requisicion.fecha_modificacion - Requisicion.fecha_creacion) / 86400.0)
    ).scalar() or 0
    recientes = (
        AuditoriaAcciones.query.order_by(AuditoriaAcciones.fecha.desc()).limit(5).all()
    )
    return render_template(
        'dashboard.html',
        total_requisiciones=total_requisiciones,
        promedio_dias=promedio_dias,
        recientes=recientes,
        title='Dashboard'
    )
@main.route('/requisiciones/crear', methods=['GET', 'POST'])
@login_required
def crear_requisicion():
    form = RequisicionForm()
    # La carga de choices para departamento se hace una sola vez
    departamentos = Departamento.query.order_by(Departamento.nombre).all()
    form.departamento_nombre.choices = [('', 'Seleccione un departamento...')] + [
        (d.nombre, d.nombre) for d in departamentos
    ]

    if request.method == 'GET':
        # Pre-llenar el formulario con datos del usuario actual
        if current_user.is_authenticated:
            if current_user.nombre_completo:
                form.nombre_solicitante.data = current_user.nombre_completo
            if hasattr(current_user, 'cedula') and current_user.cedula:
                form.cedula_solicitante.data = current_user.cedula
            if current_user.email:
                form.correo_solicitante.data = current_user.email
            if current_user.departamento_asignado:
                form.departamento_nombre.data = current_user.departamento_asignado.nombre
            
    if form.validate_on_submit():
        # Pasar el formulario validado y el ID del usuario al servicio
        nueva_requisicion = requisicion_service.crear_nueva_requisicion(form, current_user.id)
        if nueva_requisicion:
            # El servicio ya maneja el flash y el logging
            return redirect(url_for('main.requisicion_creada', requisicion_id=nueva_requisicion.id))
        # Si hay error, el servicio ya mostró un flash, simplemente re-renderizar el template
        # con los errores del formulario si los hubiera (aunque el servicio también flashea errores generales)
    
    productos_sugerencias = obtener_sugerencias_productos() # Esto puede quedar aquí si es solo para el template
    return render_template(
        'crear_requisicion.html',
        form=form,
        departamentos=departamentos, # Se sigue pasando para la populación inicial si es necesario
        title="Crear Nueva Requisición",
        unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
        productos_sugerencias=productos_sugerencias,
    )

@main.route('/requisicion/<int:requisicion_id>/creada')
@login_required
def requisicion_creada(requisicion_id):
    # Usar el servicio para obtener la requisición podría ser una opción,
    # pero get_or_404 es conciso para este caso simple.
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    return render_template('requisicion_creada.html', requisicion=requisicion, title='Requisición Creada')

@main.route('/requisiciones')
@login_required
def listar_requisiciones():
    """Lista las requisiciones visibles para el usuario actual según su rol."""
    filtro = request.args.get('filtro')
    page = request.args.get('page', 1, type=int)
    per_page = 10 # O tomar de app.config

    # La lógica de consulta y filtrado se mueve al servicio
    requisiciones_paginadas = requisicion_service.listar_requisiciones_para_usuario(
        current_user, filtro=filtro, page=page, per_page=per_page
    )

    return render_template(
        'listar_requisiciones.html',
        requisiciones_paginadas=requisiciones_paginadas,
        filtro=filtro,
        title="Requisiciones Pendientes",
        vista_actual='activas',
        datetime=datetime,
        UTC=pytz.UTC,
        TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION
    )

@main.route('/requisiciones/historial')
@login_required
def historial_requisiciones():
    page = request.args.get('page', 1, type=int)
    per_page = 10 # O tomar de app.config

    try:
        app.logger.debug(f"Historial Requisiciones - Usuario: {current_user.username}, Rol: {current_user.rol_asignado.nombre if current_user.rol_asignado else 'N/A'}")
        requisiciones_paginadas = requisicion_service.listar_historial_requisiciones(
            current_user, page=page, per_page=per_page
        )
        if requisiciones_paginadas is None and not current_user.is_authenticated: # Caso raro pero posible
             app.logger.error(f"Usuario no autenticado intentando acceder a historial.")
             flash("Debe iniciar sesión para ver el historial.", "warning")
             return redirect(url_for('main.login'))

    except Exception as e:
        flash(f"Error al cargar el historial de requisiciones: {str(e)}", "danger")
        app.logger.error(
            f"Error en historial_requisiciones para {current_user.username if hasattr(current_user, 'username') else 'desconocido'}: {e}",
            exc_info=True,
        )
        requisiciones_paginadas = None # Asegurar que sea None para el template si hay error grave

    return render_template(
        'historial_requisiciones.html',
        requisiciones_paginadas=requisiciones_paginadas, # Puede ser None si el servicio o un error lo determina
        title="Historial de Requisiciones",
        vista_actual='historial',
        datetime=datetime,
        UTC=pytz.UTC,
        TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION,
    )


@main.route('/requisicion/<int:requisicion_id>', methods=['GET', 'POST'])
@login_required
def ver_requisicion(requisicion_id):
    try:
        # Usar el servicio para obtener la requisición y manejar si no se encuentra
        requisicion = requisicion_service.obtener_requisicion_por_id(requisicion_id)
        if requisicion is None:
            # El servicio ya habrá flasheado un mensaje
            return redirect(url_for('main.listar_requisiciones'))
    except Exception as e: # Captura errores de DB u otros al obtener
        app.logger.error(f"Error al obtener requisición {requisicion_id} en la ruta: {str(e)}", exc_info=True)
        flash('Error grave al intentar cargar la requisición.', 'danger')
        return redirect(url_for('main.listar_requisiciones')) # O a una página de error general

    # Preparar formulario de cambio de estado
    form_estado = CambiarEstadoForm(obj=requisicion if request.method == 'GET' else None)
    if request.method == 'GET':
        form_estado.estado.data = requisicion.estado 

    # Obtener opciones de estado permitidas y permisos del servicio
    rol_actual_nombre = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    opciones_estado_permitidas = requisicion_service.get_opciones_estado_permitidas(requisicion, rol_actual_nombre)

    form_estado.estado.choices = opciones_estado_permitidas
    if not form_estado.estado.choices: # Salvaguarda por si el servicio devuelve lista vacía inesperadamente
        form_estado.estado.choices = [('N/A', 'No disponible')]


    # Procesar cambio de estado si el formulario es enviado
    if form_estado.validate_on_submit() and form_estado.submit_estado.data :
        # Verificar permiso general para cambiar estado (roles específicos)
        if not (rol_actual_nombre in ['Admin', 'Superadmin', 'Compras', 'Almacen']):
            flash('No tiene permiso para cambiar el estado de esta requisición.', 'danger')
            return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion.id))

        nuevo_estado_solicitado = form_estado.estado.data
        # Validar que el nuevo estado esté entre los permitidos para este rol y estado actual
        if not any(nuevo_estado_solicitado == choice[0] for choice in opciones_estado_permitidas):
            flash('Intento de cambio de estado no válido o no permitido para su rol/estado actual.', 'danger')
            return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion.id))

        comentario_ingresado = form_estado.comentario_estado.data.strip() if form_estado.comentario_estado.data else None

        # Llamar al servicio para cambiar el estado
        if requisicion_service.cambiar_estado(requisicion.id, nuevo_estado_solicitado, comentario_ingresado, current_user):
            # El servicio maneja los mensajes flash de éxito/error
            pass # Simplemente redirigir
        # Si el cambio falla, el servicio ya flasheó el error.
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion.id))

    # Obtener permisos de edición/eliminación del servicio
    permisos = requisicion_service.get_permisos_y_estado_edicion(requisicion, current_user)

    puede_cambiar_estado = (
        rol_actual_nombre in ['Admin', 'Superadmin', 'Compras', 'Almacen'] and
        len(opciones_estado_permitidas) > 1 and # Hay más de una opción (es decir, no solo el estado actual)
        any(op[0] != requisicion.estado for op in opciones_estado_permitidas) # Y al menos una opción es diferente al actual
    ) or rol_actual_nombre in ['Admin', 'Superadmin'] # Admin/Superadmin siempre pueden si hay opciones


    # Datos para el template
    creador_usuario = getattr(requisicion, 'creador', None) # Acceso directo al creador si la relación está cargada
    departamento_asignado = getattr(requisicion, 'departamento_obj', None)

    return render_template(
        'ver_requisicion.html',
        requisicion=requisicion,
        creador=creador_usuario,
        departamento=departamento_asignado,
        comentario_estado=requisicion.comentario_estado,
        title=f"Detalle Requisición {requisicion.numero_requisicion}",
        puede_editar=permisos['puede_editar'],
        puede_eliminar=permisos['puede_eliminar'],
        editable_dentro_limite_original=permisos['editable_dentro_limite_original'],
        tiempo_limite_minutos=int(TIEMPO_LIMITE_EDICION_REQUISICION.total_seconds() / 60),
        form_estado=form_estado,
        puede_cambiar_estado=puede_cambiar_estado,
    )

@main.route('/requisicion/<int:requisicion_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_requisicion(requisicion_id):
    requisicion_a_editar = requisicion_service.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
    if not requisicion_a_editar:
        return redirect(url_for('main.listar_requisiciones')) # Servicio ya flasheó

    permisos = requisicion_service.get_permisos_y_estado_edicion(requisicion_a_editar, current_user)
    if not permisos['puede_editar']:
        flash('No tiene permiso para editar esta requisición o las condiciones no se cumplen (tiempo, estado).', 'danger')
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion_a_editar.id))

    form = RequisicionForm(obj=requisicion_a_editar if request.method == 'GET' else None)
    departamentos = Departamento.query.order_by(Departamento.nombre).all()
    form.departamento_nombre.choices = [('', 'Seleccione un departamento...')] + \
                                      [(d.nombre, d.nombre) for d in departamentos]

    if request.method == 'GET':
        if getattr(requisicion_a_editar, 'departamento_obj', None):
            form.departamento_nombre.data = requisicion_a_editar.departamento_obj.nombre

        # Limpiar y repoblar detalles del formulario
        while len(form.detalles.entries) > 0:
            form.detalles.pop_entry()
        if getattr(requisicion_a_editar, 'detalles', []):
            for detalle_db in requisicion_a_editar.detalles:
                form.detalles.append_entry(detalle_db)
        else: # Asegurar al menos una entrada de detalle si no hay ninguna
            form.detalles.append_entry()


    if form.validate_on_submit():
        if requisicion_service.actualizar_requisicion(requisicion_id, form, current_user):
            return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion_a_editar.id))
        # Si falla, el servicio ya flasheó el error. Re-renderizar el form.
    
    productos_sugerencias = obtener_sugerencias_productos()
    return render_template(
        'editar_requisicion.html',
        form=form,
        title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}",
        requisicion_id=requisicion_a_editar.id,
        unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
        productos_sugerencias=productos_sugerencias
    )

@main.route('/requisicion/<int:requisicion_id>/confirmar_eliminar')
@login_required
def confirmar_eliminar_requisicion(requisicion_id):
    requisicion = requisicion_service.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
    if not requisicion:
        return redirect(url_for('main.listar_requisiciones'))

    permisos = requisicion_service.get_permisos_y_estado_edicion(requisicion, current_user)
    if not permisos['puede_eliminar']:
        flash('No tiene permiso para eliminar esta requisición o las condiciones no se cumplen.', 'danger')
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion.id))

    form = ConfirmarEliminarForm() # Formulario simple de confirmación
    return render_template(
        'confirmar_eliminar_requisicion.html',
        requisicion=requisicion,
        form=form,
        title=f"Confirmar Eliminación: {requisicion.numero_requisicion}"
    )

@main.route('/requisicion/<int:requisicion_id>/eliminar', methods=['POST'])
@login_required
def eliminar_requisicion_post(requisicion_id):
    form = ConfirmarEliminarForm() # Validar el token CSRF
    if not form.validate_on_submit():
        flash('Petición inválida o token CSRF faltante/incorrecto.', 'danger')
        return redirect(url_for('main.confirmar_eliminar_requisicion', requisicion_id=requisicion_id))

    requisicion_a_eliminar = requisicion_service.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
    if not requisicion_a_eliminar: # Doble chequeo por si acaso
        return redirect(url_for('main.listar_requisiciones'))

    permisos = requisicion_service.get_permisos_y_estado_edicion(requisicion_a_eliminar, current_user)
    if not permisos['puede_eliminar']: # Chequeo de permiso de nuevo en POST por seguridad
        flash('No tiene permiso para eliminar esta requisición o las condiciones ya no se cumplen.', 'danger')
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion_a_eliminar.id))

    if requisicion_service.eliminar_requisicion(requisicion_id, current_user):
        # El servicio ya flasheó éxito
        pass
    else:
        # El servicio ya flasheó error
        # Podríamos redirigir a ver_requisicion si la eliminación falla pero la req aún existe
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion_id))

    return redirect(url_for('main.listar_requisiciones'))

@main.route('/requisiciones/pendientes_cotizar')
@login_required
def listar_pendientes_cotizar():
    """Lista las requisiciones cuyo estado sea 'Pendiente de Cotizar'."""
    # Esta es una vista específica, podría usar el servicio `listar_por_estado_filtrado`
    page = request.args.get('page', 1, type=int)
    per_page = 10 # O de config

    # Usamos el servicio general de listar por estado, pasando el estado específico.
    # Nota: El servicio `listar_por_estado_filtrado` ya considera los permisos del rol.
    requisiciones_paginadas = requisicion_service.listar_por_estado_filtrado(
        'Pendiente de Cotizar', current_user, page=page, per_page=per_page
    )

    return render_template(
        'listar_pendientes_cotizar.html', # Se podría generalizar este template si es similar a otros
        requisiciones_paginadas=requisiciones_paginadas,
        title="Pendientes de Cotizar",
        vista_actual='pendientes_cotizar' # Para la navegación activa
    )

@main.route('/requisiciones/cotizadas')
@login_required
def listar_cotizadas():
    """Lista las requisiciones cuyo estado sea 'Cotizada'."""
    # Similar a pendientes_cotizar, usamos el servicio.
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Asumiendo que 'Cotizada' es un estado válido en ESTADOS_REQUISICION_DICT
    requisiciones_paginadas = requisicion_service.listar_por_estado_filtrado(
        'Cotizada', current_user, page=page, per_page=per_page
    )

    return render_template(
        'listar_cotizadas.html', # Podría ser un template generalizado
        requisiciones_paginadas=requisiciones_paginadas,
        title="Cotizadas", # El título se puede pasar dinámicamente
        vista_actual='cotizadas'
    )

@main.route('/requisiciones/estado/<path:estado>') # path: permite slashes en el nombre del estado si fuera necesario
@login_required
def listar_por_estado(estado):
    """Lista todas las requisiciones cuyo estado coincida con <estado>."""
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if estado not in ESTADOS_REQUISICION_DICT: # Validar estado antes de pasarlo al servicio
        app.logger.warning(f"Intento de acceso a estado no válido: {estado}")
        abort(404)

    requisiciones_paginadas = requisicion_service.listar_por_estado_filtrado(
        estado, current_user, page=page, per_page=per_page
    )
    return render_template(
        'listar_por_estado.html', # Podría ser un template más genérico si es necesario
        requisiciones_paginadas=requisiciones_paginadas,
        title=ESTADOS_REQUISICION_DICT.get(estado, estado.replace("_", " ").title()), # Título amigable
        estado=estado, # Para la UI
        vista_actual='estado' # Para la navegación activa
    )

@main.route('/requisicion/<int:requisicion_id>/imprimir')
@login_required
def imprimir_requisicion(requisicion_id):
    # Obtener la requisición a través del servicio para consistencia.
    requisicion = requisicion_service.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
    if not requisicion:
        # El servicio ya pudo haber flasheado un mensaje.
        # Si obtener_requisicion_por_id retorna None y flashea, esto es redundante.
        # Si retorna None sin flashear, entonces flash aquí o abort(404).
        # Por ahora, asumimos que el servicio flasheó si retorna None.
        return redirect(url_for('main.listar_requisiciones'))

    try:
        pdf_data = generar_pdf_requisicion(requisicion) # Esta utilidad puede permanecer aquí si es puramente de generación de PDF
        nombre_archivo = f"requisicion_{requisicion.numero_requisicion}.pdf"

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        # Asegurar comillas alrededor del nombre del archivo por si contiene caracteres especiales o espacios.
        response.headers['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        return response
    except Exception as e:
        app.logger.error(f"Error al generar PDF para requisición {requisicion_id}: {e}", exc_info=True)
        flash("Error al generar el PDF de la requisición.", "danger")
        return redirect(url_for('main.ver_requisicion', requisicion_id=requisicion_id))

@main.app_errorhandler(500)
def internal_server_error(error):
    """Maneja errores 500 mostrando una página amigable y registrando el error."""
    app.logger.error(f"Error Interno del Servidor (500): {error}", exc_info=True) # Log más descriptivo
    # Considerar hacer rollback de la sesión de DB aquí si el error pudo dejarla en un estado inconsistente.
    # Esto es especialmente importante si el error ocurrió durante una transacción.
    # from app import db # Importar db aquí para evitar importación circular si no está ya importado globalmente en este punto.
    # try:
    #     db.session.rollback()
    #     app.logger.info("Rollback de sesión de DB exitoso tras error 500.")
    # except Exception as e_rollback:
    #     app.logger.error(f"Error durante el rollback de sesión de DB tras error 500: {e_rollback}", exc_info=True)

    return render_template('500.html', title='Error Interno del Servidor'), 500
