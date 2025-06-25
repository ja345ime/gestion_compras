"""Automatizador que aplica cambios sugeridos por OpenAI."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import openai
from datetime import datetime

# Rutas de los archivos clave del sistema que se enviarán al modelo
ARCHIVOS_CLAVE = [
    "app/routes/requisiciones.py",
    "app/utils/auditoria.py",
    "app/models.py",
]

def leer_archivos(rutas):
    """Retorna un dict con el contenido de cada ruta existente."""
    # Diccionario de {ruta: contenido}
    contenidos = {}
    for ruta in rutas:
        path = Path(ruta)
        if path.exists():
            contenidos[ruta] = path.read_text(encoding="utf-8")
        else:
            print(f"Archivo no encontrado: {ruta}")
    return contenidos

def leer_prompt(ruta: str) -> str:
    """Lee el prompt de instrucciones del usuario."""
    path = Path(ruta)
    if path.exists():
        return path.read_text(encoding="utf-8")
    print(f"Archivo de prompt no encontrado: {ruta}")
    return ""

def generar_respuesta(archivos: dict, prompt: str) -> str:
    """Envía los archivos y el prompt al modelo y devuelve la respuesta."""
    mensajes = [
        {
            "role": "system",
            "content": "Utiliza los archivos proporcionados para modificar el sistema.",
        },
        {
            "role": "system",
            "content": "Archivos actuales:\n" + json.dumps(archivos, indent=2, ensure_ascii=False),
        },
        {"role": "user", "content": prompt},
    ]
    respuesta = openai.ChatCompletion.create(model="gpt-4o", messages=mensajes)
    return respuesta["choices"][0]["message"]["content"]

def extraer_json(texto: str):
    """Intenta obtener el primer objeto JSON dentro del texto."""
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio: fin + 1])
        except json.JSONDecodeError:
            pass
    return None

def guardar_archivo(ruta: str, contenido: str):
    """Guarda el contenido en la ruta indicada creando un backup previo."""
    path = Path(ruta)
    backups_dir = Path("backups_codex")
    backups_dir.mkdir(exist_ok=True)
    if path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = backups_dir / f"{path.name}.{timestamp}.bak"
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup creado: {backup_path}")
    else:
        print(f"El archivo {ruta} no existía; se creará uno nuevo.")

    path.write_text(contenido, encoding="utf-8")
    print(f"{ruta} sobrescrito correctamente.")


def main():
    """Ejecuta el automatizador."""
    # Cargar variables de entorno, incluida la API Key
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY no encontrado en .env")
        return
    openai.api_key = api_key

    # Obtener el contenido de los archivos clave y el prompt del usuario
    archivos = leer_archivos(ARCHIVOS_CLAVE)
    prompt = leer_prompt("prompt_actual.txt")

    # Solicitar al modelo los cambios a aplicar
    respuesta = generar_respuesta(archivos, prompt)
    # Mostrar la respuesta generada por el modelo
    print("Respuesta del modelo:\n", respuesta)

    cambios = extraer_json(respuesta)
    if not cambios:
        print("No se encontraron cambios válidos en la respuesta.")
        return

    for ruta, nuevo_contenido in cambios.items():
        if not isinstance(nuevo_contenido, str):
            print(f"Contenido inválido para {ruta}. Se omite.")
            continue
        guardar_archivo(ruta, nuevo_contenido)


if __name__ == "__main__":
    main()
