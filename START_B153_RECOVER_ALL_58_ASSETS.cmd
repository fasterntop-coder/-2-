@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "WORKBOOK=%~1"
set "SEARCH_ROOT=%~2"
if not defined WORKBOOK set "WORKBOOK=%~dp0BATCH118_BATTLE_BANK_STATIC_100_PERCENT.xlsx"
if not defined SEARCH_ROOT set "SEARCH_ROOT=%~dp0"

if not exist "%WORKBOOK%" (
  echo [ERROR] B118 workbook was not found:
  echo %WORKBOOK%
  echo Drag the workbook onto this CMD, or pass it as argument 1.
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% "%~dp0tools\extract_b118_assets_manifest.py" extract "%WORKBOOK%" --output "%~dp0output\B153\B118_ASSETS_58_NORMALIZED.json"
if errorlevel 1 exit /b 1

%PY% "%~dp0tools\recover_exact_assets_from_checkpoints.py" recover "%~dp0output\B153\B118_ASSETS_58_NORMALIZED.json" "%SEARCH_ROOT%" --output-dir "%~dp0output\B153\EXACT_ASSETS"
set "RC=%errorlevel%"

echo.
echo Manifest: output\B153\B118_ASSETS_58_NORMALIZED.json
echo Result:   output\B153\EXACT_ASSETS\RECOVERY_RESULT.json
exit /b %RC%
