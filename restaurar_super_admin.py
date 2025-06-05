import os
from werkzeug.security import generate_password_hash
from app import app, db, Usuario, Rol

with app.app_context():
    usuario = Usuario.query.filter_by(email="jaimegaya@granjalosmolinos.com").first()
    if usuario:
        print("El usuario ya existe")
    else:
        password = os.getenv("ADMIN_PASSWORD")
        rol_super_admin = Rol.query.filter_by(nombre="super admin").first()
        if not rol_super_admin:
            print('Error: rol "super admin" no encontrado')
        elif not password:
            print("Error: ADMIN_PASSWORD no configurada")
        else:
            nuevo = Usuario(
                nombre="jaime",
                email="jaimegaya@granjalosmolinos.com",
                contraseña=generate_password_hash(password),
                rol_id=rol_super_admin.id,
            )
            db.session.add(nuevo)
            db.session.commit()
            print("Usuario restaurado")
