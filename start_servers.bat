#Start script for Windows Command Prompt
@echo off
echo ========================================
echo    ServVia - Starting All Servers
echo ========================================
echo.

set "ROOT_DIR=%~dp0"

echo [1/2] Starting ServVia on port 8001... 
cd /d "%ROOT_DIR%servvia"
start "ServVia" cmd /k "venv\Scripts\activate.bat && python manage.py runserver 8001"

timeout /t 2 /nobreak > nul

echo [2/2] Starting Backend on port 8000...
cd /d "%ROOT_DIR%servvia-backend"
start "Backend" cmd /k "myenv\Scripts\activate.bat && python manage.py runserver 8000"

echo. 
echo ========================================
echo    All servers started!
echo ========================================
echo.
echo ServVia:   http://127.0.0.1:8001/
echo Backend:   http://127.0.0.1:8000/
echo. 
pause
