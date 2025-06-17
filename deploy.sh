#!/bin/bash
set -e

echo "📦 Descargando desde GitHub..."
git fetch origin
echo "📦 Forzando sincronización..."
git reset --hard origin/master

echo "📦 Instalando dependencias..."
pip install -r requirements.txt

echo "🗄️  Aplicando migraciones de base de datos..."
export FLASK_APP=app
flask db upgrade

echo "🚀 Reiniciando Gunicorn con systemctl..."
sudo systemctl restart gunicorn

echo "✅ Sistema actualizado y reiniciado correctamente."
