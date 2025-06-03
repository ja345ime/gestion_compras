from app import db, Usuario, Rol, app

with app.app_context():
    rol = Rol.query.filter_by(nombre='Admin').first()
    if not rol:
        rol = Rol(nombre='Admin', descripcion='Administrador')
        db.session.add(rol)
        db.session.commit()

    admin = Usuario.query.filter_by(username='admin').first()
    if admin:
        if not admin.superadmin or admin.rol_id != rol.id:
            admin.superadmin = True
            admin.rol_id = rol.id
            db.session.commit()
            print('Admin existente actualizado a superadmin')
        else:
            print('Admin ya existe')
    else:
        admin = Usuario(
            username='admin',
            cedula='V00000000',
            nombre_completo='Super Admin',
            email='admin@example.com',
            rol_id=rol.id,
            activo=True,
            superadmin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Superadmin creado')

