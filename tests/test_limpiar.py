import pytz
from datetime import datetime, timedelta
from uuid import uuid4

from app import db
from app.models import Requisicion, Usuario
from app import limpiar_requisiciones_viejas
from app import generar_pdf_requisicion


def crear_requisicion(usuario, estado, dias_ago, url=None):
    req = Requisicion(
        numero_requisicion=f"RQ{estado[:3].upper()}-{dias_ago}",
        nombre_solicitante=usuario.nombre_completo,
        cedula_solicitante=usuario.cedula,
        correo_solicitante=usuario.email,
        departamento_id=usuario.departamento_id,
        prioridad='Media',
        observaciones='test',
        creador_id=usuario.id,
        estado=estado,
        fecha_creacion=datetime.now(pytz.UTC) - timedelta(days=dias_ago),
        url_pdf_drive=url,
    )
    db.session.add(req)
    db.session.commit()
    return req


def get_or_create_admin():
    from app.models import Usuario, Rol, Departamento
    from app import db as app_db
    from uuid import uuid4
    admin = Usuario.query.filter_by(username='admin').first()
    if not admin:
        rol = Rol.query.filter_by(nombre='Admin').first()
        if not rol:
            rol = Rol(nombre='Admin', descripcion='Admin')
            app_db.session.add(rol)
            app_db.session.commit()
        departamento = Departamento.query.first()
        if not departamento:
            departamento = Departamento(nombre=f"Dept-{uuid4().hex[:6]}")
            app_db.session.add(departamento)
            app_db.session.commit()
        admin = Usuario(
            username='admin',
            cedula=f"V{uuid4().hex[:6]}",
            email=f"admin_{uuid4().hex[:4]}@example.com",
            nombre_completo='Administrador',
            rol_id=rol.id,
            departamento_id=departamento.id,
            activo=True,
            superadmin=True
        )
        admin.set_password("admin123")
        app_db.session.add(admin)
        app_db.session.commit()
    return admin


def test_generar_pdf_requisicion_genera_pdf_valido(app):
    with app.app_context():
        admin = get_or_create_admin()
        req = crear_requisicion(admin, 'Pendiente de Revisión Almacén', 0)
        pdf_bytes = generar_pdf_requisicion(req)
        assert pdf_bytes[:4] == b'%PDF'
        assert req.numero_requisicion.encode('latin-1') in pdf_bytes


def test_limpiar_elimina_historicas_y_sube_pdf(app, mocker):
    with app.app_context():
        admin = get_or_create_admin()
        r1 = crear_requisicion(admin, 'Cerrada', 20)
        r2 = crear_requisicion(admin, 'Comprada', 18, url='http://drive/existente')
        crear_requisicion(admin, 'Pendiente de Revisión Almacén', 25)

        mocker.patch('app.utils.generar_pdf_requisicion', return_value=b'data')
        subir = mocker.patch('app.utils.subir_pdf_a_drive', return_value='http://drive/nuevo')

        eliminadas = limpiar_requisiciones_viejas(15)
        # Se eliminan tanto las que ya tienen url_pdf_drive como las que suben el PDF exitosamente
        assert eliminadas == 2
        # r2 tiene url_pdf_drive, debe ser eliminada
        assert db.session.get(Requisicion, r2.id) is None
        # r1 solo se elimina si la subida es exitosa, pero el mock simula éxito solo para la primera
        subir.assert_called_once()
        restantes = Requisicion.query.count()
        assert restantes == 1


def test_no_elimina_si_falla_subida(app, mocker):
    with app.app_context():
        admin = get_or_create_admin()
        r1 = crear_requisicion(admin, 'Cerrada', 20)

        mocker.patch('app.utils.generar_pdf_requisicion', return_value=b'data')
        mocker.patch('app.utils.subir_pdf_a_drive', return_value=None)

        eliminadas = limpiar_requisiciones_viejas(15)
        assert eliminadas == 0
        assert db.session.get(Requisicion, r1.id) is not None

