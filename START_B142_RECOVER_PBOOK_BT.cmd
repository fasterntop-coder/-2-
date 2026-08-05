@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ST2 Batch142 PBOOK_BT Exact Recovery

set "ROOT=%~1"
if not defined ROOT set "ROOT=%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3 not found.
  pause
  exit /b 3
)

echo [SCAN] %ROOT%
python "%~dp0tools\recover_pbook_bt_b110.py" scan "%ROOT%" --output-dir "%~dp0output\B142"
set "ERR=%ERRORLEVEL%"

if "%ERR%"=="0" (
  echo [PASS] Exact PBOOK_BT asset recovered under output\B142.
) else (
  echo [BLOCKED] Exact B110/source bytes were not found. See B142_RECOVERY_RESULT.json.
)
pause
exit /b %ERR%
