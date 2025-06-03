import os
import pytest
from uuid import uuid4

# Configurar password de administrador para pruebas
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from app import app as flask_app, db, crear_datos_iniciales, Usuario, Rol, Departamento, Requisicion


def crear_usuario(username: str, rol_nombre: str, password: str = "test") -> Usuario:
    """Helper para crear usuarios durante las pruebas."""
    rol = Rol.query.filter_by(nombre=rol_nombre).first()
    departamento = Departamento.query.first()
    usuario = Usuario(
        username=username,
        cedula=f"V{uuid4().hex[:6]}",
        email=f"{username}_{uuid4().hex[:4]}@example.com",
        nombre_completo=username.capitalize(),
        rol_id=rol.id if rol else None,
        departamento_id=departamento.id if departamento else None,
        activo=True,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def app():
    """Instancia de la aplicación configurada para pruebas."""
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
    )
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def setup_db(app):
    """Crea y limpia la base de datos para cada prueba."""
    with app.app_context():
        db.create_all()
        crear_datos_iniciales()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user(app, setup_db):
    with app.app_context():
        usuario = Usuario.query.filter_by(username="admin").first()
        if usuario:
            return usuario
        return crear_usuario("admin", "Admin", password="admin123")


@pytest.fixture
def compras_user(app, setup_db):
    with app.app_context():
        usuario = Usuario.query.filter_by(username="compras_test").first()
        if usuario:
            return usuario
        return crear_usuario("compras_test", "Compras")


@pytest.fixture
def historial(app, setup_db, admin_user):
    """Lista de requisiciones en estado Finalizada o Rechazada."""
    with app.app_context():
        requisiciones = []
        for estado in ["Finalizada", "Rechazada"]:
            req = Requisicion(
                numero_requisicion=f"RQH{uuid4().hex[:6]}",
                nombre_solicitante=admin_user.nombre_completo,
                cedula_solicitante=admin_user.cedula,
                correo_solicitante=admin_user.email,
                departamento_id=admin_user.departamento_id,
                prioridad="Media",
                observaciones="historial",
                creador_id=admin_user.id,
                estado=estado,
            )
            db.session.add(req)
            requisiciones.append(req)
        db.session.commit()
        return requisiciones

