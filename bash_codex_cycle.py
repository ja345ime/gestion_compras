#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import subprocess

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
ESTADO_FILE = Path("/tmp/estado_bash.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")
CONTEXT_FILE = Path("/tmp/contexto.txt")
PROMPT_BASH_FILE = Path("/tmp/prompt_codex_bash.txt")
ULTIMO_ERROR_FILE = Path("/tmp/ultimo_error_bash_codex.txt")

# Configuración de OpenAI
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else OpenAI()

def ejecutar_bash():
    if not COMANDOS_FILE.exists():
        print(f"No existe {COMANDOS_FILE}, nada que ejecutar.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("No existe /tmp/comandos_codex.sh", encoding="utf-8")
        return False
    comandos = COMANDOS_FILE.read_text(encoding="utf-8").strip()
    if not comandos:
        print("El archivo de comandos está vacío.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("El archivo de comandos está vacío.", encoding="utf-8")
        return False
    try:
        resultado = subprocess.run(
            comandos,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        print("STDOUT:\n" + (resultado.stdout or ""))
        print("STDERR:\n" + (resultado.stderr or ""))
        # Detectar si el comando contiene bypass de error
        bypass = False
        if '|| echo' in comandos or '> /dev/null' in comandos or '2>&1' in comandos:
            bypass = True
        if resultado.returncode == 0:
            ESTADO_FILE.write_text("OK", encoding="utf-8")
            if ERROR_FILE.exists():
                ERROR_FILE.unlink()
            return True
        else:
            # Si hay bypass, no marcar como OK aunque el comando "oculte" el error
            ESTADO_FILE.write_text("ERROR", encoding="utf-8")
            error_out = resultado.stderr if resultado.stderr else resultado.stdout
            ERROR_FILE.write_text(error_out, encoding="utf-8")
            return False
    except Exception as e:
        print(f"Excepción al ejecutar bash: {e}")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text(str(e), encoding="utf-8")
        return False

def leer_contexto():
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text(encoding="utf-8")
    return ""

def leer_error():
    if ERROR_FILE.exists():
        return ERROR_FILE.read_text(encoding="utf-8").strip()
    return ""

def leer_comando():
    if COMANDOS_FILE.exists():
        return COMANDOS_FILE.read_text(encoding="utf-8").strip()
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

def analizar_error_con_chatgpt(error_texto, contexto, comando_actual):
    sistema_msg = (
        "Eres un experto en bash y administración de sistemas Linux. "
        "Recibirás el error de un comando bash, el contexto técnico del sistema y el comando ejecutado. "
        "Tu tarea es analizar la causa y proponer un nuevo comando bash corregido. "
        "Primero, razona brevemente la causa y solución. Luego, sugiere SOLO el nuevo comando bash corregido. "
        "Responde en formato JSON con las claves 'analisis' y 'comando'."
    )
    usuario_msg = f"Contexto:\n{contexto}\n\nComando ejecutado:\n{comando_actual}\n\nError bash:\n{error_texto}\n\nAnaliza el error y sugiere un comando bash corregido."
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": sistema_msg},
                {"role": "user", "content": usuario_msg}
            ]
        )
        texto = respuesta.choices[0].message.content.strip()
        # Intentar extraer JSON
        import json
        try:
            data = json.loads(texto)
        except Exception:
            inicio = texto.find('{')
            fin = texto.rfind('}')
            if inicio != -1 and fin != -1:
                data = json.loads(texto[inicio:fin+1])
            else:
                raise ValueError("No se pudo extraer JSON del análisis")
        return data.get('analisis', ''), data.get('comando', '')
    except Exception as e:
        print(f"Error al analizar con ChatGPT: {e}")
        return "", ""

def guardar_prompt(analisis):
    PROMPT_BASH_FILE.write_text(analisis, encoding="utf-8")

def ciclo_bash_codex(max_intentos=5):
    intentos = 0
    while intentos < max_intentos:
        print(f"\n--- Intento #{intentos+1} ---")
        comando_actual = leer_comando()
        exito = ejecutar_bash()
        estado = ESTADO_FILE.read_text(encoding="utf-8").strip() if ESTADO_FILE.exists() else ""
        if exito and estado == "OK":
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
        print(f"❌ Error detectado:\n{error_texto}")
        analisis, nuevo_comando = analizar_error_con_chatgpt(error_texto, contexto, comando_actual)
        if not analisis or not nuevo_comando:
            print("❌ No se pudo generar un nuevo comando bash.")
            break
        print(f"🔎 Análisis del error:\n{analisis}")
        print(f"💡 Nuevo comando generado:\n{nuevo_comando}")
        guardar_prompt(analisis)
        if nuevo_comando.strip() == comando_actual.strip():
            print("🔁 El comando sugerido es igual al anterior. No se reintenta.")
            break
        COMANDOS_FILE.write_text(nuevo_comando.strip() + "\n", encoding="utf-8")
        guardar_ultimo_error(error_texto)
        intentos += 1
        time.sleep(2)
    else:
        print("❌ Se alcanzó el máximo de intentos sin éxito.")

if __name__ == "__main__":
    ciclo_bash_codex()
