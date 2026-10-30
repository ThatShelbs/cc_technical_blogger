@echo off
rem ============================================================================
rem  Shared by launch.bat, setup.bat, dev.bat and check.bat. Not meant to be run on its own.
rem   1. Finds uv (a fresh winget install is not on this window's PATH yet) and sets UV_OK.
rem   2. Keeps the Python environment path short when this folder is deeply nested, because
rem      Windows stops resolving paths near 260 characters and one Anthropic SDK file name is very long.
rem ============================================================================
set "UV_OK="
where uv >nul 2>&1 && set "UV_OK=1"
if defined UV_OK goto :long_path
for %%D in ("%USERPROFILE%\.local\bin" "%LOCALAPPDATA%\Microsoft\WinGet\Links") do (
  if exist "%%~D\uv.exe" ( set "PATH=%%~D;!PATH!" & set "UV_OK=1" )
)
if defined UV_OK goto :long_path
for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*") do (
  if exist "%%~D\uv.exe" ( set "PATH=%%~D;!PATH!" & set "UV_OK=1" )
)

:long_path
if defined UV_PROJECT_ENVIRONMENT goto :eof
set "ENV_PATH=%~dp0..\backend"
set "ENV_COUNT=0"
:count
if not defined ENV_PATH goto :counted
set "ENV_PATH=%ENV_PATH:~1%"
set /a ENV_COUNT+=1
goto :count
:counted
if %ENV_COUNT% GTR 110 (
  set "UV_PROJECT_ENVIRONMENT=%USERPROFILE%\.venvs\proseferno"
  echo   Note: this folder's path is long, so the Python environment lives in %USERPROFILE%\.venvs\proseferno
)
goto :eof
