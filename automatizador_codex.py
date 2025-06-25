"""Automatizador que aplica cambios sugeridos por OpenAI.

Este script se encarga de enviar al modelo ``gpt-4o`` las instrucciones
contenidas en ``prompt_actual.txt`` y aplicar las modificaciones que el
modelo devuelva.  Cada paso imprime un mensaje claro para poder seguir el
flujo de trabajo.
"""

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

    ignorados = {"venv", "__pycache__", "backups", ".git"}
    archivos = []
    for ruta in base.rglob("*"):
        if not ruta.is_file():
            continue

        partes = set(ruta.parts)
        if partes.intersection(ignorados):
            continue

        if str(ruta).startswith(str(base / "static" / "pdf")):
            continue

        archivos.append(str(ruta))

    return archivos


def leer_archivos(rutas) -> dict:
    """Retorna un dict con el contenido de cada ruta existente."""

    contenidos: dict[str, str] = {}
    for ruta in rutas:
        path = Path(ruta)
        if not path.is_absolute():
            path = BASE_DIR / path

        if path.exists():
            try:
                contenidos[str(path)] = path.read_text(encoding="utf-8")
            except Exception as exc:
                print(f"Error al leer {path}: {exc}")
        else:
            print(f"Archivo no encontrado: {path}")

    return contenidos

def leer_prompt(ruta: str) -> str:
    """Lee el prompt de instrucciones del usuario."""

    path = Path(ruta)
    if not path.is_absolute():
        path = BASE_DIR / path

    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Error al leer el prompt: {exc}")
    else:
        print(f"Archivo de prompt no encontrado: {ruta}")
    return ""

def generar_respuesta_modelo(mensajes: list[dict], api_key: str) -> str:
    """Envía los mensajes al modelo y devuelve la respuesta de texto."""

    try:
        client = OpenAI(api_key=api_key)
        respuesta = client.chat.completions.create(
            model="gpt-4o", messages=mensajes
        )
        return respuesta.choices[0].message.content
    except Exception as exc:
        print(f"Error al comunicarse con la API: {exc}")
        return ""


def solicitar_archivos(lista_archivos: list[str], prompt: str, api_key: str):
    """Paso 1: solicita al modelo los archivos necesarios."""

    print("Preguntando al modelo qué archivos necesita...")
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
    datos = extraer_json(texto)
    if datos is None:
        print("Respuesta no válida al solicitar archivos:")
        print(texto)
    else:
        print("Archivos solicitados:", datos)
    return datos


def solicitar_cambios(archivos: dict, prompt: str, api_key: str):
    """Paso 2: solicita al modelo los cambios finales."""

    print("Solicitando cambios finales al modelo...")

    mensajes = [
        {
            "role": "system",
            "content": "Utiliza los archivos proporcionados para modificar el sistema.",
        },
        {
            "role": "system",
            "content": "Archivos actuales:\n"
            + json.dumps(archivos, indent=2, ensure_ascii=False),
        },
        {"role": "user", "content": prompt},
    ]
    texto = generar_respuesta_modelo(mensajes, api_key)

    datos = extraer_json(texto)
    if datos is None:
        print("Respuesta no válida con los cambios:")
        print(texto)
    else:
        print("Cambios propuestos recibidos para", list(datos.keys()))

    return datos

def extraer_json(texto: str):
    """Intenta obtener el primer objeto JSON dentro del texto."""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            try:
                return json.loads(texto[inicio : fin + 1])
            except json.JSONDecodeError as exc:
                print(f"Error al parsear JSON: {exc}")
        return None

def guardar_archivo(ruta: str, contenido: str):
    """Guarda el contenido en la ruta indicada creando un backup previo."""
    path = Path(ruta)
    if not path.is_absolute():
        path = BASE_DIR / path

    backups_dir = BASE_DIR / "backups_codex"
    backups_dir.mkdir(exist_ok=True)

    if path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = backups_dir / f"{path.name}.{timestamp}.bak"
        try:
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Backup creado: {backup_path}")
        except Exception as exc:
            print(f"Error al crear el backup de {path}: {exc}")
    else:
        print(f"El archivo {path} no existía; se creará uno nuevo.")

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(contenido, encoding="utf-8")
        print(f"{path} sobrescrito correctamente.")
    except Exception as exc:
        print(f"Error al escribir {path}: {exc}")


def main():
    """Ejecuta el automatizador."""
    # Cargar variables de entorno, incluida la API Key
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY no encontrado en .env")
        return

    print("Leyendo prompt_actual.txt...")
    prompt = leer_prompt("prompt_actual.txt")
    if not prompt:
        print("No se pudo leer el prompt. Abortando.")
        return

    print("Escaneando archivos del proyecto...")
    lista_archivos = listar_archivos(BASE_DIR)
    print(f"Se encontraron {len(lista_archivos)} archivos disponibles.")

    peticion = solicitar_archivos(lista_archivos, prompt, api_key)
    if not peticion:
        print("No se obtuvo una petición válida de archivos.")
        return

    archivos_a_leer = set(peticion.get("leer", []))
    for ruta in peticion.get("escribir", []):
        archivos_a_leer.add(ruta)

    print(f"Leyendo {len(archivos_a_leer)} archivos solicitados...")
    archivos_contenido = leer_archivos(archivos_a_leer)

    cambios = solicitar_cambios(archivos_contenido, prompt, api_key)
    if not cambios:
        print("No se encontraron cambios válidos en la respuesta.")
        return

    for ruta, nuevo_contenido in cambios.items():
        if not isinstance(nuevo_contenido, str):
            print(f"Contenido inválido para {ruta}. Se omite.")
            continue
        guardar_archivo(ruta, nuevo_contenido)

    print("Proceso completado")


if __name__ == "__main__":
    main()
