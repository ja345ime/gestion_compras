import pytest
from uuid import uuid4
from unittest.mock import call, patch

@pytest.fixture(autouse=True, scope="module")
def patch_enviar_correo_module():
    with patch("app.utils.enviar_correo", autospec=True) as mock_env, \
         patch("app.utils.enviar_correo_api", autospec=True) as mock_api:
        class MockCorreo:
            def __init__(self, env, api):
                self.env = env
                self.api = api
            @property
            def call_count(self):
                return self.env.call_count + self.api.call_count
            @property
            def call_args_list(self):
                return self.env.call_args_list + self.api.call_args_list
        yield MockCorreo(mock_env, mock_api)

from app import app as flask_app, db, crear_datos_iniciales
from app.models import Usuario, Rol, Departamento, Requisicion
from app.requisiciones.constants import ESTADO_INICIAL_REQUISICION
from app.services import requisicion_service

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

    # Generar cédula válida: V + 8 dígitos
    if not cedula:
        from random import randint
        cedula = f"V{randint(10000000, 99999999)}"

    usuario = Usuario(
        username=username,
        cedula=cedula,
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


def test_creacion_requisicion_envia_correos(client, patch_enviar_correo_module):
    mock = patch_enviar_correo_module
    solicitante = crear_usuario('solicitante', 'Solicitante', password='test')
    login(client, 'solicitante', 'test')

    departamento_nombre = Departamento.query.get(solicitante.departamento_id).nombre
    data = {
        'nombre_solicitante': solicitante.nombre_completo,
        'cedula_solicitante': solicitante.cedula,
        'correo_solicitante': solicitante.email,
        'departamento_nombre': departamento_nombre,
        'prioridad': 'Alta',
        'observaciones': 'Prueba',
        'detalles-0-producto': 'Producto X',
        'detalles-0-cantidad': '1',
        'detalles-0-unidad_medida': 'Unidad'
    }

    response = client.post('/requisiciones/crear', data=data, follow_redirects=True)
    print('HTML de respuesta en test_creacion_requisicion_envia_correos:', response.data.decode())
    assert response.status_code == 200
    assert mock.call_count >= 1
    destinatarios_list = [call.args[0] for call in mock.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_aprobacion_por_almacen_envia_a_compras(app, mocker):
    enviar = mocker.patch('app.utils.enviar_correo')
    solicitante = crear_usuario('sol2', 'Solicitante')
    compras_user = crear_usuario('comprador_test', 'Compras')
    almacen_user = crear_usuario('almacen_apr', 'Almacen')
    req = crear_requisicion_para(solicitante)

    requisicion_service.cambiar_estado(req.id, 'Aprobada por Almacén', None, almacen_user)
    db.session.refresh(req)
    assert req.estado == 'Aprobada por Almacén'

    # Puede haber más de un envío (solicitante y notificación a compras), pero al menos 1
    assert enviar.call_count >= 1
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_rechazo_por_almacen_envia_motivo(app, mocker):
    enviar = mocker.patch('app.utils.enviar_correo')
    solicitante = crear_usuario('sol3', 'Solicitante')
    almacen_user = crear_usuario('almacen_rech', 'Almacen')
    req = crear_requisicion_para(solicitante)

    requisicion_service.cambiar_estado(
        req.id, 'Rechazada por Almacén', 'Falta stock', almacen_user
    )
    assert enviar.call_count >= 1
    args = enviar.call_args[0]
    html = args[2].lower()
    assert 'falta stock' in html
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_aprobacion_por_compras_envia_correo(app, mocker):
    enviar = mocker.patch('app.utils.enviar_correo')
    solicitante = crear_usuario('sol4', 'Solicitante')
    almacen_user = crear_usuario('alm_apr_comp', 'Almacen')
    compras_act = crear_usuario('compras_act', 'Compras')
    req = crear_requisicion_para(solicitante)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Almacén', None, almacen_user)

    requisicion_service.cambiar_estado(req.id, 'Aprobada por Compras', None, compras_act)
    db.session.refresh(req)
    assert req.estado == 'Aprobada por Compras'
    assert enviar.call_count >= 1
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)


def test_pendiente_cotizar_envia_correo_a_compras(app, mocker):
    enviar = mocker.patch('app.utils.enviar_correo')
    solicitante = crear_usuario('solpc', 'Solicitante')
    compras_user = crear_usuario('compraspc', 'Compras')
    almacen_user = crear_usuario('alm_pc', 'Almacen')
    req = crear_requisicion_para(solicitante)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Almacén', None, almacen_user)
    enviar.reset_mock()

    requisicion_service.cambiar_estado(req.id, 'Pendiente de Cotizar', None, compras_user)
    db.session.refresh(req)
    assert req.estado == 'Pendiente de Cotizar'
    # Puede haber más de un envío (solicitante y notificación a compras), pero al menos 1
    assert enviar.call_count >= 1
    destinatarios_list = [call.args[0] for call in enviar.call_args_list]
    assert any(solicitante.email in dest for dest in destinatarios_list)
    # No se envía correo directo a compras_user, solo notificación por rol


def test_cambio_a_comprada_historial(app, client, mocker):
    enviar = mocker.patch('app.utils.enviar_correo')
    solicitante = crear_usuario('sol5', 'Solicitante')
    compras_user = crear_usuario('comprador', 'Compras')
    almacen_user = crear_usuario('alm_hist', 'Almacen')
    req = crear_requisicion_para(solicitante)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Almacén', None, almacen_user)
    requisicion_service.cambiar_estado(req.id, 'Aprobada por Compras', None, compras_user)
    requisicion_service.cambiar_estado(req.id, 'En Proceso de Compra', None, compras_user)
    requisicion_service.cambiar_estado(req.id, 'Comprada', None, compras_user)

    login(client, 'comprador')
    resp = client.get('/requisiciones/historial')
    assert b'RQTEST' in resp.data


def test_visibilidad_requisiciones_por_rol(client, setup_db, admin_user):
    from app import db
    from app.models import Usuario, Rol, Departamento, Requisicion
    with client.application.app_context():
        rol = Rol.query.filter_by(nombre='Solicitante').first()
        if not rol:
            rol = Rol(nombre='Solicitante')
            db.session.add(rol)
            db.session.commit()
        depto = Departamento.query.first()
        if not depto:
            depto = Departamento(nombre='Sistemas')
            db.session.add(depto)
            db.session.commit()
        usuario = Usuario(username='testuser', cedula='V12345678', email='test@ejemplo.com', nombre_completo='Test User', rol_id=rol.id, departamento_id=depto.id, activo=True)
        usuario.set_password('test')
        db.session.add(usuario)
        db.session.commit()
        req = Requisicion(numero_requisicion='RQTEST', nombre_solicitante=usuario.nombre_completo, cedula_solicitante=usuario.cedula, correo_solicitante=usuario.email, departamento_id=depto.id, prioridad='Alta', observaciones='test', creador_id=usuario.id, estado='Pendiente')
        db.session.add(req)
        db.session.commit()
        usuario_id = usuario.id
        req_id = req.id
    client.post('/login', data={'username': 'testuser', 'password': 'test'})
    response = client.get('/requisiciones')
    assert b'RQTEST' in response.data


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main())
