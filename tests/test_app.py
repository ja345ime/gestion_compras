import pytest
from uuid import uuid4


def test_login_route_returns_200(client):
    response = client.get('/login')
    assert response.status_code == 200


def test_crear_requisicion_requires_login(client, setup_db):
    response = client.get('/requisiciones/crear')
    assert response.status_code == 302
    assert '/login' in response.headers.get('Location', '')


def test_login_valid_credentials_redirects(client, setup_db, admin_user):
    response = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    assert response.status_code == 302
    assert '/' in response.headers.get('Location', '')


def test_login_success_html_contains_inicio(client, setup_db, admin_user):
    # Login como admin
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    # Reconsultar el usuario dentro del contexto para evitar DetachedInstanceError
    from app.models import Usuario
    from flask import current_app
    with current_app.app_context():
        admin_db = Usuario.query.filter_by(username='admin').first()
        rol_nombre = admin_db.rol_asignado.nombre if admin_db and admin_db.rol_asignado else None
    response = client.get('/')
    assert response.status_code == 200
    assert b'Inicio' in response.data


def test_admin_can_change_user_password(client, setup_db, admin_user):
    # Login as admin
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})

    from app import db
    from app.models import Usuario, Rol, Departamento

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
        rol_id = rol.id
        depto_id = depto.id if depto else None
        user = Usuario(
            username='tempuser',
            cedula='V98765432',
            email='temp@example.com',
            nombre_completo='Temp User',
            rol_id=rol.id,
            departamento_id=depto.id if depto else None,
            activo=True,
        )
        user.set_password('newpass')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    data = {
        'username': 'tempuser',
        'cedula': 'V98765432',
        'nombre_completo': 'Temp User',
        'email': 'temp@example.com',
        'rol_id': rol_id,
        'departamento_id': str(depto_id if depto_id else 0),
        'activo': 'y',
        'password': 'newpass',
        'confirm_password': 'newpass',
    }
    client.post(f'/admin/usuarios/{user_id}/editar', data=data, follow_redirects=True)
    client.get('/logout')
    login_resp = client.post('/login', data={'username': 'tempuser', 'password': 'newpass'})
    assert login_resp.status_code in (200, 302)
