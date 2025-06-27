#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADVERTENCIA: Este script automatiza la corrección de errores en la aplicación Flask gestion_compras.
No usa OpenAI directamente. Está diseñado para ser orquestado por sistemas externos (ej: N8n, ChatGPT API).
No debe usarse en producción.
"""
import os
import sys
import json
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# === Archivos temporales y rutas ===
ERROR_FILE = Path("/tmp/error.txt")
CONTEXT_FILE = Path("/tmp/contexto.txt")
ESTADO_FILE = Path("/tmp/estado.txt")
FALLA_FILE = Path("/tmp/falla.txt")
RESULTADO_FILE = Path("/tmp/resultado.txt")
PROMPT_FILE = Path("/tmp/prompt_codex.txt")
ULTIMO_ERROR_FILE = Path("/tmp/ultimo_error.txt")
BACKUP_DIR = Path("backups_codex_unificado")

# === Configuración de logging ===
logging.basicConfig(
    filename="logs/codex_unificado.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)

def leer_error():
    if ERROR_FILE.exists():
        return ERROR_FILE.read_text(encoding="utf-8").strip()
    return ""

def leer_contexto():
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text(encoding="utf-8").strip()
    return ""

def error_repetido(error_texto):
    if ULTIMO_ERROR_FILE.exists():
        ultimo = ULTIMO_ERROR_FILE.read_text(encoding="utf-8").strip()
        return error_texto == ultimo
    return False

def guardar_ultimo_error(error_texto):
    ULTIMO_ERROR_FILE.write_text(error_texto, encoding="utf-8")

def limpiar_ultimo_error():
    if ULTIMO_ERROR_FILE.exists():
        ULTIMO_ERROR_FILE.unlink()

def listar_archivos_disponibles():
    ignorar = [".git", "venv", "__pycache__", "backups_codex_unificado", "logs", "static/pdf", ".mypy_cache"]
    archivos = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignorar]
        for f in files:
            ruta = os.path.relpath(os.path.join(root, f), ".")
            if any(ruta.startswith(ig + "/") or ruta == ig for ig in ignorar):
                continue
            archivos.append(ruta)
    return archivos

def backup_y_modificar(archivo, nuevo_contenido):
    BACKUP_DIR.mkdir(exist_ok=True)
    ruta = Path(archivo)
    if ruta.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"{ruta.stem}_{timestamp}{ruta.suffix}"
        shutil.copy2(ruta, backup_path)
        log(f"Backup creado: {backup_path}")
    else:
        log(f"Creando archivo nuevo: {archivo}")
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(nuevo_contenido)
    log(f"Archivo actualizado: {archivo}")

def ejecutar_pruebas():
    log("Ejecutando pruebas con pytest tests/ ...")
    try:
        resultado = subprocess.run(
            ["pytest", "tests/", "--maxfail=5", "--disable-warnings", "-v"],
            capture_output=True,
            text=True,
            timeout=300
        )
        RESULTADO_FILE.write_text(resultado.stdout + "\n" + resultado.stderr, encoding="utf-8")
        return resultado.returncode == 0, resultado.stdout + "\n" + resultado.stderr
    except Exception as e:
        FALLA_FILE.write_text(f"Error al ejecutar pytest: {e}", encoding="utf-8")
        return False, str(e)

def main():
    log("==========================\n  INICIO Codex Unificado\n==========================")
    error_texto = leer_error()
    if not error_texto:
        log("No se encontró error a resolver en /tmp/error.txt. Saliendo.")
        ESTADO_FILE.write_text("OK", encoding="utf-8")
        return
    if error_repetido(error_texto):
        log("El mismo error ya fue atendido previamente sin éxito. No se reintenta.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        return
    contexto = leer_contexto()
    archivos_disponibles = listar_archivos_disponibles()
    # --- Generar prompt para ChatGPT externo ---
    prompt = {
        "sistema": (
            "Eres un asistente experto en Python, Flask, HTML/Jinja, pruebas Pytest y mantenimiento de aplicaciones. "
            "Recibirás un error detectado en la aplicación gestion_compras, contexto del sistema y la lista de archivos del proyecto. "
            "Analiza el error, identifica si es de backend, vistas, rutas, permisos, CSRF, etc. "
            "Indica qué archivos deben leerse y modificarse, y qué cambios realizar. "
            "Siempre haz backup antes de modificar. "
            "No intentes corregir el mismo error más de una vez. "
            "Siempre trabaja sobre la rama 'pruebas/refactor-requisiciones'. "
            "Responde en JSON: {'archivos_modificar': {'ruta': 'nuevo_contenido', ...}, 'explicacion': '...'}"
        ),
        "usuario": (
            f"Error detectado:\n{error_texto}\n\n"
            f"Contexto del sistema:\n{contexto}\n\n"
            f"Archivos del proyecto:\n{json.dumps(archivos_disponibles, ensure_ascii=False)}\n"
            "Indica los archivos a modificar y el nuevo contenido en JSON."
        )
    }
    PROMPT_FILE.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Prompt generado y guardado en {PROMPT_FILE}")
    # --- Esperar respuesta del orquestador externo (ChatGPT/N8n) ---
    print("Esperando respuesta externa con los cambios a aplicar...")
    print(f"Por favor, guarda el JSON de cambios en {PROMPT_FILE.parent}/respuesta_codex.txt y presiona Enter para continuar.")
    input()
    respuesta_file = PROMPT_FILE.parent / "respuesta_codex.txt"
    if not respuesta_file.exists():
        log("No se encontró respuesta externa. Saliendo.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        return
    try:
        respuesta = json.loads(respuesta_file.read_text(encoding="utf-8"))
        archivos_modificar = respuesta.get("archivos_modificar", {})
        explicacion = respuesta.get("explicacion", "")
    except Exception as e:
        log(f"Error al leer respuesta externa: {e}")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        return
    # --- Aplicar cambios y backups ---
    for archivo, nuevo_contenido in archivos_modificar.items():
        backup_y_modificar(archivo, nuevo_contenido)
    # --- Ejecutar pruebas ---
    exito, salida_pytest = ejecutar_pruebas()
    if exito:
        log("✅ Todas las pruebas pasaron. Solución aplicada correctamente.")
        limpiar_ultimo_error()
        ESTADO_FILE.write_text("OK", encoding="utf-8")
    else:
        log("❌ Las pruebas fallaron. Revisar /tmp/resultado.txt para detalles.")
        guardar_ultimo_error(error_texto)
        FALLA_FILE.write_text(salida_pytest, encoding="utf-8")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")

if __name__ == "__main__":
    main()
