@echo off
rem ============================================================================
rem  Run every check CI runs, in CI order, and print a summary.
rem    scripts\check.bat          lint, format check, types, tests, build
rem    scripts\check.bat --fix    apply the formatters instead of only checking them
rem    scripts\check.bat --e2e    also run the Playwright end-to-end tests
rem  Keep this list in step with .github/workflows/ci.yml.
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.."
call "%~dp0_env.bat"
if not defined UV_OK ( echo uv is required. Run scripts\setup.bat first. & exit /b 1 )

set "FIX="
set "E2E="
for %%A in (%*) do (
  if /i "%%A"=="--fix" set "FIX=1"
  if /i "%%A"=="--e2e" set "E2E=1"
)
set "FAILED="
set "PASSED=0"
set "PY=uv run --directory backend"
set "NPM=npm --prefix frontend run"

if defined FIX (
  call :step "Backend lint (fixing)" "%PY% ruff check --fix src tests scripts evals"
  call :step "Backend format" "%PY% ruff format src tests scripts evals"
  call :step "Frontend format" "%NPM% format"
) else (
  call :step "Backend lint" "%PY% ruff check src tests scripts evals"
  call :step "Backend format" "%PY% ruff format --check src tests scripts evals"
  call :step "Frontend format" "%NPM% format:check"
)
call :step "Backend types" "%PY% mypy"
call :step "Backend tests" "%PY% pytest -q"
call :step "Frontend types are current" "%PY% python scripts/export_types.py --check"
call :step "Frontend typecheck" "%NPM% typecheck"
call :step "Frontend lint" "%NPM% lint"
call :step "Frontend tests" "%NPM% test"
call :step "Frontend build" "%NPM% build"
if defined E2E call :step "End-to-end tests" "%NPM% e2e"

echo.
echo   ----------------------------------------------
if defined FAILED (
  echo   FAILED:%FAILED%
  echo   %PASSED% passed. Fix the failures above, or run scripts\check.bat --fix for formatting.
  exit /b 1
)
echo   All %PASSED% checks passed.
exit /b 0

:step
set "LABEL=%~1"
echo.
echo   == %LABEL%
call %~2
if errorlevel 1 ( set "FAILED=!FAILED! [!LABEL!]" ) else ( set /a PASSED+=1 )
goto :eof
