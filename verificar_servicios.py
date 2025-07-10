import subprocess
import json

estado = ""
log = ""

# FIXED: Use shell=False to prevent command injection
try:
    gunicorn = subprocess.run(["systemctl", "is-active", "--quiet", "gunicorn"], shell=False, capture_output=True, text=True)
    if gunicorn.returncode == 0:
        estado += "Gunicorn OK\n"
    else:
        estado += "Gunicorn ERROR\n"
        log_result = subprocess.run(["journalctl", "-u", "gunicorn", "--no-pager", "-n", "20"], 
                                  shell=False, capture_output=True, text=True)
        log += log_result.stdout + "\n"
except Exception as e:
    estado += f"Gunicorn ERROR: {e}\n"
    log += f"Error checking gunicorn: {e}\n"

try:
    nginx = subprocess.run(["systemctl", "is-active", "--quiet", "nginx"], shell=False, capture_output=True, text=True)
    if nginx.returncode == 0:
        estado += "Nginx OK\n"
    else:
        estado += "Nginx ERROR\n"
        log_result = subprocess.run(["journalctl", "-u", "nginx", "--no-pager", "-n", "20"],
                                  shell=False, capture_output=True, text=True)
        log += log_result.stdout + "\n"
except Exception as e:
    estado += f"Nginx ERROR: {e}\n"
    log += f"Error checking nginx: {e}\n"

# FIXED: Use shell=False for system log reading
try:
    # Try to read syslog, fallback to messages
    syslog_result = subprocess.run(["tail", "-n", "30", "/var/log/syslog"], 
                                 shell=False, capture_output=True, text=True)
    if syslog_result.returncode == 0:
        log += syslog_result.stdout
    else:
        messages_result = subprocess.run(["tail", "-n", "30", "/var/log/messages"],
                                       shell=False, capture_output=True, text=True)
        if messages_result.returncode == 0:
            log += messages_result.stdout
except Exception as e:
    log += f"Error reading system logs: {e}\n"

estado_final = "OK" if "ERROR" not in estado else "ERROR"

output = {
    "estado": estado_final,
    "status": estado.strip(),
    "log": log.strip()
}

try:
    with open("/home/gestion_compras/resultado_pruebas.json", "w") as f:
        json.dump(output, f, indent=2)
except Exception as e:
    print(f"Error writing results file: {e}")

print(json.dumps(output))
