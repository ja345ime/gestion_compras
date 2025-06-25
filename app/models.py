# app/models.py
# Evita hacer importaciones aquí si crea conflictos circulares
# En su lugar, importa dentro de funciones donde sean necesarios

# Código para otras definiciones de clase

def obtener_estado_inicial_requisicion():
    from .requisiciones.constants import ESTADO_INICIAL_REQUISICION
    return ESTADO_INICIAL_REQUISICION
