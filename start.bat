@echo off
setlocal EnableExtensions
chcp 65001 >nul

title Enterprise AI Workbench Launcher
cd /d "%~dp0"

echo Enterprise AI Workbench Launcher v0.2

set "AIW_PROJECT_ROOT=%CD%"
set "AIW_ENABLE_FAKE_WECOM=true"
set "AIW_DATABASE_URL=sqlite:///runtime-data/platform.db"
set "AIW_API_BASE_URL=http://127.0.0.1:8765"
set "AIW_API_STARTED=0"
set "AIW_API_PID="
set "AIW_PYTHON_EXE="
set "AIW_NO_PAUSE=0"
if /I "%~1"=="--check" set "AIW_NO_PAUSE=1"
if /I "%~1"=="--smoke" set "AIW_NO_PAUSE=1"

echo [1/5] Checking Python...
if exist "%AIW_PROJECT_ROOT%\.venv\Scripts\python.exe" set "AIW_PYTHON_EXE=%AIW_PROJECT_ROOT%\.venv\Scripts\python.exe"
for /f "delims=" %%I in ('where python 2^>nul') do if not defined AIW_PYTHON_EXE set "AIW_PYTHON_EXE=%%I"
if defined AIW_PYTHON_EXE goto python_found
echo [ERROR] Python was not found. Install Python 3.12 or 3.13 and add it to PATH.
goto error_exit

:python_found
"%AIW_PYTHON_EXE%" -c "import sys; assert sys.version_info[:2] in ((3, 12), (3, 13)), sys.version; print('Python ' + sys.version.split()[0])"
if not errorlevel 1 goto python_ok
echo [ERROR] Unsupported Python version. Python 3.12 or 3.13 is required.
goto error_exit

:python_ok
echo [2/5] Checking project dependencies...
"%AIW_PYTHON_EXE%" -c "import alembic, fastapi, httpx, keyring, pydantic, PySide6, sqlalchemy, uvicorn"
if not errorlevel 1 goto dependencies_ok
echo [ERROR] Project dependencies are incomplete.
echo Run: "%AIW_PYTHON_EXE%" -m pip install -r requirements.txt
goto error_exit

:dependencies_ok
if exist "%AIW_PROJECT_ROOT%\runtime-data" goto runtime_ready
mkdir "%AIW_PROJECT_ROOT%\runtime-data"

:runtime_ready
echo [3/5] Applying database migrations...
"%AIW_PYTHON_EXE%" -m alembic upgrade head
if not errorlevel 1 goto migration_ok
echo [ERROR] Database migration failed. Review the log above.
goto error_exit

:migration_ok
if /I not "%~1"=="--check" goto launch_api
echo [OK] Python, dependencies, and database migrations are ready.
exit /b 0

:launch_api
echo [4/5] Starting the platform API...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -Uri ($env:AIW_API_BASE_URL + '/health/ready') -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1"
if errorlevel 1 goto start_api
echo [INFO] An existing platform API is ready and will be reused.
goto launch_client

:start_api
set "AIW_API_STDOUT=%AIW_PROJECT_ROOT%\runtime-data\platform-api.stdout.log"
set "AIW_API_STDERR=%AIW_PROJECT_ROOT%\runtime-data\platform-api.stderr.log"
"%AIW_PYTHON_EXE%" scripts\launch_platform.py
if errorlevel 1 goto api_process_failed
set /p AIW_API_PID=<"%AIW_PROJECT_ROOT%\runtime-data\platform-api.pid"
if not defined AIW_API_PID goto api_process_failed
set "AIW_API_STARTED=1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ready = $false; for ($i = 0; $i -lt 20; $i++) { try { $response = Invoke-WebRequest -UseBasicParsing -Uri ($env:AIW_API_BASE_URL + '/health/ready') -TimeoutSec 1; if ($response.StatusCode -eq 200) { $ready = $true; break } } catch {}; Start-Sleep -Milliseconds 250 }; if (-not $ready) { exit 1 }"
if not errorlevel 1 goto launch_client
echo [ERROR] The platform API did not become ready.
echo Error log: %AIW_API_STDERR%
call :stop_api
goto error_exit

:api_process_failed
echo [ERROR] The platform API process could not be started.
goto error_exit

:launch_client
if /I "%~1"=="--smoke" goto smoke_complete
echo [5/5] Starting the desktop client...
"%AIW_PYTHON_EXE%" main.py
set "AIW_CLIENT_EXIT=%ERRORLEVEL%"
call :stop_api
exit /b %AIW_CLIENT_EXIT%

:smoke_complete
echo [OK] The platform API startup check passed.
call :stop_api
exit /b 0

:stop_api
if not "%AIW_API_STARTED%"=="1" exit /b 0
if not defined AIW_API_PID exit /b 0
echo Stopping the platform API started by this launcher...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-Process -Id %AIW_API_PID% -ErrorAction SilentlyContinue"
exit /b 0

:error_exit
if "%AIW_NO_PAUSE%"=="0" pause
exit /b 1
