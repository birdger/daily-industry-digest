@echo off
REM Daily industry digest fallback job entry for Windows Task Scheduler.
REM Keep this file ASCII-only: cmd.exe reads .bat as ANSI/GBK, so non-ASCII breaks paths.
setlocal
set PY=G:\code\hermes\hermes-agent\venv\Scripts\python.exe
if not exist "%PY%" set PY=python
if not exist "G:\code\github-heat\daily-industry-digest\scripts\ensure_daily.py" (
  echo [ERROR] ensure_daily.py not found
  exit /b 1
)
set PYTHONIOENCODING=utf-8
set HTTPS_PROXY=127.0.0.1:7892
set HTTP_PROXY=127.0.0.1:7892
"%PY%" "G:\code\github-heat\daily-industry-digest\scripts\ensure_daily.py"
exit /b %errorlevel%