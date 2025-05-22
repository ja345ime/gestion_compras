import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort, make_response
from dotenv import load_dotenv
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DecimalField, FieldList, FormField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import logging
from markupsafe import Markup 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from functools import wraps
import smtplib

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_por_defecto_segura')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'requisiciones.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
app.config['SMTP_USER'] = os.environ.get('SMTP_USER')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD')
app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM')
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, inicie sesión para acceder a esta página."
login_manager.login_message_category = "info"

logging.basicConfig(level=logging.DEBUG)

TIEMPO_LIMITE_EDICION_REQUISICION = timedelta(minutes=30)

UNIDADES_DE_MEDIDA_SUGERENCIAS = [
    'Kilogramo (Kg)', 'Gramo (g)', 'Miligramo (mg)', 'Tonelada (t)', 'Quintal (qq)', 'Libra (Lb)', 
    'Saco (especificar peso)', 'Bulto (especificar peso)', 'Litro (L)', 'Mililitro (mL)', 
    'Centímetro cúbico (cc ó cm³)', 'Metro cúbico (m³)', 'Galón (Gal)', 'Frasco (especificar volumen)', 
    'Botella (especificar volumen)', 'Tambor (especificar volumen)', 'Barril (especificar volumen)', 'Pipa (agua)',
    'Carretilla', 'Balde', 'Lata (especificar tamaño)', 'Metro (m)', 'Centímetro (cm)', 'Pulgada (in)', 
    'Pie (ft)', 'Rollo (especificar longitud/tipo)', 'Metro cuadrado (m²)', 'Hectárea (Ha)',
    'Unidad (Un)', 'Pieza (Pza)', 'Docena (Doc)', 'Ciento', 'Millar', 'Cabeza (Cbz) (ganado)', 
    'Planta (Plt)', 'Semilla (por unidad o peso)', 'Mata', 'Atado', 'Fardo', 'Paca', 'Bala', 
    'Caja (Cj)', 'Bolsa', 'Paleta', 'Hora (Hr)', 'Día', 'Semana', 'Mes', 'Jornal (trabajo)', 
    'Ciclo (productivo)', 'Porcentaje (%)', 'Partes por millón (ppm)', 'mg/Kg', 'mg/L', 'g/Kg', 
    'g/L', 'mL/L', 'cc/L', 'UI (Unidades Internacionales)', 'Dosis', 'Servicio (Serv)', 
    'Global (Glb)', 'Lote', 'Viaje (transporte)', 'Aplicación', 'Otro (especificar)'
]
UNIDADES_DE_MEDIDA_SUGERENCIAS.sort()

ESTADO_INICIAL_REQUISICION = 'Pendiente Revisión Almacén'
ESTADOS_REQUISICION = [
    (ESTADO_INICIAL_REQUISICION, 'Pendiente Revisión Almacén'),
    ('Aprobada por Almacén', 'Aprobada por Almacén (Enviar a Compras)'),
    ('Surtida desde Almacén', 'Surtida desde Almacén (Completada por Almacén)'),
    ('Rechazada por Almacén', 'Rechazada por Almacén'),
    ('Pendiente de Cotizar', 'Pendiente de Cotizar (En Compras)'),
    ('Aprobada por Compras', 'Aprobada por Compras (Lista para Adquirir)'),
    ('Rechazada por Compras', 'Rechazada por Compras'),
    ('En Proceso de Compra', 'En Proceso de Compra'),
    ('Comprada', 'Comprada (Esperando Recepción)'),
    ('Recibida Parcialmente', 'Recibida Parcialmente (En Almacén)'),
    ('Recibida Completa', 'Recibida Completa (En Almacén)'),
    ('Cerrada', 'Cerrada (Proceso Finalizado)'),
    ('Cancelada', 'Cancelada')
]
ESTADOS_REQUISICION_DICT = dict(ESTADOS_REQUISICION)

ESTADOS_HISTORICOS = [
    'Surtida desde Almacén',
    'Rechazada por Almacén',
    'Rechazada por Compras',
    'Comprada',
    'Cerrada',
    'Cancelada'
]

# --- Modelos ---
# (Modelos Rol, Usuario, Departamento, Requisicion, DetalleRequisicion, ProductoCatalogo como en tu archivo)
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
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    nombre_solicitante = db.Column(db.String(255), nullable=False)
    cedula_solicitante = db.Column(db.String(20), nullable=False)
    correo_solicitante = db.Column(db.String(255), nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=False)
    prioridad = db.Column(db.String(50), nullable=False)
    estado = db.Column(db.String(50), default=ESTADO_INICIAL_REQUISICION, nullable=False)
    observaciones = db.Column(db.Text, nullable=True)
    creador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    comentario_estado = db.Column(db.Text, nullable=True)
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

# --- Formularios ---
# (LoginForm, UserForm, DetalleRequisicionForm, RequisicionForm, CambiarEstadoForm como en tu archivo)
class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class UserForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    cedula = StringField('Cédula', validators=[
        DataRequired(message="La cédula es obligatoria."),
        Length(min=6, max=20, message="La cédula debe tener entre 6 y 20 caracteres."),
        Regexp(r'^[VEJGve]?\d{6,12}$', message="Formato de cédula inválido. Ej: V12345678, E123456, J123456789, G123456789 o solo números.")
    ])
    nombre_completo = StringField('Nombre Completo', validators=[DataRequired(), Length(max=120)])
    email = StringField('Correo Electrónico (Opcional)', validators=[Optional(), Email(), Length(max=120)])
    password = PasswordField('Contraseña', validators=[
        DataRequired(),
        EqualTo('confirm_password', message='Las contraseñas deben coincidir.')
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired()])
    rol_id = SelectField('Rol', coerce=int, validators=[DataRequired(message="Debe seleccionar un rol.")])
    departamento_id = SelectField('Departamento', validators=[Optional()])
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar Usuario')

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        try:
            roles_query = Rol.query.order_by(Rol.nombre).all()
            self.rol_id.choices = [(r.id, r.nombre) for r in roles_query]
            if not self.rol_id.choices:
                self.rol_id.choices = [('', 'No hay roles disponibles')]
            
            depto_query = Departamento.query.order_by(Departamento.nombre).all()
            self.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + \
                                           [(str(d.id), d.nombre) for d in depto_query]
        except Exception as e:
            app.logger.error(f"Error al poblar roles/departamentos en UserForm: {e}")
            self.rol_id.choices = [('', 'Error al cargar roles')]
            self.departamento_id.choices = [('0', 'Error al cargar deptos')]

class EditUserForm(UserForm):
    """Formulario para editar usuarios existentes."""
    password = PasswordField(
        'Nueva Contraseña (Opcional)',
        validators=[Optional(), EqualTo('confirm_password', message='Las contraseñas deben coincidir.')]
    )
    confirm_password = PasswordField('Confirmar Contraseña', validators=[Optional()])
    submit = SubmitField('Actualizar Usuario')

class DetalleRequisicionForm(FlaskForm):
    class Meta:
        csrf = False
    producto = StringField('Producto/Servicio',
                           validators=[DataRequired(), Length(max=250)],
                           render_kw={"placeholder": "Escriba o seleccione..."})
    cantidad = DecimalField('Cantidad', validators=[DataRequired()])
    unidad_medida = StringField('Unidad de Medida',
                                validators=[DataRequired(), Length(max=100)],
                                render_kw={"placeholder": "Escriba para buscar..."})

class RequisicionForm(FlaskForm):
    nombre_solicitante = StringField('Nombre del Solicitante', validators=[DataRequired(), Length(max=250)])
    cedula_solicitante = StringField('Cédula del Solicitante', validators=[
        DataRequired(message="La cédula del solicitante es obligatoria."),
        Length(min=6, max=20),
        Regexp(r'^[VEJGve]?\d{6,12}$', message="Formato de cédula inválido. Ej: V12345678 o solo números.")
    ])
    correo_solicitante = StringField('Correo Electrónico', validators=[DataRequired(), Email(), Length(max=250)])
    departamento_nombre = SelectField('Departamento', validators=[DataRequired(message="Debe seleccionar un departamento.")])
    prioridad = SelectField(
        'Prioridad',
        choices=[('', 'Seleccione una prioridad...'), ('Alta', 'Alta'), ('Media', 'Media'), ('Baja', 'Baja')],
        validators=[DataRequired(message="Debe seleccionar una prioridad.")],
        default=''
    )
    observaciones = TextAreaField('Observaciones (Opcional)')
    detalles = FieldList(FormField(DetalleRequisicionForm), min_entries=1, max_entries=20)
    submit = SubmitField('Crear Requisición')

    def __init__(self, *args, **kwargs):
        super(RequisicionForm, self).__init__(*args, **kwargs)
        try:
            self.departamento_nombre.choices = [('', 'Seleccione un departamento...')] + \
                                             [(d.nombre, d.nombre) for d in Departamento.query.order_by(Departamento.nombre).all()]
        except Exception as e:
            app.logger.error(f"Error al poblar departamentos en el formulario RequisicionForm: {e}")
            self.departamento_nombre.choices = [('', 'Error al cargar departamentos')]

class CambiarEstadoForm(FlaskForm):
    estado = SelectField('Nuevo Estado', choices=ESTADOS_REQUISICION, validators=[DataRequired()])
    comentario_estado = TextAreaField('Comentario/Motivo:', 
                                   validators=[Optional(), Length(max=500)],
                                   render_kw={"rows": 2, "placeholder": "Si rechaza o necesita aclarar, ingrese un comentario..."})
    submit_estado = SubmitField('Actualizar Estado')

# --- Decorador de Permisos ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.rol_asignado or current_user.rol_asignado.nombre != 'Admin':
            flash('Acceso no autorizado. Se requieren permisos de Administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Funciones Auxiliares ---
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

def crear_datos_iniciales():
    with app.app_context():
        departamentos_nombres = ['Administración', 'Recursos Humanos', 'Compras', 'Producción','Ventas', 'Almacén', 'Mantenimiento', 'Sistemas', 'Oficinas Generales','Finanzas', 'Marketing', 'Legal']
        for nombre_depto in departamentos_nombres:
            if not Departamento.query.filter_by(nombre=nombre_depto).first():
                depto = Departamento(nombre=nombre_depto)
                db.session.add(depto)
        roles_a_crear = {
            "Solicitante": "Puede crear y ver sus requisiciones.",
            "JefeDepartamento": "Puede aprobar requisiciones de su departamento.",
            "Almacen": "Puede revisar stock y aprobar para compra o surtir.",
            "Compras": "Puede gestionar el proceso de compra de requisiciones aprobadas.",
            "Produccion": "Rol específico para requisiciones de producción.",
            "Admin": "Acceso total al sistema."
        }
        for nombre_rol, desc_rol in roles_a_crear.items():
            if not Rol.query.filter_by(nombre=nombre_rol).first():
                rol = Rol(nombre=nombre_rol, descripcion=desc_rol)
                db.session.add(rol)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error al crear departamentos/roles iniciales: {e}")
            return

        admin_rol = Rol.query.filter_by(nombre="Admin").first()
        depto_admin = Departamento.query.filter_by(nombre="Administración").first()
        if admin_rol and not Usuario.query.filter_by(username='admin').first():
            admin_user = Usuario(
                username='admin',
                cedula='V00000000',
                email='admin@example.com',
                nombre_completo='Administrador Sistema',
                rol_id=admin_rol.id,
                departamento_id=depto_admin.id if depto_admin else None,
                activo=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            try:
                db.session.commit()
                app.logger.info("Usuario administrador 'admin' creado.")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al crear usuario admin: {e}")

def agregar_producto_al_catalogo(nombre_producto):
    if nombre_producto and nombre_producto.strip():
        nombre_estandarizado = nombre_producto.strip().title()
        producto_existente = ProductoCatalogo.query.filter_by(nombre=nombre_estandarizado).first()
        if not producto_existente:
            try:
                nuevo_producto_catalogo = ProductoCatalogo(nombre=nombre_estandarizado)
                db.session.add(nuevo_producto_catalogo)
                db.session.commit()
                app.logger.info(f"Producto '{nombre_estandarizado}' agregado al catálogo.")
            except IntegrityError:
                db.session.rollback()
                app.logger.info(f"Producto '{nombre_estandarizado}' ya existe en catálogo (manejado por IntegrityError).")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al agregar '{nombre_estandarizado}' al catálogo: {e}")

def obtener_sugerencias_productos():
    try:
        productos = ProductoCatalogo.query.order_by(ProductoCatalogo.nombre).all()
        return [p.nombre for p in productos]
    except Exception as e:
        app.logger.error(f"Error al obtener sugerencias de productos: {e}")
        return []


def obtener_emails_por_rol(nombre_rol):
    try:
        usuarios = Usuario.query.join(Rol).filter(Rol.nombre == nombre_rol, Usuario.activo == True).all()
        return [u.email for u in usuarios if u.email]
    except Exception as e:
        app.logger.error(f"Error obteniendo emails para rol {nombre_rol}: {e}")
        return []


def enviar_correo(destinatarios: list, asunto: str, mensaje: str) -> None:
    """Envía un correo usando los datos configurados en las variables de entorno."""
    smtp_server = app.config.get('SMTP_SERVER')
    if not smtp_server or not destinatarios:
        app.logger.warning('SMTP no configurado o sin destinatarios, correo no enviado')
        return

    smtp_port = app.config.get('SMTP_PORT', 587)
    smtp_user = app.config.get('SMTP_USER')
    smtp_password = app.config.get('SMTP_PASSWORD')
    remitente = app.config.get('MAIL_FROM') or smtp_user

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            msg = (
                f"From: {remitente}\r\n"
                f"To: {', '.join(destinatarios)}\r\n"
                f"Subject: {asunto}\r\n\r\n{mensaje}"
            )
            server.sendmail(remitente, destinatarios, msg.encode('utf-8'))
            app.logger.info(f"Correo enviado a {destinatarios} con asunto '{asunto}'")
    except Exception as e:
        app.logger.error(f"Error enviando correo: {e}")


def enviar_correos_por_rol(nombre_rol: str, asunto: str, mensaje: str) -> None:
    """Envía correos a todos los usuarios activos de un rol dado."""
    destinatarios = obtener_emails_por_rol(nombre_rol)
    if destinatarios:
        enviar_correo(destinatarios, asunto, mensaje)
        app.logger.info(
            f"Notificación enviada a rol {nombre_rol}: {asunto} -> {destinatarios}"
        )
    else:
        app.logger.warning(f"No se encontraron correos para el rol {nombre_rol}")


def cambiar_estado_requisicion(requisicion_id: int, nuevo_estado: str) -> None:
    """Actualiza el estado de una requisición y envía notificaciones."""
    requisicion = Requisicion.query.get(requisicion_id)
    if not requisicion:
        app.logger.error(f"Requisición {requisicion_id} no encontrada")
        return

    requisicion.estado = nuevo_estado
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error al cambiar estado de {requisicion_id}: {e}")
        return

    usuario_actual = current_user
    mensaje_solicitante = f"""
Hola {requisicion.nombre_solicitante},

Te informamos que tu requisición #{requisicion.id} ha cambiado de estado.  
📌 **Estado actual:** {nuevo_estado}

Puedes hacer seguimiento completo desde el sistema de compras interno de Granja Los Molinos.

Si tienes alguna duda, por favor contacta a tu departamento responsable.

---

⚠️ Este mensaje es confidencial. No debe ser compartido fuera de Granja Los Molinos ni reenviado sin autorización.
"""

    enviar_correo([requisicion.correo_solicitante], 'Actualización de tu requisición', mensaje_solicitante)
    app.logger.info(f"Correo enviado a {requisicion.correo_solicitante} con estado {nuevo_estado}")

    if nuevo_estado == 'Pendiente Aprobación':
        mensaje_almacen = f"""
Hola equipo de Almacén,

Se ha creado una nueva requisición interna con el número #{requisicion.id} que requiere su revisión y aprobación.

📝 **Solicitante:** {requisicion.nombre_solicitante}  
📌 **Estado actual:** {nuevo_estado}

Por favor, ingresa al sistema para revisarla, aprobarla o rechazarla según corresponda.

---

⚠️ Este mensaje es confidencial y dirigido únicamente al equipo de Almacén de Granja Los Molinos.
"""

        enviar_correos_por_rol('Almacen', 'Nueva requisición pendiente', mensaje_almacen)
        app.logger.info(f"Correo enviado al rol Almacen por requisición #{requisicion.id}")

    mensaje_compras = f"""
Hola equipo de Compras,

La requisición #{requisicion.id} fue aprobada por el departamento de Almacén y ahora se encuentra bajo su responsabilidad para cotización o gestión de compra.

📝 **Solicitante:** {requisicion.nombre_solicitante}  
📌 **Estado actual:** {nuevo_estado}

Puedes ingresar al sistema de compras interno para continuar con el proceso.

---

⚠️ Este mensaje es confidencial y dirigido exclusivamente al equipo de Compras de Granja Los Molinos.
"""

    if nuevo_estado == 'Aprobado por Almacén (Enviado a Compras)' and usuario_actual.rol_asignado and usuario_actual.rol_asignado.nombre == 'Almacen':
        enviar_correos_por_rol('Compras', 'Requisición enviada por Almacén', mensaje_compras)
        app.logger.info(f"Correo enviado al rol Compras por requisición #{requisicion.id}")


# --- Rutas de Autenticación ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if user.activo:
                login_user(user)
                next_page = request.args.get('next')
                flash('Inicio de sesión exitoso.', 'success')
                app.logger.info(f"Usuario '{user.username}' inició sesión.")
                return redirect(next_page or url_for('index'))
            else:
                flash('Esta cuenta de usuario está desactivada.', 'danger')
                app.logger.warning(f"Intento de login de usuario desactivado: {form.username.data}")
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            app.logger.warning(f"Intento de login fallido para usuario: {form.username.data}")
    return render_template('login.html', title='Iniciar Sesión', form=form)

@app.route('/logout')
@login_required
def logout():
    app.logger.info(f"Usuario '{current_user.username}' cerró sesión.")
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('login'))

# --- Rutas de Administración de Usuarios ---
@app.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    usuarios_paginados = db.session.query(Usuario).order_by(Usuario.username).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/listar_usuarios.html', usuarios_paginados=usuarios_paginados, title="Gestión de Usuarios")

@app.route('/admin/usuarios/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def crear_usuario_admin():
    form = UserForm()
    if form.validate_on_submit():
        try:
            existing_user_username = Usuario.query.filter_by(username=form.username.data).first()
            existing_user_cedula = Usuario.query.filter_by(cedula=form.cedula.data).first()
            existing_user_email = None
            if form.email.data:
                 existing_user_email = Usuario.query.filter_by(email=form.email.data).first()

            error_occurred = False
            if existing_user_username:
                flash('El nombre de usuario ya existe. Por favor, elige otro.', 'danger')
                form.username.errors.append('Ya existe.')
                error_occurred = True
            if existing_user_cedula:
                flash('La cédula ingresada ya está registrada. Por favor, verifique.', 'danger')
                form.cedula.errors.append('Ya existe.')
                error_occurred = True
            if existing_user_email:
                flash('El correo electrónico ya está registrado. Por favor, usa otro.', 'danger')
                form.email.errors.append('Ya existe.')
                error_occurred = True
            
            if not error_occurred:
                departamento_id_str = form.departamento_id.data
                final_departamento_id = None
                if departamento_id_str and departamento_id_str != '0': 
                    try:
                        final_departamento_id = int(departamento_id_str)
                    except ValueError:
                        flash('Valor de departamento no válido. Se asignará "Ninguno".', 'warning')
                        final_departamento_id = None
                
                nuevo_usuario = Usuario(
                    username=form.username.data,
                    cedula=form.cedula.data,
                    nombre_completo=form.nombre_completo.data,
                    email=form.email.data if form.email.data else None,
                    rol_id=form.rol_id.data,
                    departamento_id=final_departamento_id,
                    activo=form.activo.data
                )
                nuevo_usuario.set_password(form.password.data)
                db.session.add(nuevo_usuario)
                db.session.commit()
                flash(f'Usuario "{nuevo_usuario.username}" creado exitosamente.', 'success')
                return redirect(url_for('listar_usuarios'))
        
        except IntegrityError as e: 
            db.session.rollback()
            app.logger.error(f"Error de integridad al crear usuario (constraint BD): {e}")
            if 'usuario.username' in str(e).lower():
                flash('Error: El nombre de usuario ya existe (constraint).', 'danger')
                if not form.username.errors: form.username.errors.append('Ya existe (constraint).')
            elif 'usuario.cedula' in str(e).lower():
                flash('Error: La cédula ya está registrada (constraint).', 'danger')
                if not form.cedula.errors: form.cedula.errors.append('Ya existe (constraint).')
            elif form.email.data and 'usuario.email' in str(e).lower():
                flash('Error: El correo electrónico ya está registrado (constraint).', 'danger')
                if not form.email.errors: form.email.errors.append('Ya existe (constraint).')
            else:
                flash('Error de integridad al guardar el usuario. Verifique los datos.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error inesperado al crear el usuario: {str(e)}', 'danger')
            app.logger.error(f"Error inesperado al crear usuario: {e}", exc_info=True)
            
    return render_template('admin/crear_usuario.html', form=form, title="Crear Nuevo Usuario")


@app.route('/admin/usuarios/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    form = EditUserForm(obj=usuario)
    if request.method == 'GET':
        form.departamento_id.data = str(usuario.departamento_id) if usuario.departamento_id else '0'
        form.password.data = ''
        form.confirm_password.data = ''

    if form.validate_on_submit():
        existing_username = Usuario.query.filter(Usuario.username == form.username.data, Usuario.id != usuario.id).first()
        existing_cedula = Usuario.query.filter(Usuario.cedula == form.cedula.data, Usuario.id != usuario.id).first()
        existing_email = None
        if form.email.data:
            existing_email = Usuario.query.filter(Usuario.email == form.email.data, Usuario.id != usuario.id).first()

        error_occurred = False
        if existing_username:
            flash('El nombre de usuario ya existe. Por favor, elige otro.', 'danger')
            form.username.errors.append('Ya existe.')
            error_occurred = True
        if existing_cedula:
            flash('La cédula ingresada ya está registrada. Por favor, verifique.', 'danger')
            form.cedula.errors.append('Ya existe.')
            error_occurred = True
        if existing_email:
            flash('El correo electrónico ya está registrado. Por favor, use otro.', 'danger')
            form.email.errors.append('Ya existe.')
            error_occurred = True

        if not error_occurred:
            try:
                usuario.username = form.username.data
                usuario.cedula = form.cedula.data
                usuario.nombre_completo = form.nombre_completo.data
                usuario.email = form.email.data if form.email.data else None
                usuario.rol_id = form.rol_id.data
                depto_str = form.departamento_id.data
                usuario.departamento_id = int(depto_str) if depto_str and depto_str != '0' else None
                usuario.activo = form.activo.data
                if form.password.data:
                    usuario.set_password(form.password.data)
                db.session.commit()
                flash(f'Usuario "{usuario.username}" actualizado exitosamente.', 'success')
                return redirect(url_for('listar_usuarios'))
            except IntegrityError as e:
                db.session.rollback()
                flash('Error de integridad al actualizar el usuario.', 'danger')
                app.logger.error(f"Integridad al editar usuario {usuario_id}: {e}")
            except Exception as e:
                db.session.rollback()
                flash(f'Ocurrió un error inesperado al actualizar el usuario: {str(e)}', 'danger')
                app.logger.error(f"Error inesperado al editar usuario {usuario_id}: {e}", exc_info=True)

    return render_template('admin/editar_usuario.html', form=form, usuario_id=usuario.id, title="Editar Usuario")

# --- Rutas de Requisiciones ---
@app.route('/')
@login_required
def index():
    return render_template('inicio.html', title="Inicio")


@app.route('/requisiciones/crear', methods=['GET', 'POST'])
@login_required
def crear_requisicion():
    form = RequisicionForm()
    if request.method == 'GET':
        if current_user.is_authenticated:
            if current_user.nombre_completo:
                form.nombre_solicitante.data = current_user.nombre_completo
            if hasattr(current_user, 'cedula') and current_user.cedula:
                form.cedula_solicitante.data = current_user.cedula
            if current_user.email:
                form.correo_solicitante.data = current_user.email
            if current_user.departamento_asignado:
                form.departamento_nombre.data = current_user.departamento_asignado.nombre
            
    if form.validate_on_submit():
        try:
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Error: El departamento seleccionado no es válido.', 'danger')
                productos_sugerencias = obtener_sugerencias_productos()
                return render_template('crear_requisicion.html', form=form, title="Crear Nueva Requisición", unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS, productos_sugerencias=productos_sugerencias)

            nueva_requisicion = Requisicion(
                numero_requisicion='RQ-' + datetime.now().strftime('%Y%m%d%H%M%S%f'),
                nombre_solicitante=form.nombre_solicitante.data,
                cedula_solicitante=form.cedula_solicitante.data,
                correo_solicitante=form.correo_solicitante.data,
                departamento_id=departamento_seleccionado.id,
                prioridad=form.prioridad.data,
                observaciones=form.observaciones.data,
                creador_id=current_user.id,
                estado=ESTADO_INICIAL_REQUISICION
            )
            db.session.add(nueva_requisicion)

            for detalle_form_entry in form.detalles:
                detalle_data = detalle_form_entry.data
                if detalle_data['producto'] and detalle_data['cantidad'] is not None and detalle_data['unidad_medida']:
                    nombre_producto_estandarizado = detalle_data['producto'].strip().title()
                    detalle = DetalleRequisicion(
                        requisicion=nueva_requisicion,
                        producto=nombre_producto_estandarizado,
                        cantidad=detalle_data['cantidad'],
                        unidad_medida=detalle_data['unidad_medida']
                    )
                    db.session.add(detalle)
                    agregar_producto_al_catalogo(nombre_producto_estandarizado)

            db.session.commit()
            emails_compras = obtener_emails_por_rol('Compras')
            emails_almacen = obtener_emails_por_rol('Almacen')
            asunto = f"Nueva requisición {nueva_requisicion.numero_requisicion}"
            mensaje = (
                f"Se ha creado la requisición {nueva_requisicion.numero_requisicion} "
                f"por {nueva_requisicion.nombre_solicitante}."
            )
            enviar_correo(emails_compras + emails_almacen, asunto, mensaje)
            flash('¡Requisición creada con éxito! Número: ' + nueva_requisicion.numero_requisicion, 'success')
            return redirect(url_for('listar_requisiciones'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la requisición: {str(e)}', 'danger')
            app.logger.error(f"Error en crear_requisicion: {e}", exc_info=True)
    
    productos_sugerencias = obtener_sugerencias_productos()
    return render_template('crear_requisicion.html', form=form, title="Crear Nueva Requisición",
                           unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                           productos_sugerencias=productos_sugerencias)

# Ruta para Requisiciones ACTIVAS
@app.route('/requisiciones')
@login_required
def listar_requisiciones():
    # 1️⃣ Leer parámetro de filtro (por defecto 'todos')
    filtro = request.args.get('filtro', 'todos')

    # 2️⃣ Definir estados según rol y filtro
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol == 'Almacen':
        if filtro == 'sin_revisar':
            estados = ['Pendiente Revisión Almacén']
        elif filtro == 'por_cotizar':
            estados = ['Aprobada por Almacén']
        else:
            estados = ['Pendiente Revisión Almacén', 'Aprobada por Almacén']
    elif rol == 'Compras':
        if filtro == 'recien_llegadas':
            estados = ['Aprobada por Almacén']
        elif filtro == 'por_cotizar':
            estados = ['Pendiente de Cotizar']
        else:
            estados = ['Pendiente Revisión Almacén',
                       'Aprobada por Almacén',
                       'Pendiente de Cotizar']
    else:
        estados = None

    # 3️⃣ Construir consulta base (respeta lógica de Admin vs creador)
    query = Requisicion.query
    if rol not in ['Admin', 'Almacen', 'Compras']:
        query = query.filter_by(creador_id=current_user.id)

    # 4️⃣ Aplicar filtro de estados
    if estados is not None:
        query = query.filter(Requisicion.estado.in_(estados))

    # 5️⃣ Ejecutar y renderizar
    requisiciones = query.order_by(Requisicion.fecha_creacion.desc()).all()
    return render_template(
        'listar_requisiciones.html',
        requisiciones=requisiciones,
        filtro=filtro,
        title="Requisiciones Pendientes",
        vista_actual='activas',
        datetime=datetime,
        TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION
    )


# Nueva Ruta para el HISTORIAL de Requisiciones
@app.route('/requisiciones/historial')
@login_required
def historial_requisiciones():
    try:
        query = None
        rol_usuario = current_user.rol_asignado.nombre if hasattr(current_user, 'rol_asignado') and current_user.rol_asignado else None
        app.logger.debug(f"Historial Requisiciones - Usuario: {current_user.username}, Rol: {rol_usuario}")

        if rol_usuario == 'Admin':
            query = Requisicion.query # Admin ve todo el historial
        elif rol_usuario == 'Almacen':
            # Almacén ve en su historial las que creó O las que gestionó (pasaron por sus estados)
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([ # Estados que Almacén pudo haber gestionado
                        ESTADO_INICIAL_REQUISICION, 'Aprobada por Almacén',
                        'Surtida desde Almacén', 'Rechazada por Almacén',
                        'Comprada', 'Recibida Parcialmente', 'Recibida Completa', 'Cerrada', 'Cancelada'
                    ])
                )
            )
        elif rol_usuario == 'Compras':
            # Compras ve en su historial las que creó O las que gestionó
            query = Requisicion.query.filter(
                db.or_(
                    Requisicion.creador_id == current_user.id,
                    Requisicion.estado.in_([ # Estados que Compras pudo haber gestionado
                        'Aprobada por Almacén', 'Pendiente de Cotizar', 
                        'Aprobada por Compras', 'En Proceso de Compra', 'Comprada', 
                        'Recibida Parcialmente', 'Recibida Completa', 'Cerrada', 
                        'Rechazada por Compras', 'Cancelada'
                    ])
                )
            )
        else: # Solicitante y otros roles
            if hasattr(current_user, 'departamento_asignado') and current_user.departamento_asignado:
                query = Requisicion.query.filter(
                    db.or_(
                        Requisicion.departamento_id == current_user.departamento_id,
                        Requisicion.creador_id == current_user.id
                    )
                )
            elif hasattr(current_user, 'id'):
                query = Requisicion.query.filter_by(creador_id=current_user.id)

        if query is not None:
            query = query.filter(Requisicion.estado.in_(ESTADOS_HISTORICOS)) # Filtro clave para el historial
            requisiciones_historicas = query.order_by(Requisicion.fecha_creacion.desc()).all()
        else:
            requisiciones_historicas = []
            app.logger.warning(f"Query para historial de requisiciones fue None para {current_user.username}")
            
    except Exception as e:
        flash(f"Error al cargar el historial de requisiciones: {str(e)}", "danger")
        app.logger.error(f"Error en historial_requisiciones para {current_user.username if hasattr(current_user, 'username') else 'desconocido'}: {e}", exc_info=True)
        requisiciones_historicas = []
        
    return render_template('historial_requisiciones.html',
                           requisiciones=requisiciones_historicas,
                           title="Historial de Requisiciones",
                           vista_actual='historial', 
                           datetime=datetime, 
                           TIEMPO_LIMITE_EDICION_REQUISICION=TIEMPO_LIMITE_EDICION_REQUISICION)


@app.route('/requisicion/<int:requisicion_id>', methods=['GET', 'POST'])
@login_required
def ver_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    
    if request.method == 'GET':
        form_estado = CambiarEstadoForm(obj=requisicion)
        form_estado.estado.data = requisicion.estado 
    else: 
        form_estado = CambiarEstadoForm()

    opciones_estado_permitidas = []
    rol_actual = current_user.rol_asignado.nombre if current_user.rol_asignado else None

    if rol_actual == 'Admin':
        opciones_estado_permitidas = ESTADOS_REQUISICION
    elif rol_actual == 'Almacen':
        if requisicion.estado == ESTADO_INICIAL_REQUISICION:
            opciones_estado_permitidas = [
                (ESTADO_INICIAL_REQUISICION, ESTADOS_REQUISICION_DICT[ESTADO_INICIAL_REQUISICION]),
                ('Aprobada por Almacén', ESTADOS_REQUISICION_DICT['Aprobada por Almacén']),
                ('Surtida desde Almacén', ESTADOS_REQUISICION_DICT['Surtida desde Almacén']),
                ('Rechazada por Almacén', ESTADOS_REQUISICION_DICT['Rechazada por Almacén'])
            ]
        elif requisicion.estado == 'Comprada':
             opciones_estado_permitidas = [
                (requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado)),
                ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']),
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa'])
            ]
        elif requisicion.estado == 'Recibida Parcialmente':
            opciones_estado_permitidas = [
                (requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado)),
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa'])
            ]
        elif requisicion.estado in ['Aprobada por Almacén', 'Surtida desde Almacén', 'Rechazada por Almacén', 'Recibida Completa', 'Cerrada', 'Cancelada']:
             opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
        else: 
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
    elif rol_actual == 'Compras':
        if requisicion.estado == 'Aprobada por Almacén':
            opciones_estado_permitidas = [
                ('Aprobada por Almacén', ESTADOS_REQUISICION_DICT['Aprobada por Almacén']),
                ('Pendiente de Cotizar', ESTADOS_REQUISICION_DICT['Pendiente de Cotizar']),
                ('Rechazada por Compras', ESTADOS_REQUISICION_DICT['Rechazada por Compras']),
            ]
        elif requisicion.estado == 'Pendiente de Cotizar':
            opciones_estado_permitidas = [
                ('Pendiente de Cotizar', ESTADOS_REQUISICION_DICT['Pendiente de Cotizar']),
                ('Aprobada por Compras', ESTADOS_REQUISICION_DICT['Aprobada por Compras']),
                ('Rechazada por Compras', ESTADOS_REQUISICION_DICT['Rechazada por Compras']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada']),
            ]
        elif requisicion.estado == 'Aprobada por Compras':
            opciones_estado_permitidas = [
                ('Aprobada por Compras', ESTADOS_REQUISICION_DICT['Aprobada por Compras']),
                ('En Proceso de Compra', ESTADOS_REQUISICION_DICT['En Proceso de Compra']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada'])
            ]
        elif requisicion.estado == 'En Proceso de Compra':
            opciones_estado_permitidas = [
                ('En Proceso de Compra', ESTADOS_REQUISICION_DICT['En Proceso de Compra']),
                ('Comprada', ESTADOS_REQUISICION_DICT['Comprada']),
                ('Cancelada', ESTADOS_REQUISICION_DICT['Cancelada'])
            ]
        elif requisicion.estado == 'Comprada':
             opciones_estado_permitidas = [
                ('Comprada', ESTADOS_REQUISICION_DICT['Comprada']),
                # ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']), # Lo cambia Almacén
                # ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']),       # Lo cambia Almacén
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada']) # Compras puede cerrar si ya está comprada (o recibida)
            ]
        elif requisicion.estado == 'Recibida Parcialmente': 
            opciones_estado_permitidas = [
                ('Recibida Parcialmente', ESTADOS_REQUISICION_DICT['Recibida Parcialmente']),
                # ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']), # Lo cambia Almacén
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada'])
            ]
        elif requisicion.estado == 'Recibida Completa': 
            opciones_estado_permitidas = [
                ('Recibida Completa', ESTADOS_REQUISICION_DICT['Recibida Completa']),
                ('Cerrada', ESTADOS_REQUISICION_DICT['Cerrada'])
            ]
        elif requisicion.estado in ['Rechazada por Compras', 'Cancelada', 'Cerrada']:
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
        else: 
            opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]
    else: 
        opciones_estado_permitidas = [(requisicion.estado, ESTADOS_REQUISICION_DICT.get(requisicion.estado, requisicion.estado))]

    form_estado.estado.choices = opciones_estado_permitidas

    if request.method == 'POST' and form_estado.submit_estado.data and form_estado.validate_on_submit() :
        if not (current_user.rol_asignado and current_user.rol_asignado.nombre in ['Admin', 'Compras', 'Almacen']):
            flash('No tiene permiso para cambiar el estado de esta requisición.', 'danger')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))

        nuevo_estado = form_estado.estado.data
        if not any(nuevo_estado == choice[0] for choice in opciones_estado_permitidas):
            flash('Intento de cambio de estado no válido o no permitido para su rol/estado actual.', 'danger')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))
            
        comentario_ingresado_texto = form_estado.comentario_estado.data.strip() if form_estado.comentario_estado.data else None

        if requisicion.estado != nuevo_estado or (comentario_ingresado_texto and comentario_ingresado_texto != requisicion.comentario_estado):
            requisicion.estado = nuevo_estado
            
            if comentario_ingresado_texto:
                requisicion.comentario_estado = comentario_ingresado_texto
            
            if nuevo_estado in ['Rechazada por Almacén', 'Rechazada por Compras', 'Cancelada'] and not comentario_ingresado_texto:
                 flash('Es altamente recomendable ingresar un motivo al rechazar o cancelar la requisición.', 'warning')

            try:
                db.session.commit()
                asunto = f"Estado actualizado para {requisicion.numero_requisicion}"
                mensaje = (
                    f"Su requisición ha cambiado al estado: "
                    f"{ESTADOS_REQUISICION_DICT.get(nuevo_estado, nuevo_estado)}."
                )
                enviar_correo([requisicion.correo_solicitante], asunto, mensaje)
                flash_message = f'El estado de la requisición {requisicion.numero_requisicion} ha sido actualizado a "{ESTADOS_REQUISICION_DICT.get(nuevo_estado, nuevo_estado)}".'
                if comentario_ingresado_texto:
                    flash_message += " Comentario guardado."
                flash(flash_message, 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar el estado: {str(e)}', 'danger')
        else:
            flash('No se realizaron cambios (mismo estado y sin nuevo comentario o el mismo).', 'info')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))

    ahora = datetime.utcnow()
    editable_dentro_limite_original = False
    if requisicion.fecha_creacion:
        if ahora <= requisicion.fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            editable_dentro_limite_original = True

    puede_editar = (
        requisicion.estado == ESTADO_INICIAL_REQUISICION and
        editable_dentro_limite_original and
        requisicion.creador_id == current_user.id
    ) or (
        current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    )

    puede_eliminar = (editable_dentro_limite_original and requisicion.creador_id == current_user.id) or \
                     (current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin')

    puede_cambiar_estado = (current_user.rol_asignado and current_user.rol_asignado.nombre in ['Admin', 'Compras', 'Almacen'] and len(opciones_estado_permitidas) > 1) or \
                           (current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin')
                           
    return render_template('ver_requisicion.html',
                           requisicion=requisicion,
                           title=f"Detalle Requisición {requisicion.numero_requisicion}",
                           puede_editar=puede_editar,
                           puede_eliminar=puede_eliminar,
                           editable_dentro_limite_original=editable_dentro_limite_original,
                           tiempo_limite_minutos=int(TIEMPO_LIMITE_EDICION_REQUISICION.total_seconds() / 60),
                           form_estado=form_estado,
                           puede_cambiar_estado=puede_cambiar_estado)

@app.route('/requisicion/<int:requisicion_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_requisicion(requisicion_id):
    requisicion_a_editar = Requisicion.query.get_or_404(requisicion_id)
    es_creador = requisicion_a_editar.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.utcnow()
    dentro_del_limite = False
    if requisicion_a_editar.fecha_creacion:
        if ahora <= requisicion_a_editar.fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    estado_editable = requisicion_a_editar.estado == ESTADO_INICIAL_REQUISICION
    if not ((es_creador and dentro_del_limite and estado_editable) or es_admin):
        flash('No tiene permiso para editar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_editar.id))

    form = RequisicionForm(obj=requisicion_a_editar if request.method == 'GET' else None)
    if request.method == 'GET':
        if requisicion_a_editar.departamento_obj:
            form.departamento_nombre.data = requisicion_a_editar.departamento_obj.nombre
        while len(form.detalles.entries) > 0:
            form.detalles.pop_entry()
        for detalle_db in requisicion_a_editar.detalles:
            form.detalles.append_entry(detalle_db)

    if form.validate_on_submit():
        try:
            requisicion_a_editar.nombre_solicitante = form.nombre_solicitante.data
            requisicion_a_editar.cedula_solicitante = form.cedula_solicitante.data
            requisicion_a_editar.correo_solicitante = form.correo_solicitante.data
            departamento_seleccionado = Departamento.query.filter_by(nombre=form.departamento_nombre.data).first()
            if not departamento_seleccionado:
                flash('Departamento seleccionado no válido.', 'danger')
                productos_sugerencias = obtener_sugerencias_productos()
                return render_template('editar_requisicion.html', form=form, title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}", requisicion_id=requisicion_a_editar.id, unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS, productos_sugerencias=productos_sugerencias)

            requisicion_a_editar.departamento_id = departamento_seleccionado.id
            requisicion_a_editar.prioridad = form.prioridad.data
            requisicion_a_editar.observaciones = form.observaciones.data

            for detalle_existente in list(requisicion_a_editar.detalles):
                db.session.delete(detalle_existente)
            db.session.flush()

            for detalle_form_data in form.detalles.data:
                if detalle_form_data['producto'] and detalle_form_data['cantidad'] is not None and detalle_form_data['unidad_medida']:
                    nombre_producto_estandarizado = detalle_form_data['producto'].strip().title()
                    nuevo_detalle = DetalleRequisicion(
                        requisicion_id=requisicion_a_editar.id,
                        producto=nombre_producto_estandarizado,
                        cantidad=detalle_form_data['cantidad'],
                        unidad_medida=detalle_form_data['unidad_medida']
                    )
                    db.session.add(nuevo_detalle)
                    agregar_producto_al_catalogo(nombre_producto_estandarizado)
            db.session.commit()
            flash(f'Requisición {requisicion_a_editar.numero_requisicion} actualizada con éxito.', 'success')
            return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_editar.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la requisición: {str(e)}', 'danger')
            app.logger.error(f"Error al editar requisicion {requisicion_id}: {e}", exc_info=True)
    
    productos_sugerencias = obtener_sugerencias_productos()
    return render_template('editar_requisicion.html', form=form, title=f"Editar Requisición {requisicion_a_editar.numero_requisicion}",
                           requisicion_id=requisicion_a_editar.id,
                           unidades_sugerencias=UNIDADES_DE_MEDIDA_SUGERENCIAS,
                           productos_sugerencias=productos_sugerencias)

@app.route('/requisicion/<int:requisicion_id>/confirmar_eliminar')
@login_required
def confirmar_eliminar_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    es_creador = requisicion.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.utcnow()
    dentro_del_limite = False
    if requisicion.fecha_creacion:
        if ahora <= requisicion.fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    if not ((es_creador and dentro_del_limite) or es_admin):
        flash('No tiene permiso para eliminar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion.id))
    return render_template('confirmar_eliminar_requisicion.html',
                           requisicion=requisicion,
                           title=f"Confirmar Eliminación: {requisicion.numero_requisicion}")

@app.route('/requisicion/<int:requisicion_id>/eliminar', methods=['POST'])
@login_required
def eliminar_requisicion_post(requisicion_id):
    requisicion_a_eliminar = Requisicion.query.get_or_404(requisicion_id)
    es_creador = requisicion_a_eliminar.creador_id == current_user.id
    es_admin = current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin'
    ahora = datetime.utcnow()
    dentro_del_limite = False
    if requisicion_a_eliminar.fecha_creacion:
        if ahora <= requisicion_a_eliminar.fecha_creacion + TIEMPO_LIMITE_EDICION_REQUISICION:
            dentro_del_limite = True
    if not ((es_creador and dentro_del_limite) or es_admin):
        flash('No tiene permiso para eliminar esta requisición o el tiempo límite ha expirado.', 'danger')
        return redirect(url_for('ver_requisicion', requisicion_id=requisicion_a_eliminar.id))
    try:
        db.session.delete(requisicion_a_eliminar)
        db.session.commit()
        flash(f'Requisicion {requisicion_a_eliminar.numero_requisicion} eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la requisición: {str(e)}', 'danger')
        app.logger.error(f"Error al eliminar requisicion {requisicion_id}: {e}", exc_info=True)
    return redirect(url_for('listar_requisiciones'))

# --- Al final de app.py ---



@app.route('/requisiciones/pendientes_cotizar')
@login_required
def listar_pendientes_cotizar():
    """Lista las requisiciones cuyo estado sea 'Pendiente de Cotizar'."""
    if current_user.rol_asignado.nombre == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Pendiente de Cotizar').all()
    else:
        requisiciones = Requisicion.query.filter_by(creador_id=current_user.id, estado='Pendiente de Cotizar').all()
    return render_template('listar_pendientes_cotizar.html',
                           requisiciones=requisiciones,
                           title="Pendientes de Cotizar",
                           vista_actual='pendientes_cotizar')

@app.route('/requisiciones/cotizadas')
@login_required
def listar_cotizadas():
    """Lista las requisiciones cuyo estado sea 'Cotizada'."""
    if current_user.rol_asignado.nombre == 'Compras':
        requisiciones = Requisicion.query.filter_by(estado='Cotizada').all()
    else:
        requisiciones = Requisicion.query.filter_by(creador_id=current_user.id, estado='Cotizada').all()
    return render_template('listar_cotizadas.html',
                           requisiciones=requisiciones,
                           title="Cotizadas",
                           vista_actual='cotizadas')

@app.route('/requisiciones/estado/<path:estado>')
@login_required
def listar_por_estado(estado):
    """Lista todas las requisiciones cuyo estado coincida con <estado>."""
    # 1️⃣ Validar que el estado exista en tu lista de estados:
    if estado not in ESTADOS_REQUISICION_DICT:
        abort(404)

    # 2️⃣ Construir la consulta:
    qs = Requisicion.query.filter_by(estado=estado)
    rol = current_user.rol_asignado.nombre if current_user.rol_asignado else None
    if rol != 'Admin':
        # usuarios distintos de Admin solo ven sus propias requisiciones
        qs = qs.filter_by(creador_id=current_user.id)

    # 3️⃣ Renderizar plantilla genérica:
    requisiciones = qs.order_by(Requisicion.fecha_creacion.desc()).all()
    return render_template(
        'listar_por_estado.html',
        requisiciones=requisiciones,
        title=ESTADOS_REQUISICION_DICT[estado],
        estado=estado,
        vista_actual='estado'
    )


def _crear_pdf_minimo(cabecera, detalles):
    """Genera un PDF con logo y una tabla ordenada."""
    # Cargar imagen del logo
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo_granja.jpg')
    try:
        with open(logo_path, 'rb') as f:
            logo_bytes = f.read()
    except Exception:
        logo_bytes = b''

    def _jpeg_size(data: bytes):
        import struct
        if not data.startswith(b'\xff\xd8'):
            return 0, 0
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i+1]
            i += 2
            if marker == 0xDA:  # SOS
                break
            length = struct.unpack('>H', data[i:i+2])[0]
            if marker in (0xC0, 0xC2):
                height = struct.unpack('>H', data[i+3:i+5])[0]
                width = struct.unpack('>H', data[i+5:i+7])[0]
                return width, height
            i += length
        return 0, 0

    logo_w, logo_h = _jpeg_size(logo_bytes)
    if logo_w and logo_h:
        # Escalamos a 100 puntos de ancho
        draw_logo = True
        scale = 100.0 / logo_w
        pdf_logo_w = 100
        pdf_logo_h = logo_h * scale
    else:
        draw_logo = False

    objetos = []
    # Catalogo y paginas
    obj1 = "1 0 obj\n<< /Type /Catalog\n/Pages 2 0 R >>\nendobj\n"
    objetos.append(obj1)
    obj2 = "2 0 obj\n<< /Type /Pages\n/Kids [3 0 R]\n/Count 1 >>\nendobj\n"
    objetos.append(obj2)

    recursos = "<< /Font << /F1 5 0 R >>"
    if draw_logo:
        recursos += " /XObject << /Im1 6 0 R >>"
    recursos += " >>"

    obj3 = (
        "3 0 obj\n<< /Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]"
        f"\n/Contents 4 0 R\n/Resources {recursos} >>\nendobj\n"
    )
    objetos.append(obj3)

    contenido = []
    # Logo
    if draw_logo:
        y_pos = 792 - 50 - pdf_logo_h
        contenido.append("q")
        contenido.append(f"{pdf_logo_w} 0 0 {pdf_logo_h} 256 {y_pos} cm")
        contenido.append("/Im1 Do")
        contenido.append("Q")
        texto_y = y_pos - 40
    else:
        texto_y = 742

    contenido.append("BT")
    contenido.append("/F1 12 Tf")
    contenido.append(f"80 {texto_y} Td")
    for titulo, valor in cabecera:
        linea = f"{titulo}: {valor}".replace("(", "\\(").replace(")", "\\)")
        contenido.append(f"({linea}) Tj")
        contenido.append("0 -15 Td")
    contenido.append("ET")

    tabla_y = texto_y - (len(cabecera) * 15) - 20
    row_height = 15
    col1_x = 80
    col2_x = 150
    col3_x = 250
    total_rows = len(detalles) + 1
    tabla_height = total_rows * row_height

    contenido.append("1 w")
    ancho_total = 330  # ancho aproximado de la tabla
    borde_x = col1_x - 5
    borde_y = tabla_y - tabla_height - 5
    contenido.append(f"{borde_x} {borde_y} {ancho_total} {tabla_height + 10} re S")
    contenido.append(f"{col2_x - 5} {tabla_y} m {col2_x - 5} {tabla_y - tabla_height} l S")
    contenido.append(f"{col3_x - 5} {tabla_y} m {col3_x - 5} {tabla_y - tabla_height} l S")
    for i in range(1, total_rows):
        y = tabla_y - i * row_height
        contenido.append(f"{borde_x} {y} m {borde_x + ancho_total} {y} l S")

    contenido.append("BT")
    contenido.append("/F1 12 Tf")
    contenido.append(f"{col1_x} {tabla_y - 12} Td")
    contenido.append("(Cantidad) Tj")
    contenido.append(f"{col2_x - col1_x} 0 Td")
    contenido.append("(Unidad) Tj")
    contenido.append(f"{col3_x - col2_x} 0 Td")
    contenido.append("(Producto) Tj")
    contenido.append("ET")

    y_text = tabla_y - row_height - 12
    for cant, unidad, prod in detalles:
        cantidad = str(cant).replace("(", "\\(").replace(")", "\\)")
        unidad = str(unidad).replace("(", "\\(").replace(")", "\\)")
        producto = str(prod).replace("(", "\\(").replace(")", "\\)")
        contenido.append("BT")
        contenido.append("/F1 12 Tf")
        contenido.append(f"{col1_x} {y_text} Td")
        contenido.append(f"({cantidad}) Tj")
        contenido.append(f"{col2_x - col1_x} 0 Td")
        contenido.append(f"({unidad}) Tj")
        contenido.append(f"{col3_x - col2_x} 0 Td")
        contenido.append(f"({producto}) Tj")
        contenido.append("ET")
        y_text -= row_height

    stream = "\n".join(contenido)
    obj4 = (
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj\n"
    )
    objetos.append(obj4)
    obj5 = "5 0 obj\n<< /Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica >>\nendobj\n"
    objetos.append(obj5)

    if draw_logo:
        obj6 = (
            f"6 0 obj\n<< /Type /XObject /Subtype /Image /Width {logo_w} /Height {logo_h}"
            " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode"
            f" /Length {len(logo_bytes)} >>\nstream\n".encode('latin-1') + logo_bytes + b"\nendstream\nendobj\n"
        )
        objetos.append(obj6.decode('latin-1', 'ignore'))

    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref_offset = len(pdf)

    pdf += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"

    pdf += (
        "trailer\n<< /Root 1 0 R\n/Size %d >>\nstartxref\n%d\n%%EOF" %
        (len(objetos) + 1, xref_offset)
    )
    return pdf.encode("latin-1")


def generar_pdf_requisicion(requisicion):
    cabecera = [
        ("Requisición", requisicion.numero_requisicion),
        ("Fecha", requisicion.fecha_creacion.strftime('%d/%m/%Y %H:%M')),
        ("Solicitante", requisicion.nombre_solicitante),
        (
            "Departamento",
            requisicion.departamento_obj.nombre if requisicion.departamento_obj else "",
        ),
        ("Prioridad", requisicion.prioridad),
    ]
    if requisicion.observaciones:
        cabecera.append(("Obs", requisicion.observaciones))

    detalles = [
        (str(det.cantidad), det.unidad_medida, det.producto)
        for det in requisicion.detalles
    ]

    return _crear_pdf_minimo(cabecera, detalles)


@app.route('/requisicion/<int:requisicion_id>/imprimir')
@login_required
def imprimir_requisicion(requisicion_id):
    requisicion = Requisicion.query.get_or_404(requisicion_id)
    pdf_data = generar_pdf_requisicion(requisicion)
    nombre = f"requisicion_{requisicion.numero_requisicion}.pdf"
    resp = make_response(pdf_data)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename={nombre}'
    return resp




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        crear_datos_iniciales()
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
