@echo off
chcp 65001 >nul
title AlertSignal

echo Iniciando o AlertSignal...

:: Confere se o Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python não encontrado. Instale em https://python.org
    pause
    exit /b 1
)

:: Instala as dependências, se faltar alguma
echo Conferindo dependências...
python -m pip install -r "%~dp0requirements.txt" --quiet --disable-pip-version-check

:: Abre o navegador depois de 4 segundos, em segundo plano
start "" /B PowerShell -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://localhost:5000'"

echo.
echo Sistema rodando em http://localhost:5000
echo Feche esta janela para encerrar.
echo.
cd /d "%~dp0"
python app.py

pause
