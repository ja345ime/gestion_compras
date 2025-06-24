import pytz
from datetime import datetime, timedelta

from app import db, Requisicion, Usuario
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


def test_generar_pdf_requisicion_genera_pdf_valido(app):
    """Verifica que la función de generar PDF produce un PDF válido."""
    with app.app_context():
        admin = Usuario.query.filter_by(username='admin').first()
        req = crear_requisicion(admin, 'Pendiente de Revisión Almacén', 0)
        pdf_bytes = generar_pdf_requisicion(req)
        assert pdf_bytes[:4] == b'%PDF'
        numero = req.numero_requisicion
        assert numero.encode('latin-1') in pdf_bytes


def test_limpiar_elimina_historicas_y_sube_pdf(app, mocker):
    with app.app_context():
        admin = Usuario.query.filter_by(username='admin').first()
        r1 = crear_requisicion(admin, 'Cerrada', 20)
        r2 = crear_requisicion(admin, 'Comprada', 18, url='http://drive/existente')
        crear_requisicion(admin, 'Pendiente de Revisión Almacén', 25)

        mocker.patch('app.generar_pdf_requisicion', return_value=b'data')
        subir = mocker.patch('app.subir_pdf_a_drive', return_value='http://drive/nuevo')

        eliminadas = limpiar_requisiciones_viejas(15)
        assert eliminadas == 2
        assert db.session.get(Requisicion, r1.id) is None
        assert db.session.get(Requisicion, r2.id) is None
        subir.assert_called_once()
        restantes = Requisicion.query.count()
        assert restantes == 1


def test_no_elimina_si_falla_subida(app, mocker):
    with app.app_context():
        admin = Usuario.query.filter_by(username='admin').first()
        r1 = crear_requisicion(admin, 'Cerrada', 20)

        mocker.patch('app.generar_pdf_requisicion', return_value=b'data')
        mocker.patch('app.subir_pdf_a_drive', return_value=None)

        eliminadas = limpiar_requisiciones_viejas(15)
        assert eliminadas == 0
        assert db.session.get(Requisicion, r1.id) is not None

