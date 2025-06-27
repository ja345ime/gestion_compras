#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import openai
import subprocess

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
RESULTADO_FILE = Path("/tmp/resultado_bash_codex.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")
CONTEXT_FILE = Path("/tmp/contexto.txt")
ULTIMO_ERROR_FILE = Path("/tmp/ultimo_error_bash_codex.txt")

# Configuración de OpenAI
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


def ejecutar_bash():
    """Ejecuta el script bash_executor.py y retorna True si éxito, False si error."""
    resultado = subprocess.run([
        "python3", "/workspaces/gestion_compras/bash_executor.py"
    ], capture_output=True, text=True)
    return ERROR_FILE.exists() is False


def leer_contexto():
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text(encoding="utf-8")
    return ""

def leer_error():
    if ERROR_FILE.exists():
        return ERROR_FILE.read_text(encoding="utf-8").strip()
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

def analizar_error_con_chatgpt(error_texto, contexto):
    sistema_msg = (
        "Eres un experto en bash y administración de sistemas Linux. "
        "Recibirás el error de un comando bash y el contexto técnico del sistema. "
        "Tu tarea es analizar la causa y proponer un nuevo comando bash para solucionar el problema. "
        "Responde SOLO con el comando bash sugerido, sin explicaciones."
    )
    usuario_msg = f"Contexto:\n{contexto}\n\nError bash:\n{error_texto}\n\nSugiere un comando bash para corregirlo."
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": sistema_msg},
                {"role": "user", "content": usuario_msg}
            ]
        )
        comando = respuesta.choices[0].message.content.strip()
        # Limpiar posibles markdown
        if comando.startswith("```) and comando.endswith("```"):
            comando = comando.strip("`\n ")
        return comando
    except Exception as e:
        print(f"Error al analizar con ChatGPT: {e}")
        return ""

def ciclo_bash_codex(max_intentos=5):
    intentos = 0
    while intentos < max_intentos:
        print(f"\n--- Intento #{intentos+1} ---")
        exito = ejecutar_bash()
        if exito:
            print("✅ Comando bash ejecutado correctamente.")
            limpiar_ultimo_error()
            break
        error_texto = leer_error()
        if not error_texto:
            print("No se detectó error, saliendo.")
            break
        if error_repetido(error_texto):
            print("🔁 El mismo error ya fue atendido previamente sin éxito. No se reintenta.")
            break
        contexto = leer_contexto()
        nuevo_comando = analizar_error_con_chatgpt(error_texto, contexto)
        if not nuevo_comando:
            print("❌ No se pudo generar un nuevo comando bash.")
            break
        print(f"Nuevo comando generado:\n{nuevo_comando}")
        COMANDOS_FILE.write_text(nuevo_comando + "\n", encoding="utf-8")
        guardar_ultimo_error(error_texto)
        intentos += 1
        time.sleep(2)
    else:
        print("❌ Se alcanzó el máximo de intentos sin éxito.")

if __name__ == "__main__":
    ciclo_bash_codex()
