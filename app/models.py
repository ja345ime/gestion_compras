"""Modelos de la aplicación."""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db


def obtener_estado_inicial_requisicion() -> str:
    """Devuelve el estado inicial definido para las requisiciones."""
    from .requisiciones.constants import ESTADO_INICIAL_REQUISICION

    return ESTADO_INICIAL_REQUISICION


class Rol(db.Model):
    __tablename__ = "rol"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(100))

    usuarios = db.relationship("Usuario", backref="rol_asignado", lazy=True)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<Rol {self.nombre}>"


class Departamento(db.Model):
    __tablename__ = "departamento"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

    usuarios = db.relationship("Usuario", backref="departamento_asignado", lazy=True)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<Departamento {self.nombre}>"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    activo = db.Column(db.Boolean, default=True)
    superadmin = db.Column(db.Boolean, default=False)
    rol_id = db.Column(db.Integer, db.ForeignKey("rol.id"), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamento.id"))
    ultimo_login = db.Column(db.DateTime)
    session_token = db.Column(db.String(100))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<Usuario {self.username}>"


class Requisicion(db.Model):
    __tablename__ = "requisicion"

    id = db.Column(db.Integer, primary_key=True)
    numero_requisicion = db.Column(db.String(30), unique=True, nullable=False)
    nombre_solicitante = db.Column(db.String(100), nullable=False)
    cedula_solicitante = db.Column(db.String(20), nullable=False)
    correo_solicitante = db.Column(db.String(100), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamento.id"), nullable=False)
    prioridad = db.Column(db.String(20), nullable=False)
    observaciones = db.Column(db.Text)
    creador_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    estado = db.Column(db.String(50), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    url_pdf_drive = db.Column(db.String(200))
    comentario_estado = db.Column(db.Text, nullable=True)

    departamento_obj = db.relationship("Departamento")
    creador_obj = db.relationship("Usuario")
    detalles = db.relationship(
        "DetalleRequisicion",
        backref="requisicion",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<Requisicion {self.numero_requisicion}>"


class DetalleRequisicion(db.Model):
    __tablename__ = "detalle_requisicion"

    id = db.Column(db.Integer, primary_key=True)
    requisicion_id = db.Column(db.Integer, db.ForeignKey("requisicion.id"), nullable=False)
    producto = db.Column(db.String(100), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    unidad_medida = db.Column(db.String(20), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<DetalleRequisicion {self.producto} x {self.cantidad}>"


class ProductoCatalogo(db.Model):
    __tablename__ = "producto_catalogo"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<ProductoCatalogo {self.nombre}>"


class AuditoriaAcciones(db.Model):
    __tablename__ = "auditoria_acciones"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    modulo = db.Column(db.String(50), nullable=False)
    objeto = db.Column(db.String(100), nullable=False)
    accion = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - representation
        return f"<AuditoriaAcciones {self.modulo}:{self.accion}>"


class IntentoLoginFallido(db.Model):
    __tablename__ = "intento_login_fallido"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45))
    username = db.Column(db.String(50))
    exito = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - representation
        estado = "EXITO" if self.exito else "FALLIDO"
        return f"<IntentoLogin {self.ip} - {self.username} - {estado}>"


class AdminVirtual(UserMixin):
    """Usuario virtual utilizado para el login especial de admin."""

    def __init__(self) -> None:
        self.id = 0
        self.username = "admin"
        self.superadmin = True
        self.session_token = None
        # Simular un rol asignado para compatibilidad con vistas y tests
        class RolVirtual:
            nombre = "Admin"
        self.rol_asignado = RolVirtual()

    def __repr__(self) -> str:  # pragma: no cover - representation
        return "<AdminVirtual 0>"

