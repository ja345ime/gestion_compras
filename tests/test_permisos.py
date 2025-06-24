import pytest
import pytz
from datetime import datetime, timedelta
from app import db, Usuario, Rol, Departamento, Requisicion, AuditoriaAcciones


def crear_requisicion_prueba(usuario: Usuario, estado: str = None, dias_atras: int = 0) -> Requisicion:
    """Crea y guarda en BD una requisicion de prueba para el usuario dado."""
    req = Requisicion(
        numero_requisicion='RQTEST',
        nombre_solicitante=usuario.nombre_completo,
        cedula_solicitante=usuario.cedula,
        correo_solicitante=usuario.email,
        departamento_id=usuario.departamento_id or Departamento.query.first().id,
        prioridad='Alta',
        observaciones='Prueba',
        creador_id=usuario.id,
        estado=estado or 'Pendiente Revisión Almacén'
    )
    if dias_atras:
        req.fecha_creacion = datetime.now(pytz.UTC) - timedelta(days=dias_atras)
    db.session.add(req)
    db.session.commit()
    return req


def test_solicitante_puede_editar_su_requisicion_en_30min(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_edit',
            cedula='V11223344',
            email='sol_edit@example.com',
            nombre_completo='Sol Edit',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        req = crear_requisicion_prueba(user)
        req_id = req.id
    client.post('/login', data={'username': 'sol_edit', 'password': 'pass123'}, follow_redirects=True)
    resp = client.get(f'/requisicion/{req_id}/editar')
    assert resp.status_code == 200
    assert b'RQTEST' in resp.data


def test_solicitante_no_edita_despues_30min(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_edit2',
            cedula='V44332211',
            email='sol_edit2@example.com',
            nombre_completo='Sol Edit2',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        req = crear_requisicion_prueba(user, dias_atras=1)
        req_id = req.id
    client.post('/login', data={'username': 'sol_edit2', 'password': 'pass123'}, follow_redirects=True)
    resp = client.get(f'/requisicion/{req_id}/editar', follow_redirects=True)
    assert resp.status_code == 200
    assert b'No tiene permiso para editar' in resp.data


def test_solicitante_no_edita_despues_cambio_estado(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_edit3',
            cedula='V55667788',
            email='sol_edit3@example.com',
            nombre_completo='Sol Edit3',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        req = crear_requisicion_prueba(user)
        req.estado = 'Aprobada por Almacén'
        db.session.commit()
        req_id = req.id
    client.post('/login', data={'username': 'sol_edit3', 'password': 'pass123'}, follow_redirects=True)
    resp = client.get(f'/requisicion/{req_id}/editar', follow_redirects=True)
    assert resp.status_code == 200
    assert b'No tiene permiso para editar' in resp.data


def test_otro_usuario_no_puede_editar_requisicion(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user1 = Usuario(
            username='sol_owner',
            cedula='V12121212',
            email='owner@example.com',
            nombre_completo='Owner User',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user1.set_password('pass123')
        user2 = Usuario(
            username='sol_other',
            cedula='V34343434',
            email='other@example.com',
            nombre_completo='Other User',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user2.set_password('pass123')
        db.session.add_all([user1, user2])
        db.session.commit()
        req = crear_requisicion_prueba(user1)
        req_id = req.id
    client.post('/login', data={'username': 'sol_other', 'password': 'pass123'}, follow_redirects=True)
    resp = client.get(f'/requisicion/{req_id}/editar', follow_redirects=True)
    assert resp.status_code == 200
    assert b'No tiene permiso para editar' in resp.data


def test_admin_puede_editar_siempre(app, client):
    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='Admin').first()
        admin = Usuario(
            username='admin_edit',
            cedula='V90909090',
            email='admin_edit@example.com',
            nombre_completo='Admin Editor',
            rol_id=rol_admin.id,
            departamento_id=None,
            activo=True,
            superadmin=False
        )
        admin.set_password('pass123')
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_time',
            cedula='V78787878',
            email='sol_time@example.com',
            nombre_completo='Sol Time',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add_all([admin, user])
        db.session.commit()
        req = crear_requisicion_prueba(user, dias_atras=5)
        req_id = req.id
    client.post('/login', data={'username': 'admin_edit', 'password': 'pass123'}, follow_redirects=True)
    resp = client.get(f'/requisicion/{req_id}/editar')
    assert resp.status_code == 200
    assert b'RQTEST' in resp.data


def test_solicitante_puede_eliminar_en_30min(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_del',
            cedula='V56565656',
            email='sol_del@example.com',
            nombre_completo='Sol Delete',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        req = crear_requisicion_prueba(user)
        req_id = req.id
    client.post('/login', data={'username': 'sol_del', 'password': 'pass123'}, follow_redirects=True)
    get_resp = client.get(f'/requisicion/{req_id}/confirmar_eliminar')
    assert get_resp.status_code == 200
    resp = client.post(f'/requisicion/{req_id}/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Requisicion.query.get(req_id) is None
        log = AuditoriaAcciones.query.filter_by(modulo='Requisiciones', objeto='RQTEST', accion='eliminar').first()
        assert log is not None
        assert log.usuario_id == Usuario.query.filter_by(username='sol_del').first().id


def test_solicitante_no_elimina_despues_30min(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_del2',
            cedula='V56565657',
            email='sol_del2@example.com',
            nombre_completo='Sol Delete2',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add(user)
        db.session.commit()
        req = crear_requisicion_prueba(user)
        req.fecha_creacion = datetime.now(pytz.UTC) - timedelta(days=1)
        db.session.commit()
        req_id = req.id
    client.post('/login', data={'username': 'sol_del2', 'password': 'pass123'}, follow_redirects=True)
    resp = client.post(f'/requisicion/{req_id}/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Requisicion.query.get(req_id) is not None
        log = AuditoriaAcciones.query.filter_by(modulo='Requisiciones', objeto='RQTEST', accion='eliminar').first()
        assert log is None


def test_otro_usuario_no_puede_eliminar_requisicion(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        owner = Usuario(
            username='sol_owner2',
            cedula='V23232323',
            email='owner2@example.com',
            nombre_completo='Owner User2',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        owner.set_password('pass123')
        other = Usuario(
            username='sol_other2',
            cedula='V45454545',
            email='other2@example.com',
            nombre_completo='Other User2',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        other.set_password('pass123')
        db.session.add_all([owner, other])
        db.session.commit()
        req = crear_requisicion_prueba(owner)
        req_id = req.id
    client.post('/login', data={'username': 'sol_other2', 'password': 'pass123'}, follow_redirects=True)
    resp = client.post(f'/requisicion/{req_id}/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Requisicion.query.get(req_id) is not None
        log = AuditoriaAcciones.query.filter_by(modulo='Requisiciones', objeto='RQTEST', accion='eliminar').first()
        assert log is None


def test_admin_puede_eliminar_cualquier_requisicion(app, client):
    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='Admin').first()
        admin = Usuario(
            username='admin_del',
            cedula='V97979797',
            email='admindel@example.com',
            nombre_completo='Admin Delete',
            rol_id=rol_admin.id,
            departamento_id=None,
            activo=True
        )
        admin.set_password('pass123')
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        user = Usuario(
            username='sol_target',
            cedula='V21212121',
            email='targetreq@example.com',
            nombre_completo='Target Req',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        user.set_password('pass123')
        db.session.add_all([admin, user])
        db.session.commit()
        req = crear_requisicion_prueba(user)
        req.fecha_creacion = datetime.now(pytz.UTC) - timedelta(days=10)
        db.session.commit()
        req_id = req.id
    client.post('/login', data={'username': 'admin_del', 'password': 'pass123'}, follow_redirects=True)
    resp = client.post(f'/requisicion/{req_id}/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Requisicion.query.get(req_id) is None
        log = AuditoriaAcciones.query.filter_by(modulo='Requisiciones', objeto='RQTEST', accion='eliminar').first()
        assert log is not None
        assert log.usuario_id == Usuario.query.filter_by(username='admin_del').first().id


def test_no_permiso_cambio_estado_por_rol_incorrecto(app, client):
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        solicitante = Usuario(
            username='sol_estado',
            cedula='V66665555',
            email='solestado@example.com',
            nombre_completo='Sol Estado',
            rol_id=rol_sol.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        solicitante.set_password('pass123')
        rol_alm = Rol.query.filter_by(nombre='Almacen').first()
        almacen = Usuario(
            username='alm_estado',
            cedula='V88880000',
            email='almestado@example.com',
            nombre_completo='Alm Estado',
            rol_id=rol_alm.id,
            departamento_id=Departamento.query.first().id,
            activo=True
        )
        almacen.set_password('pass123')
        db.session.add_all([solicitante, almacen])
        db.session.commit()
        req = crear_requisicion_prueba(solicitante)
        req_id = req.id
    client.post('/login', data={'username': 'sol_estado', 'password': 'pass123'}, follow_redirects=True)
    resp = client.post(f'/requisicion/{req_id}', data={'estado': 'Aprobada por Almacén', 'comentario_estado': ''}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'No tiene permiso para cambiar el estado' in resp.data or b'no valid' in resp.data.lower()
    client.get('/logout')
    client.post('/login', data={'username': 'alm_estado', 'password': 'pass123'}, follow_redirects=True)
    resp2 = client.post(f'/requisicion/{req_id}', data={'estado': 'Aprobada por Almacén', 'comentario_estado': ''}, follow_redirects=True)
    assert resp2.status_code == 200
    with app.app_context():
        req_db = Requisicion.query.get(req_id)
        assert req_db.estado == 'Aprobada por Almacén'
        log = AuditoriaAcciones.query.filter_by(modulo='Requisiciones', objeto=str(req_id), accion='estado:Aprobada por Almacén').first()
        assert log is not None
        assert log.usuario_id == Usuario.query.filter_by(username='alm_estado').first().id
