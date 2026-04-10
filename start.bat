@echo off
setlocal enabledelayedexpansion

echo.
echo  ==========================================
echo   Traffic Lab - Startup
echo  ==========================================
echo.

:: ── ASK FOR NGINX PORT ──────────────────────────────────────────
:ask_nginx_port
set "NGINX_PORT="
set /p "NGINX_PORT=Enter Nginx port (UI)  [default: 1225]: "

:: If user pressed Enter with no input, use default
if "!NGINX_PORT!"=="" set "NGINX_PORT=1225"

:: Validate: must be a number between 1 and 65535
echo !NGINX_PORT!| findstr /r "^[0-9][0-9]*$" >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] "!NGINX_PORT!" is not a valid port number. Please enter a number between 1 and 65535.
    goto ask_nginx_port
)
if !NGINX_PORT! LSS 1 (
    echo  [ERROR] Port must be at least 1.
    goto ask_nginx_port
)
if !NGINX_PORT! GTR 65535 (
    echo  [ERROR] Port must be 65535 or less.
    goto ask_nginx_port
)

:: Check if port is free using netstat
netstat -ano | findstr /r "[:.]!NGINX_PORT! " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  [ERROR] Port !NGINX_PORT! is already in use. Choose a different port.
    goto ask_nginx_port
)
echo  [OK] Port !NGINX_PORT! is free.

:: ── ASK FOR GRAFANA PORT ─────────────────────────────────────────
:ask_grafana_port
set "GRAFANA_PORT="
set /p "GRAFANA_PORT=Enter Grafana port        [default: 3000]: "

if "!GRAFANA_PORT!"=="" set "GRAFANA_PORT=3000"

echo !GRAFANA_PORT!| findstr /r "^[0-9][0-9]*$" >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] "!GRAFANA_PORT!" is not a valid port number.
    goto ask_grafana_port
)
if !GRAFANA_PORT! LSS 1 (
    echo  [ERROR] Port must be at least 1.
    goto ask_grafana_port
)
if !GRAFANA_PORT! GTR 65535 (
    echo  [ERROR] Port must be 65535 or less.
    goto ask_grafana_port
)

:: Check Grafana port is free
netstat -ano | findstr /r "[:.]!GRAFANA_PORT! " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  [ERROR] Port !GRAFANA_PORT! is already in use. Choose a different port.
    goto ask_grafana_port
)
echo  [OK] Port !GRAFANA_PORT! is free.

:: Prevent same port for both
if "!NGINX_PORT!"=="!GRAFANA_PORT!" (
    echo  [ERROR] Nginx and Grafana cannot use the same port.
    goto ask_nginx_port
)

:: ── SUMMARY ──────────────────────────────────────────────────────
echo.
echo  ==========================================
echo   Starting with:
echo     UI (Nginx)  →  http://localhost:!NGINX_PORT!
echo     Grafana     →  http://localhost:!GRAFANA_PORT!
echo  ==========================================
echo.

:: ── WRITE .env FILE ──────────────────────────────────────────────
:: docker compose reads .env automatically for variable substitution
(
    echo NGINX_PORT=!NGINX_PORT!
    echo GRAFANA_PORT=!GRAFANA_PORT!
) > .env

echo  [INFO] Written .env file with ports.
echo  [INFO] Starting Docker Compose...
echo.

:: ── START DOCKER COMPOSE ─────────────────────────────────────────
docker compose up --build

endlocal
