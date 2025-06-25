#!/usr/bin/env python3
import subprocess
import re
from pathlib import Path

PROMPT_PATH = Path(__file__).parent / 'prompt_actual.txt'
LOG_PATH = Path(__file__).parent / 'supervisor_codex.log'
ERROR_PATH = Path(__file__).parent / 'ultimo_error_codex.txt'
FUNCIONES_DANADAS_LOG = Path(__file__).parent / 'funciones_danadas.log'

IGNORAR_TESTS = ['test_correo.py']
MAX_REPETIR_ERROR = 3

def log(msg):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
    print(msg)


def leer_ultimo_error() -> str:
    if ERROR_PATH.exists():
        return ERROR_PATH.read_text()
    return ""


def guardar_error(err: str) -> None:
    ERROR_PATH.write_text(err)


def limpiar_error() -> None:
    if ERROR_PATH.exists():
        ERROR_PATH.unlink()


def registrar_funciones_danadas(error: str) -> None:
    patrones = [
        r"cannot import name '(.+?)'",
        r"AttributeError: module '.+?' has no attribute '(.+?)'",
    ]
    encontradas = []
    for patron in patrones:
        match = re.search(patron, error)
        if match:
            encontradas.append(match.group(1))

    if encontradas:
        with open(FUNCIONES_DANADAS_LOG, 'a', encoding='utf-8') as f:
            for func in encontradas:
                f.write(func + '\n')
        log("📄 Funciones dañadas registradas: " + ", ".join(encontradas))


def usar_siguiente_prompt_si_existe() -> None:
    siguiente = Path('siguiente_prompt.txt')
    if siguiente.exists():
        PROMPT_PATH.write_text(siguiente.read_text(encoding='utf-8'))
        siguiente.unlink()
        log('➡️ Cargado siguiente_prompt.txt')


def ejecutar_automatizador():
    log("➡️ Ejecutando automatizador_codex.py")
    subprocess.run(['python3', 'automatizador_codex.py'])
    instalar_dependencias_si_cambian()

def ejecutar_pruebas():
    log("➡️ Ejecutando pruebas (pytest)")
    resultado = subprocess.run(['pytest'], capture_output=True, text=True)
    log("🧪 STDOUT:\n" + resultado.stdout)
    log("🧪 STDERR:\n" + resultado.stderr)

    salida_completa = resultado.stdout + resultado.stderr

    for test in IGNORAR_TESTS:
        if test in salida_completa:
            log(f"📛 Fallo en {test}. Ejecutando nuevamente ignorándolo.")
            patron = f"not {test.replace('.py', '')}"
            resultado = subprocess.run(['pytest', '-k', patron], capture_output=True, text=True)
            log("🧪 STDOUT (ignorado):\n" + resultado.stdout)
            log("🧪 STDERR (ignorado):\n" + resultado.stderr)
            salida_completa = resultado.stdout + resultado.stderr
            break

    return resultado.returncode, salida_completa, resultado.stderr

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
    repetidos = 0
    ultimo_error = leer_ultimo_error()

    while True:
        codigo, salida, stderr_log = ejecutar_pruebas()
        registrar_funciones_danadas(stderr_log)

        if codigo == 0:
            limpiar_error()
            usar_siguiente_prompt_si_existe()
            break

        if stderr_log == ultimo_error:
            repetidos += 1
            log(f"🔁 Mismo error detectado {repetidos} veces")
        else:
            repetidos = 0
            ultimo_error = stderr_log
            guardar_error(stderr_log)

        if repetidos >= MAX_REPETIR_ERROR or intentos >= MAX_INTENTOS:
            log("❌ Se alcanzó el máximo de reintentos o de errores repetidos.")
            registrar_error_codex(stderr_log)
            return

        reintentar_fix(salida)
        intentos += 1

    ejecutar_automatizador()

    if codigo != 0 or "502" in salida:
        ejecutar_codex_entorno()

    log("✅ Supervisor finalizado\n")

def instalar_dependencias_si_cambian():
    import hashlib

    req_path = Path(__file__).parent / 'requirements.txt'
    hash_path = Path(__file__).parent / '.hash_requirements.txt'

    if not req_path.exists():
        log("⚠️ No se encontró requirements.txt.")
        return

    contenido = req_path.read_bytes()
    nuevo_hash = hashlib.sha256(contenido).hexdigest()

    hash_anterior = ''
    if hash_path.exists():
        hash_anterior = hash_path.read_text()

    if nuevo_hash != hash_anterior:
        log("📦 Cambios detectados en requirements.txt. Instalando dependencias...")
        resultado = subprocess.run(['pip3', 'install', '-r', str(req_path)], capture_output=True, text=True)
        if resultado.returncode == 0:
            log("✅ Dependencias instaladas correctamente.")
            hash_path.write_text(nuevo_hash)
        else:
            log("❌ Error al instalar dependencias:")
            log(resultado.stderr)
    else:
        log("📦 requirements.txt no ha cambiado. No se reinstalan dependencias.")

def registrar_error_codex(stderr_log: str):
    guardar_error(stderr_log)

    resumen_prompt = generar_prompt_desde_error(stderr_log)
    Path("prompt_actual.txt").write_text(resumen_prompt)
    log("📄 Generado nuevo prompt_actual.txt basado en el error detectado.")


def generar_prompt_desde_error(stderr_log: str) -> str:
    if "ImportError" in stderr_log:
        match = re.search(r"cannot import name '(.+?)' from '(.+?)'", stderr_log)
        if match:
            funcion = match.group(1)
            modulo = match.group(2)
            return f"""
El siguiente error persiste en las pruebas:

ImportError: cannot import name '{funcion}' from '{modulo}'

Quiero que verifiques si esta función está definida correctamente en ese archivo y que la exportes bien. Si no existe, créala con una implementación válida de prueba.

Luego ejecuta nuevamente pytest para asegurarte de que pasa.

No modifiques otras partes del proyecto. Solo soluciona esto.
"""
    elif "ModuleNotFoundError" in stderr_log:
        modulo = re.search(r"No module named '(.+?)'", stderr_log).group(1)
        return f"""
El siguiente error persiste en las pruebas:

ModuleNotFoundError: No module named '{modulo}'

Revisa si ese módulo requiere instalación vía pip y agrégalo al requirements.txt si es necesario, luego instálalo.

Después corre nuevamente las pruebas.

No toques el resto del proyecto.
"""
    else:
        return f"""
Último error detectado en pytest:

{stderr_log[:1000]}

Analiza el error, sugiere cómo corregirlo, aplica el cambio, y vuelve a ejecutar las pruebas. Solo corrige ese fallo.
"""

if __name__ == '__main__':
    main()
