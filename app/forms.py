
from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, TextAreaField, SubmitField,
    PasswordField, BooleanField, DecimalField,
    FieldList, FormField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp, NumberRange

from flask import current_app


class LoginForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')


class UserForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    cedula = StringField(
        'Cédula',
        validators=[
            DataRequired(message="La cédula es obligatoria."),
            Length(min=6, max=20, message="La cédula debe tener entre 6 y 20 caracteres."),
            Regexp(r'^[VEJGve]?\d{6,12}$', message="Formato de cédula inválido. Ej: V12345678, E123456, J123456789, G123456789 o solo números.")
        ]
    )
    nombre_completo = StringField('Nombre Completo', validators=[DataRequired(), Length(max=120)])
    email = StringField('Correo Electrónico (Opcional)', validators=[Optional(), Email(), Length(max=120)])
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(), EqualTo('confirm_password', message='Las contraseñas deben coincidir.')]
    )
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired()])
    rol_id = SelectField('Rol', coerce=int, validators=[DataRequired(message="Debe seleccionar un rol.")])
    departamento_id = SelectField('Departamento', validators=[Optional()])
    activo = BooleanField('Activo', default=True)
    submit = SubmitField('Guardar Usuario')

    def __init__(self, *args, **kwargs):
        from .models import Rol, Departamento
        super(UserForm, self).__init__(*args, **kwargs)
        try:
            roles_query = Rol.query.order_by(Rol.nombre).all()
            self.rol_id.choices = [(r.id, r.nombre) for r in roles_query]
            if not self.rol_id.choices:
                self.rol_id.choices = [('', 'No hay roles disponibles')]

            depto_query = Departamento.query.order_by(Departamento.nombre).all()
            self.departamento_id.choices = [('0', 'Ninguno (Opcional)')] + [(str(d.id), d.nombre) for d in depto_query]
        except Exception as e:
            current_app.logger.error(f"Error al poblar roles/departamentos en UserForm: {e}")
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

    producto = StringField(
        'Producto/Servicio',
        validators=[DataRequired(), Length(max=250)],
        render_kw={"placeholder": "Escriba o seleccione..."}
    )
    cantidad = DecimalField(
        'Cantidad',
        validators=[
            DataRequired(message="La cantidad es obligatoria."),
            NumberRange(min=0.01, message="La cantidad debe ser un número positivo.")
        ]
    )
    unidad_medida = StringField(
        'Unidad de Medida',
        validators=[DataRequired(message="La unidad de medida es obligatoria."), Length(max=100)],
        render_kw={"placeholder": "Escriba para buscar..."}
    )


class RequisicionForm(FlaskForm):
    nombre_solicitante = StringField('Nombre del Solicitante', validators=[DataRequired(), Length(max=250)])
    cedula_solicitante = StringField(
        'Cédula del Solicitante',
        validators=[
            DataRequired(message="La cédula del solicitante es obligatoria."),
            Length(min=6, max=20),
            Regexp(r'^[VEJGve]?\d{6,12}$', message="Formato de cédula inválido. Ej: V12345678 o solo números.")
        ]
    )
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
        # Las opciones del departamento se cargarán desde cada vista
        # para evitar consultas fuera de contexto de aplicación

from app.requisiciones.constants import ESTADOS_REQUISICION

class CambiarEstadoForm(FlaskForm):
    estado = SelectField('Nuevo Estado', choices=ESTADOS_REQUISICION, validators=[DataRequired()])
    comentario_estado = TextAreaField(
        'Comentario/Motivo:',
        validators=[Optional(), Length(max=500)],
        render_kw={"rows": 2, "placeholder": "Si rechaza o necesita aclarar, ingrese un comentario..."}
    )
    submit_estado = SubmitField('Actualizar Estado')


class ConfirmarEliminarForm(FlaskForm):
    """Formulario simple para confirmar la eliminación de una requisición."""

    submit = SubmitField('Sí, Eliminar Requisición')



class ConfirmarEliminarUsuarioForm(FlaskForm):
    """Formulario simple para confirmar la eliminación de un usuario."""

    submit = SubmitField('Sí, Eliminar Usuario')
