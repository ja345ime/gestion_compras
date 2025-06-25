#!/usr/bin/env python3
"""Herramienta para diagnosticar y reparar la API de Codex.

Detecta procesos de Gunicorn, Flask o Nginx, revisa si el puerto 8000
está ocupado y valida el servicio ``codex_api.service``. Si encuentra
problemas intenta aplicar soluciones de forma automática y guarda un
registro de todo en ``codex_entorno.log``.
"""

from __future__ import annotations

import logging
import socket
import subprocess
from pathlib import Path

LOG_FILE = Path(__file__).with_name("codex_entorno.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _buscar_proceso(nombre: str) -> bool:
    """Busca un proceso por nombre utilizando ``pgrep`` o ``ps``."""

    try:
        proc = subprocess.run(
            ["pgrep", "-fl", nombre], capture_output=True, text=True, check=False
        )
        if proc.returncode == 0:
            logging.info("Proceso %s activo: %s", nombre, proc.stdout.strip())
            return True
        logging.info("Proceso %s no encontrado", nombre)
        return False
    except FileNotFoundError:
        # Si pgrep no existe se utiliza ps
        proc = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        lineas = [l for l in proc.stdout.splitlines() if nombre in l]
        if lineas:
            logging.info("Proceso %s activo: %s", nombre, " | ".join(lineas))
            return True
        logging.info("Proceso %s no encontrado", nombre)
        return False
    except Exception as exc:
        logging.exception("Error al buscar el proceso %s: %s", nombre, exc)
        return False


def _puerto_ocupado(puerto: int) -> bool:
    """Devuelve ``True`` si el puerto está en uso."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        resultado = sock.connect_ex(("127.0.0.1", puerto))
        if resultado == 0:
            logging.info("El puerto %s está en uso", puerto)
            return True
        logging.info("El puerto %s está libre", puerto)
        return False


def _estado_servicio(nombre: str) -> tuple[bool, Path | None]:
    """Verifica existencia y estado de un archivo ``.service``."""

    posibles = [
        Path("/etc/systemd/system") / nombre,
        Path("/lib/systemd/system") / nombre,
        Path("/usr/lib/systemd/system") / nombre,
    ]
    ruta = next((p for p in posibles if p.exists()), None)

    if not ruta:
        logging.warning("%s no existe", nombre)
        return False, None

    logging.info("Se encontró %s en %s", nombre, ruta)

    try:
        out = subprocess.run(
            ["systemctl", "status", nombre], capture_output=True, text=True, check=False
        )
        logging.info(out.stdout)
        if "Active: active (running)" in out.stdout:
            logging.info("%s está activo", nombre)
            return True, ruta
        logging.warning("%s no está activo", nombre)
    except Exception as exc:
        logging.exception("No se pudo verificar %s: %s", nombre, exc)
    return False, ruta


SERVICE_TEMPLATE = """[Unit]
Description=codex API Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/gestion_compras
Environment=\"PATH=/home/gestion_compras/venv/bin\"
ExecStart=/home/gestion_compras/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

[Install]
WantedBy=multi-user.target
"""


def _crear_servicio(ruta: Path) -> None:
    """Crea o repara el archivo de servicio."""

    try:
        logging.info("Escribiendo archivo de servicio en %s", ruta)
        ruta.write_text(SERVICE_TEMPLATE, encoding="utf-8")
        subprocess.run(["systemctl", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "enable", "codex_api.service"], check=False)
    except Exception as exc:
        logging.exception("Error al crear el servicio: %s", exc)


def _reiniciar_gunicorn() -> None:
    """Intenta reiniciar Gunicorn mediante systemctl."""

    try:
        subprocess.run(["systemctl", "restart", "gunicorn"], check=False)
        logging.info("Gunicorn reiniciado")
    except Exception as exc:
        logging.exception("No se pudo reiniciar Gunicorn: %s", exc)


def _mostrar_logs(nombre: str) -> None:
    """Muestra las últimas líneas del log del servicio."""

    try:
        out = subprocess.run(
            ["journalctl", "-u", nombre, "--no-pager", "-n", "20"],
            capture_output=True,
            text=True,
            check=False,
        )
        logging.info("Logs recientes de %s:\n%s", nombre, out.stdout)
    except Exception as exc:
        logging.exception("No se pudieron obtener los logs de %s: %s", nombre, exc)


def main() -> None:
    logging.info("===== Verificando entorno =====")
    gunicorn = _buscar_proceso("gunicorn")
    flask = _buscar_proceso("flask")
    nginx = _buscar_proceso("nginx")

    ocupado = _puerto_ocupado(8000)
    servicio_activo, ruta_serv = _estado_servicio("codex_api.service")

    if not gunicorn and servicio_activo:
        logging.warning("Gunicorn parece detenido. Intentando reiniciar...")
        _reiniciar_gunicorn()

    if not servicio_activo:
        destino = ruta_serv or Path("/etc/systemd/system/codex_api.service")
        _crear_servicio(destino)
        _reiniciar_gunicorn()
        _mostrar_logs("codex_api.service")
    elif not ocupado:
        logging.warning("El puerto 8000 no está en uso. Revisar logs...")
        _mostrar_logs("codex_api.service")

    if nginx and ocupado:
        logging.info("Entorno operativo sin problemas aparentes.")


if __name__ == "__main__":
    main()
