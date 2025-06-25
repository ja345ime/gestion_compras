
import pytest
from flask import url_for
from app import create_app, db
from app.models import Usuario, Rol
from flask_login import login_user

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

def crear_usuario(client, username, rol_nombre):
    rol = Rol(nombre=rol_nombre)
    db.session.add(rol)
    db.session.commit()
    user = Usuario(username=username, rol_id=rol.id, password_hash='123')
    db.session.add(user)
    db.session.commit()
    return user

def login(client, username):
    return client.post('/login', data={'username': username, 'password': '123'}, follow_redirects=True)

@pytest.mark.parametrize("ruta", [
    "/",
    "/login",
    "/logout",
    "/dashboard",
    "/requisiciones",
    "/requisiciones/historial",
    "/requisiciones/pendientes_cotizar",
    "/requisiciones/cotizadas",
    "/admin/usuarios",
])
def test_vistas_basicas_cargan(client, ruta):
    # Crear y loguear como superadmin para todas las vistas
    user = crear_usuario(client, "superadmin1", "Superadmin")
    login(client, "superadmin1")
    resp = client.get(ruta, follow_redirects=True)
    assert resp.status_code == 200 or resp.status_code == 302  # Redirección válida también
