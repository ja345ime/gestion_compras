from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, TextAreaField, SubmitField,
    PasswordField, BooleanField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp

from .models import Rol, Departamento
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


class ConfirmarEliminarUsuarioForm(FlaskForm):
    """Formulario simple para confirmar la eliminación de un usuario."""

    submit = SubmitField('Sí, Eliminar Usuario')
