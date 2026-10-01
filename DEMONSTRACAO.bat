@echo off
chcp 65001 >nul
title AlertSignal (demonstração)

echo Abrindo a demonstração do AlertSignal (dados fictícios, nenhum e-mail é enviado)...

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python não encontrado. Instale em https://python.org
    pause
    exit /b 1
)

python -m pip install -r "%~dp0requirements.txt" --quiet --disable-pip-version-check

start "" /B PowerShell -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://localhost:5001'"

echo.
echo Demonstração em http://localhost:5001
echo Feche esta janela para encerrar.
echo.
cd /d "%~dp0"
python app.py --demo --porta 5001

pause
