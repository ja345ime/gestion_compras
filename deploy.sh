#!/usr/bin/env bash

# Script de despliegue automatico para /opt/granja-compras
set -e
LOG_FILE="deploy.log"
REPO_DIR="/opt/granja-compras"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

cd "$REPO_DIR" || { echo "Directorio $REPO_DIR no encontrado"; exit 1; }

# Activar entorno virtual
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
else
    echo "Entorno virtual no encontrado" && exit 1
fi

# Cargar variables del entorno
source .env && set -a

# Obtener rama actual
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Actualizar codigo
if ! git pull --rebase=false; then
    echo "$TIMESTAMP - error: git pull fallo" >> "$LOG_FILE"
    exit 1
fi

# Verificar conflictos
if [ -n "$(git ls-files -u)" ]; then
    git merge --abort
    echo "Error: Conflictos al hacer git pull" >&2
    echo "$TIMESTAMP - error: conflictos al hacer git pull" >> "$LOG_FILE"
    exit 1
fi

# Preparar commit si hay cambios
if ! git diff-index --quiet HEAD --; then
    git add -A
    git commit -m "💬 Deploy automático: $(date '+%Y-%m-%d %H:%M:%S')"
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN vacío o inválido" >&2
    echo "$TIMESTAMP - error: GITHUB_TOKEN vacío o inválido" >> "$LOG_FILE"
    exit 1
fi

# Push de cambios
if ./git_push.sh "$BRANCH"; then
    echo "$TIMESTAMP - éxito: push correcto" >> "$LOG_FILE"
    # Reiniciar Gunicorn
    pkill gunicorn || true
    source venv/bin/activate
    nohup gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app &
    echo "✅ Deploy finalizado: código actualizado y Gunicorn reiniciado."
else
    echo "$TIMESTAMP - error: push fallo" >> "$LOG_FILE"
    echo "Error: Push fallo" >&2
    exit 1
fi
