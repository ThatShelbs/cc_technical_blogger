@echo off
rem ============================================================================
rem  Proseferno developer mode (Windows): API with auto-reload + Vite dev server
rem  with hot module replacement. Add --demo to use canned AI responses.
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

where uv >nul 2>&1 || ( echo uv is required: winget install --id=astral-sh.uv -e & exit /b 1 )
where npm >nul 2>&1 || ( echo Node.js is required: https://nodejs.org & exit /b 1 )

uv sync --project backend --quiet || exit /b 1
if not exist "frontend\node_modules\" ( pushd frontend & call npm ci --no-audit --no-fund & popd )

start "Proseferno API" cmd /k "uv run --project backend proseferno --reload %*"
start "Proseferno UI" cmd /k "cd frontend && npm run dev"
echo.
echo   API:  http://127.0.0.1:8732/docs
echo   App:  http://localhost:5173   (opens in a moment)
timeout /t 4 >nul
start "" "http://localhost:5173"
