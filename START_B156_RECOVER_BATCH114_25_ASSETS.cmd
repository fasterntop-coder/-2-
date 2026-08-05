@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH156_B114_25_EXACT"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\recover_exact_assets_from_checkpoints.py recover manifests\BATCH114_25_EXACT_TARGETS.json "%ROOT%" --output-dir "%OUT%"
) else (
  python tools\recover_exact_assets_from_checkpoints.py recover manifests\BATCH114_25_EXACT_TARGETS.json "%ROOT%" --output-dir "%OUT%"
)

echo.
echo Result: %OUT%\RECOVERY_RESULT.json
pause
