@echo off
rem ============================================================================
rem  Build the Windows app (packaging\dist\Proseferno\Proseferno.exe) and, when
rem  Inno Setup 6 is installed, the installer (packaging\installer\*.exe).
rem  Needs uv and Node.js, like launch.bat. End users need neither.
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0.."

echo   [1/3] Building the web interface...
pushd frontend
if not exist "node_modules\" call npm ci --no-audit --no-fund --loglevel=error || ( popd & goto :failed )
call npm run build --silent || ( popd & goto :failed )
popd

echo   [2/3] Bundling Python and the backend with PyInstaller...
uv run --project backend --group package pyinstaller --noconfirm --clean ^
  --distpath packaging\dist --workpath packaging\dist\build packaging\proseferno.spec
if errorlevel 1 goto :failed
rmdir /s /q packaging\dist\build 2>nul

echo   [3/3] Making the installer...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist "%%~P" set "ISCC=%%~P"
)
if not defined ISCC (
  echo   Inno Setup 6 is not installed, so only the app folder was built:
  echo     packaging\dist\Proseferno\Proseferno.exe
  echo   For an installer: winget install JRSoftware.InnoSetup, then run this again.
  goto :eof
)
for /f "delims=" %%V in ('uv run --project backend python -c "import proseferno; print(proseferno.__version__)"') do set "VERSION=%%V"
"%ISCC%" /Qp /DAppVersion=%VERSION% packaging\proseferno.iss
if errorlevel 1 goto :failed
echo   Installer: packaging\installer\Proseferno-Setup-%VERSION%.exe
goto :eof

:failed
echo.
echo   Build failed. Scroll up for the error.
exit /b 1
