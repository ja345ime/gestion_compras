from flask import current_app as app
from flask import Blueprint, render_template, flash, redirect, url_for, request, abort, make_response, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
import pytz
from sqlalchemy.exc import IntegrityError

from . import db, DURACION_SESION
# Requisition constants are no longer directly used here
# from .requisiciones.constants import (...)
from .utils import (
    registrar_intento,
    exceso_intentos,
    admin_required,
    superadmin_required,
    # agregar_producto_al_catalogo, # Moved
    # obtener_sugerencias_productos, # Moved
    # enviar_correo, # Potentially moved if only used by req routes
    # enviar_correos_por_rol, # Potentially moved
    # generar_mensaje_correo, # Potentially moved
    # cambiar_estado_requisicion, # Moved
    # guardar_pdf_requisicion, # Moved
    # limpiar_requisiciones_viejas, # Moved (the function itself, route was also moved)
    # generar_pdf_requisicion, # Moved
    registrar_accion, # Keep if used by remaining routes (e.g., user management)
)

from .models import (
    # Requisicion, # Moved (mostly)
    # DetalleRequisicion, # Moved
    # ProductoCatalogo, # Moved
    AdminVirtual,
    AuditoriaAcciones, # Keep if used by dashboard or other main routes
    Requisicion # Keep for Dashboard and Index
)

from .forms import (
    LoginForm,
    UserForm,
    EditUserForm,
    ConfirmarEliminarUsuarioForm,
)
# Requisition forms are no longer imported here
# from .requisiciones.forms import (...)

main = Blueprint('main', __name__)
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
    from .models import Usuario

    page = request.args.get('page', 1, type=int)
    per_page = 10
    usuarios_paginados = db.session.query(Usuario).order_by(Usuario.username).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/listar_usuarios.html', usuarios_paginados=usuarios_paginados, title="Gestión de Usuarios")

@main.route('/admin/usuarios/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def crear_usuario():
    """Permite a un administrador crear nuevos usuarios."""
    from .models import Rol, Usuario, Departamento
    form = UserForm()
    all_roles = Rol.query.order_by(Rol.nombre).all()
    all_departamentos = Departamento.query.order_by(Departamento.nombre).all()

    if current_user.superadmin:
        roles_for_form = all_roles
        departamentos_for_form = all_departamentos
    else: # current_user is Admin (not Super Admin)
        roles_for_form = [r for r in all_roles if r.nombre not in ['Admin', 'Super Admin']]
        if current_user.departamento_id: # Admin might be restricted to their department
            departamentos_for_form = [current_user.departamento_asignado] if current_user.departamento_asignado else [] # Ensure it's a list
            # If admin is not assigned a department, can they assign any? Or none?
            # For now, let's assume they can see all departments if not restricted to one.
            # This part of departments was not in the requirements, keeping original logic if admin has dept.
        else:
            departamentos_for_form = all_departamentos


    form.rol_id.choices = [(r.id, r.nombre) for r in roles_for_form]
    # Populate form.departamento_id.choices based on departamentos_for_form
    # The original code filtered `departamentos` variable, then used it for choices.
    # Let's ensure `departamentos` (used in template context) and `form.departamento_id.choices` are consistent.
    # The original code for departments for non-superadmin:
    # if current_user.departamento_id:
    # departamentos = [current_user.departamento_asignado]
    # This seems to be about restricting which departments an Admin can assign a user to,
    # not directly related to Super Admin role restrictions. I will keep this department logic as is for now.
    # The variable `departamentos` is passed to the template.
    # The `form.departamento_id.choices` should be based on `departamentos_for_form` if that's intended.
    # Original: form.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + [(str(d.id), d.nombre) for d in departamentos]
    # `departamentos` in this line refers to the filtered list if user is not SA and has a dept.

    _departments_for_choices = all_departamentos # Default to all
    if not current_user.superadmin and current_user.departamento_id and current_user.departamento_asignado:
        _departments_for_choices = [current_user.departamento_asignado]

    form.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + [
        (str(d.id), d.nombre) for d in _departments_for_choices
    ]
    # The template context `departamentos` should be `all_departamentos` or the filtered list.
    # The variable passed to render_template as `departamentos` is `departamentos`. Let's align.
    # This is confusing. Let's simplify the `departamentos` variable for the template.
    # The critical part is `form.rol_id.choices`.

    # For template context, pass `all_departamentos` or the filtered list.
    # Original code passes `departamentos` which is `all_departamentos` or `[current_user.departamento_asignado]`
    # This seems fine.

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
                # Security check: was this role part of the allowed choices?
                # roles_for_form was used to set form.rol_id.choices
                allowed_role_ids = [r.id for r in roles_for_form]
                if not rol_asignado or rol_asignado.id not in allowed_role_ids:
                    flash('Rol seleccionado no válido o no permitido.', 'danger')
                    error_occurred = True
                # Explicit check for Admin/Super Admin assignment by non-SA
                elif rol_asignado.nombre in ['Admin', 'Super Admin'] and not current_user.superadmin:
                    flash('Solo un Super Admin puede asignar los roles "Admin" o "Super Admin".', 'danger')
                    error_occurred = True

            # Proceed only if no errors regarding roles or other user data
            if not error_occurred:
                # This 'superadmin_flag' will determine the boolean field on the User model
                superadmin_flag = rol_asignado.nombre == 'Super Admin' # Use space "Super Admin"

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
                return redirect(url_for('main.listar_usuarios'))
        
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
        roles=all_roles, # Use all_roles for template context if needed for display
        departamentos=all_departamentos, # Use all_departamentos for template context
        title="Crear Nuevo Usuario"
    )


@main.route('/admin/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    from .models import Usuario, Rol, Departamento

    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.superadmin and not current_user.superadmin:
        flash('No puede editar a un superadministrador.', 'danger')
        return redirect(url_for('main.listar_usuarios'))
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
                if current_user.superadmin: # Only Super Admin can change the role
                    nuevo_rol_id = form.rol_id.data
                    # Check if rol_id is actually changing, and if new role is valid
                    if usuario.rol_id != nuevo_rol_id:
                        nuevo_rol_obj = db.session.get(Rol, nuevo_rol_id)
                        if nuevo_rol_obj:
                            usuario.rol_id = nuevo_rol_obj.id
                            usuario.superadmin = (nuevo_rol_obj.nombre == 'Super Admin') # Use space
                        else:
                            # This case should ideally be caught by form validation if choices were restricted
                            flash("Rol seleccionado para cambio no es válido.", "danger")
                            # Decide if this is a hard error or just ignore role change
                            # For now, let's assume form validation or dropdown handles valid choices
                            # and if it gets here with an invalid new_rol_id, it's an issue.
                            # However, to prevent crash, we might just not change the role.
                            # Sticking to original logic: if SA, they can change it.
                            # The form should provide valid rol_ids.
                            pass # Or log an error
                    # If rol_id is not changing, but SA is editing, ensure superadmin flag is consistent if somehow it diverged.
                    # This is unlikely if only SA can change roles.
                    elif usuario.rol_asignado.nombre == 'Super Admin' and not usuario.superadmin:
                         usuario.superadmin = True
                    elif usuario.rol_asignado.nombre != 'Super Admin' and usuario.superadmin:
                         usuario.superadmin = False


                depto_str = form.departamento_id.data
                usuario.departamento_id = int(depto_str) if depto_str and depto_str != '0' else None
                usuario.activo = form.activo.data
                if form.password.data:
                    usuario.set_password(form.password.data)
                    usuario.session_token = None
                db.session.commit()
                registrar_accion(current_user.id, 'Usuarios', usuario.username, 'editar')
                flash(f'Usuario "{usuario.username}" actualizado exitosamente.', 'success')
                return redirect(url_for('main.listar_usuarios'))
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
    from .models import Usuario

    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('No puede eliminar su propio usuario.', 'danger')
        return redirect(url_for('main.editar_usuario', usuario_id=usuario_id))
    form = ConfirmarEliminarUsuarioForm()
    return render_template('admin/confirmar_eliminar_usuario.html',
                           usuario=usuario,
                           form=form,
                           title=f"Confirmar Eliminación: {usuario.username}")


@main.route('/admin/usuarios/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
@admin_required # Keep basic admin requirement
# @superadmin_required # Remove this, add logic inside
def eliminar_usuario_post(usuario_id):
    from .models import Usuario

    form = ConfirmarEliminarUsuarioForm() # For CSRF token validation primarily
    usuario_a_eliminar = Usuario.query.get_or_404(usuario_id)

    if usuario_a_eliminar.id == current_user.id:
        flash('No puede eliminar su propio usuario.', 'danger')
        return redirect(url_for('main.listar_usuarios')) # Or main.editar_usuario

    # Permission check:
    # Only Super Admin can delete Super Admins or Admins.
    # Admin can delete users with other roles.
    is_target_sa_or_admin = usuario_a_eliminar.superadmin or \
                            (usuario_a_eliminar.rol_asignado and usuario_a_eliminar.rol_asignado.nombre == 'Admin')

    if is_target_sa_or_admin and not current_user.superadmin:
        if usuario_a_eliminar.superadmin:
            flash('Solo un Super Admin puede eliminar a otro Super Admin.', 'danger')
        else: # Target is Admin
            flash('Solo un Super Admin puede eliminar a un Admin.', 'danger')
        return redirect(url_for('main.listar_usuarios'))

    if not form.validate_on_submit(): # Check CSRF etc. after permission checks
        flash('Petición inválida.', 'danger')
        return redirect(url_for('main.confirmar_eliminar_usuario', usuario_id=usuario_id))

    try:
        # Store username before deleting, in case it's needed and object becomes inaccessible
        username_eliminado = usuario_a_eliminar.username
        db.session.delete(usuario_a_eliminar)
        db.session.commit()
        registrar_accion(current_user.id, 'Usuarios', username_eliminado, 'eliminar')
        flash(f'Usuario {username_eliminado} eliminado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
        app.logger.error(f"Error al eliminar usuario {usuario_id}: {e}", exc_info=True)
    return redirect(url_for('main.listar_usuarios'))


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
@main.app_errorhandler(500)
def internal_server_error(error):
    """Maneja errores 500 mostrando una página amigable y registrando el error."""
    app.logger.error(f"Error 500: {error}", exc_info=True)
    return render_template('500.html', title='Error Interno'), 500
