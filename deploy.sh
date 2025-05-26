#!/bin/bash
set -e

echo "📦 Haciendo pull de Git..."
git pull origin main

echo "📦 Instalando dependencias..."
pip install -r requirements.txt

echo "🚀 Reiniciando Gunicorn con systemctl..."
sudo systemctl restart gunicorn

echo "✅ Sistema actualizado y reiniciado correctamente."
