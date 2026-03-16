@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_ROOT=%%~fI"

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] uv not found. Install uv first: https://docs.astral.sh/uv/
  pause
  exit /b 1
)

echo [INFO] Project root: %PROJECT_ROOT%

echo [INFO] Building frontend with Vite...
start "Frontend build with Vite" cmd /k "cd /d ""%PROJECT_ROOT%/frontend"" && vite build"

echo [INFO] Starting Celery worker...
start "Celery Worker" cmd /k "cd /d ""%PROJECT_ROOT%"" && uv run python -m celery -A backend.web.celery_app:celery_app worker -l info -Q video_processing -P solo"

echo [INFO] Starting Flask API...
start "Flask API" cmd /k "cd /d ""%PROJECT_ROOT%"" && uv run python -m backend.app"

echo [OK] Services started in two windows.
echo [NOTE] Ensure Redis in WSL is running before starting tasks.
endlocal
