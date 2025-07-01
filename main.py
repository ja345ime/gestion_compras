"""Main file exposing a FastAPI endpoint that runs a LangGraph agent."""

import os
import subprocess
from typing import List, TypedDict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.runnables import RunnableLambda

# Load environment variables if a .env file is present
load_dotenv()

# Log of agent actions for each request
agent_log: List[str] = []


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
    """Insert a line after the first occurrence of another line."""
    global agent_log
    agent_log.append(f"→ Insertando línea en {path} después de '{line_to_find}'")
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        msg = f"Error: Archivo '{path}' no encontrado."
        agent_log.append(f"✖ {msg}")
        return msg
    inserted = False
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if line_to_find in line and not inserted:
            new_lines.append(new_line + ("\n" if not new_line.endswith("\n") else ""))
            inserted = True
    if not inserted:
        msg = f"Advertencia: No se encontró la línea '{line_to_find}' en '{path}'."
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


@tool
def run_tests(test_path: str = "tests/") -> str:
    """Run pytest on the given path and return the output."""
    global agent_log
    agent_log.append(f"→ Ejecutando tests Pytest en: {test_path}")
    try:
        result = subprocess.run(["pytest", test_path], capture_output=True, text=True)
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        agent_log.append(f"✔ Resultado run_tests:\n{output}")
        return output
    except Exception as e:
        msg = f"Error al ejecutar tests: {e}"
        agent_log.append(f"✖ {msg}")
        return msg


@tool
def check_logs(log_path: str = "logs/app.log", num_lines: int = 100) -> str:
    """Return the last `num_lines` of the specified log file."""
    global agent_log
    agent_log.append(f"→ Leyendo últimas {num_lines} líneas de log: {log_path}")
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        output = "".join(lines[-num_lines:])
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
    overwrite_file,
    append_file,
    insert_line_after,
    restart_service,
    run_tests,
    check_logs,
    read_file,
]


# --- LLM and agent setup ---
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    llm = ChatOpenAI(
        model_name=os.getenv("OPENAI_MODEL", "gpt-4-0613"),
        temperature=0,
        openai_api_key=openai_api_key,
    )
    agent = create_react_agent(tools, llm)

    class AgentState(TypedDict):
        input: str
        result: str | None

    def run_agent(state: AgentState) -> AgentState:
        result = agent.invoke({"input": state["input"]})
        agent_log.append(f"✔ Resultado del agente:\n{result}")
        return {"input": state["input"], "result": result}

    workflow = StateGraph(AgentState)
    workflow.add_node("run_agent", RunnableLambda(run_agent))
    workflow.set_entry_point("run_agent")
    workflow.set_finish_point("run_agent")
    agent_executor = workflow.compile()
else:
    llm = None
    agent_executor = None


class PromptRequest(BaseModel):
    prompt: str


class AgentResponse(BaseModel):
    status: str
    message: str
    full_log: List[str]


app = FastAPI(title="LangGraph Agent", version="1.0.0")


@app.post("/run-agent", response_model=AgentResponse)
async def run_agent_endpoint(request: PromptRequest):
    """Execute the agent with the provided prompt."""
    if agent_executor is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada")

    global agent_log
    agent_log = [f"Prompt recibido: {request.prompt}"]
    try:
        state = {"input": request.prompt, "result": None}
        result_state = agent_executor.invoke(state)
        result = result_state.get("result") if isinstance(result_state, dict) else str(result_state)
        agent_log.append(f"Respuesta final del agente: {result}")
        return AgentResponse(status="success", message=result, full_log=agent_log)
    except Exception as e:
        msg = f"Error interno del agente: {e}"
        agent_log.append(f"✖ {msg}")
        raise HTTPException(status_code=500, detail=msg)

