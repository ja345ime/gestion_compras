
import pytest
from unittest.mock import patch
from app.utils import enviar_correo, generar_mensaje_correo
from app.models import Usuario, Requisicion

@pytest.fixture
def requisicion_mock():
    class Req:
        numero_requisicion = "REQ-001"
        prioridad = "Alta"
        estado = "Aprobada por Almacén"
        observaciones = "Urgente"
        solicitante = Usuario(nombre_usuario="jaime", email="jaime@test.com")
    return Req()

@patch("app.utils.enviar_correo_api")
def test_envio_correo_a_solicitante(mock_enviar, requisicion_mock):
    mensaje = generar_mensaje_correo("Solicitante", requisicion_mock, "Aprobada por Almacén", "")
    enviar_correo(["jaime@test.com"], "Prueba de correo", mensaje)
    assert mock_enviar.called
    assert "REQUISICIÓN" in mensaje
    assert "jaime@test.com" in str(mock_enviar.call_args)
