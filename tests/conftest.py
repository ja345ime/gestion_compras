import pytest
from app import create_app, db
from config import Config
import os

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture(scope='module')
def crear_usuario():
    def _crear_usuario(nombre="Test", email="test@example.com", rol="Solicitante"):
        usuario = Usuario(nombre=nombre, email=email, rol=rol)
        db.session.add(usuario)
        db.session.commit()
        return usuario
    return _crear_usuario








def test_client():
    flask_app = create_app(config_class=TestConfig)

    # Create a test client using the Flask application configured for testing
    with flask_app.test_client() as testing_client:
        with flask_app.app_context():
            db.create_all()
            yield testing_client
            db.drop_all()
