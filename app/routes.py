from flask import current_app as app
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, make_response, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
import pytz
from sqlalchemy.exc import IntegrityError

from . import (
    db,
    ESTADO_INICIAL_REQUISICION,
    ESTADOS_REQUISICION,
    ESTADOS_REQUISICION_DICT,
    ESTADOS_HISTORICOS,
    UNIDADES_DE_MEDIDA_SUGERENCIAS,
    TIEMPO_LIMITE_EDICION_REQUISICION,
    DURACION_SESION,
    registrar_intento,
    exceso_intentos,
    agregar_producto_al_catalogo,
    obtener_sugerencias_productos,
    enviar_correo,
    enviar_correos_por_rol,
    generar_mensaje_correo,
    cambiar_estado_requisicion,
    guardar_pdf_requisicion,
    limpiar_requisiciones_viejas,
    generar_pdf_requisicion,
    registrar_accion,
)

from .models import (
    Rol,
    Usuario,
    Departamento,
    Requisicion,
    DetalleRequisicion,
    ProductoCatalogo,
    AdminVirtual,
    AuditoriaAcciones,
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

main = Blueprint('main', __name__)
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
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
            return redirect(next_page or url_for("index"))

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
                return redirect(next_page or url_for('index'))
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
    return redirect(url_for('login'))
@main.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    usuarios_paginados = db.session.query(Usuario).order_by(Usuario.username).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/listar_usuarios.html', usuarios_paginados=usuarios_paginados, title="Gestión de Usuarios")

@main.route('/admin/usuarios/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def crear_usuario():
    """Permite a un administrador crear nuevos usuarios."""
    form = UserForm()
    roles = Rol.query.all()
    departamentos = Departamento.query.all()

    if not current_user.superadmin:
        roles = [r for r in roles if r.nombre != 'Superadmin']
        if current_user.departamento_id:
            departamentos = [current_user.departamento_asignado]

    form.rol_id.choices = [(r.id, r.nombre) for r in roles]
    form.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + [
        (str(d.id), d.nombre) for d in departamentos
    ]
    if form.validate_on_submit():
        try:
            existing_user_username = Usuario.query.filter_by(username=form.username.data).first()
            existing_user_cedula = Usuario.query.filter_by(cedula=form.cedula.data).first()
            existing_user_email = None
            if form.email.data:
                 existing_user_email = Usuario.query.filter_by(email=form.email.data).first()

            error_occurred = False
            if existing_user_username:
                flash('El nombre de usuario ya existe. Por favor, elige otro.', 'danger')
                form.username.errors.append('Ya existe.')
                error_occurred = True
            if existing_user_cedula:
                flash('La cédula ingresada ya está registrada. Por favor, verifique.', 'danger')
                form.cedula.errors.append('Ya existe.')
                error_occurred = True
            if existing_user_email:
                flash('El correo electrónico ya está registrado. Por favor, usa otro.', 'danger')
                form.email.errors.append('Ya existe.')
                error_occurred = True
            
            if not error_occurred:
                departamento_id_str = form.departamento_id.data
                final_departamento_id = None
                if departamento_id_str and departamento_id_str != '0':
                    try:
                        final_departamento_id = int(departamento_id_str)
                    except ValueError:
                        flash('Valor de departamento no válido. Se asignará "Ninguno".', 'warning')
                        final_departamento_id = None

                rol_asignado = db.session.get(Rol, form.rol_id.data)
                if rol_asignado and rol_asignado.nombre in ['Admin', 'Superadmin'] and not current_user.superadmin:
                    flash('Solo un superadministrador puede asignar los roles Admin o Superadmin.', 'danger')
                    return redirect(url_for('listar_usuarios'))

                superadmin_flag = rol_asignado.nombre == 'Superadmin'

                nuevo_usuario = Usuario(
                    username=form.username.data,
                    cedula=form.cedula.data,
                    nombre_completo=form.nombre_completo.data,
                    email=form.email.data if form.email.data else None,
                    rol_id=form.rol_id.data,
                    departamento_id=final_departamento_id,
                    activo=form.activo.data,
                    superadmin=superadmin_flag
                )
                nuevo_usuario.set_password(form.password.data)
                db.session.add(nuevo_usuario)
                db.session.commit()
                registrar_accion(current_user.id, 'Usuarios', nuevo_usuario.username, 'crear')
                flash(f'Usuario "{nuevo_usuario.username}" creado exitosamente.', 'success')
                return redirect(url_for('listar_usuarios'))
        
        except IntegrityError as e: 
            db.session.rollback()
            app.logger.error(f"Error de integridad al crear usuario (constraint BD): {e}")
            if 'usuario.username' in str(e).lower():
                flash('Error: El nombre de usuario ya existe (constraint).', 'danger')
                if not form.username.errors: form.username.errors.append('Ya existe (constraint).')
            elif 'usuario.cedula' in str(e).lower():
                flash('Error: La cédula ya está registrada (constraint).', 'danger')
                if not form.cedula.errors: form.cedula.errors.append('Ya existe (constraint).')
            elif form.email.data and 'usuario.email' in str(e).lower():
                flash('Error: El correo electrónico ya está registrado (constraint).', 'danger')
                if not form.email.errors: form.email.errors.append('Ya existe (constraint).')
            else:
                flash('Error de integridad al guardar el usuario. Verifique los datos.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado al crear el usuario: {str(e)}', 'danger')
            app.logger.error(f"Error inesperado al crear usuario: {e}", exc_info=True)
            
    return render_template(
        'admin/crear_usuario.html',
        form=form,
        roles=roles,
        departamentos=departamentos,
        title="Crear Nuevo Usuario"
    )


@main.route('/admin/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.superadmin and not current_user.superadmin:
        flash('No puede editar a un superadministrador.', 'danger')
        return redirect(url_for('listar_usuarios'))
    form = EditUserForm(obj=usuario)
    if request.method == 'GET':
        form.departamento_id.data = str(usuario.departamento_id) if usuario.departamento_id else '0'
        form.password.data = ''
        form.confirm_password.data = ''

    if form.validate_on_submit():
        existing_username = Usuario.query.filter(Usuario.username == form.username.data, Usuario.id != usuario.id).first()
        existing_cedula = Usuario.query.filter(Usuario.cedula == form.cedula.data, Usuario.id != usuario.id).first()
        existing_email = None
        if form.email.data:
            existing_email = Usuario.query.filter(Usuario.email == form.email.data, Usuario.id != usuario.id).first()

        error_occurred = False
        if existing_username:
            flash('El nombre de usuario ya existe. Por favor, elige otro.', 'danger')
            form.username.errors.append('Ya existe.')
            error_occurred = True
        if existing_cedula:
            flash('La cédula ingresada ya está registrada. Por favor, verifique.', 'danger')
            form.cedula.errors.append('Ya existe.')
            error_occurred = True
        if existing_email:
            flash('El correo electrónico ya está registrado. Por favor, use otro.', 'danger')
            form.email.errors.append('Ya existe.')
            error_occurred = True

        if not error_occurred:
            try:
                usuario.username = form.username.data
                usuario.cedula = form.cedula.data
                usuario.nombre_completo = form.nombre_completo.data
                usuario.email = form.email.data if form.email.data else None
                if current_user.superadmin:
                    usuario.rol_id = form.rol_id.data
                    nuevo_rol = db.session.get(Rol, form.rol_id.data)
                    usuario.superadmin = nuevo_rol.nombre == 'Superadmin'
                depto_str = form.departamento_id.data
                usuario.departamento_id = int(depto_str) if depto_str and depto_str != '0' else None
                usuario.activo = form.activo.data
                if form.password.data:
                    usuario.set_password(form.password.data)
                    usuario.session_token = None
                db.session.commit()
                registrar_accion(current_user.id, 'Usuarios', usuario.username, 'editar')
                flash(f'Usuario "{usuario.username}" actualizado exitosamente.', 'success')
                return redirect(url_for('listar_usuarios'))
            except IntegrityError as e:
                db.session.rollback()
                flash('Error de integridad al actualizar el usuario.', 'danger')
                app.logger.error(f"Integridad al editar usuario {usuario_id}: {e}")
            except Exception as e:
                db.session.rollback()
                flash(f'Ocurrió un error inesperado al actualizar el usuario: {str(e)}', 'danger')
                app.logger.error(f"Error inesperado al editar usuario {usuario_id}: {e}", exc_info=True)

    roles = Rol.query.all()
    departamentos = Departamento.query.all()
    return render_template('admin/editar_usuario.html', form=form,
                           usuario_id=usuario.id,
                           roles=roles,
                           departamentos=departamentos,
                           title="Editar Usuario")


@main.route('/admin/usuarios/<int:usuario_id>/confirmar_eliminar')
@login_required
@admin_required
def confirmar_eliminar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('No puede eliminar su propio usuario.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    form = ConfirmarEliminarUsuarioForm()
    return render_template('admin/confirmar_eliminar_usuario.html',
                           usuario=usuario,
                           form=form,
                           title=f"Confirmar Eliminación: {usuario.username}")


@main.route('/admin/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
@admin_required
@superadmin_required
def eliminar_usuario_post(usuario_id):
    form = ConfirmarEliminarUsuarioForm()
    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('No puede eliminar su propio usuario.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    if not form.validate_on_submit():
        flash('Petición inválida.', 'danger')
        return redirect(url_for('confirmar_eliminar_usuario', usuario_id=usuario_id))
    try:
        db.session.delete(usuario)
        db.session.commit()
        registrar_accion(current_user.id, 'Usuarios', usuario.username, 'eliminar')
        flash(f'Usuario {usuario.username} eliminado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
        app.logger.error(f"Error al eliminar usuario {usuario_id}: {e}", exc_info=True)
    return redirect(url_for('listar_usuarios'))


@main.route('/admin/limpiar_requisiciones_viejas')
@login_required
@admin_required
def limpiar_requisiciones_viejas_route():
    """Limpia requisiciones finalizadas antiguas."""
    dias = request.args.get('dias', 15, type=int)
    eliminadas = limpiar_requisiciones_viejas(dias, guardar_mensaje=True)
    flash(f'Se eliminaron {eliminadas} requisiciones antiguas.', 'success')
    return redirect(url_for('historial_requisiciones'))
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
    departamentos = Departamento.query.order_by(Departamento.nombre).all()
    form.departamento_nombre.choices = [('', 'Seleccione un departamento...')] + [
        (d.nombre, d.nombre) for d in departamentos
    ]
    if request.method == 'GET':
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
        try:
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Error: El departamento seleccionado no es válido.', 'danger')
                productos_sugerencias = obtener_sugerencias_productos()
                return render_template(
                    'crear_requisicion.html',
                    form=form,
                    departamentos=departamentos,
                    title="Crear Nueva Requisición",
                    unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                    productos_sugerencias=productos_sugerencias,
                )

            nueva_requisicion = Requisicion(
                numero_requisicion='RQ-' + datetime.now().strftime('%Y%m%d%H%M%S%f'),
                nombre_solicitante=form.nombre_solicitante.data,
                cedula_solicitante=form.cedula_solicitante.data,
                correo_solicitante=form.correo_solicitante.data,
                departamento_id=departamento_seleccionado.id,
                prioridad=form.prioridad.data,
                observaciones=form.observaciones.data,
                creador_id=current_user.id,
                estado=ESTADO_INICIAL_REQUISICION
            )
            db.session.add(nueva_requisicion)

            for detalle_form_entry in form.detalles:
                detalle_data = detalle_form_entry.data
                if detalle_data['producto'] and detalle_data['cantidad'] is not None and detalle_data['unidad_medida']:
                    nombre_producto_estandarizado = detalle_data['producto'].strip().title()
                    detalle = DetalleRequisicion(
                        requisicion=nueva_requisicion,
                        producto=nombre_producto_estandarizado,
                        cantidad=detalle_data['cantidad'],
                        unidad_medida=detalle_data['unidad_medida']
                    )
                    db.session.add(detalle)
                    agregar_producto_al_catalogo(nombre_producto_estandarizado)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la requisición: {str(e)}', 'danger')
            app.logger.error(f"Error en crear_requisicion: {e}", exc_info=True)
        else:
            try:
                mensaje = generar_mensaje_correo('Solicitante', nueva_requisicion, nueva_requisicion.estado, "")
                enviar_correo([nueva_requisicion.correo_solicitante], 'Requisición creada', mensaje)

                if nueva_requisicion.estado == ESTADO_INICIAL_REQUISICION:
                    mensaje_almacen = generar_mensaje_correo('Almacén', nueva_requisicion, nueva_requisicion.estado, "")
                    enviar_correos_por_rol('Almacen', 'Nueva requisición pendiente', mensaje_almacen)

                guardar_pdf_requisicion(nueva_requisicion)
            except Exception as e:
                app.logger.error(f"Error tras crear requisición {nueva_requisicion.id}: {e}", exc_info=True)

            flash('¡Requisición creada con éxito! Número: ' + nueva_requisicion.numero_requisicion, 'success')
            return redirect(url_for('requisicion_creada', requisicion_id=nueva_requisicion.id))
    
    productos_sugerencias = obtener_sugerencias_productos()
    return render_template(
        'crear_requisicion.html',
        form=form,
        departamentos=departamentos,
        title="Crear Nueva Requisición",
        unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
        productos_sugerencias=productos_sugerencias,
    )
@main.route('/requisicion/<int:requisicion_id>/creada')
@login_required
def requisicion_creada(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    return render_template('requisicion_creada.html', requisicion=requisicion, title='Requisición Creada')

@main.route('/requisiciones')
@login_required
def listar_requisiciones():
    """Lista las requisiciones visibles para el usuario actual según su rol."""
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    filtro = request.args.get('filtro')

    # Consulta base
    query = Requisicion.query

    if rol == 'Compras':
        # Requisiciones que maneja el departamento de compras
        estados = [
            'Aprobada por Almacén',      # Enviado a Compras
            'Pendiente de Cotizar',

        ]
        query = query.filter(Requisicion.estado.in_(estados))
    elif rol == 'Almacen':
        # Requisiciones gestionadas por almacén
        estados = [
            'Pendiente Revisión Almacén',
            'Aprobada por Almacén'
        ]
        query = query.filter(Requisicion.estado.in_(estados))
    elif rol == 'Solicitante':
        # Un solicitante solo ve las requisiciones que él mismo creó
        query = query.filter_by(creador_id=current_user.id)
    # Cualquier otro rol (Admin u otros) ve todas las requisiciones

    # -- Filtros adicionales provenientes del parámetro "filtro" --
    if filtro == 'sin_revisar' and rol == 'Almacen':
        query = query.filter_by(estado=ESTADO_INICIAL_REQUISICION)
    elif filtro == 'por_cotizar':
        if rol == 'Almacen':
            query = query.filter_by(estado='Aprobada por Almacén')
        elif rol == 'Compras':
            query = query.filter_by(estado='Pendiente de Cotizar')
    elif filtro == 'recien_llegadas' and rol == 'Compras':
        query = query.filter_by(estado='Aprobada por Almacén')
    elif filtro == 'todos':
        pass  # sin filtro adicional

    page = request.args.get('page', 1, type=int)
    requisiciones_paginadas = (
        query.order_by(Requisicion.fecha_creacion.desc())
        .paginate(page=page, per_page=10)
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
    try:
        query = None
        rol_usuario = current_user.rol_asignado.nombre if hasattr(current_user, 'rol_asignado') and current_user.rol_asignado else None
        app.logger.debug(f"Historial Requisiciones - Usuario: {current_user.username}, Rol: {rol_usuario}")

        if rol_usuario == 'Admin':
            query = Requisicion.query # Admin ve todo el historial
        elif rol_usuario == 'Almacen':
            # Almacén ve en su historial las que creó O las que gestionó (pasaron por sus estados)
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([ # Estados que Almacén pudo haber gestionado
                        ESTADO_INICIAL_REQUISICION, 'Aprobada por Almacén',
                        'Surtida desde Almacén', 'Rechazada por Almacén',
                        'Comprada', 'Recibida Parcialmente', 'Recibida Completa', 'Cerrada', 'Cancelada'
                    ])
                )
            )
        elif rol_usuario == 'Compras':
            # Compras ve en su historial las que creó O las que gestionó
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([ # Estados que Compras pudo haber gestionado
                        'Aprobada por Almacén', 'Pendiente de Cotizar', 
                        'Aprobada por Compras', 'En Proceso de Compra', 'Comprada', 
                        'Recibida Parcialmente', 'Recibida Completa', 'Cerrada', 
                        'Rechazada por Compras', 'Cancelada'
                    ])
                )
            )
        else: # Solicitante y otros roles
            if hasattr(current_user, 'departamento_asignado') and current_user.departamento_asignado:
                query = Requisicion.query.filter(
                    db.or_(
                        Requisicion.departamento_id == current_user.departamento_id,
                        Requisicion.creador_id == current_user.id
                    )
                )
            elif hasattr(current_user, 'id'):
                query = Requisicion.query.filter_by(creador_id=current_user.id)

        if query is not None:
            query = query.filter(Requisicion.estado.in_(ESTADOS_HISTORICOS))  # Filtro clave para el historial
            page = request.args.get('page', 1, type=int)
            requisiciones_paginadas = (
                query.order_by(Requisicion.fecha_creacion.desc())
                .paginate(page=page, per_page=10)
            )
        else:
            requisiciones_paginadas = None
            app.logger.warning(
                f"Query para historial de requisiciones fue None para {current_user.username}"
            )
            
    except Exception as e:
        flash(f"Error al cargar el historial de requisiciones: {str(e)}", "danger")
        app.logger.error(
            f"Error en historial_requisiciones para {current_user.username if hasattr(current_user, 'username') else 'desconocido'}: {e}",
            exc_info=True,
        )
        requisiciones_paginadas = None
        
    return render_template(
        'historial_requisiciones.html',
        requisiciones_paginadas=requisiciones_paginadas,
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
        requisicion = Requisicion.query.get(requisicion_id)
    except Exception as e:
        app.logger.error(f"Error al ver requisición: {str(e)}", exc_info=True)
        abort(500)

    if requisicion is None:
        flash('Requisición no encontrada.', 'danger')
        return redirect(url_for('listar_requisiciones'))

    if not all([requisicion.numero_requisicion, requisicion.estado, requisicion.prioridad]):
        flash('La requisición tiene datos incompletos.', 'warning')
    
    if request.method == 'GET':
        form_estado = CambiarEstadoForm(obj=requisicion)
        form_estado.estado.data = requisicion.estado 
    else: 
        form_estado = CambiarEstadoForm()

    opciones_estado_permitidas = []
    rol_actual = current_user.rol_asignado.nombre if current_user.rol_asignado else None

    if rol_actual == 'Admin':
        opciones_estado_permitidas = ESTADOS_REQUISICION
    elif rol_actual == 'Almacen':
        if requisicion.estado == ESTADO_INICIAL_REQUISICION:
            opciones_estado_permitidas = [
                (ESTADO_INICIAL_REQUISICION, ESTADOS_REQUISICION_DICT[ESTADO_INICIAL_REQUISICION]),
                ('Aprobada por Almacén', ESTADOS_REQUISICION_DICT['Aprobada por Almacén']),
                ('Surtida desde Almacén', ESTADOS_REQUISICION_DICT['Surtida desde Almacén']),
                ('Rechazada por Almacén', ESTADOS_REQUISICION_DICT['Rechazada por Almacén'])
            ]
        elif requisicion.estado == 'Comprada':
             opciones_estado_permitidas = [
                (requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado)),
                ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']),
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa'])
            ]
        elif requisicion.estado == 'Recibida Parcialmente':
            opciones_estado_permitidas = [
                (requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado)),
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa'])
            ]
        elif requisicion.estado in ['Aprobada por Almacén', 'Surtida desde Almacén', 'Rechazada por Almacén', 'Recibida Completa', 'Cerrada', 'Cancelada']:
             opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
        else: 
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
    elif rol_actual == 'Compras':
        if requisicion.estado == 'Aprobada por Almacén':
            opciones_estado_permitidas = [
                ('Aprobada por Almacén', ESTADOS_REQUISICION_DICT['Aprobada por Almacén']),
                ('Pendiente de Cotizar', ESTADOS_REQUISICION_DICT['Pendiente de Cotizar']),
                ('Rechazada por Compras', ESTADOS_REQUISICION_DICT['Rechazada por Compras']),
            ]
        elif requisicion.estado == 'Pendiente de Cotizar':
            opciones_estado_permitidas = [
                ('Pendiente de Cotizar', ESTADOS_REQUISICION_DICT['Pendiente de Cotizar']),
                ('Aprobada por Compras', ESTADOS_REQUISICION_DICT['Aprobada por Compras']),
                ('Rechazada por Compras', ESTADOS_REQUISICION_DICT['Rechazada por Compras']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada']),
            ]
        elif requisicion.estado == 'Aprobada por Compras':
            opciones_estado_permitidas = [
                ('Aprobada por Compras', ESTADOS_REQUISICION_DICT['Aprobada por Compras']),
                ('Comprada', ESTADOS_REQUISICION_DICT['Comprada']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada'])
            ]
        elif requisicion.estado == 'En Proceso de Compra':
            opciones_estado_permitidas = [
                ('En Proceso de Compra', ESTADOS_REQUISICION_DICT['En Proceso de Compra']),
                ('Comprada', ESTADOS_REQUISICION_DICT['Comprada']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada'])
            ]
        elif requisicion.estado == 'Comprada':
             opciones_estado_permitidas = [
                ('Comprada', ESTADOS_REQUISICION_DICT['Comprada']),
                # ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']), # Lo cambia Almacén
                # ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']),       # Lo cambia Almacén
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada']) # Compras puede cerrar si ya está comprada (o recibida)
            ]
        elif requisicion.estado == 'Recibida Parcialmente': 
            opciones_estado_permitidas = [
                ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']),
                # ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']), # Lo cambia Almacén
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada'])
            ]
        elif requisicion.estado == 'Recibida Completa': 
            opciones_estado_permitidas = [
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']),
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada'])
            ]
        elif requisicion.estado in ['Rechazada por Compras', 'Cancelada', 'Cerrada']:
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
        else: 
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
    else: 
        opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]

    form_estado.estado.choices = opciones_estado_permitidas
    if not form_estado.estado.choices:
        form_estado.estado.choices = [('N/A', 'No disponible')]

    if request.method == 'POST' and form_estado.submit_estado.data and form_estado.validate_on_submit() :
        if not (current_user.rol_asignado and current_user.rol_asignado.nombre in ['Admin', 'Compras', 'Almacen']):
            flash('No tiene permiso para cambiar el estado de esta requisición.', 'danger')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))

        nuevo_estado = form_estado.estado.data
        if not any(nuevo_estado == choice[0] for choice in opciones_estado_permitidas):
            flash('Intento de cambio de estado no válido o no permitido para su rol/estado actual.', 'danger')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))

        comentario_ingresado_texto = form_estado.comentario_estado.data.strip() if form_estado.comentario_estado.data else None

        if requisicion.estado != nuevo_estado or (comentario_ingresado_texto and comentario_ingresado_texto != requisicion.comentario_estado):
            if nuevo_estado in ['Rechazada por Almacén', 'Rechazada por Compras', 'Cancelada'] and not comentario_ingresado_texto:
                flash('Es altamente recomendable ingresar un motivo al rechazar o cancelar la requisición.', 'warning')

            if cambiar_estado_requisicion(
                requisicion.id, nuevo_estado, current_user, comentario_ingresado_texto
            ):
                flash_message = f'El estado de la requisición {requisicion.numero_requisicion} ha sido actualizado a "{ESTADOS_REQUISICION_DICT.get(nuevo_estado, nuevo_estado)}".'
                if comentario_ingresado_texto:
                    flash_message += " Comentario guardado."
                flash(flash_message, 'success')
            else:
                flash('Error al actualizar el estado.', 'danger')
        else:
            flash('No se realizaron cambios (mismo estado y sin nuevo comentario o el mismo).', 'info')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))

    # Usamos un datetime con zona horaria UTC para evitar errores de comparación
    ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
    editable_dentro_limite_original = False
    if requisicion.fecha_creacion:
        fecha_creacion = requisicion.fecha_creacion.replace(tzinfo=None)
        if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            editable_dentro_limite_original = True

    puede_editar = (
        requisicion.estado == ESTADO_INICIAL_REQUISICION and
        editable_dentro_limite_original and
        requisicion.creador_id == current_user.id
    ) or (
        current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    )

    puede_eliminar = (editable_dentro_limite_original and requisicion.creador_id == current_user.id) or \
                     (current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin')

    puede_cambiar_estado = (
        current_user.rol_asignado
        and current_user.rol_asignado.nombre in ['Admin', 'Compras', 'Almacen']
        and len(opciones_estado_permitidas) > 1
    ) or (
        current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    )

    creador_usuario = getattr(requisicion, 'creador', None)
    departamento_asignado = getattr(requisicion, 'departamento_obj', None)
    comentario_estado_texto = getattr(requisicion, 'comentario_estado', None)

    return render_template(
        'ver_requisicion.html',
        requisicion=requisicion,
        creador=creador_usuario,
        departamento=departamento_asignado,
        comentario_estado=comentario_estado_texto,
        title=f"Detalle Requisición {requisicion.numero_requisicion}",
        puede_editar=puede_editar,
        puede_eliminar=puede_eliminar,
        editable_dentro_limite_original=editable_dentro_limite_original,
        tiempo_limite_minutos=int(
            TIEMPO_LIMITE_EDICION_REQUISICION.total_seconds() / 60
        ),
        form_estado=form_estado,
        puede_cambiar_estado=puede_cambiar_estado,
    )
@main.route('/requisicion/<int:requisicion_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_requisicion(requisicion_id):
    try:
        requisicion_a_editar = Requisicion.query.get(requisicion_id)
    except Exception as e:
        app.logger.error(f"Error al editar requisición: {str(e)}", exc_info=True)
        abort(500)

    if requisicion_a_editar is None:
        flash('Requisición no encontrada.', 'danger')
        return redirect(url_for('listar_requisiciones'))

    if not all([requisicion_a_editar.numero_requisicion, requisicion_a_editar.estado, requisicion_a_editar.prioridad]):
        flash('La requisición tiene datos incompletos.', 'warning')
    es_creador = requisicion_a_editar.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
    dentro_del_limite = False
    if requisicion_a_editar.fecha_creacion:
        fecha_creacion = requisicion_a_editar.fecha_creacion.replace(tzinfo=None)
        if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    estado_editable = requisicion_a_editar.estado == ESTADO_INICIAL_REQUISICION
    if not ((es_creador and dentro_del_limite and estado_editable) or es_admin):
        flash('No tiene permiso para editar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_editar.id))

    form = RequisicionForm(obj=requisicion_a_editar if request.method == 'GET' else None)
    departamentos = Departamento.query.order_by(Departamento.nombre).all()
    form.departamento_nombre.choices = [('', 'Seleccione un departamento...')] + [
        (d.nombre, d.nombre) for d in departamentos
    ]
    if request.method == 'GET':
        if getattr(requisicion_a_editar, 'departamento_obj', None):
            form.departamento_nombre.data = requisicion_a_editar.departamento_obj.nombre
        while len(form.detalles.entries) > 0:
            form.detalles.pop_entry()
        detalles_iterables = getattr(requisicion_a_editar, 'detalles', [])
        if detalles_iterables:
            for detalle_db in detalles_iterables:
                form.detalles.append_entry(detalle_db)
        else:
            form.detalles.append_entry()

    if form.validate_on_submit():
        try:
            requisicion_a_editar.nombre_solicitante = form.nombre_solicitante.data
            requisicion_a_editar.cedula_solicitante = form.cedula_solicitante.data
            requisicion_a_editar.correo_solicitante = form.correo_solicitante.data
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Departamento seleccionado no válido.', 'danger')
                productos_sugerencias = obtener_sugerencias_productos()
                return render_template('editar_requisicion.html', form=form, title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}", requisicion_id=requisicion_a_editar.id, unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS, productos_sugerencias=productos_sugerencias)

            requisicion_a_editar.departamento_id = departamento_seleccionado.id
            requisicion_a_editar.prioridad = form.prioridad.data
            requisicion_a_editar.observaciones = form.observaciones.data

            for detalle_existente in list(requisicion_a_editar.detalles):
                db.session.delete(detalle_existente)
            db.session.flush()

            for detalle_form_data in form.detalles.data:
                producto = detalle_form_data.get('producto')
                cantidad = detalle_form_data.get('cantidad')
                unidad_medida = detalle_form_data.get('unidad_medida')
                if producto and cantidad is not None and unidad_medida:
                    nombre_producto_estandarizado = producto.strip().title()
                    nuevo_detalle = DetalleRequisicion(
                        requisicion_id=requisicion_a_editar.id,
                        producto=nombre_producto_estandarizado,
                        cantidad=cantidad,
                        unidad_medida=unidad_medida
                    )
                    db.session.add(nuevo_detalle)
                    agregar_producto_al_catalogo(nombre_producto_estandarizado)
            db.session.commit()
            flash(f'Requisición {requisicion_a_editar.numero_requisicion} actualizada con éxito.', 'success')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_editar.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error al editar requisición: {str(e)}", exc_info=True)
            abort(500)
    
    productos_sugerencias = obtener_sugerencias_productos()
    return render_template('editar_requisicion.html', form=form, title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}",
                           requisicion_id=requisicion_a_editar.id,
                           unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                           productos_sugerencias=productos_sugerencias)
@main.route('/requisicion/<int:requisicion_id>/confirmar_eliminar')
@login_required
def confirmar_eliminar_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    es_creador = requisicion.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
    dentro_del_limite = False
    if requisicion.fecha_creacion:
        fecha_creacion = requisicion.fecha_creacion.replace(tzinfo=None)
        if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    if not ((es_creador and dentro_del_limite) or es_admin):
        flash('No tiene permiso para eliminar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))
    form = ConfirmarEliminarForm()
    return render_template('confirmar_eliminar_requisicion.html',
                           requisicion=requisicion,
                           form=form,
                           title=f"Confirmar Eliminación: {requisicion.numero_requisicion}")
@main.route('/requisicion/<int:requisicion_id>/eliminar', methods=['POST'])
@login_required
def eliminar_requisicion_post(requisicion_id):
    form = ConfirmarEliminarForm()
    requisicion_a_eliminar = Requisicion.query.get_or_404(requisicion_id)
    es_creador = requisicion_a_eliminar.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
    dentro_del_limite = False
    if requisicion_a_eliminar.fecha_creacion:
        fecha_creacion = requisicion_a_eliminar.fecha_creacion.replace(tzinfo=None)
        if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    if not ((es_creador and dentro_del_limite) or es_admin):
        flash('No tiene permiso para eliminar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_eliminar.id))
    if not form.validate_on_submit():
        flash('Petición inválida.', 'danger')
        return redirect(url_for('confirmar_eliminar_requisicion', requisicion_id=requisicion_id))
    try:
        db.session.delete(requisicion_a_eliminar)
        db.session.commit()
        registrar_accion(current_user.id, 'Requisiciones', requisicion_a_eliminar.numero_requisicion, 'eliminar')
        flash(f'Requisicion {requisicion_a_eliminar.numero_requisicion} eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la requisición: {str(e)}', 'danger')
        app.logger.error(f"Error al eliminar requisicion {requisicion_id}: {e}", exc_info=True)
    return redirect(url_for('listar_requisiciones'))
@main.route('/requisiciones/pendientes_cotizar')
@login_required
def listar_pendientes_cotizar():
    """Lista las requisiciones cuyo estado sea 'Pendiente de Cotizar'."""
    rol_usuario = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol_usuario == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Pendiente de Cotizar').all()
    else:
        requisiciones = Requisicion.query.filter_by(creador_id=current_user.id, estado='Pendiente de Cotizar').all()
    return render_template('listar_pendientes_cotizar.html',
                           requisiciones=requisiciones,
                           title="Pendientes de Cotizar",
                           vista_actual='pendientes_cotizar')
@main.route('/requisiciones/cotizadas')
@login_required
def listar_cotizadas():
    """Lista las requisiciones cuyo estado sea 'Cotizada'."""
    rol_usuario = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol_usuario == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Cotizada').all()
    else:
        requisiciones = Requisicion.query.filter_by(creador_id=current_user.id, estado='Cotizada').all()
    return render_template('listar_cotizadas.html',
                           requisiciones=requisiciones,
                           title="Cotizadas",
                           vista_actual='cotizadas')
@main.route('/requisiciones/estado/<path:estado>')
@login_required
def listar_por_estado(estado):
    """Lista todas las requisiciones cuyo estado coincida con <estado>."""
    # 1️⃣ Validar que el estado exista en tu lista de estados:
    if estado not in ESTADOS_REQUISICION_DICT:
        abort(404)

    # 2️⃣ Construir la consulta:
    qs = Requisicion.query.filter_by(estado=estado)
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol != 'Admin':
        # usuarios distintos de Admin solo ven sus propias requisiciones
        qs = qs.filter_by(creador_id=current_user.id)

    # 3️⃣ Renderizar plantilla genérica con paginación
    page = request.args.get('page', 1, type=int)
    requisiciones_paginadas = (
        qs.order_by(Requisicion.fecha_creacion.desc())
        .paginate(page=page, per_page=10)
    )
    return render_template(
        'listar_por_estado.html',
        requisiciones_paginadas=requisiciones_paginadas,
        title=ESTADOS_REQUISICION_DICT[estado],
        estado=estado,
        vista_actual='estado'
    )
@main.route('/requisicion/<int:requisicion_id>/imprimir')
@login_required
def imprimir_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    pdf_data = generar_pdf_requisicion(requisicion)
    nombre = f"requisicion_{requisicion.numero_requisicion}.pdf"
    resp = make_response(pdf_data)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={nombre}'
    return resp
@main.app_errorhandler(500)
def internal_server_error(error):
    """Maneja errores 500 mostrando una página amigable y registrando el error."""
    app.logger.error(f"Error 500: {error}", exc_info=True)
    return render_template('500.html', title='Error Interno'), 500
