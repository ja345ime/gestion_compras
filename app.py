import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Jaime2020SuperSeguroConUsuariosYPermisos!'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'requisiciones.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
            estados = ['Aprobada por Almacén', 'Pendiente de Cotizar']
    else:
        estados = None

    # 3️⃣ Construir consulta base (respeta lógica de Admin vs creador)
    query = Requisicion.query
    if rol != 'Admin':
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

    puede_editar = (editable_dentro_limite_original and requisicion.creador_id == current_user.id) or \
                   (current_user.rol_asignado and current_user.rol_asignado.nombre == 'Admin')

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
    if not ((es_creador and dentro_del_limite) or es_admin):
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




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        crear_datos_iniciales()
    app.run(debug=True)
