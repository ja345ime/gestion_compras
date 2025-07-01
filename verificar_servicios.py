import subprocess
import json

estado = ""
log = ""

gunicorn = subprocess.run("systemctl is-active --quiet gunicorn", shell=True)
if gunicorn.returncode == 0:
    estado += "Gunicorn OK\n"
else:
    estado += "Gunicorn ERROR\n"
    log += subprocess.getoutput("journalctl -u gunicorn --no-pager -n 20") + "\n"

nginx = subprocess.run("systemctl is-active --quiet nginx", shell=True)
if nginx.returncode == 0:
    estado += "Nginx OK\n"
else:
    estado += "Nginx ERROR\n"
    log += subprocess.getoutput("journalctl -u nginx --no-pager -n 20") + "\n"

log += subprocess.getoutput("tail -n 30 /var/log/syslog 2>/dev/null || tail -n 30 /var/log/messages")

estado_final = "OK" if "ERROR" not in estado else "ERROR"

output = {
    "estado": estado_final,
    "status": estado.strip(),
    "log": log.strip()
}

with open("/home/gestion_compras/resultado_pruebas.json", "w") as f:
    json.dump(output, f, indent=2)


print(json.dumps(output))
