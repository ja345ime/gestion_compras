"""Main file exposing a FastAPI endpoint that runs a LangGraph agent."""

import os
import subprocess
from typing import List, TypedDict, Union, Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Cargar variables de entorno primero ---
# Es crucial que load_dotenv() se ejecute ANTES de que cualquier código intente leer variables de entorno.
load_dotenv()

# --- Importaciones de LangChain y LangGraph ---
# Usaremos las rutas de importación estándar para las versiones más recientes.
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage # Necesario para el historial de mensajes
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda  # Importar RunnableLambda

# --- Definición manual de ToolInvocation para evitar ModuleNotFoundError ---
# Si 'from langgraph.schema import ToolInvocation' falla constantemente,
# podemos definir una clase simple que cumpla con la interfaz esperada por LangGraph.
# LangGraph solo necesita que el objeto tenga atributos 'tool' y 'tool_input'.
class ToolInvocation(BaseModel):
    tool: str
    tool_input: Union[str, dict]


# Log de acciones del agente para cada solicitud (se reinicia en cada petición)
agent_log: List[str] = []

# --- Definición de herramientas (Tools) para el agente ---
# Se utiliza el decorador @tool de LangChain para permitir múltiples argumentos (OpenAI function-calling).

@tool
def run_bash(cmd: str) -> str:
    """Run a bash command on the server and return its output."""
    global agent_log
    agent_log.append(f"→ Ejecutando comando Bash: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        agent_log.append(f"✔ Resultado run_bash:\n{output}")
        return output
    except subprocess.CalledProcessError as e:
        msg = f"Error al ejecutar comando Bash:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        agent_log.append(f"✖ {msg}")
        return msg
    except Exception as e:
        msg = f"Error inesperado al ejecutar comando Bash: {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def leer_archivo(path: str) -> str:
    """Lee el contenido de un archivo dado su path."""
    global agent_log
    agent_log.append(f"→ Leyendo archivo: {path}")
    try:
        with open(path, "r") as f:
            contenido = f.read()
            agent_log.append(f"✔ Contenido leído: {contenido[:200]}...")
            return contenido
    except Exception as e:
        agent_log.append(f"✖ Error al leer el archivo: {e}")
        return f"Error leyendo el archivo: {e}"

@tool
def overwrite_file(path: str, content: str) -> str:
    """Overwrite the given file with the provided content."""
    global agent_log
    agent_log.append(f"→ Sobrescribiendo archivo: {path}")
    try:
        with open(path, "w") as f:
            f.write(content)
        msg = f"Archivo '{path}' sobrescrito con éxito."
        agent_log.append(f"✔ {msg}")
        return msg
    except Exception as e:
        msg = f"Error al sobrescribir archivo '{path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def append_file(path: str, content: str) -> str:
    """Append text to the end of a file."""
    global agent_log
    agent_log.append(f"→ Agregando contenido al final del archivo: {path}")
    try:
        with open(path, "a") as f:
            f.write("\n" + content)
        msg = f"Contenido añadido al final del archivo '{path}'."
        agent_log.append(f"✔ {msg}")
        return msg
    except Exception as e:
        msg = f"Error al agregar contenido al archivo '{path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def insert_line_after(path: str, line_to_find: str, new_line: str) -> str:
    """Insert a new line in the file given, after the first occurrence of 'line_to_find'."""
    global agent_log
    agent_log.append(f"→ Insertando línea en {path} después de '{line_to_find}'")
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ {msg}")
        return msg
    except Exception as e:
        msg = f"Error al leer archivo '{path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg
    
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line_to_find in line and not inserted:
            new_lines.append(new_line + ("\n" if not new_line.endswith("\n") else ""))
            inserted = True
    
    if not inserted:
        msg = f"Advertencia: No se encontró la línea '{line_to_find}' en '{path}'. No se insertó el contenido."
        agent_log.append(f"✔ {msg}")
        return msg
    
    try:
        with open(path, "w") as f:
            f.writelines(new_lines)
        msg = f"Contenido insertado después de '{line_to_find}' en '{path}'."
        agent_log.append(f"✔ {msg}")
        return msg
    except Exception as e:
        msg = f"Error al escribir en el archivo '{path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def restart_service(service_name: str) -> str:
    """Restart a system service using systemctl."""
    global agent_log
    agent_log.append(f"→ Reiniciando servicio: {service_name}")
    try:
        result = subprocess.run(["sudo", "systemctl", "restart", service_name], capture_output=True, text=True, check=True)
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        agent_log.append(f"✔ Resultado restart_service:\n{output}")
        return output
    except subprocess.CalledProcessError as e:
        msg = f"Error al reiniciar servicio '{service_name}':\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        agent_log.append(f"✖ {msg}")
        return msg
    except Exception as e:
        msg = f"Error inesperado al reiniciar servicio '{service_name}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def run_tests(test_path: str = "tests/") -> str:
    """Run pytest on the given path and return the output."""
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
        
        result = subprocess.run(["pytest", test_path], capture_output=True, text=True, check=False) # check=False para capturar fallos
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        agent_log.append(f"✔ Resultado run_tests:\n{output}")
        return output
    except FileNotFoundError:
        msg = "Error: pytest no encontrado. Asegúrate de que esté instalado."
        agent_log.append(f"✖ {msg}")
        return msg
    except Exception as e:
        msg = f"Error inesperado al ejecutar tests: {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def check_logs(log_path: str = "logs/app.log", num_lines: int = 100) -> str:
    """Return the last `num_lines` of the specified log file."""
    global agent_log
    agent_log.append(f"→ Leyendo últimas {num_lines} líneas de log: {log_path}")
    try:
        if not os.path.exists(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            with open(log_path, "w") as f:
                f.write("Log de prueba 1\nLog de prueba 2\nLog de prueba 3\n")
            agent_log.append(f"Creado archivo de log de ejemplo: {log_path}")
        
        with open(log_path, "r") as f:
            lines = f.readlines()
        output = "".join(lines[-num_lines:]) if num_lines > 0 else ""
        agent_log.append(f"✔ Resultado check_logs:\n{output}")
        return output
    except Exception as e:
        msg = f"Error al leer el log '{log_path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg

@tool
def read_file(path: str) -> str:
    """Read and return the entire contents of a text file."""
    global agent_log
    agent_log.append(f"→ Leyendo archivo completo: {path}")
    try:
        with open(path, "r") as f:
            content = f.read()
        agent_log.append(f"✔ Resultado read_file: contenido de {len(content)} bytes")
        return content
    except Exception as e:
        msg = f"Error al leer archivo '{path}': {e}"
        agent_log.append(f"✖ {msg}")
        return msg


# Lista de herramientas disponibles para el agente
tools = [
    run_bash,
    leer_archivo,
    overwrite_file,
    append_file,
    insert_line_after,
    restart_service,
    run_tests,
    check_logs,
    read_file
]

# --- Definición del estado del grafo para LangGraph ---
# El estado debe ser compatible con lo que LangGraph espera y lo que el agente necesita
class AgentState(TypedDict):
    messages: List[BaseMessage] # Historial de mensajes para el agente

# --- Función para ejecutar herramientas (necesaria para el nodo 'tool_node') ---
# Esta función debe definirse ANTES de que se use en el grafo.
def execute_tools(state: AgentState) -> Dict[str, Any]:
    last_message = state["messages"][-1]
    tool_outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args")
        
        # Buscar la herramienta por nombre y ejecutarla
        found_tool = next((t for t in tools if t.name == tool_name), None)
        if found_tool:
            try:
                output = found_tool.invoke(tool_args)
                tool_outputs.append(ToolMessage(content=str(output), tool_call_id=tool_call.get("id")))
            except Exception as e:
                tool_outputs.append(ToolMessage(content=f"Error ejecutando herramienta {tool_name}: {e}", tool_call_id=tool_call.get("id")))
        else:
            tool_outputs.append(ToolMessage(content=f"Herramienta {tool_name} no encontrada.", tool_call_id=tool_call.get("id")))
    
    # Añadir las salidas de las herramientas al historial de mensajes
    return {"messages": state["messages"] + tool_outputs}


# --- Configuración del modelo de lenguaje (LLM) y agente ---
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("ADVERTENCIA: OPENAI_API_KEY no está configurada. El agente no funcionará sin ella.")
    llm = None # Aseguramos que llm sea None si no hay API key
    agent_executor = None
else:
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"), # Usamos gpt-4o como default para las últimas versiones
        temperature=0,
        openai_api_key=openai_api_key,
    )

    # Definición del prompt para el agente ReAct
    
    # create_react_agent ya incluye placeholders para `tools` y `agent_scratchpad`
    # Simplificamos el prompt siguiendo las indicaciones de Codex
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un asistente experto."),
        ("human", "{{input}}")
    ])

    # Crear el agente con el LLM y las herramientas disponibles
    # create_react_agent es una Runnable, no necesita ser envuelta en StateGraph para su uso básico
    agent_runnable = create_react_agent(llm, tools=tools, prompt=prompt)
    agent_runnable = agent_runnable.with_config({"run_name": "agente"})
    agent_runnable = RunnableLambda(lambda x: {"input": x["messages"][-1].content}) | agent_runnable
    # Definimos la cadena de procesamiento para el nodo del agente
    # Esta cadena toma el 'messages' del AgentState y lo transforma en el 'input' y 'agent_scratchpad'
    # que espera el agent_runnable.
    agent_node_chain = (
        RunnablePassthrough.assign(
            input=lambda x: x["messages"][-1].content, # El input es el contenido del último HumanMessage
            agent_scratchpad=lambda x: [
                msg for msg in x["messages"][:-1] if isinstance(msg, (AIMessage, ToolMessage))
            ], # El scratchpad son los mensajes anteriores que no son HumanMessage
        )
        | agent_runnable # Luego pasamos esto al agente ReAct
    )

    # Construcción del grafo con LangGraph
    workflow = StateGraph(AgentState)
    workflow.add_node("agent_node", agent_node_chain) # Nodo para el agente, ahora es una cadena
    workflow.add_node("tool_node", execute_tools) # Nodo para ejecutar herramientas

    # Función para decidir el siguiente paso del grafo
    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        # Si el último mensaje del agente tiene llamadas a herramientas, ir al nodo de herramientas
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tool_node"
        # Si no tiene llamadas a herramientas, el agente ha terminado de responder
        return END

    # Definir la entrada del grafo
    workflow.set_entry_point("agent_node")

    # Definir las transiciones condicionales desde el nodo del agente
    workflow.add_conditional_edges(
        "agent_node",
        should_continue,
        {
            "tool_node": "tool_node", # Si hay tool_calls, ir a tool_node
            END: END # Si no, terminar
        }
    )
    # Después de ejecutar las herramientas, volver al agente para que evalúe la salida
    workflow.add_edge("tool_node", "agent_node")

    agent_executor = workflow.compile()


class PromptRequest(BaseModel):
    prompt: str


class AgentResponse(BaseModel):
    status: str
    message: str
    full_log: List[str]


app = FastAPI(
    title="Agente IA Autónomo para Desarrollo/Mantenimiento",
    description="Agente de IA que puede leer/escribir archivos, ejecutar comandos de sistema, correr tests y analizar logs para mantener una app Flask.",
    version="0.2.0"
)

@app.post("/run-agent")
async def run_agent(req: PromptRequest):
    """Execute the agent using a JSON body with a 'prompt' field."""
    if agent_executor is None:
        return JSONResponse(content={"detail": "OPENAI_API_KEY no configurada"}, status_code=500)

    try:
        # Convertir el campo 'prompt' en la estructura que espera el agente
        prompt = req.prompt
        messages = [HumanMessage(content=prompt)]
        inputs = {"messages": messages, "steps": []}

        result = agent_executor.invoke(inputs)
        return {"respuesta": result["messages"][-1].content}
    except Exception as e:
        return JSONResponse(content={"detail": f"Error interno del agente: {e}"}, status_code=500)
