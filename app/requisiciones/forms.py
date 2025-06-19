from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, TextAreaField, SubmitField,
    DecimalField, FieldList, FormField
)
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp

from .constants import ESTADOS_REQUISICION


class DetalleRequisicionForm(FlaskForm):
    class Meta:
        csrf = False

    producto = StringField(
        'Producto/Servicio',
        validators=[DataRequired(), Length(max=250)],
        render_kw={"placeholder": "Escriba o seleccione..."}
    )
    cantidad = DecimalField('Cantidad', validators=[DataRequired()])
    unidad_medida = StringField(
        'Unidad de Medida',
        validators=[DataRequired(), Length(max=100)],
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
