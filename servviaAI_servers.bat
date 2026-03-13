@echo off
title ServVia AI Healthcare - Server Launcher
color 0A

echo.
echo  =====================================================
echo   ServVia Neuro-Symbolic AI Healthcare
echo   Starting servers...
echo  =====================================================
echo.

echo [1/2] Starting ServVia AI server on port 9000...
start "ServVia AI :9000" cmd /k "cd /d C:\Users\cools\servviaAI\servvia && call venv\Scripts\activate && echo [ServVia AI] Venv activated. Starting on port 9000... && python manage.py runserver 0.0.0.0:9000"

timeout /t 2 /nobreak >nul

echo [2/2] Starting ServVia Backend server on port 9001...
start "ServVia Backend :9001" cmd /k "cd /d C:\Users\cools\servviaAI\servvia-backend && call venv\Scripts\activate && echo [ServVia Backend] Venv activated. Starting on port 9001... && python manage.py runserver 0.0.0.0:9001"

echo.
echo  Both servers launched in separate windows.
echo  ServVia AI      ^-^> http://127.0.0.1:9000
echo  ServVia Backend ^-^> http://127.0.0.1:9001
echo.
pause
