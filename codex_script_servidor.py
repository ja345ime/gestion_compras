"""
Este script automatiza la validación de cambios en el código fuente mediante prompts y pruebas automáticas.

IMPORTANTE: Este script debe ejecutarse únicamente en entornos de desarrollo o staging, nunca en producción.

Requiere que la variable de entorno OPENAI_API_KEY esté definida para la integración con servicios de OpenAI.

Flujo:
1. Lee el prompt desde /tmp/prompt.txt
2. Ejecuta las pruebas automáticas con pytest
3. Escribe el resultado en /tmp/estado.txt y, si hay error, el detalle en /tmp/falla.txt
"""
import os
import subprocess

PROMPT_PATH = "/tmp/prompt.txt"
RESULTADO_PATH = "/tmp/resultado.txt"
FALLA_PATH = "/tmp/falla.txt"
ESTADO_PATH = "/tmp/estado.txt"

# Verifica la variable de entorno OPENAI_API_KEY
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("La variable de entorno OPENAI_API_KEY no está definida. Configúrala antes de ejecutar este script.")

# 1. Lee el prompt (esto es solo para registro, el cambio lo hace otro proceso)
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    prompt = f.read()

# 2. Ejecuta las pruebas automáticas
subprocess.run("pytest tests/ > /tmp/resultado.txt", shell=True)

# 3. Analiza el resultado
with open(RESULTADO_PATH, "r", encoding="utf-8") as f:
    resultado = f.read()

if ("FAILED" in resultado) or ("ERROR" in resultado):
    with open(FALLA_PATH, "w", encoding="utf-8") as f:
        f.write(resultado)
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        f.write("ERROR")
else:
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        f.write("OK")
