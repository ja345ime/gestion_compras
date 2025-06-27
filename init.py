from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Importa blueprints, modelos y formularios
from .models import db
from .routes import main_bp
from .forms import CustomForm

# Carga condicional del blueprint de Telegram
try:
    from .webhook_telegram import telegram_bp
except ImportError:
    telegram_bp = None

# Función para crear la aplicación
def create_app():
    app = Flask(__name__)

    # Configuración específica para diferentes entornos
    app.config.from_object('config.Config')

    # Inicializa extensiones
    db.init_app(app)

    # Registro de Blueprints
    app.register_blueprint(main_bp)

    if telegram_bp:
        app.register_blueprint(telegram_bp)

    return app
