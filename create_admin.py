import os
from dotenv import load_dotenv

load_dotenv()

from app import db, Usuario, Rol, app

with app.app_context():
    rol = Rol.query.filter_by(nombre='Superadmin').first()
    if not rol:
        rol = Rol(nombre='Superadmin', descripcion='Superadministrador')
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
        password = os.getenv("ADMIN_PASSWORD")
        if not password:
            print("ERROR: ADMIN_PASSWORD no está definida en el archivo .env")
            exit(1)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print('Superadmin creado')

