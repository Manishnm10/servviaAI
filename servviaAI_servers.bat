@echo off
title ServVia AI Healthcare - Server Launcher
color 0A

echo.
echo  =====================================================
echo   ServVia Neuro-Symbolic AI Healthcare
echo   Starting servers...
echo  =====================================================
echo.

echo [1/3] Starting Ollama (Edge AI) on port 11434...
start "Ollama Edge AI" ollama serve

timeout /t 3 /nobreak >nul

echo [2/3] Starting ServVia AI server on port 9000...
start "ServVia AI :9000" cmd /k "cd /d C:\Users\cools\servviaAI\servvia && call venv\Scripts\activate && echo [ServVia AI] Venv activated. Starting on port 9000... && python manage.py runserver 0.0.0.0:9000"

timeout /t 2 /nobreak >nul

echo [3/3] Starting ServVia Backend server on port 9001...
start "ServVia Backend :9001" cmd /k "cd /d C:\Users\cools\servviaAI\servvia-backend && call venv\Scripts\activate && echo [ServVia Backend] Venv activated. Starting on port 9001... && python manage.py runserver 0.0.0.0:9001"

echo.
echo  =====================================================
echo   All servers launched in separate windows.
echo   ServVia AI      ^-^> http://127.0.0.1:9000
echo   ServVia Backend ^-^> http://127.0.0.1:9001
echo   Ollama Edge AI  ^-^> http://127.0.0.1:11434
echo  =====================================================
echo.
echo  Press any key HERE to STOP all servers and Ollama...
pause >nul

echo.
echo  Shutting down all services...
taskkill /FI "WINDOWTITLE eq ServVia AI :9000" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ServVia Backend :9001" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Ollama Edge AI" /T /F >nul 2>&1
taskkill /IM ollama.exe /F >nul 2>&1
echo  Done. All servers stopped.
timeout /t 2 /nobreak >nul
