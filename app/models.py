from datetime import datetime
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .config import ESTADO_INICIAL_REQUISICION

class Rol(db.Model):
    __tablename__ = 'rol'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    usuarios = db.relationship('Usuario', backref='rol_asignado', lazy='dynamic', foreign_keys='Usuario.rol_id')

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    nombre_completo = db.Column(db.String(120), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=True)
    rol_id = db.Column(db.Integer, db.ForeignKey('rol.id'), nullable=False)
    superadmin = db.Column(db.Boolean, default=False)
    session_token = db.Column(db.String(100), nullable=True)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    requisiciones_creadas = db.relationship('Requisicion', backref='creador', lazy='dynamic', foreign_keys='Requisicion.creador_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Departamento(db.Model):
    __tablename__ = 'departamento'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    requisiciones = db.relationship('Requisicion', backref='departamento_obj', lazy='dynamic', foreign_keys='Requisicion.departamento_id')
    usuarios = db.relationship('Usuario', backref='departamento_asignado', lazy='dynamic', foreign_keys='Usuario.departamento_id')

class Requisicion(db.Model):
    __tablename__ = 'requisicion'
    id = db.Column(db.Integer, primary_key=True)
    numero_requisicion = db.Column(db.String(255), unique=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC), nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    nombre_solicitante = db.Column(db.String(255), nullable=False)
    cedula_solicitante = db.Column(db.String(20), nullable=False)
    correo_solicitante = db.Column(db.String(255), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=False)
    prioridad = db.Column(db.String(50), nullable=False)
    estado = db.Column(db.String(50), default=ESTADO_INICIAL_REQUISICION, nullable=False)
    observaciones = db.Column(db.Text, nullable=True)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    comentario_estado = db.Column(db.Text, nullable=True)
    url_pdf_drive = db.Column(db.String(255), nullable=True)
    detalles = db.relationship('DetalleRequisicion', backref='requisicion', lazy=True, cascade="all, delete-orphan")

class DetalleRequisicion(db.Model):
    __tablename__ = 'detalle_requisicion'
    id = db.Column(db.Integer, primary_key=True)
    requisicion_id = db.Column(db.Integer, db.ForeignKey('requisicion.id'), nullable=False)
    producto = db.Column(db.String(255), nullable=False)
    cantidad = db.Column(db.Numeric(10, 2), nullable=False)
    unidad_medida = db.Column(db.String(100), nullable=False)

class ProductoCatalogo(db.Model):
    __tablename__ = 'producto_catalogo'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), unique=True, nullable=False)


class IntentoLoginFallido(db.Model):
    __tablename__ = 'intento_login_fallido'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=True)
    ip = db.Column(db.String(45), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC))
    exito = db.Column(db.Boolean, default=False)


class AuditoriaAcciones(db.Model):
    __tablename__ = 'auditoria_acciones'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    accion = db.Column(db.String(50), nullable=False)
    modulo = db.Column(db.String(100), nullable=False)
    objeto = db.Column(db.String(100), nullable=True)
    fecha = db.Column(db.DateTime, default=lambda: datetime.now(pytz.UTC))
class AdminVirtual(UserMixin):
    def __init__(self):
        self.id = 0
        self.username = "admin"
        self.nombre_completo = "Administrador del Sistema"
        self.superadmin = True
        self.activo = True
        self.session_token = None
        # Simulamos un objeto rol para que `current_user.rol_asignado.nombre` no falle
        self.rol_asignado = type("RolVirtual", (), {"nombre": "Superadmin"})()

    def get_id(self):
        return str(self.id)
