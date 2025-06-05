import os

from app import app, db

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gestion_compras.db')

if not os.path.exists(DB_FILE):
    with app.app_context():
        db.create_all()
        print("Base de datos creada exitosamente.")
        print("Tablas creadas:", db.engine.table_names())
else:
    with app.app_context():
        print("La base de datos ya existe.")
        print("Tablas existentes:", db.engine.table_names())
