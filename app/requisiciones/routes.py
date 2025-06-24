from flask import current_app as app
from flask import render_template, flash, redirect, url_for, request, abort, make_response, session
from flask_login import login_required, current_user
from datetime import datetime
import pytz
from sqlalchemy.exc import IntegrityError

from .. import db
from .constants import (
    ESTADO_INICIAL_REQUISICION,
    ESTADOS_REQUISICION,
    ESTADOS_REQUISICION_DICT,
    ESTADOS_HISTORICOS,
    UNIDADES_DE_MEDIDA_SUGERENCIAS,
    TIEMPO_LIMITE_EDICION_REQUISICION
)

from app.decorators import admin_required
import app.utils as utils
from ..models import (
    Requisicion,
    DetalleRequisicion,
    ProductoCatalogo,  # Used by agregar_producto_al_catalogo
)
from .forms import (
    RequisicionForm,
    CambiarEstadoForm,
    ConfirmarEliminarForm
)
from . import requisiciones_bp


@requisiciones_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear_requisicion():
    from ..models import Departamento, Usuario

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
                productos_sugerencias = utils.obtener_sugerencias_productos()
                return render_template(
                    'requisiciones/crear_requisicion.html',  # Changed template path
                    form=form,
                    departamentos=departamentos,
                    title="Crear Nueva Requisición",
                    unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                    productos_sugerencias=productos_sugerencias,
                    vista_actual='crear'
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
                    utils.agregar_producto_al_catalogo(nombre_producto_estandarizado)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la requisición: {str(e)}', 'danger')
            app.logger.error(f"Error en crear_requisicion: {e}", exc_info=True)
        else:
            try:
                mensaje = utils.generar_mensaje_correo('Solicitante', nueva_requisicion, nueva_requisicion.estado, "")
                utils.enviar_correo([nueva_requisicion.correo_solicitante], 'Requisición creada', mensaje)

                if nueva_requisicion.estado == ESTADO_INICIAL_REQUISICION:
                    from ..models import Rol
                    mensaje_almacen = utils.generar_mensaje_correo('Almacén', nueva_requisicion, nueva_requisicion.estado, "")
                    utils.enviar_correos_por_rol('Almacen', 'Nueva requisición pendiente', mensaje_almacen, Usuario, Rol)

                utils.guardar_pdf_requisicion(nueva_requisicion)
            except Exception as e:
                app.logger.error(f"Error tras crear requisición {nueva_requisicion.id}: {e}", exc_info=True)

            flash('¡Requisición creada con éxito! Número: ' + nueva_requisicion.numero_requisicion, 'success')
            return redirect(url_for('requisiciones.requisicion_creada', requisicion_id=nueva_requisicion.id)) # Changed blueprint name

    productos_sugerencias = utils.obtener_sugerencias_productos()
    return render_template(
        'requisiciones/crear_requisicion.html',  # Changed template path
        form=form,
        departamentos=departamentos,
        title="Crear Nueva Requisición",
        unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
        productos_sugerencias=productos_sugerencias,
        vista_actual='crear'
    )

@requisiciones_bp.route('/<int:requisicion_id>/creada')
@login_required
def requisicion_creada(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    # Assuming 'requisicion_creada.html' is specific to requisiciones, keep it in 'templates/requisiciones/'
    return render_template('requisiciones/requisicion_creada.html', requisicion=requisicion, title='Requisición Creada', vista_actual='creada')


@requisiciones_bp.route('/') # Path changed to be the root of the blueprint
@login_required
def listar_requisiciones():
    """Lista las requisiciones visibles para el usuario actual según su rol."""
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    filtro = request.args.get('filtro')

    query = Requisicion.query

    if rol == 'Compras':
        estados = ['Aprobada por Almacén', 'Pendiente de Cotizar']
        query = query.filter(Requisicion.estado.in_(estados))
    elif rol == 'Almacen':
        estados = ['Pendiente Revisión Almacén', 'Aprobada por Almacén']
        query = query.filter(Requisicion.estado.in_(estados))
    elif rol == 'Solicitante':
        query = query.filter_by(creador_id=current_user.id)

    if filtro == 'sin_revisar' and rol == 'Almacen':
        query = query.filter_by(estado=ESTADO_INICIAL_REQUISICION)
    elif filtro == 'por_cotizar':
        if rol == 'Almacen':
            query = query.filter_by(estado='Aprobada por Almacén')
        elif rol == 'Compras':
            query = query.filter_by(estado='Pendiente de Cotizar')
    elif filtro == 'recien_llegadas' and rol == 'Compras':
        query = query.filter_by(estado='Aprobada por Almacén')

    page = request.args.get('page', 1, type=int)
    requisiciones_paginadas = (
        query.order_by(Requisicion.fecha_creacion.desc())
        .paginate(page=page, per_page=10)
    )
    return render_template(
        'requisiciones/listar_requisiciones.html', # Changed template path
        requisiciones_paginadas=requisiciones_paginadas,
        filtro=filtro,
        title="Requisiciones Pendientes",
        vista_actual='activas', # This might need adjustment based on how views are structured
        datetime=datetime,
        UTC=pytz.UTC,
        TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION
    )

@requisiciones_bp.route('/historial')
@login_required
def historial_requisiciones():
    try:
        query = None
        rol_usuario = current_user.rol_asignado.nombre if hasattr(current_user, 'rol_asignado') and current_user.rol_asignado else None
        app.logger.debug(f"Historial Requisiciones - Usuario: {current_user.username}, Rol: {rol_usuario}")

        if rol_usuario == 'Admin':
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
        else:
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
            query = query.filter(Requisicion.estado.in_(ESTADOS_HISTORICOS))
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
        'requisiciones/historial_requisiciones.html', # Changed template path
        requisiciones_paginadas=requisiciones_paginadas,
        title="Historial de Requisiciones",
        vista_actual='historial', # This might need adjustment
        datetime=datetime,
        UTC=pytz.UTC,
        TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION,
    )

@requisiciones_bp.route('/<int:requisicion_id>', methods=['GET', 'POST'])
@login_required
def ver_requisicion(requisicion_id):
    from ..models import Usuario

    try:
        requisicion = Requisicion.query.get(requisicion_id)
    except Exception as e:
        app.logger.error(f"Error al ver requisición: {str(e)}", exc_info=True)
        abort(500)

    if requisicion is None:
        flash('Requisición no encontrada.', 'danger')
        return redirect(url_for('requisiciones.listar_requisiciones')) # Changed blueprint name

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
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada'])
            ]
        elif requisicion.estado == 'Recibida Parcialmente':
            opciones_estado_permitidas = [
                ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']),
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
            return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion.id)) # Changed blueprint name

        nuevo_estado = form_estado.estado.data
        if not any(nuevo_estado == choice[0] for choice in opciones_estado_permitidas):
            flash('Intento de cambio de estado no válido o no permitido para su rol/estado actual.', 'danger')
            return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion.id)) # Changed blueprint name

        comentario_ingresado_texto = form_estado.comentario_estado.data.strip() if form_estado.comentario_estado.data else None

        if requisicion.estado != nuevo_estado or (comentario_ingresado_texto and comentario_ingresado_texto != requisicion.comentario_estado):
            if nuevo_estado in ['Rechazada por Almacén', 'Rechazada por Compras', 'Cancelada'] and not comentario_ingresado_texto:
                flash('Es altamente recomendable ingresar un motivo al rechazar o cancelar la requisición.', 'warning')

            from ..models import Rol
            if utils.cambiar_estado_requisicion(
                requisicion.id,
                nuevo_estado,
                current_user,
                comentario_ingresado_texto,
                Usuario,
                Rol,
            ):
                flash_message = f'El estado de la requisición {requisicion.numero_requisicion} ha sido actualizado a "{ESTADOS_REQUISICION_DICT.get(nuevo_estado, nuevo_estado)}".'
                if comentario_ingresado_texto:
                    flash_message += " Comentario guardado."
                flash(flash_message, 'success')
            else:
                flash('Error al actualizar el estado.', 'danger')
        else:
            flash('No se realizaron cambios (mismo estado y sin nuevo comentario o el mismo).', 'info')
        return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion.id)) # Changed blueprint name

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
        'requisiciones/ver_requisicion.html', # Changed template path
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
        vista_actual='detalle'
    )

@requisiciones_bp.route('/<int:requisicion_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_requisicion(requisicion_id):
    from ..models import Departamento

    try:
        requisicion_a_editar = Requisicion.query.get(requisicion_id)
    except Exception as e:
        app.logger.error(f"Error al editar requisición: {str(e)}", exc_info=True)
        abort(500)

    if requisicion_a_editar is None:
        flash('Requisición no encontrada.', 'danger')
        return redirect(url_for('requisiciones.listar_requisiciones')) # Changed blueprint name

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
        return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion_a_editar.id)) # Changed blueprint name

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
                productos_sugerencias = utils.obtener_sugerencias_productos()
                return render_template('requisiciones/editar_requisicion.html',
                                      form=form,
                                      title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}",
                                      requisicion_id=requisicion_a_editar.id,
                                      unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                                      productos_sugerencias=productos_sugerencias,
                                      vista_actual='editar')  # Changed template path

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
                    utils.agregar_producto_al_catalogo(nombre_producto_estandarizado)
            db.session.commit()
            flash(f'Requisición {requisicion_a_editar.numero_requisicion} actualizada con éxito.', 'success')
            return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion_a_editar.id)) # Changed blueprint name
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error al editar requisición: {str(e)}", exc_info=True)
            abort(500)

    productos_sugerencias = utils.obtener_sugerencias_productos()
    return render_template('requisiciones/editar_requisicion.html',
                           form=form,
                           title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}",  # Changed template path
                           requisicion_id=requisicion_a_editar.id,
                           unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                           productos_sugerencias=productos_sugerencias,
                           vista_actual='editar')

@requisiciones_bp.route('/<int:requisicion_id>/confirmar_eliminar')
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
        return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion.id)) # Changed blueprint name
    form = ConfirmarEliminarForm()
    # Assuming 'confirmar_eliminar_requisicion.html' is specific to requisiciones
    return render_template('requisiciones/confirmar_eliminar_requisicion.html',
                           requisicion=requisicion,
                           form=form,
                           title=f"Confirmar Eliminación: {requisicion.numero_requisicion}",
                           vista_actual='confirmar_eliminar')

@requisiciones_bp.route('/<int:requisicion_id>/eliminar', methods=['POST'])
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
        return redirect(url_for('requisiciones.ver_requisicion', requisicion_id=requisicion_a_eliminar.id)) # Changed blueprint name
    if not form.validate_on_submit():
        flash('Petición inválida.', 'danger')
        return redirect(url_for('requisiciones.confirmar_eliminar_requisicion', requisicion_id=requisicion_id)) # Changed blueprint name
    try:
        db.session.delete(requisicion_a_eliminar)
        db.session.commit()
        utils.registrar_accion(current_user.id, 'Requisiciones', requisicion_a_eliminar.numero_requisicion, 'eliminar')
        flash(f'Requisicion {requisicion_a_eliminar.numero_requisicion} eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la requisición: {str(e)}', 'danger')
        app.logger.error(f"Error al eliminar requisicion {requisicion_id}: {e}", exc_info=True)
    return redirect(url_for('requisiciones.listar_requisiciones')) # Changed blueprint name

@requisiciones_bp.route('/pendientes_cotizar')
@login_required
def listar_pendientes_cotizar():
    rol_usuario = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol_usuario == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Pendiente de Cotizar').all()
    else:
        # Non-Compras users should probably not see this, or only their own if applicable
        # For now, let's assume only Compras uses this specific view.
        # If others can, adjust query and template path if needed.
        flash("Acceso no autorizado a esta vista.", "warning")
        return redirect(url_for('requisiciones.listar_requisiciones'))

    # Assuming 'listar_pendientes_cotizar.html' is specific to requisiciones
    return render_template('requisiciones/listar_pendientes_cotizar.html',
                           requisiciones=requisiciones,
                           title="Pendientes de Cotizar",
                           vista_actual='pendientes_cotizar')

@requisiciones_bp.route('/cotizadas')
@login_required
def listar_cotizadas():
    rol_usuario = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol_usuario == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Cotizada').all() # Assuming 'Cotizada' is a valid state
    else:
        # Similar to above, adjust if other roles can access this.
        flash("Acceso no autorizado a esta vista.", "warning")
        return redirect(url_for('requisiciones.listar_requisiciones'))

    # Assuming 'listar_cotizadas.html' is specific to requisiciones
    return render_template('requisiciones/listar_cotizadas.html',
                           requisiciones=requisiciones,
                           title="Cotizadas",
                           vista_actual='cotizadas')

@requisiciones_bp.route('/estado/<path:estado>')
@login_required
def listar_por_estado(estado):
    if estado not in ESTADOS_REQUISICION_DICT:
        abort(404)

    qs = Requisicion.query.filter_by(estado=estado)
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol != 'Admin': # Consider if other roles like Compras/Almacen should see all for specific states they manage
        # For now, only Admin sees all, others see their own.
        if not (rol in ['Compras', 'Almacen'] and estado in ESTADOS_REQUISICION_DICT): # Basic check, might need refinement
             qs = qs.filter_by(creador_id=current_user.id)
        # More sophisticated logic might be needed here depending on exact requirements for Compras/Almacen visibility

    page = request.args.get('page', 1, type=int)
    requisiciones_paginadas = (
        qs.order_by(Requisicion.fecha_creacion.desc())
        .paginate(page=page, per_page=10)
    )
    # Assuming 'listar_por_estado.html' is specific to requisiciones
    return render_template(
        'requisiciones/listar_por_estado.html',
        requisiciones_paginadas=requisiciones_paginadas,
        title=ESTADOS_REQUISICION_DICT[estado],
        estado=estado,
        vista_actual='estado' # This might need adjustment
    )

@requisiciones_bp.route('/<int:requisicion_id>/imprimir')
@login_required
def imprimir_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    # Add permission check if necessary, e.g., only creator or admin/compras/almacen can print
    pdf_data = utils.generar_pdf_requisicion(requisicion)
    nombre = f"requisicion_{requisicion.numero_requisicion}.pdf"
    resp = make_response(pdf_data)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={nombre}'
    return resp

@requisiciones_bp.route('/admin/limpiar_requisiciones_viejas') # Path is now /requisiciones/admin/limpiar_requisiciones_viejas
@login_required
@admin_required
def limpiar_requisiciones_viejas_route():
    """Limpia requisiciones finalizadas antiguas."""
    dias = request.args.get('dias', 15, type=int)
    eliminadas = utils.limpiar_requisiciones_viejas(dias, guardar_mensaje=True) # limpiar_requisiciones_viejas from ..utils
    flash(f'Se eliminaron {eliminadas} requisiciones antiguas.', 'success')
    return redirect(url_for('requisiciones.historial_requisiciones')) # Redirect to new blueprint path
