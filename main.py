# main.py
import os
import subprocess
from typing import TypedDict
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from dotenv import load_dotenv

# Cargar variables de entorno desde .env, si está disponible
load_dotenv()

# Cargar la API de OpenAI y herramientas de LangChain
try:
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_openai_functions_agent, AgentExecutor
    from langchain.tools import tool
    from langgraph.graph import StateGraph, END
    from langchain.agents.openai_functions_agent.prompt import FUNCTIONS_AGENT_PROMPT
except ImportError as e:
    raise ImportError("Necesitas instalar langchain y sus dependencias para ejecutar este agente.") 

# --- Definición de herramientas (Tools) para el agente ---
# Se utiliza el decorador @tool de LangChain para permitir múltiples argumentos (OpenAI function-calling).
agent_log = []  # Registro global de acciones del agente (se reinicia en cada petición)

@tool
def run_bash(cmd: str) -> str:
    """Ejecuta un comando Bash en el servidor y devuelve su salida."""
    global agent_log
    agent_log.append(f"→ Ejecutando comando Bash: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        output = f"Comando ejecutado con éxito:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        agent_log.append(f"✔ Resultado run_bash:\n{output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = (f"Error al ejecutar comando Bash:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}\nError: {e}")
        agent_log.append(f"✖ Error en run_bash:\n{error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error inesperado al ejecutar comando Bash: {e}"
        agent_log.append(f"✖ Error en run_bash (inesperado): {error_msg}")
        return error_msg

@tool
def overwrite_file(path: str, content: str) -> str:
    """Sobrescribe el archivo especificado con el contenido proporcionado."""
    global agent_log
    agent_log.append(f"→ Sobrescribiendo archivo: {path}")
    try:
        with open(path, 'w') as f:
            f.write(content)
        result = f"Archivo '{path}' sobrescrito con éxito."
        agent_log.append(f"✔ Resultado overwrite_file: {result}")
        return result
    except FileNotFoundError:
        error_msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ Error en overwrite_file: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error al sobrescribir archivo '{path}': {e}"
        agent_log.append(f"✖ Error en overwrite_file: {error_msg}")
        return error_msg

@tool
def append_file(path: str, content: str) -> str:
    """Agrega el texto proporcionado al final del archivo especificado."""
    global agent_log
    agent_log.append(f"→ Agregando contenido al final del archivo: {path}")
    try:
        with open(path, 'a') as f:
            f.write("\n" + content)
        result = f"Contenido añadido al final del archivo '{path}'."
        agent_log.append(f"✔ Resultado append_file: {result}")
        return result
    except FileNotFoundError:
        error_msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ Error en append_file: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error al agregar contenido al archivo '{path}': {e}"
        agent_log.append(f"✖ Error en append_file: {error_msg}")
        return error_msg

@tool
def insert_line_after(path: str, line_to_find: str, new_line: str) -> str:
    """Inserta una nueva línea en el archivo dado, después de la primera aparición de 'line_to_find'."""
    global agent_log
    agent_log.append(f"→ Insertando línea en {path} después de '{line_to_find}'")
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        error_msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ Error en insert_line_after: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error al leer archivo '{path}': {e}"
        agent_log.append(f"✖ Error en insert_line_after: {error_msg}")
        return error_msg
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line_to_find in line and not inserted:
            new_lines.append(new_line + ("\n" if not new_line.endswith("\n") else ""))
            inserted = True
    if not inserted:
        msg = f"Advertencia: No se encontró la línea '{line_to_find}' en '{path}'. No se insertó el contenido."
        agent_log.append(f"✔ Resultado insert_line_after: {msg}")
        return msg
    try:
        with open(path, 'w') as f:
            f.writelines(new_lines)
        result = f"Contenido insertado después de '{line_to_find}' en '{path}'."
        agent_log.append(f"✔ Resultado insert_line_after: {result}")
        return result
    except Exception as e:
        error_msg = f"Error al escribir en el archivo '{path}': {e}"
        agent_log.append(f"✖ Error en insert_line_after: {error_msg}")
        return error_msg

@tool
def restart_service(service_name: str) -> str:
    """Reinicia un servicio del sistema usando systemctl (requiere permisos adecuados)."""
    global agent_log
    agent_log.append(f"→ Reiniciando servicio: {service_name}")
    try:
        result = subprocess.run(['sudo', 'systemctl', 'restart', service_name],
                                 capture_output=True, text=True, check=True)
        output = (f"Servicio '{service_name}' reiniciado con éxito:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        agent_log.append(f"✔ Resultado restart_service:\n{output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = (f"Error al reiniciar servicio '{service_name}':\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}\nError: {e}")
        agent_log.append(f"✖ Error en restart_service: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error inesperado al reiniciar servicio '{service_name}': {e}"
        agent_log.append(f"✖ Error en restart_service: {error_msg}")
        return error_msg

@tool
def run_tests(test_path: str = "tests/") -> str:
    """Ejecuta PyTest en la ruta especificada (por defecto 'tests/') y devuelve la salida."""
    global agent_log
    agent_log.append(f"→ Ejecutando tests Pytest en: {test_path}")
    try:
        # Si no existe la carpeta de tests, creamos un test de ejemplo (para demostración)
        if not os.path.exists(test_path):
            os.makedirs(test_path, exist_ok=True)
        example_test = os.path.join(test_path, "test_example.py")
        if not os.path.exists(example_test):
            with open(example_test, "w") as f:
                f.write('''\
def test_example_success():
    assert True

def test_example_failure():
    assert False  # Este test fallará para demostrar la corrección
''')
            agent_log.append(f"Creado archivo de test de ejemplo: {example_test}")
        result = subprocess.run(['pytest', test_path], capture_output=True, text=True)
        if result.returncode == 0:
            output = f"Tests ejecutados con éxito:\n{result.stdout}"
        else:
            output = (f"Tests ejecutados con fallos (código {result.returncode}):\n"
                      f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        agent_log.append(f"✔ Resultado run_tests:\n{output}")
        return output
    except FileNotFoundError:
        error_msg = "Error: pytest no encontrado. Asegúrate de que esté instalado."
        agent_log.append(f"✖ Error en run_tests: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error inesperado al ejecutar tests: {e}"
        agent_log.append(f"✖ Error en run_tests: {error_msg}")
        return error_msg

@tool
def check_logs(log_path: str = "logs/app.log", num_lines: int = 100) -> str:
    """Lee las últimas 'num_lines' líneas del archivo de log especificado."""
    global agent_log
    agent_log.append(f"→ Leyendo últimas {num_lines} líneas de log: {log_path}")
    try:
        if not os.path.exists(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            with open(log_path, "w") as f:
                f.write("Log de prueba 1\nLog de prueba 2\nLog de prueba 3\n")
            agent_log.append(f"Creado archivo de log de ejemplo: {log_path}")
        with open(log_path, 'r') as f:
            lines = f.readlines()
        output = "".join(lines[-num_lines:]) if num_lines > 0 else ""
        agent_log.append(f"✔ Resultado check_logs:\n{output}")
        return output
    except Exception as e:
        error_msg = f"Error al leer el log '{log_path}': {e}"
        agent_log.append(f"✖ Error en check_logs: {error_msg}")
        return error_msg

@tool
def read_file(path: str) -> str:
    """Lee el contenido completo de un archivo de texto."""
    global agent_log
    agent_log.append(f"→ Leyendo archivo completo: {path}")
    try:
        with open(path, 'r') as f:
            content = f.read()
        agent_log.append(f"✔ Resultado read_file: (contenido leído, {len(content)} bytes)")
        return content
    except FileNotFoundError:
        error_msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ Error en read_file: {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error al leer archivo '{path}': {e}"
        agent_log.append(f"✖ Error en read_file: {error_msg}")
        return error_msg

# Lista de herramientas disponibles para el agente
tools = [run_bash, overwrite_file, append_file, insert_line_after,
         restart_service, run_tests, check_logs, read_file]

# --- Configuración del modelo de lenguaje (LLM) y agente ---
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print(
        "ADVERTENCIA: OPENAI_API_KEY no está configurada. "
        "El agente no se inicializará hasta que proporciones la clave."
    )
    llm = None
    agent_executor = None
else:
    # Usamos GPT-4 (o GPT-3.5) a través de la API de OpenAI
    llm = ChatOpenAI(
        model_name=os.getenv("OPENAI_MODEL", "gpt-4-0613"),
        temperature=0,
        openai_api_key=openai_api_key,
    )
    # Crear el agente base con las herramientas definidas
    base_agent = create_openai_functions_agent(llm, tools, FUNCTIONS_AGENT_PROMPT)
    base_executor = AgentExecutor(agent=base_agent, tools=tools, verbose=False)

    class AgentState(TypedDict):
        input: str
        result: str | None
        done: bool

    def interpret_prompt(state: AgentState) -> AgentState:
        agent_log.append(f"→ Interpretando prompt: {state['input']}")
        return state

    def execute_tool(state: AgentState) -> AgentState:
        response = base_executor.invoke({"input": state["input"]})
        result = response.get("output", response) if isinstance(response, dict) else response
        state["result"] = result
        state["done"] = True
        return state

    def analyze_result(state: AgentState) -> AgentState:
        agent_log.append(f"✔ Resultado herramienta:\n{state.get('result', '')}")
        return state

    def decide_next(state: AgentState) -> str:
        return "end" if state.get("done") else "repeat"

    workflow = StateGraph(AgentState)
    workflow.add_node("interpret_prompt", interpret_prompt)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_node("analyze_result", analyze_result)
    workflow.add_node("decide", decide_next)
    workflow.add_edge("interpret_prompt", "execute_tool")
    workflow.add_edge("execute_tool", "analyze_result")
    workflow.add_edge("analyze_result", "decide")
    workflow.add_conditional_edges("decide", {"repeat": "interpret_prompt", "end": END})
    workflow.set_entry_point("interpret_prompt")
    agent_executor = workflow.compile()

# Modelos Pydantic para la API HTTP
class PromptRequest(BaseModel):
    prompt: str

class AgentResponse(BaseModel):
    status: str
    message: str
    full_log: list[str]

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Agente IA Autónomo para Desarrollo/Mantenimiento",
    description="Agente de IA que puede leer/escribir archivos, ejecutar comandos de sistema, correr tests y analizar logs para mantener una app Flask.",
    version="0.2.0"
)

@app.post("/run-agent", response_model=AgentResponse)
async def run_agent(request: PromptRequest = Body(...)):
    """Endpoint HTTP para ejecutar el agente con un prompt dado."""
    prompt = request.prompt
    # Reiniciar el log de acciones por cada solicitud
    global agent_log
    agent_log = [f"Prompt recibido: {prompt}"]
    try:
        if agent_executor is None:
            raise RuntimeError(
                "OPENAI_API_KEY no configurada. Configúrala y reinicia la aplicación."
            )
        # Ejecutar el agente con el prompt del usuario
        result_state = agent_executor.invoke({"input": prompt})
        result = result_state.get("result") if isinstance(result_state, dict) else result_state
        if not isinstance(result, str):
            result = str(result)
        agent_log.append(f"Respuesta final del agente: {result}")
        return AgentResponse(status="success", message=result, full_log=agent_log)
    except Exception as e:
        error_msg = f"Error interno del agente: {e}"
        agent_log.append(f"✖ {error_msg}")
        # Responder con un error HTTP 500 y el detalle
        raise HTTPException(status_code=500, detail=error_msg)

# --- Instrucciones de ejecución ---
# 1. Instala las dependencias requeridas:
#    pip install fastapi uvicorn langchain openai langchain-openai langgraph python-dotenv pytest
# 2. Define tu clave de API de OpenAI en una variable de entorno o en un archivo .env como OPENAI_API_KEY="TU_API_KEY".
# 3. Inicia la aplicación:
#    uvicorn main:app --host 0.0.0.0 --port 8000
# 4. Envía solicitudes POST al endpoint /run-agent con JSON {"prompt": "..."}.
#    Ejemplo:
#       curl -X POST "http://localhost:8000/run-agent" -H "Content-Type: application/json" -d '{"prompt": "Lee las últimas 50 líneas de logs/app.log"}'
