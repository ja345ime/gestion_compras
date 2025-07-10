#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import shlex
from pathlib import Path

COMANDOS_FILE = Path("/tmp/comandos_codex.sh")
ESTADO_FILE = Path("/tmp/estado_bash.txt")
ERROR_FILE = Path("/tmp/error_bash_codex.txt")

# SECURITY: Define allowed commands to prevent arbitrary command execution
ALLOWED_COMMANDS = {
    'ls', 'cat', 'grep', 'head', 'tail', 'wc', 'find', 'sort', 'uniq',
    'ps', 'df', 'du', 'free', 'top', 'uptime', 'whoami', 'id',
    'git', 'pip', 'python', 'python3', 'pytest', 'flask'
}

def is_command_safe(command_line):
    """
    Basic security check to ensure only safe commands are executed.
    This is a simplified check - in production, implement more robust validation.
    """
    try:
        # Split the command line to get the base command
        tokens = shlex.split(command_line)
        if not tokens:
            return False
        
        base_command = tokens[0].split('/')[-1]  # Get command name without path
        
        # Check if the base command is in our allowed list
        if base_command not in ALLOWED_COMMANDS:
            return False
            
        # Additional checks for dangerous patterns
        dangerous_patterns = ['rm', 'rmdir', 'mv', 'cp', 'chmod', 'chown', 
                            'sudo', 'su', 'passwd', 'userdel', 'useradd',
                            '>', '>>', '|', '&', ';', '$(', '`']
        
        command_str = ' '.join(tokens)
        for pattern in dangerous_patterns:
            if pattern in command_str:
                return False
                
        return True
    except Exception:
        return False

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
    
    # SECURITY: Validate commands before execution
    if not is_command_safe(comandos):
        print("Comando no permitido por razones de seguridad.")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("Comando no permitido por razones de seguridad.", encoding="utf-8")
        return
    
    try:
        # FIXED: Use shlex.split to safely parse command arguments
        command_args = shlex.split(comandos)
        resultado = subprocess.run(
            command_args,
            shell=False,  # FIXED: Never use shell=True
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
    except ValueError as e:
        print(f"Error parsing command: {e}")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text(f"Error parsing command: {e}", encoding="utf-8")
    except subprocess.TimeoutExpired:
        print("Comando excedió el tiempo límite de 120 segundos")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text("Comando excedió el tiempo límite de 120 segundos", encoding="utf-8")
    except Exception as e:
        print(f"Excepción al ejecutar comando: {e}")
        ESTADO_FILE.write_text("ERROR", encoding="utf-8")
        ERROR_FILE.write_text(str(e), encoding="utf-8")

if __name__ == "__main__":
    ejecutar_bash()
