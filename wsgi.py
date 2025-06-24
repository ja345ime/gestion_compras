from app import app, db, crear_datos_iniciales

# Ensure tables, roles and departments exist when running via gunicorn
with app.app_context():
    db.create_all()
    try:
        from app.models import Rol, Usuario, Departamento
        crear_datos_iniciales(Rol, Departamento, Usuario)
    except Exception as exc:
        app.logger.warning(f"No se pudieron crear datos iniciales: {exc}")

