import pytest

from app import db
from app.models import Usuario, Rol, AuditoriaAcciones


def login_user(client, username: str, password: str):
    """Helper to log in a user via the client and ensure success."""
    resp = client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)
    assert resp.status_code == 200, f"Login failed for user {username}"
    return resp


def test_superadmin_can_create_any_user(app, client):
    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='Admin').first()
        superadmin_user = Usuario(
            username='admin2',
            cedula='V00000222',
            email='admin2@example.com',
            nombre_completo='Administrador2',
            rol_id=rol_admin.id,
            departamento_id=None,
            activo=True,
            superadmin=True,
        )
        superadmin_user.set_password('pass123')
        db.session.add(superadmin_user)
        db.session.commit()
        superadmin_id = superadmin_user.id

    login_user(client, 'admin2', 'pass123')
    with app.app_context():
        rol_superadmin = Rol.query.filter_by(nombre='Superadmin').first()
        rol_admin = Rol.query.filter_by(nombre='Admin').first()

    new_data = {
        'username': 'nuevo_super',
        'cedula': 'V12345000',
        'nombre_completo': 'Nuevo Superadmin',
        'email': 'newsuper@example.com',
        'password': 'abc123',
        'confirm_password': 'abc123',
        'rol_id': rol_superadmin.id,
        'departamento_id': '0',
        'activo': 'y',
    }
    response = client.post('/admin/usuarios/crear', data=new_data, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        nuevo_user = Usuario.query.filter_by(username='nuevo_super').first()
        assert nuevo_user is not None
        assert nuevo_user.rol_asignado.nombre == 'Superadmin'
        assert nuevo_user.superadmin is True
        log = AuditoriaAcciones.query.filter_by(modulo='Usuarios', objeto=nuevo_user.username, accion='crear').first()
        assert log is not None
        assert log.usuario_id == superadmin_id

    new_data['username'] = 'nuevo_admin'
    new_data['cedula'] = 'V12345001'
    new_data['nombre_completo'] = 'Nuevo Admin'
    new_data['email'] = 'newadmin@example.com'
    new_data['rol_id'] = rol_admin.id
    response = client.post('/admin/usuarios/crear', data=new_data, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        nuevo_user2 = Usuario.query.filter_by(username='nuevo_admin').first()
        assert nuevo_user2 is not None
        assert nuevo_user2.rol_asignado.nombre == 'Admin'
        log2 = AuditoriaAcciones.query.filter_by(modulo='Usuarios', objeto=nuevo_user2.username, accion='crear').first()
        assert log2 is not None and log2.usuario_id == superadmin_id


def test_admin_can_create_only_allowed_roles(app, client):
    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='Admin').first()
        admin_user = Usuario(
            username='admin_norm',
            cedula='V00000333',
            email='admin_norm@example.com',
            nombre_completo='Admin Normal',
            rol_id=rol_admin.id,
            departamento_id=None,
            activo=True,
            superadmin=False,
        )
        admin_user.set_password('pass123')
        db.session.add(admin_user)
        db.session.commit()
        admin_id = admin_user.id

    login_user(client, 'admin_norm', 'pass123')
    with app.app_context():
        rol_almacen = Rol.query.filter_by(nombre='Almacen').first()
        rol_compras = Rol.query.filter_by(nombre='Compras').first()

    data_almacen = {
        'username': 'user_almacen',
        'cedula': 'V55555111',
        'nombre_completo': 'User Almacen',
        'email': 'almacen@example.com',
        'password': 'test123',
        'confirm_password': 'test123',
        'rol_id': rol_almacen.id,
        'departamento_id': '0',
        'activo': 'y',
    }
    resp = client.post('/admin/usuarios/crear', data=data_almacen, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        u_almacen = Usuario.query.filter_by(username='user_almacen').first()
        assert u_almacen is not None
        assert u_almacen.rol_asignado.nombre == 'Almacen'
        log = AuditoriaAcciones.query.filter_by(modulo='Usuarios', objeto=u_almacen.username, accion='crear').first()
        assert log is not None and log.usuario_id == admin_id

    data_compras = {
        'username': 'user_compras',
        'cedula': 'V55555112',
        'nombre_completo': 'User Compras',
        'email': 'compras@example.com',
        'password': 'test123',
        'confirm_password': 'test123',
        'rol_id': rol_compras.id,
        'departamento_id': '0',
        'activo': 'y',
    }
    resp = client.post('/admin/usuarios/crear', data=data_compras, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        u_compras = Usuario.query.filter_by(username='user_compras').first()
        assert u_compras is not None
        assert u_compras.rol_asignado.nombre == 'Compras'
        log2 = AuditoriaAcciones.query.filter_by(modulo='Usuarios', objeto=u_compras.username, accion='crear').first()
        assert log2 is not None and log2.usuario_id == admin_id


def test_admin_cannot_create_admin_or_superadmin(app, client):
    login_user(client, 'admin_norm', 'pass123')
    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='Admin').first()
        rol_super = Rol.query.filter_by(nombre='Superadmin').first()

    data = {
        'username': 'user_nope',
        'cedula': 'V99999001',
        'nombre_completo': 'User Nope',
        'email': 'nope@example.com',
        'password': 'test123',
        'confirm_password': 'test123',
        'rol_id': rol_admin.id,
        'departamento_id': '0',
        'activo': 'y',
    }
    resp = client.post('/admin/usuarios/crear', data=data, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(username='user_nope').first() is None
        log = AuditoriaAcciones.query.filter_by(objeto='user_nope', accion='crear').first()
        assert log is None

    data['username'] = 'user_nope2'
    data['cedula'] = 'V99999002'
    data['email'] = 'nope2@example.com'
    data['rol_id'] = rol_super.id
    resp = client.post('/admin/usuarios/crear', data=data, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(username='user_nope2').first() is None
        log2 = AuditoriaAcciones.query.filter_by(objeto='user_nope2', accion='crear').first()
        assert log2 is None


def test_admin_cannot_edit_superadmin(app, client):
    with app.app_context():
        rol_super = Rol.query.filter_by(nombre='Superadmin').first()
        target_user = Usuario(
            username='super_target',
            cedula='V10101010',
            email='target@example.com',
            nombre_completo='Super Target',
            rol_id=rol_super.id,
            departamento_id=None,
            activo=True,
            superadmin=True,
        )
        target_user.set_password('pass123')
        db.session.add(target_user)
        db.session.commit()
        target_id = target_user.id

    login_user(client, 'admin_norm', 'pass123')
    resp = client.post(
        f'/admin/usuarios/{target_id}/editar',
        data={
            'username': 'super_target',
            'cedula': 'V10101010',
            'nombre_completo': 'Super Target Mod',
            'email': 'target@example.com',
            'rol_id': str(rol_super.id),
            'departamento_id': '0',
            'activo': 'y',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        same_user = Usuario.query.get(target_id)
        assert same_user is not None
        assert same_user.nombre_completo == 'Super Target'
        log = AuditoriaAcciones.query.filter_by(objeto=same_user.username, accion='editar').first()
        assert log is None


def test_admin_cannot_delete_superadmin(app, client):
    login_user(client, 'admin_norm', 'pass123')
    resp = client.post('/admin/usuarios/super_target/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(username='super_target').first() is not None
        log = AuditoriaAcciones.query.filter_by(objeto='super_target', accion='eliminar').first()
        assert log is None


def test_superadmin_can_delete_user(app, client):
    login_user(client, 'admin2', 'pass123')
    with app.app_context():
        rol_sol = Rol.query.filter_by(nombre='Solicitante').first()
        temp_user = Usuario(
            username='temp_del',
            cedula='V77777888',
            email='tempdel@example.com',
            nombre_completo='Temp Delete',
            rol_id=rol_sol.id,
            departamento_id=None,
            activo=True,
        )
        temp_user.set_password('temp123')
        db.session.add(temp_user)
        db.session.commit()
        temp_id = temp_user.id

    get_resp = client.get(f'/admin/usuarios/{temp_id}/confirmar_eliminar')
    assert get_resp.status_code == 200
    resp = client.post(f'/admin/usuarios/{temp_id}/eliminar', data={}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Usuario.query.get(temp_id) is None
        log = AuditoriaAcciones.query.filter_by(modulo='Usuarios', objeto='temp_del', accion='eliminar').first()
        assert log is not None
        assert log.usuario_id == Usuario.query.filter_by(username='admin2').first().id
