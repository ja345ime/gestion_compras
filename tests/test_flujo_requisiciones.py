import pytest
from uuid import uuid4
from unittest.mock import call
from app import app as flask_app, db, crear_datos_iniciales
from app.models import Usuario, Rol, Departamento, Requisicion
from app.requisiciones.constants import ESTADO_INICIAL_REQUISICION
from app.services.requisicion_service import  requisicion_service

@pytest.fixture
def app(tmp_path):
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI='sqlite:///' + str(tmp_path / 'test.db')
    )
    with flask_app.app_context():
        db.create_all()
        crear_datos_iniciales(Rol, Departamento, Usuario)
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()


def crear_usuario(
    username: str,
    rol_nombre: str,
    password: str = 'test',
    cedula: str | None = None,
    email: str | None = None,
):
    """Crea un usuario para pruebas garantizando unicidad en cédula y correo."""
    rol = Rol.query.filter_by(nombre=rol_nombre).first()
    if not rol:
        rol = Rol(nombre=rol_nombre, descripcion=f"Rol {rol_nombre}")
        db.session.add(rol)
        db.session.commit()

    departamento = Departamento.query.first()
    if not departamento:
        departamento = Departamento(nombre=f"Dept-{uuid4().hex[:6]}")
        db.session.add(departamento)
        db.session.commit()

    usuario = Usuario(
        username=username,
        cedula=cedula or f"V{uuid4().hex[:6]}",
        email=email or f"{username}_{uuid4().hex[:4]}@example.com",
        nombre_completo=username.capitalize(),
        rol_id=rol.id,
        departamento_id=departamento.id,
        activo=True,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def login(client, username: str, password: str = 'test'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def crear_requisicion_para(usuario: Usuario):
    req = Requisicion(
        numero_requisicion='RQTEST',
        nombre_solicitante=usuario.nombre_completo,
        cedula_solicitante=usuario.cedula,
        correo_solicitante=usuario.email,
        departamento_id=usuario.departamento_id,
        prioridad='Alta',
        observaciones='test',
        creador_id=usuario.id,
        estado=ESTADO_INICIAL_REQUISICION
    )
    db.session.add(req)
    db.session.commit()
    return req


def test_creacion_requisicion_envia_correos(client, mocker):
    enviar = mocker.patch('app.enviar_correo')
    almacen_user = crear_usuario('alm_test', 'Almacen')
    solicitante = crear_usuario('solicitante', 'Solicitante')
    login(client, 'solicitante')

    data = {
        'nombre_solicitante': 'Solicitante Test',
        'cedula_solicitante': 'V12345678',
        'correo_solicitante': 'sol@example.com',
        'departamento_nombre': Departamento.query.first().nombre,
        'prioridad': 'Alta',
        'observaciones': 'Prueba',
        'detalles-0-producto': 'Producto X',
        'detalles-0-cantidad': '1',
        'detalles-0-unidad_medida': 'Unidad'
    }

    response = client.post('/requisiciones/crear', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert enviar.call_count == 2
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)
    assert any(almacen_user.email in dest for dest in destinatarios_list)


def test_aprobacion_por_almacen_envia_a_compras(app, mocker):
    enviar = mocker.patch('app.enviar_correo')
    solicitante = crear_usuario('sol2', 'Solicitante')
    compras_user = crear_usuario('comprador_test', 'Compras')
    almacen_user = crear_usuario('almacen_apr', 'Almacen')
    req = crear_requisicion_para(solicitante)

    cambiar_estado_requisicion(req.id, 'Aprobada por Almacén', almacen_user, None, Usuario, Rol)
    db.session.refresh(req)
    assert req.estado == 'Aprobada por Almacén'

    assert enviar.call_count == 2
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(compras_user.email in dest for dest in destinatarios_list)
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_rechazo_por_almacen_envia_motivo(app, mocker):
    enviar = mocker.patch('app.enviar_correo')
    solicitante = crear_usuario('sol3', 'Solicitante')
    almacen_user = crear_usuario('almacen_rech', 'Almacen')
    req = crear_requisicion_para(solicitante)

    cambiar_estado_requisicion(
        req.id, 'Rechazada por Almacén', almacen_user, 'Falta stock', Usuario, Rol
    )
    assert enviar.call_count >= 1
    args = enviar.call_args[0]
    html = args[2].lower()
    assert 'falta stock' in html
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_aprobacion_por_compras_envia_correo(app, mocker):
    enviar = mocker.patch('app.enviar_correo')
    solicitante = crear_usuario('sol4', 'Solicitante')
    almacen_user = crear_usuario('alm_apr_comp', 'Almacen')
    compras_act = crear_usuario('compras_act', 'Compras')
    req = crear_requisicion_para(solicitante)
    cambiar_estado_requisicion(req.id, 'Aprobada por Almacén', almacen_user, None, Usuario, Rol)

    cambiar_estado_requisicion(req.id, 'Aprobada por Compras', compras_act, None, Usuario, Rol)
    db.session.refresh(req)
    assert req.estado == 'Aprobada por Compras'
    assert enviar.call_count >= 1
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_pendiente_cotizar_envia_correo_a_compras(app, mocker):
    enviar = mocker.patch('app.enviar_correo')
    solicitante = crear_usuario('solpc', 'Solicitante')
    compras_user = crear_usuario('compraspc', 'Compras')
    almacen_user = crear_usuario('alm_pc', 'Almacen')
    req = crear_requisicion_para(solicitante)
    cambiar_estado_requisicion(req.id, 'Aprobada por Almacén', almacen_user, None, Usuario, Rol)
    enviar.reset_mock()

    cambiar_estado_requisicion(req.id, 'Pendiente de Cotizar', compras_user, None, Usuario, Rol)
    db.session.refresh(req)
    assert req.estado == 'Pendiente de Cotizar'
    assert enviar.call_count == 2
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(compras_user.email in dest for dest in destinatarios_list)
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_cambio_a_comprada_historial(app, client, mocker):
    enviar = mocker.patch('app.enviar_correo')
    solicitante = crear_usuario('sol5', 'Solicitante')
    compras_user = crear_usuario('comprador', 'Compras')
    almacen_user = crear_usuario('alm_hist', 'Almacen')
    req = crear_requisicion_para(solicitante)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Almacén', almacen_user, None)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Compras', compras_user, None)
    requisicion_service.cambiar_estado(req.id, 'En Proceso de Compra', compras_user, None)
    requisicion_service.cambiar_estado(req.id, 'Comprada', compras_user, None)

    login(client, 'comprador')
    resp = client.get('/requisiciones/historial')
    assert b'RQTEST' in resp.data


def test_visibilidad_requisiciones_por_rol(app, client):
    solicitante = crear_usuario('sol6', 'Solicitante')
    almacen = crear_usuario('almacen_user', 'Almacen')
    compras_user = crear_usuario('compras_user', 'Compras')
    req = crear_requisicion_para(solicitante)

    # visible para solicitante
    login(client, 'sol6')
    resp = client.get('/requisiciones')
    assert b'RQTEST' in resp.data

    # visible para almacen
    login(client, 'almacen_user')
    resp = client.get('/requisiciones')
    assert b'RQTEST' in resp.data

    # no visible para compras hasta que pase a su estado
    login(client, 'compras_user')
    print("Estado actual:", req.estado)
    resp = client.get('/requisiciones')
    if req.estado == 'Pendiente de Revisión Almacén':
        assert b'RQTEST' not in resp.data
    else:
        print("La requisición ya fue procesada por Almacén y es visible para Compras.")

    cambiar_estado_requisicion(req.id, 'Aprobada por Almacén', almacen, None, Usuario, Rol)
    resp = client.get('/requisiciones')
    assert b'RQTEST' in resp.data


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main())
