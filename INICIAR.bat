@echo off
title AlertSignal — Grupo Zen

echo Iniciando AlertSignal...

:: Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em https://python.org
    pause
    exit
)

:: Instala dependencias se necessario
echo Verificando dependencias...
pip install flask apscheduler openpyxl pandas werkzeug --quiet 2>nul

:: Abre o navegador apos 4 segundos em segundo plano
start "" /B PowerShell -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://localhost:5000'"

:: Sobe o servidor
echo.
echo Sistema rodando em http://localhost:5000
echo Feche esta janela para encerrar o sistema.
echo.
python app.py

pause
