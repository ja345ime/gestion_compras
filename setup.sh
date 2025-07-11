#!/usr/bin/env bash
set -e
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m flask --app wsgi run

# Actualizar PATH y aplicar migraciones Alembic automáticamente
export PATH=$PATH:~/.local/bin
alembic -c migrations/alembic.ini upgrade head
