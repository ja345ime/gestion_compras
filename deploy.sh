#!/bin/bash
set -e

echo "📦 Haciendo pull de Git..."
git pull origin master

echo "📦 Instalando dependencias..."
pip install -r requirements.txt

echo "🗄️  Aplicando migraciones de base de datos..."
export FLASK_APP=app
flask db upgrade

echo "🚀 Reiniciando Gunicorn con systemctl..."
sudo systemctl restart gunicorn

echo "✅ Sistema actualizado y reiniciado correctamente."
