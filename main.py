import os
import subprocess
import json
from typing import List

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

try:
    import openai  # type: ignore
except Exception:  # pragma: no cover - OpenAI puede no estar instalado
    openai = None  # type: ignore

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv es opcional
    def load_dotenv(*args, **kwargs):
        return None



# Cargar variables de entorno desde .env (para la API Key de OpenAI, etc.)
load_dotenv()

app = FastAPI(
    title="Agente de IA para Administración de Servidor",
    description="API para un agente de IA que puede interactuar con un servidor, generar código y resolver problemas.",
    version="0.1.0"
)
print("✅ main.py SE ESTÁ EJECUTANDO")
# --- Configuración del LLM (Modelo de Lenguaje Grande) ---
# Es crucial que tengas una API Key válida para un LLM.
# Si no tienes una, puedes usar un modelo local o simularlo.
# Para GPT-4, necesitarías la API Key de OpenAI.
# Si la variable de entorno OPENAI_API_KEY no está configurada, esto fallará.
# Para este ejemplo, usaremos la API de OpenAI directamente.
# Si quieres simular, puedes crear una clase que imite el comportamiento del modelo.
# Por ejemplo:
# class MockLLM:
#     def invoke(self, messages):
#         print(f"MockLLM recibió: {messages}")
#         # Simula una respuesta simple
#         return AIMessage(content="Simulando una respuesta del LLM.")
# llm = MockLLM()

# Intenta cargar la API Key de OpenAI. Si no está, advierte.
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("ADVERTENCIA: La variable de entorno OPENAI_API_KEY no está configurada.")
    print("El agente intentará usarla, pero fallará si no es válida.")
    print("Para un uso real, asegúrate de configurarla o usa un LLM local/alternativo.")
    print("Puedes obtener una en https://platform.openai.com/account/api-keys")

if openai and openai_api_key:
    openai.api_key = openai_api_key


# --- Definición de Herramientas para el Agente ---
# Estas funciones simulan las interacciones con el servidor.
# NOTA IMPORTANTE: Para un entorno de producción, la ejecución de comandos Bash (run_bash)
# y la edición de archivos DEBEN hacerse a través de SSH (usando librerías como paramiko o pexpect)
# y con permisos muy limitados para el usuario SSH del agente.
# Aquí se usan subprocess para simplificar la demostración local.

def run_bash(cmd: str) -> str:
    """
    Ejecuta un comando Bash en el servidor y devuelve su salida.
    ADVERTENCIA: Para un entorno real, esto DEBERÍA usar SSH (paramiko/pexpect)
    con permisos limitados, no subprocess localmente.
    Ejemplo: run_bash("ls -la /var/www/html")
    """
    try:
        print(f"Ejecutando comando Bash: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return f"Comando ejecutado con éxito:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.CalledProcessError as e:
        return f"Error al ejecutar comando Bash:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}\nError: {e}"
    except Exception as e:
        return f"Error inesperado al ejecutar comando Bash: {e}"

def edit_file(path: str, content: str, mode: str = "overwrite") -> str:
    """
    Modifica el contenido de un archivo en la ruta especificada.
    'mode' puede ser 'overwrite' (sobrescribe el archivo), 'append' (añade al final) o 'insert_line_after' (inserta después de una línea específica).
    Para 'insert_line_after', 'content' debe ser un JSON con {'line_to_find': '...', 'new_content': '...'}.
    Ejemplo: edit_file("config.py", "DEBUG = False", mode="overwrite")
    Ejemplo: edit_file("logs/app.log", "Nuevo log entry", mode="append")
    Ejemplo: edit_file("index.html", '{"line_to_find": "<div id=\\"app\\">", "new_content": "  <button>Nuevo Botón</button>"}', mode="insert_line_after")
    """
    try:
        if mode == "overwrite":
            with open(path, 'w') as f:
                f.write(content)
            return f"Archivo '{path}' sobrescrito con éxito."
        elif mode == "append":
            with open(path, 'a') as f:
                f.write("\n" + content)
            return f"Contenido añadido al final del archivo '{path}'."
        elif mode == "insert_line_after":
            try:
                params = json.loads(content)
                line_to_find = params['line_to_find']
                new_content = params['new_content']
            except json.JSONDecodeError:
                return "Error: Para 'insert_line_after', 'content' debe ser un JSON válido."

            with open(path, 'r') as f:
                lines = f.readlines()

            new_lines = []
            inserted = False
            for line in lines:
                new_lines.append(line)
                if line_to_find in line and not inserted:
                    new_lines.append(new_content + "\n")
                    inserted = True
            
            if not inserted:
                return f"Advertencia: No se encontró la línea '{line_to_find}' en '{path}'. No se insertó el contenido."

            with open(path, 'w') as f:
                f.writelines(new_lines)
            return f"Contenido insertado después de '{line_to_find}' en '{path}'."
        else:
            return f"Modo de edición '{mode}' no soportado. Use 'overwrite', 'append' o 'insert_line_after'."
    except FileNotFoundError:
        return f"Error: Archivo '{path}' no encontrado."
    except Exception as e:
        return f"Error al editar archivo '{path}': {e}"

def restart_service(service_name: str) -> str:
    """
    Reinicia un servicio del sistema (ej. gunicorn, nginx, apache2).
    ADVERTENCIA: Esto requiere permisos de sudo en el servidor para el usuario que ejecuta el agente.
    Ejemplo: restart_service("gunicorn")
    """
    try:
        print(f"Intentando reiniciar servicio: {service_name}")
        # Usar sudo para reiniciar servicios. Esto requiere configuración previa de sudoers.
        result = subprocess.run(['sudo', 'systemctl', 'restart', service_name], capture_output=True, text=True, check=True)
        return f"Servicio '{service_name}' reiniciado con éxito:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.CalledProcessError as e:
        return f"Error al reiniciar servicio '{service_name}':\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}\nError: {e}"
    except Exception as e:
        return f"Error inesperado al reiniciar servicio '{service_name}': {e}"

def run_tests(test_path: str = "tests/") -> str:
    """
    Ejecuta los tests de Pytest en la ruta especificada (por defecto 'tests/').
    Devuelve la salida completa de Pytest.
    Ejemplo: run_tests("tests/my_app_tests.py")
    """
    try:
        print(f"Ejecutando tests en: {test_path}")
        # Simula la creación de un archivo de test si no existe para la demo
        if not os.path.exists(test_path):
            os.makedirs(test_path)
            with open(os.path.join(test_path, "test_example.py"), "w") as f:
                f.write("""
def test_example_success():
    assert True

def test_example_failure():
    assert False # Este test fallará para demostrar la corrección
""")
            print(f"Creado archivo de test de ejemplo en {test_path}/test_example.py")

        result = subprocess.run(['pytest', test_path], capture_output=True, text=True, check=False) # check=False para capturar fallos
        if result.returncode == 0:
            return f"Tests ejecutados con éxito:\n{result.stdout}"
        else:
            return f"Tests ejecutados con fallos (código de salida {result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{e.stderr}"
    except FileNotFoundError:
        return "Error: pytest no encontrado. Asegúrate de que esté instalado (pip install pytest)."
    except Exception as e:
        return f"Error inesperado al ejecutar tests: {e}"

def check_logs(log_path: str = "logs/app.log", num_lines: int = 100) -> str:
    """
    Lee las últimas N líneas de un archivo de log de aplicación.
    Ejemplo: check_logs("logs/nginx_error.log", 50)
    """
    try:
        print(f"Leyendo últimas {num_lines} líneas de: {log_path}")
        # Simula la creación de un archivo de log si no existe para la demo
        if not os.path.exists(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path))
        if not os.path.exists(log_path):
            with open(log_path, "w") as f:
                f.write("Log de prueba 1\nLog de prueba 2\nLog de prueba 3\n")
            print(f"Creado archivo de log de ejemplo en {log_path}")

        with open(log_path, 'r') as f:
            lines = f.readlines()
        return "".join(lines[-num_lines:])
    except FileNotFoundError:
        return f"Error: Archivo '{path}' no encontrado."
    except Exception as e:
        return f"Error inesperado al leer log: {e}"

class PromptRequest(BaseModel):
    prompt: str


class AgentResponse(BaseModel):
    status: str
    message: str
    full_log: List[str]


@app.post("/run-agent", response_model=AgentResponse)
async def run_agent(request: PromptRequest = Body(...)):
    """Ejecuta el agente de IA con el prompt dado y devuelve el resultado."""
    prompt = request.prompt
    full_log = [f"Prompt recibido: {prompt}"]

    try:
        if openai and openai_api_key:
            client = openai.OpenAI(api_key=openai_api_key)
            respuesta = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
            )
            mensaje = respuesta.choices[0].message.content
        else:
            mensaje = f"Simulación de respuesta para: {prompt}"
        full_log.append(mensaje)
        return AgentResponse(status="success", message=mensaje, full_log=full_log)
    except Exception as e:
        print(f"Error en el agente: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del agente: {e}")

# --- Instrucciones para ejecutar el servidor FastAPI ---
# Para ejecutar esta API, guarda el código como `main.py` y luego en tu terminal:
# 1. Asegúrate de tener un entorno virtual limpio:
#    deactivate # Si estás en un entorno virtual
#    rm -rf venv_agente # Elimina el entorno virtual existente
#    rm -rf ~/.cache/pip # Limpia la caché global de pip
#    rm -rf __pycache__ # Elimina cachés de Python
#    python3 -m venv venv_agente # Crea un nuevo entorno virtual
#    source venv_agente/bin/activate # Activa el entorno virtual
#
# 2. Instala las dependencias más recientes:
#    pip install fastapi uvicorn langchain langchain-openai langgraph python-dotenv
#    (Si usas paramiko para SSH: pip install paramiko)
#    (Si usas pexpect para SSH: pip install pexpect)
#    (Si usas pytest para tests: pip install pytest)
#
# 3. Crea un archivo `.env` en la misma carpeta con tu API Key de OpenAI:
#    OPENAI_API_KEY="tu_api_key_de_openai_aqui"
#
# 4. Ejecuta el servidor:
#    uvicorn main:app --host 0.0.0.0 --port 8001
#
# 5. Podrás probarlo con una herramienta como Postman, Insomnia, o directamente desde N8N
#    en la URL http://localhost:8001/run-agent con un POST request.

# --- Ejemplo de uso (desde N8N o CURL) ---
# POST http://localhost:8001/run-agent
# Headers: Content-Type: application/json
# Body:
# {
#   "prompt": "Agrega un nuevo h1 con el texto 'Bienvenido a mi App' en la línea después de <div id=\"app\"> en el archivo index.html. Luego, ejecuta los tests y reinicia el servicio de gunicorn."
# }
#
# O un prompt más simple:
# {
#   "prompt": "Lee las últimas 50 líneas del log de la aplicación en logs/app.log"
# }
#
# O para simular un fallo y corrección (si el test_example_failure está activo):
# {
#   "prompt": "Ejecuta los tests de la aplicación. Si hay fallos, dime qué pasó."
# }
