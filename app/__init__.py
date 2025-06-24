import os
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, abort, make_response, session

from sqlalchemy import inspect


from dotenv import load_dotenv
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import pytz

import logging
from logging.handlers import RotatingFileHandler
from threading import Thread
from markupsafe import Markup 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from functools import wraps
import requests
# from email_utils import render_correo_html # Eliminado por redundancia
import base64
import click

from .config import *

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
from . import models
from .models import (
    Rol,
    Usuario,
    Departamento,
    Requisicion,
    DetalleRequisicion,
    ProductoCatalogo,
    IntentoLoginFallido,
    AuditoriaAcciones,
    AdminVirtual,
)
from .utils import (
    ensure_session_token_column,
    ensure_ultimo_login_column,
    registrar_accion,
    registrar_intento,
    exceso_intentos,
    load_user,
    crear_datos_iniciales,
    agregar_producto_al_catalogo,
    obtener_sugerencias_productos,
    obtener_emails_por_rol,
    generar_mensaje_correo,
    enviar_correo,
    enviar_correos_por_rol,
    cambiar_estado_requisicion,
    generar_pdf_requisicion,
    subir_pdf_a_drive,
    guardar_pdf_requisicion,
    limpiar_requisiciones_viejas,
)



def create_app():
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))


    # Configuración de logging a archivo
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
        except Exception:
            app.logger.exception('Error al configurar el logging a archivo.')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_por_defecto_segura')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'postgresql://localhost/gestion_compras'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER')
    app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
    app.config['SMTP_USER'] = os.environ.get('SMTP_USER')
    app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
    app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Por favor, inicie sesión para acceder a esta página."
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    from . import routes
    app.register_blueprint(routes.main)

    with app.app_context():
        try:
            ensure_session_token_column()
            ensure_ultimo_login_column()
        except Exception as exc:
            app.logger.warning(f'No se pudo actualizar la base de datos: {exc}')

    return app




app = create_app()


@app.before_request
def validar_sesion_activa():
    if current_user.is_authenticated and hasattr(current_user, 'session_token'):
        token_en_sesion = session.get('session_token')
        token_en_usuario = current_user.session_token
        if token_en_sesion != token_en_usuario:
            logout_user()
            flash('Tu sesión ha expirado o fue iniciada en otro dispositivo.', 'warning')
            return redirect(url_for('main.login'))


# Filtro para convertir saltos de línea en etiquetas <br>
@app.template_filter('nl2br')
def nl2br(value):
    """Convierte los saltos de línea en etiquetas ``<br>`` para mostrar texto
    multilínea en plantillas."""
    if value is None:
        return ''
    escaped = Markup.escape(value)
    return Markup('<br>'.join(escaped.splitlines()))



from .forms import (
    LoginForm,
    UserForm,
    EditUserForm,
    DetalleRequisicionForm,
    RequisicionForm,
    CambiarEstadoForm,
    ConfirmarEliminarForm,
    ConfirmarEliminarUsuarioForm,
)

# --- Modelos ---
# (Modelos Rol, Usuario, Departamento, Requisicion, DetalleRequisicion, ProductoCatalogo como en tu archivo)


# --- Decorador de Permisos ---



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            crear_datos_iniciales()
        except Exception as e:
            app.logger.warning(f"No se pudieron crear datos iniciales: {e}")
    # Ejecutar con `flask run` o gunicorn
    # app.run(debug=os.environ.get('FLASK_DEBUG') == '1')

@app.cli.command('crear-datos')
def cli_crear_datos():
    """Crea roles y departamentos iniciales."""
    crear_datos_iniciales()
    click.echo('Datos iniciales creados.')


@app.cli.command('crear-admin')
@click.option('--password', default=None, help='Contraseña para el usuario admin')
def cli_crear_admin(password):
    """Crea o actualiza el usuario administrador."""
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
        superadmin=True
    )
    admin.set_password(pwd)
    db.session.add(admin)
    db.session.commit()
    click.echo('Superadmin creado')

@app.cli.command('init-db')
def cli_init_db():
    """Crea todas las tablas de la base de datos."""
    db.create_all()
    click.echo('Base de datos inicializada.')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            crear_datos_iniciales()
        except Exception as e:
            app.logger.warning(f"No se pudieron crear datos iniciales: {e}")
    # Ejecutar con `flask run` o gunicorn
    # app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
