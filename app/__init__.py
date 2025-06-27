import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

import click
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, logout_user
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from markupsafe import Markup
import logging

# Constantes y configuración
from .requisiciones.constants import (
    ESTADO_INICIAL_REQUISICION,
    ESTADOS_REQUISICION,
    ESTADOS_REQUISICION_DICT,
    ESTADOS_HISTORICOS,
    UNIDADES_DE_MEDIDA_SUGERENCIAS,
    TIEMPO_LIMITE_EDICION_REQUISICION,
)
from .config import DURACION_SESION

# Cargar variables de entorno
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Extensiones globales
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Utilidades que necesitan las pruebas
from .utils import (
    ensure_session_token_column,
    ensure_ultimo_login_column,
    crear_datos_iniciales,
    generar_pdf_requisicion,
    subir_pdf_a_drive,
    guardar_pdf_requisicion,
    registrar_accion,
    registrar_intento,
    exceso_intentos,
    load_user,
    enviar_correo,
    enviar_correos_por_rol,
    agregar_producto_al_catalogo,
    obtener_sugerencias_productos,
    obtener_emails_por_rol,
    generar_mensaje_correo,
)


def create_app(config_name: str | None = None) -> Flask:
    """Crea y configura la aplicación."""
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, 'templates'),
        static_folder=os.path.join(BASE_DIR, 'static'),
    )

    # Configuración principal
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_por_defecto_segura')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER')
    app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
    app.config['SMTP_USER'] = os.environ.get('SMTP_USER')
    app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
    app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM')

    if config_name == "testing":
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}

    # Logging a archivo cuando no esté en modo debug
    if not app.debug:
        try:
            log_dir = os.environ.get('LOG_PATH', os.path.join(BASE_DIR, 'logs'))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'app.log')
            handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
            handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            handler.setLevel(logging.INFO)
            app.logger.addHandler(handler)
            app.logger.setLevel(logging.INFO)
        except Exception:  # pragma: no cover - si falla logging no aborta
            app.logger.exception('Error al configurar logging a archivo.')

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor, inicie sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)

    from . import routes
    app.register_blueprint(routes.main)
    from .requisiciones import requisiciones_bp
    app.register_blueprint(requisiciones_bp)
    from .webhook_telegram import telegram_bp
    app.register_blueprint(telegram_bp)


    with app.app_context():
        try:
            ensure_session_token_column()
            ensure_ultimo_login_column()
        except Exception as exc:  # pragma: no cover - actualización best effort
            app.logger.warning(f'No se pudo actualizar la base de datos: {exc}')

    return app


# Crear aplicación para importación directa
app = create_app()


@app.before_request
def validar_sesion_activa():
    """Verifica que el token de sesión coincida con el guardado en BD."""
    if current_user.is_authenticated and hasattr(current_user, 'session_token'):
        if session.get('session_token') != current_user.session_token:
            logout_user()
            flash('Tu sesión ha expirado o fue iniciada en otro dispositivo.', 'warning')
            return redirect(url_for('main.login'))


@app.template_filter('nl2br')
def nl2br(value: str | None) -> str:
    """Convierte los saltos de línea en etiquetas <br>."""
    if value is None:
        return ''
    escaped = Markup.escape(value)
    return Markup('<br>'.join(escaped.splitlines()))


# Importar formularios para registrarlos en el módulo
from .forms import (
    LoginForm,
    UserForm,
    EditUserForm,
    ConfirmarEliminarUsuarioForm,
)
from .requisiciones.forms import (
    RequisicionForm,
    DetalleRequisicionForm,
    CambiarEstadoForm,
    ConfirmarEliminarForm,
)


@app.cli.command('crear-datos')
def cli_crear_datos():
    """Crea roles y departamentos iniciales."""
    from .models import Rol, Usuario, Departamento
    #crear_datos_iniciales(Rol, Departamento, Usuario)
    click.echo('Datos iniciales creados.')


@app.cli.command('crear-admin')
@click.option('--password', default=None, help='Contraseña para el usuario admin')
def cli_crear_admin(password: str | None):
    """Crea o actualiza el usuario administrador."""
    from .models import Rol, Usuario
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
            click.echo('Admin existente actualizado a superadmin')
        else:
            click.echo('Admin ya existe')
        return
    pwd = password or os.environ.get('ADMIN_PASSWORD')
    if not pwd:
        click.echo('ADMIN_PASSWORD no configurada')
        return
    admin = Usuario(
        username='admin',
        cedula='V00000000',
        nombre_completo='Super Admin',
        email=os.environ.get('ADMIN_EMAIL', 'admin@example.com'),
        rol_id=rol.id,
        activo=True,
        superadmin=True,
    )
    admin.set_password(pwd)
    db.session.add(admin)
    db.session.commit()
    click.echo('Superadmin creado')


@app.cli.command('init-db')
def cli_init_db():
    """Inicializa la base de datos."""
    db.create_all()
    click.echo('Base de datos inicializada.')


def limpiar_requisiciones_viejas(dias: int) -> int:
    """Compatibilidad para pruebas: delega al servicio de requisiciones."""
    from .services.requisicion_service import requisicion_service
    return requisicion_service.limpiar_requisiciones_antiguas(dias, None)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            from .models import Rol, Usuario, Departamento
            #crear_datos_iniciales(Rol, Departamento, Usuario)
        except Exception as e:  # pragma: no cover - fallos en inicio no detienen
            app.logger.warning(f'No se pudieron crear datos iniciales: {e}')
    # Se puede ejecutar con flask run o gunicorn

# Exportaciones útiles para pruebas
__all__ = [
    "app",
    "db",
    "crear_datos_iniciales",
    "limpiar_requisiciones_viejas",
]
