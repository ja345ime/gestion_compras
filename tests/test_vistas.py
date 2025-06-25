
import pytest
from flask import url_for
from app import create_app, db
from app.models import Usuario, Rol
from flask_login import login_user
from .conftest import crear_usuario

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
    """Crear usuario con todos los campos usando helper de conftest."""
    with client.application.app_context():
        return crear_usuario(username, rol_nombre, password="123")

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
    user = crear_usuario_test(client, "superadmin1", "Superadmin")
    login(client, "superadmin1")
    resp = client.get(ruta, follow_redirects=True)
    assert resp.status_code == 200 or resp.status_code == 302  # Redirección válida también
