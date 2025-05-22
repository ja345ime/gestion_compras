@echo off
title Actualizar Sistema - Granja Los Molinos
echo ================================
echo  Actualizando desde GitHub...
echo ================================
cd /d %~dp0

REM Activar entorno virtual
call venv\Scripts\activate

REM Detener procesos Flask anteriores si los hay (manual)
echo.
echo Asegúrate de cerrar manualmente el servidor anterior (Ctrl+C) si sigue activo.
pause

REM Hacer pull desde la rama master
git pull origin master

REM Arrancar la app Flask
echo ================================
echo   Iniciando servidor Flask...
echo ================================
python app.py
pause
