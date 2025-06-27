#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
from pathlib import Path

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
RESULTADO_FILE = Path("/tmp/resultado_bash_codex.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")
ESTADO_FILE = Path("/tmp/estado_bash.txt")


def ejecutar_bash():
    if not COMANDOS_FILE.exists():
        print(f"No existe {COMANDOS_FILE}, nada que ejecutar.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        return
    comandos = COMANDOS_FILE.read_text(encoding="utf-8")
    try:
        resultado = subprocess.run(
            ["bash", "-c", comandos],
            capture_output=True,
            text=True,
            timeout=120
        )
        salida = (resultado.stdout or "") + (resultado.stderr or "")
        print(salida)
        RESULTADO_FILE.write_text(salida, encoding="utf-8")
        if resultado.returncode != 0:
            ERROR_FILE.write_text(salida, encoding="utf-8")
            ESTADO_FILE.write_text("ERROR", encoding="utf-8")
            print(f"❌ Error al ejecutar bash. Código: {resultado.returncode}")
        else:
            if ERROR_FILE.exists():
                ERROR_FILE.unlink()
            ESTADO_FILE.write_text("OK", encoding="utf-8")
            print("✅ Comando bash ejecutado correctamente.")
    except Exception as e:
        error_msg = str(e)
        print(error_msg)
        ERROR_FILE.write_text(error_msg, encoding="utf-8")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")

if __name__ == "__main__":
    ejecutar_bash()
