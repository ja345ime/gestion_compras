
import pytest
from app import create_app, db
from app.models import Usuario, Rol, Requisicion
from flask_login import login_user
from tests.conftest import crear_usuario

@pytest.fixture
def client():
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def crear_usuario_test(client, username, rol_nombre):
    """Crear usuario utilizando helper de conftest con todos los campos."""
    with client.application.app_context():
        return crear_usuario(username, rol_nombre, password="123")

def login(client, username):
    return client.post('/login', data={'username': username, 'password': '123'}, follow_redirects=True)

def test_superadmin_crea_admin(client):
    user = crear_usuario_test(client, 'superadmin1', 'Superadmin')
    login(client, 'superadmin1')
    resp = client.post('/admin/usuarios/crear', data={
        'username': 'admin1',
        'rol_id': 2,
        'password': '123',
        'confirmar': '123',
        'departamento_id': 1,
        'cedula': '111',
        'email': 'admin1@correo.com'
    }, follow_redirects=True)
    assert b'Usuario creado exitosamente' in resp.data

def test_admin_no_edita_superadmin(client):
    superadmin = crear_usuario_test(client, 'superadmin1', 'Superadmin')
    admin = crear_usuario_test(client, 'admin1', 'Admin')
    login(client, 'admin1')
    resp = client.get(f'/admin/usuarios/editar/{superadmin.id}', follow_redirects=True)
    assert b'No tienes permiso' in resp.data or b'Error' in resp.data

def test_solicitante_ve_solo_sus_requisiciones(client):
    solicitante1 = crear_usuario_test(client, 'user1', 'Solicitante')
    solicitante2 = crear_usuario_test(client, 'user2', 'Solicitante')
    req = Requisicion(creador_id=solicitante1.id, estado='Pendiente')
    db.session.add(req)
    db.session.commit()
    login(client, 'user2')
    resp = client.get('/requisiciones')
    assert b'No hay requisiciones' in resp.data or req.numero_requisicion.encode() not in resp.data
