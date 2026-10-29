@echo off
rem ============================================================================
rem  Proseferno developer setup (Windows). Safe to run again at any time.
rem  Installs what you need to work on the code: uv, Node.js, the Python and web
rem  packages, and (optionally) the browser used by the end-to-end tests.
rem  Just want to use the app? Double-click launch.bat in the repository root.
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
title Proseferno setup
cd /d "%~dp0.."

echo.
echo   ==============================================
echo     Proseferno developer setup
echo   ==============================================
echo.

rem --- 1. uv ---------------------------------------------------------------------
call "%~dp0_env.bat"
if not defined UV_OK (
  echo   uv is not installed. It manages Python and the backend environment.
  choice /c YN /m "  Install uv now with winget"
  if errorlevel 2 goto :need_uv
  winget install --id=astral-sh.uv -e --accept-source-agreements --accept-package-agreements
  call "%~dp0_env.bat"
  if not defined UV_OK goto :need_uv
)
echo   [1/4] uv is ready.

rem --- 2. Node.js 22 or newer -----------------------------------------------------
set "NODE_MAJOR="
where node >nul 2>&1 && for /f "tokens=1 delims=." %%M in ('node --version') do set "NODE_MAJOR=%%M"
if defined NODE_MAJOR set "NODE_MAJOR=%NODE_MAJOR:v=%"
if not defined NODE_MAJOR goto :install_node
if %NODE_MAJOR% LSS 22 goto :install_node
echo   [2/4] Node.js %NODE_MAJOR% is ready.
goto :python

:install_node
echo   Node.js 22 or newer is needed to build the web interface.
choice /c YN /m "  Install Node.js LTS now with winget"
if errorlevel 2 goto :need_node
winget install --id=OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
set "PATH=%ProgramFiles%\nodejs;%PATH%"
where node >nul 2>&1 || goto :need_node
echo   [2/4] Node.js is ready.

rem --- 3. Packages ----------------------------------------------------------------
:python
echo   [3/4] Installing Python and web packages...
uv sync --project backend --quiet
if errorlevel 1 goto :failed
if not exist "frontend\node_modules\" (
  pushd frontend
  call npm ci --no-audit --no-fund --loglevel=error
  if errorlevel 1 ( popd & goto :failed )
  popd
)

rem --- 4. Optional: browser for end-to-end tests ----------------------------------------
choice /c YN /m "  Install the browser for end-to-end tests (about 150 MB; skip if you have Edge or Chrome)"
if not errorlevel 2 (
  pushd frontend
  call npx playwright install chromium
  popd
)

echo.
echo   [4/4] Checking this machine...
uv run --project backend proseferno doctor

echo   Next:
echo     launch.bat --demo        try the app with canned responses, no keys needed
echo     scripts\dev.bat --demo   developer mode with hot reload
echo     scripts\check.bat        run every check CI runs
echo     docs\onboarding.md       your first day on the project
echo.
pause
goto :eof

:need_uv
echo.
echo   Please install uv, then run this again:
echo     winget install --id=astral-sh.uv -e
echo   or see https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1

:need_node
echo.
echo   Please install Node.js 22 LTS (https://nodejs.org), then run this again.
pause
exit /b 1

:failed
echo.
echo   Setup failed. Scroll up for the error, then run:
echo     uv run --project backend proseferno doctor
echo   Common fixes are in docs\onboarding.md under Troubleshooting.
pause
exit /b 1
