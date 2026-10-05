@echo off
rem Start the ExpressBus demo on Windows: backend on :8000, frontend on :3000, demo clock pinned.
rem
rem   run_demo.bat                          synthetic demo data
rem   set DATA_SOURCE=gtfs ^& run_demo.bat   real VAG trips (synthetic roster)
rem
rem DATA_SOURCE, DEMO_DATE, DEMO_TIME and OPTIMIZE_TIME_LIMIT_S can be set beforehand and take precedence
rem over backend\.env. Each server runs in its own window; close the windows to stop the demo.

setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"

if not defined DATA_SOURCE set "DATA_SOURCE=synthetic"
if not defined DEMO_DATE (
  if /i "%DATA_SOURCE%"=="gtfs" (set "DEMO_DATE=2026-07-01") else (set "DEMO_DATE=2026-10-05")
)
if not defined DEMO_TIME set "DEMO_TIME=09:15"

where curl >nul 2>nul || (echo ERROR: curl not found ^(it ships with Windows 10 and later^) & exit /b 1)
where npm >nul 2>nul || (echo ERROR: npm not found: install Node.js & exit /b 1)
set "PY=python"
where python >nul 2>nul || set "PY=py -3"

curl -s -o nul http://127.0.0.1:8000/health && (echo ERROR: port 8000 is in use: stop the other backend first & exit /b 1)
curl -s -o nul http://127.0.0.1:3000 && (echo ERROR: port 3000 is in use: stop the other frontend first & exit /b 1)

rem Use backend\.venv, or backend\.venv-win if .venv is a Linux/WSL environment.
set "VENV=%ROOT%backend\.venv"
if not exist "%VENV%\Scripts\python.exe" if exist "%VENV%\bin" set "VENV=%ROOT%backend\.venv-win"
if not exist "%VENV%\Scripts\python.exe" (
  echo Setting up the backend ^(first run^)...
  %PY% -m venv "%VENV%" || exit /b 1
  "%VENV%\Scripts\python.exe" -m pip install -q -r backend\requirements.txt || exit /b 1
)
if not exist "frontend\node_modules" (
  echo Installing frontend packages ^(first run^)...
  pushd frontend & call npm install --no-fund --no-audit & popd
)

echo Starting backend  (DATA_SOURCE=%DATA_SOURCE%, DEMO_DATE=%DEMO_DATE%, DEMO_TIME=%DEMO_TIME%)...
start "ExpressBus backend :8000" /d "%ROOT%backend" cmd /k ""%VENV%\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000"

set /a tries=0
:wait_backend
set /a tries+=1
if %tries% gtr 60 (echo ERROR: backend didn't start; see its window & exit /b 1)
timeout /t 1 /nobreak >nul
curl -sf -o nul http://127.0.0.1:8000/health || goto wait_backend

echo Starting frontend...
start "ExpressBus frontend :3000" /d "%ROOT%frontend" cmd /k "npm run dev -- --port 3000"

rem Warm up: fills the /optimize fallback cache with the requests the Optimization page sends.
curl -sf -o nul -X POST http://127.0.0.1:8000/optimize -H "Content-Type: application/json" -d "{\"allowOvertime\": true}"
curl -sf -o nul -X POST http://127.0.0.1:8000/optimize -H "Content-Type: application/json" -d "{\"allowOvertime\": false}"
curl -sf -o nul http://127.0.0.1:8000/dashboard

set /a tries=0
:wait_frontend
set /a tries+=1
if %tries% gtr 120 (echo ERROR: frontend didn't start; see its window & exit /b 1)
timeout /t 1 /nobreak >nul
curl -sf -o nul http://127.0.0.1:3000 || goto wait_frontend

echo.
echo   ExpressBus demo is running
echo   --------------------------
echo   App:       http://localhost:3000
echo   Admin:     http://localhost:3000/admin
echo   API docs:  http://localhost:8000/docs
echo   Close the two server windows to stop the demo.
endlocal
