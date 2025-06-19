from __future__ import annotations

import os
import tempfile
import base64
from functools import wraps
from datetime import datetime, timedelta
import pytz
from threading import Thread
import requests
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from flask import current_app as app, session, redirect, url_for, flash
from flask_login import current_user

from . import db, login_manager
from .requisiciones.constants import (
    ESTADO_INICIAL_REQUISICION,
    ESTADOS_HISTORICOS_REQUISICION,
)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (
            not current_user.is_authenticated
            or not current_user.rol_asignado
            or current_user.rol_asignado.nombre != "Admin"
        ):
            flash(
                "Acceso no autorizado. Se requieren permisos de Administrador.",
                "danger",
            )
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated_function


def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.superadmin:
            flash("Acceso restringido a superadministradores.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated_function


def ensure_session_token_column():
    inspector = inspect(db.engine)
    if "usuario" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("usuario")]
        if "session_token" not in cols:
            db.session.execute(
                "ALTER TABLE usuario ADD COLUMN session_token VARCHAR(100)"
            )
            db.session.commit()


def ensure_ultimo_login_column():
    inspector = inspect(db.engine)
    if "usuario" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("usuario")]
        if "ultimo_login" not in cols:
            db.session.execute(
                "ALTER TABLE usuario ADD COLUMN ultimo_login DATETIME"
            )
            db.session.commit()


def registrar_accion(
    usuario_id: int | None,
    modulo: str,
    objeto: str | None,
    accion: str,
) -> None:
    from .models import AuditoriaAcciones
    try:
        entrada = AuditoriaAcciones(
            usuario_id=usuario_id,
            modulo=modulo,
            objeto=objeto,
            accion=accion,
        )
        db.session.add(entrada)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.error(f"Error al registrar auditoría: {exc}")


def registrar_intento(ip: str, username: str | None, exito: bool) -> None:
    from .models import IntentoLoginFallido
    try:
        intento = IntentoLoginFallido(ip=ip, username=username, exito=exito)
        db.session.add(intento)
        db.session.commit()
    except Exception:
        db.session.rollback()


def exceso_intentos(ip: str, username: str | None) -> bool:
    from .models import IntentoLoginFallido
    limite = datetime.now(pytz.UTC) - timedelta(minutes=10)
    fallidos_ip = (
        IntentoLoginFallido.query.filter_by(ip=ip, exito=False)
        .filter(IntentoLoginFallido.timestamp >= limite)
        .count()
    )
    if fallidos_ip >= 5:
        return True
    if username:
        fallidos_user = (
            IntentoLoginFallido.query.filter_by(username=username, exito=False)
            .filter(IntentoLoginFallido.timestamp >= limite)
            .count()
        )
        if fallidos_user >= 5:
            return True
    return False


@login_manager.user_loader
def load_user(user_id):
    from .models import AdminVirtual, Usuario
    try:
        if user_id == "0":
            admin = AdminVirtual()
            admin.session_token = session.get("session_token")
            return admin
        return db.session.get(Usuario, int(user_id))
    except Exception as e:
        db.session.rollback()
        app.logger.error(
            f"Error crítico en load_user para user_id {user_id}: {e}", exc_info=True
        )
        return None


def crear_datos_iniciales(Rol, Departamento, Usuario):
    with app.app_context():
        departamentos_nombres = [
            "Administración",
            "Recursos Humanos",
            "Compras",
            "Producción",
            "Ventas",
            "Almacén",
            "Mantenimiento",
            "Sistemas",
            "Oficinas Generales",
            "Finanzas",
            "Marketing",
            "Legal",
        ]
        for nombre_depto in departamentos_nombres:
            if not Departamento.query.filter_by(nombre=nombre_depto).first():
                depto = Departamento(nombre=nombre_depto)
                db.session.add(depto)
        roles_a_crear = {
            "Solicitante": "Puede crear y ver sus requisiciones.",
            "JefeDepartamento": "Puede aprobar requisiciones de su departamento.",
            "Almacen": "Puede revisar stock y aprobar para compra o surtir.",
            "Compras": "Puede gestionar el proceso de compra de requisiciones aprobadas.",
            "Produccion": "Rol específico para requisiciones de producción.",
            "Admin": "Acceso total al sistema.",
            "Superadmin": "Superadministrador del sistema",
        }
        for nombre_rol, desc_rol in roles_a_crear.items():
            if not Rol.query.filter_by(nombre=nombre_rol).first():
                rol = Rol(nombre=nombre_rol, descripcion=desc_rol)
                db.session.add(rol)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error al crear departamentos/roles iniciales: {e}")
            return

        admin_rol = Rol.query.filter_by(nombre="Admin").first()
        depto_admin = Departamento.query.filter_by(nombre="Administración").first()
        if admin_rol and not Usuario.query.filter_by(username="admin").first():
            admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
            admin_password = os.environ.get("ADMIN_PASSWORD")
            if not admin_password:
                app.logger.error(
                    "ADMIN_PASSWORD no configurada; no se creó usuario admin."
                )
            else:
                admin_user = Usuario(
                    username="admin",
                    cedula="V00000000",
                    email=admin_email,
                    nombre_completo="Administrador Sistema",
                    rol_id=admin_rol.id,
                    departamento_id=depto_admin.id if depto_admin else None,
                    activo=True,
                )
                admin_user.set_password(admin_password)
                db.session.add(admin_user)
                try:
                    db.session.commit()
                    app.logger.info("Usuario administrador 'admin' creado.")
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"Error al crear usuario admin: {e}")


def agregar_producto_al_catalogo(nombre_producto: str):
    from .models import ProductoCatalogo
    if nombre_producto and nombre_producto.strip():
        nombre_estandarizado = nombre_producto.strip().title()
        producto_existente = ProductoCatalogo.query.filter_by(
            nombre=nombre_estandarizado
        ).first()
        if not producto_existente:
            try:
                nuevo_producto_catalogo = ProductoCatalogo(
                    nombre=nombre_estandarizado
                )
                db.session.add(nuevo_producto_catalogo)
                db.session.commit()
                app.logger.info(
                    f"Producto '{nombre_estandarizado}' agregado al catálogo."
                )
            except IntegrityError:
                db.session.rollback()
                app.logger.info(
                    f"Producto '{nombre_estandarizado}' ya existe en catálogo (manejado por IntegrityError)."
                )
            except Exception as e:
                db.session.rollback()
                app.logger.error(
                    f"Error al agregar '{nombre_estandarizado}' al catálogo: {e}"
                )


def obtener_sugerencias_productos():
    from .models import ProductoCatalogo
    try:
        productos = ProductoCatalogo.query.order_by(ProductoCatalogo.nombre).all()
        return [p.nombre for p in productos]
    except Exception as e:
        app.logger.error(f"Error al obtener sugerencias de productos: {e}")
        return []


def obtener_emails_por_rol(nombre_rol: str, UsuarioModel, RolModel):
    try:
        usuarios = (
            UsuarioModel.query.join(RolModel)
            .filter(RolModel.nombre == nombre_rol, UsuarioModel.activo == True)
            .all()
        )
        return [u.email for u in usuarios if u.email]
    except Exception as e:
        app.logger.error(f"Error obteniendo emails para rol {nombre_rol}: {e}")
        return []


def generar_mensaje_correo(
    rol_destino: str,
    requisicion: Requisicion,
    estado_actual: str,
    motivo: str = "",
) -> str:
    from .models import Requisicion
    titulo = ""
    cuerpo = ""

    if rol_destino == "Solicitante":
        titulo = "Actualización de requisición"
        cuerpo = (
            f"Hola {requisicion.nombre_solicitante},\n\n"
            f"Te informamos que tu requisición #{requisicion.id} ha cambiado de estado.\n"
            f"Prioridad: {requisicion.prioridad}\n"
            "Puedes hacer seguimiento completo desde el sistema de compras interno de Granja Los Molinos.\n"
            "Si tienes alguna duda, por favor contacta a tu departamento responsable."
        )
        if estado_actual == "Rechazada por Almacén" and motivo:
            cuerpo += f"\n\n⚠️ Motivo del rechazo: {motivo}"
        cuerpo += (
            "\n---\n"
            "Este mensaje fue generado automáticamente por el sistema de compras de Granja Los Molinos. No responder a este correo."
        )
    elif rol_destino == "Almacén":
        titulo = "Nueva requisición pendiente"
        cuerpo = (
            "Hola equipo de Almacén,\n\n"
            f"Se ha creado una nueva requisición interna con el número #{requisicion.id} que requiere su revisión y aprobación.\n"
            f"Solicitante: {requisicion.nombre_solicitante}\n"
            f"Prioridad: {requisicion.prioridad}\n"
            "Por favor, ingresa al sistema para revisarla, aprobarla o rechazarla según corresponda."
        )
        if estado_actual == "Rechazada por Almacén" and motivo:
            cuerpo += f"\n\n⚠️ Motivo del rechazo: {motivo}"
        cuerpo += (
            "\n---\n"
            "Este mensaje fue generado automáticamente por el sistema de compras de Granja Los Molinos. No responder a este correo."
        )
    elif rol_destino == "Compras":
        titulo = "Requisición para compras"
        cuerpo = (
            "Hola equipo de Compras,\n\n"
            f"La requisición #{requisicion.id} fue aprobada por el departamento de Almacén y ahora se encuentra bajo su responsabilidad para cotización o gestión de compra.\n"
            f"Solicitante: {requisicion.nombre_solicitante}\n"
            f"Prioridad: {requisicion.prioridad}\n"
            "Puedes ingresar al sistema de compras interno para continuar con el proceso."
        )
        cuerpo += (
            "\n---\n"
            "Este mensaje fue generado automáticamente por el sistema de compras de Granja Los Molinos. No responder a este correo."
        )
    else:
        return ""

    logo_path = os.path.join(app.static_folder, "images", "logo_granja.jpg")
    try:
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")
            logo_html = (
                f'<img src="data:image/jpeg;base64,{logo_base64}" style="max-height:60px;">'
            )
    except Exception as e:
        app.logger.error(f"Error cargando logo: {e}")
        logo_html = "Logo Granja Los Molinos"

    cuerpo_html = "<br>".join(cuerpo.splitlines())

    color_encabezado = "#1D1455"
    color_boton = "#F99C1B"
    color_fondo_pie = "#f0f0f0"

    html = f"""
    <!DOCTYPE html>
    <html lang=\"es\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>{titulo}</title>
    </head>
    <body style=\"font-family: Arial, Helvetica, sans-serif; margin:0; padding:0;\">
        <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"border-collapse:collapse;\">
            <tr>
                <td style=\"background-color:{color_encabezado}; padding:20px; text-align:center;\">
                    {logo_html}
                </td>
            </tr>
            <tr>
                <td style=\"background-color:#ffffff; padding:30px;\">
                    <h2 style=\"color:{color_encabezado}; margin-top:0;\">{titulo}</h2>
                    <p>Hola,</p>
                    <p>{cuerpo_html}</p>
                    <p style=\"margin:20px 0;\">
                        <span style=\"background-color:{color_encabezado}; color:#ffffff; padding:8px 12px; border-radius:4px;\">
                            {estado_actual}
                        </span>
                    </p>
                    <p style=\"text-align:center; margin:30px 0;\">
                        <a href=\"https://sistema.granjalosmolinos.com\" style=\"background-color:{color_boton}; color:#ffffff; text-decoration:none; padding:10px 20px; border-radius:4px;\">
                            Ingresar al sistema
                        </a>
                    </p>
                </td>
            </tr>
            <tr>
                <td style=\"background-color:#ffffff; color:#666666; font-size:12px; padding:15px; text-align:center;\">
                    Este mensaje es confidencial y está dirigido solo a su destinatario. No responda a este correo, ya que es enviado desde una cuenta automática.
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


def enviar_correo_api(destinatarios: list, asunto: str, html_content: str) -> None:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", os.getenv("MAIL_FROM"))
    sender_name = os.getenv("BREVO_SENDER_NAME", "Sistema")

    if not api_key or not sender_email or not destinatarios:
        app.logger.warning(
            "Brevo API no configurada o sin destinatarios, correo no enviado"
        )
        return

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": d} for d in destinatarios],
        "subject": asunto,
        "htmlContent": html_content,
    }

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if 200 <= resp.status_code < 300:
            app.logger.info(
                f"Correo enviado via Brevo API a {destinatarios} con asunto '{asunto}'"
            )
        else:
            app.logger.error(f"Error Brevo API {resp.status_code}: {resp.text}")
    except Exception as exc:
        app.logger.error(f"Error enviando correo via Brevo API: {exc}")


def enviar_correo(destinatarios: list, asunto: str, mensaje: str) -> None:
    Thread(target=enviar_correo_api, args=(destinatarios, asunto, mensaje), daemon=True).start()


def enviar_correos_por_rol(
    nombre_rol: str, asunto: str, mensaje: str, UsuarioModel, RolModel
) -> None:
    destinatarios = obtener_emails_por_rol(nombre_rol, UsuarioModel, RolModel)
    if destinatarios:
        enviar_correo(destinatarios, asunto, mensaje)
        app.logger.info(
            f"Notificación enviada a rol {nombre_rol}: {asunto} -> {destinatarios}"
        )
    else:
        app.logger.warning(f"No se encontraron correos para el rol {nombre_rol}")


def cambiar_estado_requisicion(
    requisicion_id: int,
    nuevo_estado: str,
    usuario_actual: Usuario | None = None,
    comentario: str | None = None,
    UsuarioModel=None,
    RolModel=None,
) -> bool:
    from .models import Requisicion, Usuario
    requisicion = db.session.get(Requisicion, requisicion_id)
    if not requisicion:
        app.logger.error(f"Requisición {requisicion_id} no encontrada")
        return False

    requisicion.estado = nuevo_estado
    if comentario is not None:
        requisicion.comentario_estado = comentario
    try:
        db.session.commit()
        registrar_accion(
            usuario_actual.id if usuario_actual else None,
            "Requisiciones",
            str(requisicion_id),
            f"estado:{nuevo_estado}",
        )
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error al cambiar estado de {requisicion_id}: {e}")
        return False

    mensaje_solicitante = generar_mensaje_correo(
        "Solicitante", requisicion, nuevo_estado, comentario or ""
    )
    enviar_correo(
        [requisicion.correo_solicitante], "Actualización de tu requisición", mensaje_solicitante
    )
    app.logger.info(
        f"Correo enviado a {requisicion.correo_solicitante} con estado {nuevo_estado}"
    )

    if nuevo_estado == ESTADO_INICIAL_REQUISICION:
        mensaje_almacen = generar_mensaje_correo(
            "Almacén", requisicion, nuevo_estado, comentario or ""
        )
        enviar_correos_por_rol(
            "Almacen",
            "Nueva requisición pendiente",
            mensaje_almacen,
            UsuarioModel,
            RolModel,
        )
        app.logger.info(
            f"Correo enviado al rol Almacen por requisición #{requisicion.id}"
        )

    if nuevo_estado == "Aprobada por Almacén":
        mensaje_compras = generar_mensaje_correo(
            "Compras", requisicion, nuevo_estado, comentario or ""
        )
        enviar_correos_por_rol(
            "Compras",
            "Requisición enviada por Almacén",
            mensaje_compras,
            UsuarioModel,
            RolModel,
        )
        app.logger.info(
            f"Correo enviado al rol Compras por requisición #{requisicion.id}"
        )

    if nuevo_estado == "Pendiente de Cotizar":
        mensaje_compras = generar_mensaje_correo(
            "Compras", requisicion, nuevo_estado, comentario or ""
        )
        enviar_correos_por_rol(
            "Compras",
            "Requisición pendiente por cotizar",
            mensaje_compras,
            UsuarioModel,
            RolModel,
        )
        app.logger.info(
            f"Correo enviado al rol Compras (pendiente por cotizar) por requisición #{requisicion.id}"
        )

    return True


def _crear_pdf_minimo(cabecera, detalles):
    logo_path = os.path.join(app.static_folder, "images", "logo_granja.jpg")
    try:
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
    except Exception:
        logo_bytes = b""

    def _jpeg_size(data: bytes):
        import struct
        if not data.startswith(b"\xff\xd8"):
            return 0, 0
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            i += 2
            if marker == 0xDA:
                break
            length = struct.unpack(">H", data[i : i + 2])[0]
            if marker in (0xC0, 0xC2):
                height = struct.unpack(">H", data[i + 3 : i + 5])[0]
                width = struct.unpack(">H", data[i + 5 : i + 7])[0]
                return width, height
            i += length
        return 0, 0

    logo_w, logo_h = _jpeg_size(logo_bytes)
    if logo_w and logo_h:
        draw_logo = True
        scale = 100.0 / logo_w
        pdf_logo_w = 100
        pdf_logo_h = logo_h * scale
    else:
        draw_logo = False

    objetos = []
    objetos.append("1 0 obj\n<< /Type /Catalog\n/Pages 2 0 R >>\nendobj\n")
    objetos.append("2 0 obj\n<< /Type /Pages\n/Kids [3 0 R]\n/Count 1 >>\nendobj\n")

    recursos = "<< /Font << /F1 5 0 R >>"
    if draw_logo:
        recursos += " /XObject << /Im1 6 0 R >>"
    recursos += " >>"

    obj3 = (
        "3 0 obj\n<< /Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]"
        f"\n/Contents 4 0 R\n/Resources {recursos} >>\nendobj\n"
    )
    objetos.append(obj3)

    contenido = []
    if draw_logo:
        y_pos = 792 - 50 - pdf_logo_h
        contenido.append("q")
        contenido.append(f"{pdf_logo_w} 0 0 {pdf_logo_h} 256 {y_pos} cm")
        contenido.append("/Im1 Do")
        contenido.append("Q")
        texto_y = y_pos - 40
    else:
        texto_y = 742

    contenido.append("BT")
    contenido.append("/F1 12 Tf")
    contenido.append(f"80 {texto_y} Td")
    for titulo, valor in cabecera:
        linea = f"{titulo}: {valor}".replace("(", "\\(").replace(")", "\\)")
        contenido.append(f"({linea}) Tj")
        contenido.append("0 -15 Td")
    contenido.append("ET")

    tabla_y = texto_y - (len(cabecera) * 15) - 20
    row_height = 15
    col1_x = 80
    col2_x = 150
    col3_x = 250
    total_rows = len(detalles) + 1
    tabla_height = total_rows * row_height

    contenido.append("1 w")
    ancho_total = 330
    borde_x = col1_x - 5
    borde_y = tabla_y - tabla_height - 5
    contenido.append(f"{borde_x} {borde_y} {ancho_total} {tabla_height + 10} reS")
    contenido.append(f"{col2_x - 5} {tabla_y} m {col2_x - 5} {tabla_y - tabla_height} l S")
    contenido.append(f"{col3_x - 5} {tabla_y} m {col3_x - 5} {tabla_y - tabla_height} l S")
    for i in range(1, total_rows):
        y = tabla_y - i * row_height
        contenido.append(f"{borde_x} {y} m {borde_x + ancho_total} {y} l S")

    contenido.append("BT")
    contenido.append("/F1 12 Tf")
    contenido.append(f"{col1_x} {tabla_y - 12} Td")
    contenido.append("(Cantidad) Tj")
    contenido.append(f"{col2_x - col1_x} 0 Td")
    contenido.append("(Unidad) Tj")
    contenido.append(f"{col3_x - col2_x} 0 Td")
    contenido.append("(Producto) Tj")
    contenido.append("ET")

    y_text = tabla_y - row_height - 12
    for cant, unidad, prod in detalles:
        cantidad = str(cant).replace("(", "\\(").replace(")", "\\)")
        unidad = str(unidad).replace("(", "\\(").replace(")", "\\)")
        producto = str(prod).replace("(", "\\(").replace(")", "\\)")
        contenido.append("BT")
        contenido.append("/F1 12 Tf")
        contenido.append(f"{col1_x} {y_text} Td")
        contenido.append(f"({cantidad}) Tj")
        contenido.append(f"{col2_x - col1_x} 0 Td")
        contenido.append(f"({unidad}) Tj")
        contenido.append(f"{col3_x - col2_x} 0 Td")
        contenido.append(f"({producto}) Tj")
        contenido.append("ET")
        y_text -= row_height

    stream = "\n".join(contenido)
    obj4 = f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj\n"
    objetos.append(obj4)
    obj5 = "5 0 obj\n<< /Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica >>\nendobj\n"
    objetos.append(obj5)

    if draw_logo:
        obj6 = (
            f"6 0 obj\n<< /Type /XObject /Subtype /Image /Width {logo_w} /Height {logo_h}"
            " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode"
            f" /Length {len(logo_bytes)} >>\nstream\n".encode("latin-1")
            + logo_bytes
            + b"\nendstream\nendobj\n"
        )
        objetos.append(obj6.decode("latin-1", "ignore"))

    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref_offset = len(pdf)

    pdf += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"

    pdf += "trailer\n<< /Root 1 0 R\n/Size %d >>\nstartxref\n%d\n%%EOF" % (
        len(objetos) + 1,
        xref_offset,
    )
    return pdf.encode("latin-1")


def generar_pdf_requisicion(requisicion: Requisicion):
    from .models import Requisicion
    cabecera = [
        ("Requisición", requisicion.numero_requisicion),
        ("Fecha", requisicion.fecha_creacion.strftime("%d/%m/%Y %H:%M")),
        ("Solicitante", requisicion.nombre_solicitante),
        (
            "Departamento",
            requisicion.departamento_obj.nombre if requisicion.departamento_obj else "",
        ),
        ("Prioridad", requisicion.prioridad),
    ]
    if requisicion.observaciones:
        cabecera.append(("Obs", requisicion.observaciones))

    detalles = [
        (str(det.cantidad), det.unidad_medida, det.producto)
        for det in requisicion.detalles
    ]

    return _crear_pdf_minimo(cabecera, detalles)


def subir_pdf_a_drive(nombre_archivo: str, ruta_local_pdf: str) -> str | None:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.service_account import Credentials

        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        if not folder_id:
            app.logger.error("GOOGLE_DRIVE_FOLDER_ID no configurado")
            return None

        creds = Credentials.from_service_account_file(
            os.path.join(BASE_DIR, "service_account.json"),
            scopes=["https://www.googleapis.com/auth/drive"],
        )

        service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": nombre_archivo,
            "parents": [folder_id],
        }
        media = MediaFileUpload(ruta_local_pdf, mimetype="application/pdf")

        respuesta = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink,webContentLink")
            .execute()
        )

        file_id = respuesta.get("id")
        if file_id:
            service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
            ).execute()

        return respuesta.get("webViewLink") or respuesta.get("webContentLink")
    except Exception as exc:
        app.logger.error(f"Error subiendo {ruta_local_pdf} a Drive: {exc}", exc_info=True)
        return None


def guardar_pdf_requisicion(requisicion: Requisicion):
    from .models import Requisicion
    pdf_dir = os.path.join(app.static_folder, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    path = os.path.join(pdf_dir, f"requisicion_{requisicion.id}.pdf")
    try:
        pdf_bytes = generar_pdf_requisicion(requisicion)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
    except Exception as e:
        app.logger.error(f"Error guardando PDF {path}: {e}", exc_info=True)
        return None
    return path


def limpiar_requisiciones_viejas(dias: int = 15, guardar_mensaje: bool = False) -> int:
    from .models import Requisicion
    fecha_limite = datetime.now(pytz.UTC) - timedelta(days=dias)
    try:
        requisiciones = (
            Requisicion.query
            .filter(Requisicion.estado.in_(ESTADOS_HISTORICOS_REQUISICION))
            .filter(Requisicion.fecha_creacion < fecha_limite)
            .all()
        )

        eliminadas = 0
        subidas = 0

        for req in requisiciones:
            subida_exitosa = True

            if not req.url_pdf_drive:
                try:
                    pdf_bytes = generar_pdf_requisicion(req)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(pdf_bytes)
                        tmp.flush()
                        nombre = f"requisicion_{req.numero_requisicion}.pdf"
                        url = subir_pdf_a_drive(nombre, tmp.name)
                    os.remove(tmp.name)

                    if url:
                        req.url_pdf_drive = url
                        db.session.commit()
                        app.logger.info(f"Requisicion {req.id} subida a Drive")
                        subidas += 1
                    else:
                        subida_exitosa = False
                except Exception as exc:
                    db.session.rollback()
                    app.logger.error(
                        f"Error generando/subiendo PDF de requisicion {req.id}: {exc}",
                        exc_info=True,
                    )
                    subida_exitosa = False

            if subida_exitosa and req.url_pdf_drive:
                try:
                    db.session.delete(req)
                    db.session.commit()
                    eliminadas += 1
                    app.logger.info(f"Requisicion {req.id} eliminada")
                except Exception as exc:
                    db.session.rollback()
                    app.logger.error(
                        f"Error eliminando requisicion {req.id}: {exc}", exc_info=True
                    )

        if guardar_mensaje and eliminadas:
            session["notificacion_limpieza"] = (
                f"Se eliminaron {eliminadas} requisiciones del sistema. {subidas} PDFs fueron subidos a Drive."
            )

        app.logger.info(
            f"limpiar_requisiciones_viejas: {subidas} subidas, {eliminadas} eliminadas"
        )
        return eliminadas

    except Exception as exc:
        db.session.rollback()
        app.logger.error(
            f"Error en limpiar_requisiciones_viejas: {exc}", exc_info=True
        )
        return 0
