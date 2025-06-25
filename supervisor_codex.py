#!/usr/bin/env python3
import subprocess
from pathlib import Path

PROMPT_PATH = Path(__file__).parent / 'prompt_actual.txt'
LOG_PATH = Path(__file__).parent / 'supervisor_codex.log'

def log(msg):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    print(msg)

def ejecutar_automatizador():
    log("➡️ Ejecutando automatizador_codex.py")
    subprocess.run(['python3', 'automatizador_codex.py'])

def ejecutar_pruebas():
    log("➡️ Ejecutando pruebas (pytest)")
    resultado = subprocess.run(['pytest'], capture_output=True, text=True)
    log("🧪 STDOUT:\n" + resultado.stdout)
    log("🧪 STDERR:\n" + resultado.stderr)
    return resultado.returncode, resultado.stdout + resultado.stderr

def reintentar_fix(error_texto):
    log("⚠️ Fallaron las pruebas. Reintentando con nuevo prompt.")
    nuevo_prompt = f"Arregla los errores detectados en las pruebas. Logs:\n{error_texto}"
    PROMPT_PATH.write_text(nuevo_prompt, encoding='utf-8')
    ejecutar_automatizador()

def ejecutar_codex_entorno():
    log("🛠 Ejecutando codex_entorno.py")
    subprocess.run(['python3', 'codex_entorno.py'])

def main():
    log("========== INICIO SUPERVISOR ==========")
    ejecutar_automatizador()
    
    codigo, salida = ejecutar_pruebas()
    
    MAX_REINTENTOS = 2
    intentos = 0
    
    while codigo != 0 and intentos < MAX_REINTENTOS:
    	reintentar_fix(salida)
    	codigo, salida = ejecutar_pruebas()
    	intentos += 1

    if codigo != 0 or "502" in salida:
        ejecutar_codex_entorno()
    
    log("✅ Supervisor finalizado\n")

if __name__ == '__main__':
    main()
