from datetime import timedelta

TIEMPO_LIMITE_EDICION_REQUISICION = timedelta(minutes=30)
DURACION_SESION = timedelta(hours=1)

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
    'Aprobada por Compras',
    'Rechazada por Compras',
    'Comprada',
    'Cerrada',
    'Cancelada'
]

