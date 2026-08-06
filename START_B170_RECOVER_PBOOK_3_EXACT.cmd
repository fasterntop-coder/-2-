@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH170_PBOOK_3_EXACT"

if not exist "%OUT%" mkdir "%OUT%"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\recover_integrate_production_assets.py validate manifests\PBOOK_3_EXACT_TARGETS.json || goto :fail
  py -3 tools\recover_integrate_production_assets.py run manifests\PBOOK_3_EXACT_TARGETS.json "%ROOT%" --output-dir "%OUT%" --require-all || goto :fail
) else (
  python tools\recover_integrate_production_assets.py validate manifests\PBOOK_3_EXACT_TARGETS.json || goto :fail
  python tools\recover_integrate_production_assets.py run manifests\PBOOK_3_EXACT_TARGETS.json "%ROOT%" --output-dir "%OUT%" --require-all || goto :fail
)

echo.
echo Result: %OUT%\PATCH_RESULT.json
pause
exit /b 0

:fail
echo.
echo Batch170 failed. No PBOOK candidate should be trusted.
pause
exit /b 1
