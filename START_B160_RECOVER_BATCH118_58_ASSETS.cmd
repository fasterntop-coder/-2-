@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH160_B118_58_EXACT"
set "PY=python"
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"

if not exist "%OUT%" mkdir "%OUT%"

%PY% tools\compose_exact_asset_lineage.py compose manifests\BATCH115_33_EXACT_TARGETS.json manifests\BATCH116_9_EXACT_DELTA.json --output "%OUT%\BATCH116_42_EXACT_TARGETS.json"
if errorlevel 1 goto :fail

%PY% tools\compose_exact_asset_lineage.py compose manifests\BATCH115_33_EXACT_TARGETS.json manifests\BATCH116_9_EXACT_DELTA.json manifests\BATCH117_14_EXACT_DELTA.json --output "%OUT%\BATCH117_56_EXACT_TARGETS.json"
if errorlevel 1 goto :fail

%PY% tools\compose_exact_asset_lineage.py compose manifests\BATCH115_33_EXACT_TARGETS.json manifests\BATCH116_9_EXACT_DELTA.json manifests\BATCH117_14_EXACT_DELTA.json manifests\BATCH118_2_EXACT_DELTA.json --output "%OUT%\BATCH118_58_EXACT_TARGETS.json"
if errorlevel 1 goto :fail

%PY% tools\recover_exact_assets_from_checkpoints.py recover "%OUT%\BATCH118_58_EXACT_TARGETS.json" "%ROOT%" --output-dir "%OUT%\RECOVERED_58"
set "RC=%errorlevel%"

echo.
echo Generated manifests:
echo   %OUT%\BATCH116_42_EXACT_TARGETS.json
echo   %OUT%\BATCH117_56_EXACT_TARGETS.json
echo   %OUT%\BATCH118_58_EXACT_TARGETS.json
echo Recovery result:
echo   %OUT%\RECOVERED_58\RECOVERY_RESULT.json
pause
exit /b %RC%

:fail
echo Batch160 lineage composition failed. No recovery scan was started.
pause
exit /b 1
