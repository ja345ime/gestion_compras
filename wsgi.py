from app import app, db, crear_datos_iniciales

# Ensure tables, roles and departments exist when running via gunicorn
with app.app_context():
    db.create_all()
    try:
        crear_datos_iniciales()
    except Exception as exc:
        app.logger.warning(f"No se pudieron crear datos iniciales: {exc}")

