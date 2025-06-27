#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import openai

# Configuración de logging: se registra todo en debug.log
LOG_FILE = Path(__file__).with_name("debug.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# Directorio base del proyecto (ruta absoluta en el entorno controlado)
BASE_DIR = Path("/home/gestion_compras")

# Archivos temporales clave
ERROR_FILE = Path("/tmp/error_vistas.txt")
CONTEXT_FILE = Path("/tmp/contexto.txt")
PROMPT_VISTAS_FILE = Path("/tmp/prompt_codex_vistas.txt")
PROMPT_SERVIDOR_FILE = Path("/tmp/prompt.txt")      # para delegar al codex de servidor
RESULTADO_FILE = Path("/tmp/resultado_vistas.txt")
FALLA_FILE = Path("/tmp/falla_vistas.txt")
ESTADO_FILE = Path("/tmp/estado_vistas.txt")
ULTIMO_ERROR_FILE = Path("/tmp/ultimo_error_vistas.txt")

# Ignorar ciertos directorios/archivos al listar
IGNORADOS = {"venv", "__pycache__", "backups", ".git"}

def leer_error_vistas() -> str:
    """Lee el error de vistas desde ERROR_FILE y lo retorna como string (o vacío si no hay)."""
    if not ERROR_FILE.exists():
        log.info(f"No se encontró {ERROR_FILE}, abortando ejecución.")
        return ""
    try:
        texto = ERROR_FILE.read_text(encoding="utf-8").strip()
        if texto:
            log.info(f"🐞 Error de vistas detectado:\n{texto}")
        else:
            log.info("El archivo de error de vistas está vacío.")
        return texto
    except Exception as e:
        log.error(f"Error al leer {ERROR_FILE}: {e}")
        return ""

def es_error_de_codigo(error_texto: str) -> bool:
    """Heurística simple para determinar si el error corresponde a un fallo de código/backend."""
    texto = error_texto.lower()
    if "traceback" in texto or "exception" in texto or "error" in texto and "error" in texto[:10]:
        return True
    if "502 bad gateway" in texto or "nginx" in texto:
        return True
    return False

def analizar_error_con_chatgpt(error_texto: str, contexto: str) -> str:
    """Analiza el error usando ChatGPT y genera una sugerencia de solución/prompt técnico."""
    if not error_texto:
        return ""
    sistema_msg = (
        "Eres un asistente experto en desarrollo web (Flask/Python) y administración de servidores. "
        "Recibirás la descripción de un error ocurrido en la interfaz de la aplicación web, junto con el contexto técnico del sistema. "
        "Tu tarea es analizar la causa del error y proponer una solución específica. "
        "Responde con un conjunto de instrucciones técnicas claras y paso a paso para resolver el problema."
    )
    usuario_msg = f"**Contexto del sistema:**\n{contexto}\n\n**Error detectado en la interfaz:**\n{error_texto}\n\nPor favor, indica la causa más probable y cómo solucionarla paso a paso en el código o configuración del sistema."
    try:
        log.info("🤖 Analizando el error con ChatGPT (modelo GPT-4)...")
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no encontrado en .env")
        openai.api_key = api_key
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": sistema_msg},
                {"role": "user", "content": usuario_msg}
            ]
        )
        analisis = respuesta.choices[0].message.content.strip()
        log.info(f"🤖 Análisis generado:\n{analisis}")
        return analisis
    except Exception as exc:
        log.error(f"Error al comunicarse con la API de OpenAI: {exc}")
        return ""

def generar_prompt_tecnico(instrucciones: str) -> str:
    """Genera el prompt técnico final a partir de las instrucciones/análisis proporcionado."""
    if not instrucciones:
        return ""
    prompt = instrucciones.strip()
    try:
        PROMPT_VISTAS_FILE.write_text(prompt, encoding="utf-8")
        log.info(f"✏️ Prompt técnico escrito en {PROMPT_VISTAS_FILE}")
    except Exception as e:
        log.error(f"Error al escribir prompt en archivo: {e}")
    return prompt

def listar_archivos_disponibles(base: Path) -> list[str]:
    """Devuelve la lista de rutas de todos los archivos en el proyecto, excluyendo directorios irrelevantes."""
    archivos = []
    for ruta in base.rglob("*"):
        if not ruta.is_file():
            continue
        partes = set(ruta.parts)
        if partes.intersection(IGNORADOS):
            continue
        if str(ruta).startswith(str(base / "static" / "pdf")):
            continue
        archivos.append(str(ruta.relative_to(base)))
    return archivos

def solicitar_archivos_necesarios(lista_archivos: list[str], prompt_texto: str) -> dict:
    """Solicita al modelo qué archivos debe leer/modificar para aplicar las instrucciones dadas. Retorna un dict con listas 'leer' y 'escribir'."""
    mensajes = [
        {"role": "system", "content": "Decide qué archivos necesitas leer para aplicar las instrucciones propuestas."},
        {"role": "system", "content": "Archivos disponibles:\n" + "\n".join(lista_archivos)},
        {"role": "user", "content": prompt_texto}
    ]
    try:
        respuesta = openai.ChatCompletion.create(model="gpt-4o", messages=mensajes)
        texto = respuesta.choices[0].message.content
    except Exception as e:
        log.error(f"Error solicitando archivos al modelo: {e}")
        return {}
    datos = None
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin != -1:
            try:
                datos = json.loads(texto[inicio:fin+1])
            except Exception as e:
                log.error(f"Respuesta de archivos no es JSON válido: {e} - Respuesta: {texto}")
                datos = None
    if datos is None:
        log.error("❌ No se pudo obtener una lista válida de archivos necesarios para la corrección.")
        return {}
    log.info(f"📄 Archivos que se leerán: {datos.get('leer', [])} | Archivos a modificar: {datos.get('escribir', [])}")
    return datos

def leer_archivos_proyecto(rutas: list[str]) -> dict:
    """Lee el contenido de las rutas indicadas (relativas al BASE_DIR) y retorna un dict {ruta: contenido}."""
    contenidos = {}
    for ruta_rel in rutas:
        ruta = BASE_DIR / ruta_rel
        if not ruta.exists():
            log.warning(f"⚠️ Archivo solicitado no existe: {ruta_rel}")
            continue
        try:
            contenidos[ruta_rel] = ruta.read_text(encoding="utf-8")
        except Exception as exc:
            log.error(f"Error al leer {ruta_rel}: {exc}")
    return contenidos

def solicitar_cambios_archivos(archivos_contenido: dict, prompt_texto: str) -> dict:
    """Solicita al modelo los cambios a realizar en los archivos proporcionados, según el prompt dado. Retorna un dict {archivo: nuevo_contenido}."""
    mensajes = [
        {"role": "system", "content": "Utiliza los archivos proporcionados para proponer los cambios necesarios."},
        {"role": "system", "content": "Archivos actuales:\n" + json.dumps(archivos_contenido, indent=2, ensure_ascii=False)},
        {"role": "user", "content": prompt_texto}
    ]
    try:
        respuesta = openai.ChatCompletion.create(model="gpt-4o", messages=mensajes)
        texto = respuesta.choices[0].message.content
    except Exception as e:
        log.error(f"Error solicitando cambios al modelo: {e}")
        return {}
    datos = None
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin != -1:
            try:
                datos = json.loads(texto[inicio:fin+1])
            except Exception as e:
                log.error(f"Respuesta de cambios no es JSON válido: {e} - Respuesta: {texto}")
                datos = None
    if datos is None:
        log.error("❌ No se pudo interpretar los cambios propuestos por el modelo.")
        return {}
    log.info(f"🛠 Cambios propuestos para archivos: {list(datos.keys())}")
    return datos

def aplicar_cambios(cambios: dict) -> None:
    """Aplica los cambios propuestos en los archivos del proyecto, creando backups de los archivos modificados."""
    backup_dir = BASE_DIR / "backups_codex_vistas"
    backup_dir.mkdir(exist_ok=True)
    for ruta_rel, nuevo_contenido in cambios.items():
        ruta = BASE_DIR / ruta_rel
        try:
            if ruta.exists():
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                backup_path = backup_dir / f"{ruta.name}.{timestamp}.bak"
                backup_path.write_text(ruta.read_text(encoding="utf-8"), encoding="utf-8")
                log.info(f"📦 Backup creado: {backup_path}")
            else:
                log.info(f"Archivo nuevo será creado: {ruta_rel}")
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(nuevo_contenido, encoding="utf-8")
            log.info(f"✅ Archivo actualizado: {ruta_rel}")
        except Exception as exc:
            log.error(f"Error al aplicar cambio en {ruta_rel}: {exc}")

def validar_resultado() -> bool:
    """Verifica si la aplicación responde correctamente después de los cambios. Retorna True si está OK, False si persiste el error."""
    try:
        resultado = subprocess.run(
            ["curl", "-I", "http://localhost:5000"],
            capture_output=True, text=True, timeout=10
        )
    except Exception as exc:
        log.error(f"Error al ejecutar curl de validación: {exc}")
        return False
    salida = (resultado.stdout or "") + (resultado.stderr or "")
    log.info(f"🌐 Resultado de verificación:\n{salida}")
    return "200 OK" in salida

def delegar_a_codex_servidor(error_texto: str, contexto: str) -> None:
    """Delega el problema al Codex de servidor escribiendo un nuevo prompt en /tmp/prompt.txt."""
    prompt = (
        f"{contexto}\n\nSe ha detectado el siguiente error en la interfaz de la aplicación:\n{error_texto}\n\n"
        "Analiza y corrige este problema realizando los cambios de código necesarios en el sistema."
    )
    try:
        PROMPT_SERVIDOR_FILE.write_text(prompt, encoding="utf-8")
        log.info(f"➡️ Error de código detectado. Prompt delegado a codex_script_servidor en {PROMPT_SERVIDOR_FILE}")
    except Exception as e:
        log.error(f"Error al delegar prompt a codex_script_servidor: {e}")

def main():
    advertencia = (
        "⚠️ ADVERTENCIA: Este script aplica cambios automáticamente basándose en errores de vistas. "
        "Úselo **solo en entornos de prueba** o controlados; nunca en producción."
    )
    print(advertencia)
    log.warning(advertencia)

    error_texto = leer_error_vistas()
    if not error_texto:
        return

    if ULTIMO_ERROR_FILE.exists():
        try:
            ultimo_err = ULTIMO_ERROR_FILE.read_text(encoding="utf-8")
        except Exception:
            ultimo_err = ""
        if error_texto == ultimo_err:
            log.info("🔁 El mismo error ya fue atendido previamente sin éxito. No se reintenta.")
            return

    try:
        contexto = CONTEXT_FILE.read_text(encoding="utf-8") if CONTEXT_FILE.exists() else ""
    except Exception as e:
        contexto = ""
        log.error(f"Error al leer contexto: {e}")

    if es_error_de_codigo(error_texto):
        delegar_a_codex_servidor(error_texto, contexto)
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        FALLA_FILE.write_text(error_texto, encoding="utf-8")
        ULTIMO_ERROR_FILE.write_text(error_texto, encoding="utf-8")
        return

    instrucciones = analizar_error_con_chatgpt(error_texto, contexto)
    if not instrucciones:
        log.error("No se obtuvo análisis ni instrucciones para el error. Finalizando.")
        return

    prompt = generar_prompt_tecnico(instrucciones)
    if not prompt:
        log.error("Prompt técnico vacío, no se puede proceder.")
        return

    lista_archivos = listar_archivos_disponibles(BASE_DIR)
    log.info(f"📁 Archivos disponibles en el proyecto: {len(lista_archivos)} archivos encontrados.")

    peticion_archivos = solicitar_archivos_necesarios(lista_archivos, prompt)
    if not peticion_archivos:
        FALLA_FILE.write_text("El modelo no indicó qué archivos revisar para este error.", encoding="utf-8")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ULTIMO_ERROR_FILE.write_text(error_texto, encoding="utf-8")
        return

    archivos_a_leer = set(peticion_archivos.get("leer", []))
    for ruta in peticion_archivos.get("escribir", []):
        archivos_a_leer.add(ruta)
    archivos_a_leer = list(archivos_a_leer)

    archivos_contenido = leer_archivos_proyecto(archivos_a_leer)
    if not archivos_contenido:
        log.error("No se pudo leer ningún archivo del listado solicitado. Abortando.")
        return

    cambios = solicitar_cambios_archivos(archivos_contenido, prompt)
    if not cambios:
        FALLA_FILE.write_text("El modelo no propuso cambios para solucionar el error.", encoding="utf-8")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ULTIMO_ERROR_FILE.write_text(error_texto, encoding="utf-8")
        log.error("❌ El modelo no devolvió cambios ejecutables.")
        return

    aplicar_cambios(cambios)
    RESULTADO_FILE.write_text(
        "Archivos modificados: " + ", ".join(cambios.keys()), encoding="utf-8"
    )

    if validar_resultado():
        ESTADO_FILE.write_text("OK", encoding="utf-8")
        log.info("🎉 Problema de vistas solucionado correctamente. Estado 'OK' registrado.")
        if ULTIMO_ERROR_FILE.exists():
            ULTIMO_ERROR_FILE.unlink()
    else:
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        try:
            resultado = FALLA_FILE.read_text(encoding="utf-8") if FALLA_FILE.exists() else "(ver logs)"
        except Exception:
            resultado = "(no disponible)"
        log.error(f"💥 La validación indica que el error persiste. Detalles: {resultado}")
        ULTIMO_ERROR_FILE.write_text(error_texto, encoding="utf-8")

if __name__ == "__main__":
    main()
