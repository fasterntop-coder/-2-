@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH166_PRODUCTION_WITH_SK0403_SK0504_SK0501_SK0502_SK0505"
set "COMBINED=%OUT%\CD1_PRODUCTION_38_ASSETS.json"

if not exist "%OUT%" mkdir "%OUT%"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\compose_production_manifests.py compose manifests\CD1_PRODUCTION_STORY_MOVIE_TARGETS.json manifests\SK0403_FINAL_EXACT_TARGET.json manifests\SK0504_FINAL_EXACT_TARGET.json manifests\SK0501_FINAL_EXACT_TARGET.json manifests\SK0502_FINAL_EXACT_TARGET.json manifests\SK0505_FINAL_EXACT_TARGET.json --output "%COMBINED%" || goto :fail
  py -3 tools\recover_integrate_production_assets.py run "%COMBINED%" "%ROOT%" --output-dir "%OUT%" || goto :fail
) else (
  python tools\compose_production_manifests.py compose manifests\CD1_PRODUCTION_STORY_MOVIE_TARGETS.json manifests\SK0403_FINAL_EXACT_TARGET.json manifests\SK0504_FINAL_EXACT_TARGET.json manifests\SK0501_FINAL_EXACT_TARGET.json manifests\SK0502_FINAL_EXACT_TARGET.json manifests\SK0505_FINAL_EXACT_TARGET.json --output "%COMBINED%" || goto :fail
  python tools\recover_integrate_production_assets.py run "%COMBINED%" "%ROOT%" --output-dir "%OUT%" || goto :fail
)

echo.
echo Result: %OUT%\PATCH_RESULT.json
pause
exit /b 0

:fail
echo.
echo Batch166 failed. No candidate should be trusted.
pause
exit /b 1
