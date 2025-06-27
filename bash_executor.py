#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
from pathlib import Path

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
RESULTADO_FILE = Path("/tmp/resultado_bash_codex.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")


def ejecutar_bash():
    if not COMANDOS_FILE.exists():
        print(f"No existe {COMANDOS_FILE}, nada que ejecutar.")
        return
    comandos = COMANDOS_FILE.read_text(encoding="utf-8")
    try:
        resultado = subprocess.run(
            ["bash", "-c", comandos],
            capture_output=True,
            text=True,
            timeout=120
        )
        RESULTADO_FILE.write_text(resultado.stdout + resultado.stderr, encoding="utf-8")
        if resultado.returncode != 0:
            ERROR_FILE.write_text(resultado.stdout + resultado.stderr, encoding="utf-8")
            print(f"❌ Error al ejecutar bash. Código: {resultado.returncode}")
        else:
            if ERROR_FILE.exists():
                ERROR_FILE.unlink()
            print("✅ Comando bash ejecutado correctamente.")
    except Exception as e:
        ERROR_FILE.write_text(str(e), encoding="utf-8")
        print(f"❌ Excepción al ejecutar bash: {e}")

if __name__ == "__main__":
    ejecutar_bash()
