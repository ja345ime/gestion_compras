"""Automatizador que aplica cambios sugeridos por OpenAI."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# Directorio base absoluto del proyecto
BASE_DIR = Path("/home/gestion_compras")


def listar_archivos(base: Path) -> list[str]:
    """Devuelve la lista de archivos disponibles en el proyecto."""
    archivos = []
    for ruta in base.rglob("*"):
        if ruta.is_file() and "venv" not in str(ruta) and "__pycache__" not in str(ruta):
            archivos.append(str(ruta))
    return archivos


def leer_archivos(rutas):
    """Retorna un dict con el contenido de cada ruta existente."""
    contenidos = {}
    for ruta in rutas:
        path = Path(ruta)
        if path.exists():
            contenidos[str(path)] = path.read_text(encoding="utf-8")
        else:
            print(f"Archivo no encontrado: {path}")
    return contenidos

def leer_prompt(ruta: str) -> str:
    """Lee el prompt de instrucciones del usuario."""
    path = Path(ruta)
    if path.exists():
        return path.read_text(encoding="utf-8")
    print(f"Archivo de prompt no encontrado: {ruta}")
    return ""

def generar_respuesta_modelo(mensajes: list[dict], api_key: str) -> str:
    """Envía los mensajes al modelo y devuelve la respuesta de texto."""
    client = OpenAI(api_key=api_key)
    respuesta = client.chat.completions.create(model="gpt-4o", messages=mensajes)
    return respuesta.choices[0].message.content


def solicitar_archivos(lista_archivos: list[str], prompt: str, api_key: str):
    """Paso 1: solicita al modelo los archivos necesarios."""
    mensajes = [
        {
            "role": "system",
            "content": "Decide que archivos necesitas leer para aplicar las instrucciones.",
        },
        {
            "role": "system",
            "content": "Archivos disponibles:\n" + "\n".join(lista_archivos),
        },
        {"role": "user", "content": prompt},
    ]
    texto = generar_respuesta_modelo(mensajes, api_key)
    return extraer_json(texto)


def solicitar_cambios(archivos: dict, prompt: str, api_key: str):
    """Paso 2: solicita al modelo los cambios finales."""
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
    texto = generar_respuesta_modelo(mensajes, api_key)
    return extraer_json(texto)

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

    path.parent.mkdir(parents=True, exist_ok=True)
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
    prompt = leer_prompt("prompt_actual.txt")

    # Paso 1: obtener lista de archivos y preguntar cuáles leer
    lista_archivos = listar_archivos(BASE_DIR)
    peticion = solicitar_archivos(lista_archivos, prompt, api_key)
    if not peticion:
        print("No se obtuvo una petición válida de archivos.")
        return

    archivos_a_leer = set(peticion.get("leer", []))
    for ruta in peticion.get("escribir", []):
        if Path(ruta).exists():
            archivos_a_leer.add(ruta)

    archivos_contenido = leer_archivos(archivos_a_leer)

    # Paso 2: solicitar los cambios finales
    cambios = solicitar_cambios(archivos_contenido, prompt, api_key)
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
