#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
from pathlib import Path

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
ESTADO_FILE = Path("/tmp/estado_bash.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")


def ejecutar_bash():
    if not COMANDOS_FILE.exists():
        print(f"No existe {COMANDOS_FILE}, nada que ejecutar.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("No existe /tmp/comandos_codex.sh", encoding="utf-8")
        return
    comandos = COMANDOS_FILE.read_text(encoding="utf-8").strip()
    if not comandos:
        print("El archivo de comandos está vacío.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("El archivo de comandos está vacío.", encoding="utf-8")
        return
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
        if resultado.returncode == 0:
            ESTADO_FILE.write_text("OK", encoding="utf-8")
            if ERROR_FILE.exists():
                ERROR_FILE.unlink()
        else:
            ESTADO_FILE.write_text("ERROR", encoding="utf-8")
            # Preferir stderr, si no hay, usar stdout
            error_out = resultado.stderr if resultado.stderr else resultado.stdout
            ERROR_FILE.write_text(error_out, encoding="utf-8")
    except Exception as e:
        print(f"Excepción al ejecutar bash: {e}")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text(str(e), encoding="utf-8")

if __name__ == "__main__":
    ejecutar_bash()
