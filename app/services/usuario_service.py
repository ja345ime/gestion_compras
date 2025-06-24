# app/services/usuario_service.py

"""
Este módulo contendrá la lógica de negocio relacionada con los usuarios.
"""

from flask import current_app, flash
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Usuario, Rol, Departamento
from app.utils import registrar_accion
# Los formularios UserForm, EditUserForm se manejarán en las rutas.

class UsuarioService:

    def listar_usuarios_paginados(self, page=1, per_page=10, error_out=False):
        """Devuelve una lista paginada de usuarios."""
        return db.session.query(Usuario).order_by(Usuario.username).paginate(
            page=page, per_page=per_page, error_out=error_out
        )

    def obtener_usuario_por_id(self, usuario_id):
        """Obtiene un usuario por su ID, o devuelve 404 si no se encuentra."""
        return Usuario.query.get_or_404(usuario_id)

    def crear_nuevo_usuario(self, form, current_user):
        """
        Crea un nuevo usuario.
        Devuelve el usuario creado o None si hay error.
        """
        try:
            # Validaciones de existencia (username, cédula, email)
            existing_user_username = Usuario.query.filter_by(username=form.username.data).first()
            existing_user_cedula = Usuario.query.filter_by(cedula=form.cedula.data).first()
            existing_user_email = None
            if form.email.data:
                 existing_user_email = Usuario.query.filter_by(email=form.email.data).first()

            error_messages = []
            if existing_user_username:
                error_messages.append('El nombre de usuario ya existe.')
                form.username.errors.append('Ya existe.')
            if existing_user_cedula:
                error_messages.append('La cédula ingresada ya está registrada.')
                form.cedula.errors.append('Ya existe.')
            if existing_user_email:
                error_messages.append('El correo electrónico ya está registrado.')
                form.email.errors.append('Ya existe.')

            if error_messages:
                flash(' '.join(error_messages), 'danger')
                return None

            # Validación de departamento
            departamento_id_str = form.departamento_id.data
            final_departamento_id = None
            if departamento_id_str and departamento_id_str != '0':
                try:
                    final_departamento_id = int(departamento_id_str)
                    # Opcional: verificar que el departamento exista si no se confía en el SelectField
                    # if not Departamento.query.get(final_departamento_id):
                    #     flash('Departamento seleccionado no válido.', 'warning')
                    #     final_departamento_id = None # O manejar error
                except ValueError:
                    flash('Valor de departamento no válido. Se asignará "Ninguno".', 'warning')
                    final_departamento_id = None

            # Validación de rol (permiso para asignar ciertos roles)
            rol_asignado = db.session.get(Rol, form.rol_id.data)
            if not rol_asignado: # Debería ser prevenido por DataRequired en el form.rol_id
                flash('Rol seleccionado no válido.', 'danger')
                return None

            if rol_asignado.nombre in ['Admin', 'Superadmin'] and not current_user.superadmin:
                flash('Solo un superadministrador puede asignar los roles Admin o Superadmin.', 'danger')
                return None # O redirigir desde la ruta

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
            return nuevo_usuario

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Error de integridad al crear usuario (constraint BD): {e}")
            # Estos errores son más específicos de la BD, podrían ser redundantes si las validaciones previas funcionan
            if 'usuario.username' in str(e).lower() and not form.username.errors:
                flash('Error BD: El nombre de usuario ya existe.', 'danger')
                form.username.errors.append('Ya existe (constraint BD).')
            elif 'usuario.cedula' in str(e).lower() and not form.cedula.errors:
                flash('Error BD: La cédula ya está registrada.', 'danger')
                form.cedula.errors.append('Ya existe (constraint BD).')
            elif form.email.data and 'usuario.email' in str(e).lower() and not form.email.errors:
                flash('Error BD: El correo electrónico ya está registrado.', 'danger')
                form.email.errors.append('Ya existe (constraint BD).')
            else:
                flash('Error de integridad de base de datos al guardar el usuario.', 'danger')
            return None
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado al crear el usuario: {str(e)}', 'danger')
            current_app.logger.error(f"Error inesperado al crear usuario: {e}", exc_info=True)
            return None

    def actualizar_usuario(self, usuario_id, form, current_user):
        """
        Actualiza un usuario existente.
        Devuelve el usuario actualizado o None si hay error.
        """
        usuario = self.obtener_usuario_por_id(usuario_id) # get_or_404
        if not usuario: return None # No debería ocurrir si se usa get_or_404

        if usuario.superadmin and not current_user.superadmin:
            flash('No puede editar a un superadministrador.', 'danger')
            return None

        # Validaciones de unicidad para campos que cambian
        if usuario.username != form.username.data:
            existing_username = Usuario.query.filter(Usuario.username == form.username.data, Usuario.id != usuario.id).first()
            if existing_username:
                flash('El nombre de usuario ya existe. Por favor, elige otro.', 'danger')
                form.username.errors.append('Ya existe.')
                return None

        if usuario.cedula != form.cedula.data:
            existing_cedula = Usuario.query.filter(Usuario.cedula == form.cedula.data, Usuario.id != usuario.id).first()
            if existing_cedula:
                flash('La cédula ingresada ya está registrada. Por favor, verifique.', 'danger')
                form.cedula.errors.append('Ya existe.')
                return None

        if form.email.data and usuario.email != form.email.data:
            existing_email = Usuario.query.filter(Usuario.email == form.email.data, Usuario.id != usuario.id).first()
            if existing_email:
                flash('El correo electrónico ya está registrado. Por favor, use otro.', 'danger')
                form.email.errors.append('Ya existe.')
                return None

        try:
            usuario.username = form.username.data
            usuario.cedula = form.cedula.data
            usuario.nombre_completo = form.nombre_completo.data
            usuario.email = form.email.data if form.email.data else None

            if current_user.superadmin: # Solo superadmin puede cambiar rol
                nuevo_rol_id = form.rol_id.data
                if usuario.rol_id != nuevo_rol_id:
                    nuevo_rol_obj = db.session.get(Rol, nuevo_rol_id)
                    if not nuevo_rol_obj:
                        flash("Rol seleccionado no válido.", "danger")
                        return None
                    # No permitir que un Superadmin se quite a sí mismo el rol de Superadmin si es el único
                    if usuario.id == current_user.id and usuario.superadmin and nuevo_rol_obj.nombre != 'Superadmin':
                        num_superadmins = Usuario.query.filter_by(superadmin=True).count()
                        if num_superadmins <= 1:
                            flash('No puede eliminarse como el único Superadmin.', 'danger')
                            return None
                    usuario.rol_id = nuevo_rol_id
                    usuario.superadmin = nuevo_rol_obj.nombre == 'Superadmin'

            # Departamento (asumiendo que un admin puede cambiarlo si tiene permiso sobre el usuario)
            depto_str = form.departamento_id.data
            usuario.departamento_id = int(depto_str) if depto_str and depto_str != '0' else None

            # Activo
            if usuario.id == current_user.id and not form.activo.data: # No permitirse desactivarse a sí mismo
                 flash('No puede desactivar su propia cuenta.', 'danger')
                 form.activo.data = True # Revertir
                 #return None # O simplemente no cambiar y continuar

            # No permitir desactivar al último superadmin activo
            if usuario.superadmin and not form.activo.data:
                active_superadmins = Usuario.query.filter_by(superadmin=True, activo=True).count()
                if active_superadmins <=1 and usuario.activo: # Si este es el último que estaba activo
                    flash('No se puede desactivar al último Superadmin activo.', 'danger')
                    form.activo.data = True # Revertir

            usuario.activo = form.activo.data

            if form.password.data: # Si se proveyó una nueva contraseña
                usuario.set_password(form.password.data)
                usuario.session_token = None # Forzar nuevo login si cambia contraseña

            db.session.commit()
            registrar_accion(current_user.id, 'Usuarios', usuario.username, 'editar')
            flash(f'Usuario "{usuario.username}" actualizado exitosamente.', 'success')
            return usuario

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Error de integridad al editar usuario {usuario_id}: {e}")
            # Similar al crear, manejar errores de constraint de BD
            if 'usuario.username' in str(e).lower() and not form.username.errors:
                 flash('Error BD: El nombre de usuario ya existe.', 'danger')
            elif 'usuario.cedula' in str(e).lower() and not form.cedula.errors:
                 flash('Error BD: La cédula ya está registrada.', 'danger')
            elif form.email.data and 'usuario.email' in str(e).lower() and not form.email.errors:
                 flash('Error BD: El correo electrónico ya está registrado.', 'danger')
            else:
                flash('Error de integridad de base de datos al actualizar el usuario.', 'danger')
            return None
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado al actualizar el usuario: {str(e)}', 'danger')
            current_app.logger.error(f"Error inesperado al editar usuario {usuario_id}: {e}", exc_info=True)
            return None

    def eliminar_usuario(self, usuario_id, current_user):
        """
        Elimina un usuario. Solo Superadmin puede hacerlo.
        Devuelve True si fue exitoso, False en caso contrario.
        """
        usuario = self.obtener_usuario_por_id(usuario_id)
        if not usuario: return False

        if not current_user.superadmin: # Doble chequeo de permiso
            flash('Solo un superadministrador puede eliminar usuarios.', 'danger')
            return False

        if usuario.id == current_user.id:
            flash('No puede eliminar su propio usuario.', 'danger')
            return False

        # Prevenir eliminación del último Superadmin
        if usuario.superadmin:
            num_superadmins = Usuario.query.filter_by(superadmin=True).count()
            if num_superadmins <= 1:
                flash('No se puede eliminar al único Superadmin del sistema.', 'danger')
                return False

        try:
            username_eliminado = usuario.username
            db.session.delete(usuario)
            db.session.commit()
            registrar_accion(current_user.id, 'Usuarios', username_eliminado, 'eliminar')
            flash(f'Usuario {username_eliminado} eliminado con éxito.', 'success')
            return True
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
            current_app.logger.error(f"Error al eliminar usuario {usuario_id}: {e}", exc_info=True)
            return False

    def get_roles_para_formulario(self, current_user):
        """Obtiene los roles que el current_user puede asignar."""
        if current_user.superadmin:
            return Rol.query.order_by(Rol.nombre).all()
        else: # Admin normal no puede asignar rol Superadmin
            return Rol.query.filter(Rol.nombre != 'Superadmin').order_by(Rol.nombre).all()

    def get_departamentos_para_formulario(self, current_user):
        """Obtiene los departamentos que el current_user puede asignar."""
        # Si un Admin está restringido a su departamento, solo debería poder asignar ese.
        # Esta lógica podría necesitar ser más granular si los Admin tienen restricciones.
        # Por ahora, si es superadmin o admin sin depto asignado, ve todos.
        # Si es admin CON depto asignado, ¿debería estar restringido? Asumamos que sí para crear/editar.
        if current_user.superadmin or not current_user.departamento_id:
            return Departamento.query.order_by(Departamento.nombre).all()
        else: # Admin con departamento asignado
            return [current_user.departamento_asignado] if current_user.departamento_asignado else []


usuario_service = UsuarioService()
