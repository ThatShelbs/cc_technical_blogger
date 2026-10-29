@echo off
rem ============================================================================
rem  Proseferno launcher (Windows). Double-click to start the app.
rem  Extra arguments are passed through, e.g.  launch.bat --demo
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
title Proseferno
cd /d "%~dp0"

set "PORT=8732"
if defined PROSEFERNO_PORT set "PORT=%PROSEFERNO_PORT%"

echo.
echo   ==============================================
echo     Proseferno  -  technical blogs in your voice
echo   ==============================================
echo.

rem --- Already running? Just open it. ---------------------------------------
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo   Something is already running on port %PORT%. Opening it in your browser.
  echo   If that is not Proseferno, set PROSEFERNO_PORT to another port and try again.
  start "" "http://127.0.0.1:%PORT%"
  goto :eof
)

rem --- 1. uv (manages Python and the backend environment) --------------------
call :find_uv
if not defined UV_OK (
  echo   uv is not installed. Proseferno uses it to manage Python.
  choice /c YN /m "  Install uv now with winget"
  if errorlevel 2 goto :need_uv
  winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
  call :find_uv
  if not defined UV_OK goto :need_uv
)

rem --- 2. Node.js (builds the web interface) ---------------------------------
where node >nul 2>&1
if errorlevel 1 (
  echo   Node.js is not installed. It is needed to build the web interface.
  choice /c YN /m "  Install Node.js LTS now with winget"
  if errorlevel 2 goto :need_node
  winget install --id=OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
  where node >nul 2>&1
  if errorlevel 1 goto :need_node
)

rem --- 3. Backend environment ------------------------------------------------
echo   [1/3] Preparing the Python environment...
uv sync --project backend --quiet
if errorlevel 1 goto :failed

rem --- 4. Web interface ----------------------------------------------------------
if not exist "frontend\node_modules\" (
  echo   [2/3] Installing web interface packages, first run only...
  pushd frontend
  call npm ci --no-audit --no-fund --loglevel=error
  if errorlevel 1 ( popd & goto :failed )
  popd
) else (
  echo   [2/3] Web interface packages are installed.
)
node frontend\scripts\needs-build.mjs
if not errorlevel 1 (
  echo   [3/3] Building the web interface...
  pushd frontend
  call npm run build --silent
  if errorlevel 1 ( popd & goto :failed )
  popd
) else (
  echo   [3/3] Web interface is up to date.
)

rem --- 5. Start ------------------------------------------------------------------
echo.
echo   Starting Proseferno at http://127.0.0.1:%PORT%
echo   Your browser will open when it is ready. Close this window to stop.
echo.
uv run --project backend proseferno --open --port %PORT% %*
goto :eof

rem ===============================================================================
:find_uv
rem Shared with scripts\setup.bat: finds uv (a fresh install is not on this window's PATH yet) and sets UV_OK.
call "%~dp0scripts\_env.bat"
goto :eof

:need_uv
echo.
echo   Please install uv, then run launch.bat again:
echo     winget install --id=astral-sh.uv -e
echo   or see https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1

:need_node
echo.
echo   Please install Node.js LTS (https://nodejs.org), then run launch.bat again.
pause
exit /b 1

:failed
echo.
echo   Setup failed. Scroll up for the error. Common fixes:
echo     - Check your internet connection (first run downloads packages).
echo     - Close other Proseferno windows and try again.
echo   To see exactly what is wrong on this machine, run:
echo     uv run --project backend proseferno doctor
pause
exit /b 1
