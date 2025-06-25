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
    
    MAX_INTENTOS = 10
    intentos = 0

    while True:
        codigo, salida = ejecutar_pruebas()
        if codigo == 0:
            break
        if intentos >= MAX_INTENTOS:
            break
        reintentar_fix(salida)
        intentos += 1

    # Nueva lógica automática
    if intentos >= MAX_INTENTOS:
        log("❌ Se alcanzó el máximo de reintentos.")

        if (
            "Se alcanzó el máximo de reintentos" in salida
            or "ImportError" in salida
            or "cannot import name" in salida
        ):
            log(
                "⚠️ Se detectó error no resuelto. Se suspende el uso del nuevo prompt."
            )
            # El sistema no aplica el siguiente prompt automáticamente
            return

    # Solo si no hubo errores previos no resueltos
    ejecutar_automatizador()

    if codigo != 0 or "502" in salida:
        ejecutar_codex_entorno()
    
    log("✅ Supervisor finalizado\n")

if __name__ == '__main__':
    main()
