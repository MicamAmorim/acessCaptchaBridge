@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo Falha ao iniciar. Instale Python 3.10 ou superior e verifique a porta 8765.
  pause
)
