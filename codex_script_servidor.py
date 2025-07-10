#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import time
import os
from pathlib import Path

def ejecutar_tests():
    """
    Ejecuta los tests y guarda el resultado en un archivo.
    FIXED: Replaced shell=True with safe subprocess call.
    """
    try:
        # FIXED: Use shell=False and proper argument list to prevent command injection
        result = subprocess.run(
            ["pytest", "tests/"],
            shell=False,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        # Save result to file
        with open("/tmp/resultado.txt", "w") as f:
            f.write(f"Return code: {result.returncode}\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\nSTDERR:\n")
            f.write(result.stderr)
            
        print(f"Tests ejecutados. Return code: {result.returncode}")
        print("Resultado guardado en /tmp/resultado.txt")
        
    except subprocess.TimeoutExpired:
        error_msg = "Tests excedieron el tiempo límite de 5 minutos"
        print(error_msg)
        with open("/tmp/resultado.txt", "w") as f:
            f.write(f"ERROR: {error_msg}\n")
    except Exception as e:
        error_msg = f"Error ejecutando tests: {e}"
        print(error_msg)
        with open("/tmp/resultado.txt", "w") as f:
            f.write(f"ERROR: {error_msg}\n")

if __name__ == "__main__":
    ejecutar_tests()
