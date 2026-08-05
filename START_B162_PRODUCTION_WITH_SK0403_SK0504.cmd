@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH162_PRODUCTION_WITH_SK0403_SK0504"
set "COMBINED=%OUT%\CD1_PRODUCTION_35_ASSETS.json"

if not exist "%OUT%" mkdir "%OUT%"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\compose_production_manifests.py compose manifests\CD1_PRODUCTION_STORY_MOVIE_TARGETS.json manifests\SK0403_FINAL_EXACT_TARGET.json manifests\SK0504_FINAL_EXACT_TARGET.json --output "%COMBINED%" || goto :fail
  py -3 tools\recover_integrate_production_assets.py run "%COMBINED%" "%ROOT%" --output-dir "%OUT%" || goto :fail
) else (
  python tools\compose_production_manifests.py compose manifests\CD1_PRODUCTION_STORY_MOVIE_TARGETS.json manifests\SK0403_FINAL_EXACT_TARGET.json manifests\SK0504_FINAL_EXACT_TARGET.json --output "%COMBINED%" || goto :fail
  python tools\recover_integrate_production_assets.py run "%COMBINED%" "%ROOT%" --output-dir "%OUT%" || goto :fail
)

echo.
echo Result: %OUT%\PATCH_RESULT.json
pause
exit /b 0

:fail
echo.
echo Batch162 failed. No candidate should be trusted.
pause
exit /b 1
