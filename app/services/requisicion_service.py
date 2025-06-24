# app/services/requisicion_service.py

"""
Este módulo contendrá la lógica de negocio relacionada con las requisiciones.
"""

from flask import current_app, flash, abort
from datetime import datetime
import pytz

from app import db, ESTADO_INICIAL_REQUISICION, ESTADOS_REQUISICION, ESTADOS_REQUISICION_DICT, ESTADOS_HISTORICOS, TIEMPO_LIMITE_EDICION_REQUISICION
from app.models import Requisicion, DetalleRequisicion, Departamento
from app.utils import (
    agregar_producto_al_catalogo,
    enviar_correo,
    enviar_correos_por_rol,
    generar_mensaje_correo,
    # cambiar_estado_requisicion as util_cambiar_estado_requisicion, # Se integra la lógica aquí
    guardar_pdf_requisicion, # Podría integrarse o llamarse desde aquí si se genera PDF en el servicio
    registrar_accion,
    # limpiar_requisiciones_viejas as util_limpiar_requisiciones_viejas # Se integra la lógica aquí
    subir_pdf_a_drive, # Necesario para la lógica integrada
    generar_pdf_requisicion as util_generar_pdf_requisicion, # Necesario para la lógica integrada
)
import tempfile # Necesario para la lógica integrada
import os # Necesario para la lógica integrada
from datetime import timedelta # Necesario para la lógica integrada

# Los formularios (RequisicionForm, CambiarEstadoForm, ConfirmarEliminarForm) se manejarán en las rutas
# y los datos validados se pasarán a los métodos del servicio.


class RequisicionService:

    def crear_nueva_requisicion(self, form, current_user_id):
        """
        Crea una nueva requisición con sus detalles.
        Devuelve la nueva requisición creada o None si hay error.
        """
        try:
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Error: El departamento seleccionado no es válido.', 'danger')
                return None

            nueva_requisicion = Requisicion(
                numero_requisicion='RQ-' + datetime.now().strftime('%Y%m%d%H%M%S%f'),
                nombre_solicitante=form.nombre_solicitante.data,
                cedula_solicitante=form.cedula_solicitante.data,
                correo_solicitante=form.correo_solicitante.data,
                departamento_id=departamento_seleccionado.id,
                prioridad=form.prioridad.data,
                observaciones=form.observaciones.data,
                creador_id=current_user_id,
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

            # Notificaciones y PDF post-commit
            try:
                mensaje = generar_mensaje_correo('Solicitante', nueva_requisicion, nueva_requisicion.estado, "")
                enviar_correo([nueva_requisicion.correo_solicitante], 'Requisición creada', mensaje)

                if nueva_requisicion.estado == ESTADO_INICIAL_REQUISICION:
                    mensaje_almacen = generar_mensaje_correo('Almacén', nueva_requisicion, nueva_requisicion.estado, "")
                    enviar_correos_por_rol('Almacen', 'Nueva requisición pendiente', mensaje_almacen)

                guardar_pdf_requisicion(nueva_requisicion)
            except Exception as e_notify:
                current_app.logger.error(f"Error en notificaciones/PDF para requisición {nueva_requisicion.id}: {e_notify}", exc_info=True)
                # No se hace rollback aquí ya que la requisición ya fue creada. Se podría loguear o encolar para reintento.

            flash(f'¡Requisición creada con éxito! Número: {nueva_requisicion.numero_requisicion}', 'success')
            return nueva_requisicion
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear la requisición en servicio: {e}", exc_info=True)
            flash(f'Error al crear la requisición: {str(e)}', 'danger')
            return None

    def obtener_requisicion_por_id(self, requisicion_id, check_incomplete=True):
        """Obtiene una requisición por su ID. Aborta con 404 si no se encuentra."""
        requisicion = Requisicion.query.get(requisicion_id)
        if requisicion is None:
            flash('Requisición no encontrada.', 'danger')
            return None # La ruta manejará el redirect o abort(404)

        if check_incomplete and not all([requisicion.numero_requisicion, requisicion.estado, requisicion.prioridad]):
            flash('La requisición tiene datos incompletos.', 'warning')
        return requisicion

    def actualizar_requisicion(self, requisicion_id, form, current_user):
        """Actualiza una requisición existente."""
        requisicion_a_editar = self.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
        if not requisicion_a_editar:
            return False # Ya se mostró flash en obtener_requisicion_por_id

        # Lógica de permisos (ya validada en la ruta antes de llamar al servicio)
        # es_creador = requisicion_a_editar.creador_id == current_user.id
        # es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
        # ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
        # dentro_del_limite = False
        # if requisicion_a_editar.fecha_creacion:
        #     fecha_creacion = requisicion_a_editar.fecha_creacion.replace(tzinfo=None)
        #     if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
        #         dentro_del_limite = True
        # estado_editable = requisicion_a_editar.estado == ESTADO_INICIAL_REQUISICION
        # if not ((es_creador and dentro_del_limite and estado_editable) or es_admin):
        #     flash('No tiene permiso para editar esta requisición o el tiempo límite ha expirado.', 'danger')
        #     return False

        try:
            requisicion_a_editar.nombre_solicitante = form.nombre_solicitante.data
            requisicion_a_editar.cedula_solicitante = form.cedula_solicitante.data
            requisicion_a_editar.correo_solicitante = form.correo_solicitante.data
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Departamento seleccionado no válido.', 'danger')
                return False

            requisicion_a_editar.departamento_id = departamento_seleccionado.id
            requisicion_a_editar.prioridad = form.prioridad.data
            requisicion_a_editar.observaciones = form.observaciones.data

            # Eliminar detalles existentes y agregar los nuevos
            for detalle_existente in list(requisicion_a_editar.detalles):
                db.session.delete(detalle_existente)
            db.session.flush() # Asegura que los deletes se ejecuten antes de los adds

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
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al editar requisición en servicio: {str(e)}", exc_info=True)
            flash('Error al actualizar la requisición.', 'danger')
            return False

    def eliminar_requisicion(self, requisicion_id, current_user):
        """Elimina una requisición."""
        requisicion_a_eliminar = self.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
        if not requisicion_a_eliminar:
            return False

        # Lógica de permisos (ya validada en la ruta antes de llamar al servicio)
        # es_creador = requisicion_a_eliminar.creador_id == current_user.id
        # es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
        # ahora = datetime.now(pytz.UTC).replace(tzinfo=None)
        # dentro_del_limite = False
        # if requisicion_a_eliminar.fecha_creacion:
        #     fecha_creacion = requisicion_a_eliminar.fecha_creacion.replace(tzinfo=None)
        #     if ahora <= fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
        #         dentro_del_limite = True
        # if not ((es_creador and dentro_del_limite) or es_admin):
        #     flash('No tiene permiso para eliminar esta requisición o el tiempo límite ha expirado.', 'danger')
        #     return False

        try:
            numero_req = requisicion_a_eliminar.numero_requisicion
            db.session.delete(requisicion_a_eliminar)
            db.session.commit()
            registrar_accion(current_user.id, 'Requisiciones', numero_req, 'eliminar')
            flash(f'Requisicion {numero_req} eliminada con éxito.', 'success')
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al eliminar requisicion {requisicion_id} en servicio: {e}", exc_info=True)
            flash(f'Error al eliminar la requisición: {str(e)}', 'danger')
            return False

    def cambiar_estado(self, requisicion_id, nuevo_estado, comentario, current_user):
        """Cambia el estado de una requisición."""
        requisicion = self.obtener_requisicion_por_id(requisicion_id, check_incomplete=False)
        if not requisicion:
            return False # Flash ya mostrado

        # La validación de si el rol puede cambiar al nuevo_estado se hace en la ruta (ver `opciones_estado_permitidas`)
        # Aquí solo ejecutamos el cambio.

        if requisicion.estado == nuevo_estado and (not comentario or comentario == requisicion.comentario_estado):
            flash('No se realizaron cambios (mismo estado y sin nuevo comentario o el mismo).', 'info')
            return True # No es un error, pero no hubo cambio real

        if nuevo_estado in ['Rechazada por Almacén', 'Rechazada por Compras', 'Cancelada'] and not comentario:
            flash('Es altamente recomendable ingresar un motivo al rechazar o cancelar la requisición.', 'warning')

        # Lógica de util_cambiar_estado_requisicion integrada aquí:
        requisicion.estado = nuevo_estado
        if comentario is not None: # Asegurar que el comentario se actualice solo si se provee uno nuevo
            requisicion.comentario_estado = comentario

        try:
            db.session.commit()
            registrar_accion(
                current_user.id if current_user else None, # current_user puede ser AdminVirtual sin id real en BD
                "Requisiciones",
                str(requisicion.id),
                f"estado:{nuevo_estado}",
            )

            # Notificaciones por correo
            mensaje_solicitante = generar_mensaje_correo(
                "Solicitante", requisicion, nuevo_estado, comentario or ""
            )
            enviar_correo(
                [requisicion.correo_solicitante], "Actualización de tu requisición", mensaje_solicitante
            )
            current_app.logger.info(
                f"Correo enviado a {requisicion.correo_solicitante} con estado {nuevo_estado}"
            )

            if nuevo_estado == ESTADO_INICIAL_REQUISICION: # Aunque raro cambiar A este estado, se mantiene la lógica
                mensaje_almacen = generar_mensaje_correo(
                    "Almacén", requisicion, nuevo_estado, comentario or ""
                )
                enviar_correos_por_rol(
                    "Almacen", "Nueva requisición pendiente", mensaje_almacen
                )
            elif nuevo_estado == "Aprobada por Almacén":
                mensaje_compras = generar_mensaje_correo(
                    "Compras", requisicion, nuevo_estado, comentario or ""
                )
                enviar_correos_por_rol(
                    "Compras", "Requisición enviada por Almacén", mensaje_compras
                )
            elif nuevo_estado == "Pendiente de Cotizar": # Ejemplo de otro estado que podría notificar a Compras
                 mensaje_compras_cotizar = generar_mensaje_correo(
                    "Compras", requisicion, nuevo_estado, comentario or ""
                )
                 enviar_correos_por_rol(
                    "Compras", "Requisición pendiente por cotizar", mensaje_compras_cotizar
                )
            # Añadir más notificaciones para otros cambios de estado si es necesario

            flash_message = f'El estado de la requisición {requisicion.numero_requisicion} ha sido actualizado a "{ESTADOS_REQUISICION_DICT.get(nuevo_estado, nuevo_estado)}".'
            if comentario: # Solo si se guardó un comentario nuevo o actualizado
                flash_message += " Comentario guardado."
            flash(flash_message, 'success')
            return True

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al cambiar estado de requisición {requisicion_id} en servicio: {e}", exc_info=True)
            flash('Error crítico al actualizar el estado de la requisición.', 'danger')
            return False

    def listar_requisiciones_para_usuario(self, current_user, filtro=None, page=1, per_page=10):
        """Lista las requisiciones activas visibles para el usuario actual según su rol y filtro."""
        rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
        query = Requisicion.query

        if rol == 'Compras':
            estados = ['Aprobada por Almacén', 'Pendiente de Cotizar']
            query = query.filter(Requisicion.estado.in_(estados))
        elif rol == 'Almacen':
            estados = ['Pendiente Revisión Almacén', 'Aprobada por Almacén']
            query = query.filter(Requisicion.estado.in_(estados))
        elif rol == 'Solicitante':
            query = query.filter_by(creador_id=current_user.id)
        # Admin y otros roles ven todas por defecto (sin filtro de rol aquí)

        # Filtros adicionales
        if filtro == 'sin_revisar' and rol == 'Almacen':
            query = query.filter_by(estado=ESTADO_INICIAL_REQUISICION)
        elif filtro == 'por_cotizar':
            if rol == 'Almacen': # Almacén puede ver las que envió a compras.
                query = query.filter_by(estado='Aprobada por Almacén')
            elif rol == 'Compras':
                query = query.filter_by(estado='Pendiente de Cotizar')
        elif filtro == 'recien_llegadas' and rol == 'Compras': # Requisiciones que acaban de ser aprobadas por almacén
            query = query.filter_by(estado='Aprobada por Almacén')

        # Excluir estados históricos si no es una vista de historial
        query = query.filter(Requisicion.estado.notin_(ESTADOS_HISTORICOS))

        requisiciones_paginadas = query.order_by(Requisicion.fecha_creacion.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return requisiciones_paginadas

    def listar_historial_requisiciones(self, current_user, page=1, per_page=10):
        """Lista el historial de requisiciones para el usuario actual."""
        query = None
        rol_usuario = current_user.rol_asignado.nombre if hasattr(current_user, 'rol_asignado') and current_user.rol_asignado else None

        if rol_usuario == 'Admin' or rol_usuario == 'Superadmin': # Superadmin también debe ver todo
            query = Requisicion.query
        elif rol_usuario == 'Almacen':
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([
                        ESTADO_INICIAL_REQUISICION, 'Aprobada por Almacén',
                        'Surtida desde Almacén', 'Rechazada por Almacén',
                        'Comprada', 'Recibida Parcialmente', 'Recibida Completa', 'Cerrada', 'Cancelada'
                    ])
                )
            )
        elif rol_usuario == 'Compras':
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([
                        'Aprobada por Almacén', 'Pendiente de Cotizar',
                        'Aprobada por Compras', 'En Proceso de Compra', 'Comprada',
                        'Recibida Parcialmente', 'Recibida Completa', 'Cerrada',
                        'Rechazada por Compras', 'Cancelada'
                    ])
                )
            )
        else: # Solicitante y otros roles sin privilegios especiales
            if hasattr(current_user, 'departamento_asignado') and current_user.departamento_asignado:
                query = Requisicion.query.filter(
                    db.or_(
                        Requisicion.departamento_id == current_user.departamento_id,
                        Requisicion.creador_id == current_user.id
                    )
                )
            elif hasattr(current_user, 'id'): # Si no tiene departamento, al menos sus requisiciones
                query = Requisicion.query.filter_by(creador_id=current_user.id)

        if query is not None:
            query = query.filter(Requisicion.estado.in_(ESTADOS_HISTORICOS))
            requisiciones_paginadas = query.order_by(Requisicion.fecha_creacion.desc()).paginate(page=page, per_page=per_page, error_out=False)
            return requisiciones_paginadas

        current_app.logger.warning(f"Query para historial de requisiciones fue None para {current_user.username}")
        return None # La ruta manejará el error o un template vacío

    def get_permisos_y_estado_edicion(self, requisicion, current_user):
        """
        Determina si una requisición es editable o eliminable por el usuario actual,
        y si está dentro del límite de tiempo original para edición.
        Retorna un diccionario con: puede_editar, puede_eliminar, editable_dentro_limite_original.
        """
        if not requisicion:
            return {'puede_editar': False, 'puede_eliminar': False, 'editable_dentro_limite_original': False}

        es_creador = requisicion.creador_id == current_user.id
        es_admin_o_super = current_user.rol_asignado and current_user.rol_asignado.nombre in ['Admin', 'Superadmin']

        ahora = datetime.now(pytz.UTC).replace(tzinfo=None) # Comparar con fechas de DB sin tz naive
        editable_dentro_limite_original = False
        if requisicion.fecha_creacion:
            # Asegurar que fecha_creacion también sea naive UTC para la comparación
            fecha_creacion_naive_utc = requisicion.fecha_creacion.replace(tzinfo=None)
            if ahora <= fecha_creacion_naive_utc + TIEMPO_LIMITE_EDICION_REQUISICION:
                editable_dentro_limite_original = True

        estado_permite_edicion_creador = requisicion.estado == ESTADO_INICIAL_REQUISICION

        puede_editar = (es_creador and estado_permite_edicion_creador and editable_dentro_limite_original) or es_admin_o_super
        # La eliminación para el creador también depende del tiempo límite y estado inicial. Admin siempre puede.
        puede_eliminar = (es_creador and estado_permite_edicion_creador and editable_dentro_limite_original) or es_admin_o_super

        return {
            'puede_editar': puede_editar,
            'puede_eliminar': puede_eliminar,
            'editable_dentro_limite_original': editable_dentro_limite_original,
        }

    def get_opciones_estado_permitidas(self, requisicion, current_user_rol_nombre):
        """
        Determina las opciones de cambio de estado permitidas para una requisición
        basado en su estado actual y el rol del usuario.
        """
        opciones = []
        estado_actual = requisicion.estado

        if current_user_rol_nombre == 'Admin' or current_user_rol_nombre == 'Superadmin':
            return ESTADOS_REQUISICION # Admin/Superadmin puede cambiar a cualquier estado

        if current_user_rol_nombre == 'Almacen':
            if estado_actual == ESTADO_INICIAL_REQUISICION:
                opciones = [ESTADO_INICIAL_REQUISICION, 'Aprobada por Almacén', 'Surtida desde Almacén', 'Rechazada por Almacén']
            elif estado_actual == 'Comprada':
                opciones = [estado_actual, 'Recibida Parcialmente', 'Recibida Completa']
            elif estado_actual == 'Recibida Parcialmente':
                opciones = [estado_actual, 'Recibida Completa']
            elif estado_actual in ['Aprobada por Almacén', 'Surtida desde Almacén', 'Rechazada por Almacén', 'Recibida Completa', 'Cerrada', 'Cancelada']:
                opciones = [estado_actual] # Solo puede ver el estado actual, no cambiarlo desde aquí a otro
            else: # Otros estados no manejados directamente por Almacén
                opciones = [estado_actual]

        elif current_user_rol_nombre == 'Compras':
            if estado_actual == 'Aprobada por Almacén':
                opciones = [estado_actual, 'Pendiente de Cotizar', 'Rechazada por Compras']
            elif estado_actual == 'Pendiente de Cotizar':
                opciones = [estado_actual, 'Aprobada por Compras', 'Rechazada por Compras', 'Cancelada']
            elif estado_actual == 'Aprobada por Compras':
                opciones = [estado_actual, 'Comprada', 'Cancelada']
            # 'En Proceso de Compra' no está en ESTADOS_REQUISICION, parece ser un estado no usado o de un flujo anterior.
            # Se omite por ahora, si es necesario se puede añadir.
            elif estado_actual == 'Comprada':
                opciones = [estado_actual, 'Cerrada'] # Compras puede cerrar si ya está comprada (o recibida)
            elif estado_actual == 'Recibida Parcialmente':
                opciones = [estado_actual, 'Cerrada']
            elif estado_actual == 'Recibida Completa':
                opciones = [estado_actual, 'Cerrada']
            elif estado_actual in ['Rechazada por Compras', 'Cancelada', 'Cerrada']:
                opciones = [estado_actual]
            else: # Otros estados no manejados directamente por Compras
                opciones = [estado_actual]

        else: # Solicitante u otros roles no pueden cambiar estado directamente
            opciones = [estado_actual]

        # Convertir a formato de choices para el formulario
        return [(op, ESTADOS_REQUISICION_DICT.get(op, op)) for op in opciones]

    def listar_por_estado_filtrado(self, estado_param, current_user, page=1, per_page=10):
        """Lista requisiciones por un estado específico, aplicando filtros de rol."""
        if estado_param not in ESTADOS_REQUISICION_DICT:
            abort(404) # O retornar None y que la ruta maneje

        query = Requisicion.query.filter_by(estado=estado_param)
        rol_nombre = current_user.rol_asignado.nombre if current_user.rol_asignado else None

        # Si no es Admin/Superadmin, solo ve sus propias requisiciones o las de su departamento
        # Esto es un filtro general, la lógica de `listar_requisiciones` es más específica para "activos"
        if rol_nombre not in ['Admin', 'Superadmin']:
            if hasattr(current_user, 'departamento_id') and current_user.departamento_id:
                 query = query.filter(
                     db.or_(
                         Requisicion.creador_id == current_user.id,
                         Requisicion.departamento_id == current_user.departamento_id # Ver las de su departamento
                     )
                 )
            else:
                query = query.filter_by(creador_id == current_user.id)


        requisiciones_paginadas = query.order_by(Requisicion.fecha_creacion.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return requisiciones_paginadas

    def limpiar_requisiciones_antiguas(self, dias: int, current_user_id: int | None):
        """
        Limpia requisiciones antiguas que están en estados históricos.
        Sube sus PDFs a Drive si no están ya allí y luego las elimina de la BD.
        """
        fecha_limite = datetime.now(pytz.UTC) - timedelta(days=dias)
        eliminadas_count = 0
        subidas_count = 0

        try:
            requisiciones_a_limpiar = (
                Requisicion.query
                .filter(Requisicion.estado.in_(ESTADOS_HISTORICOS))
                .filter(Requisicion.fecha_creacion < fecha_limite)
                .all()
            )

            for req in requisiciones_a_limpiar:
                subida_exitosa_o_necesaria = True # Asumir éxito si no se necesita subir

                if not req.url_pdf_drive: # Solo intentar subir si no hay URL
                    try:
                        pdf_bytes = util_generar_pdf_requisicion(req) # Usar la utilidad de utils
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf_file:
                            tmp_pdf_file.write(pdf_bytes)
                            tmp_pdf_file.flush() # Asegurar que todo esté escrito antes de leerlo
                            nombre_drive = f"requisicion_{req.numero_requisicion}.pdf"
                            # Llamar a la utilidad de utils para subir a Drive
                            url_drive = subir_pdf_a_drive(nombre_drive, tmp_pdf_file.name)
                        os.remove(tmp_pdf_file.name) # Eliminar archivo temporal

                        if url_drive:
                            req.url_pdf_drive = url_drive
                            # No hacer commit aquí, se hará junto con la eliminación o al final.
                            current_app.logger.info(f"PDF de Requisición {req.id} subido a Drive: {url_drive}")
                            subidas_count += 1
                        else:
                            current_app.logger.error(f"Fallo al subir PDF de Requisición {req.id} a Drive.")
                            subida_exitosa_o_necesaria = False
                    except Exception as e_pdf:
                        current_app.logger.error(f"Error generando/subiendo PDF para requisición {req.id} durante limpieza: {e_pdf}", exc_info=True)
                        subida_exitosa_o_necesaria = False

                # Proceder a eliminar solo si la subida fue exitosa o si ya tenía URL (no se intentó subir)
                if subida_exitosa_o_necesaria:
                    try:
                        db.session.delete(req)
                        # El commit se hará una vez al final del bucle para eficiencia.
                        eliminadas_count += 1
                    except Exception as e_delete:
                        db.session.rollback() # Rollback parcial para esta requisición
                        current_app.logger.error(f"Error eliminando requisición {req.id} tras intento de subida/verificación de PDF: {e_delete}", exc_info=True)
                else:
                    # Si la subida falló y era necesaria, no eliminar la requisición para no perder el PDF.
                    # Se podría intentar de nuevo en una futura ejecución.
                    current_app.logger.warning(f"Requisición {req.id} no eliminada porque la subida del PDF falló o el PDF no se pudo generar.")

            if eliminadas_count > 0 or subidas_count > 0 : # Hacer commit si hubo cambios
                db.session.commit()

            if eliminadas_count > 0 : # Solo registrar acción si se eliminó algo
                 registrar_accion(current_user_id, 'Sistema', f'Limpieza de {eliminadas_count} requisiciones antiguas ({dias} días). {subidas_count} PDFs subidos.', 'ejecutar')

            current_app.logger.info(f"Servicio limpiar_requisiciones_antiguas: {subidas_count} PDFs subidos, {eliminadas_count} requisiciones eliminadas.")
            return eliminadas_count

        except Exception as e_main:
            db.session.rollback() # Rollback general si algo falla en el proceso principal
            current_app.logger.error(f"Error mayor en el servicio limpiar_requisiciones_antiguas: {e_main}", exc_info=True)
            return -1 # Indicar error


requisicion_service = RequisicionService()
