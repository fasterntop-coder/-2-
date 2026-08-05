@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"

echo [B154] Exact story and movie production integration
echo Search root: %ROOT%
python tools\recover_integrate_production_assets.py run manifests\CD1_PRODUCTION_STORY_MOVIE_TARGETS.json "%ROOT%" --output-dir output\B154_PRODUCTION
set RC=%ERRORLEVEL%
echo.
echo Result: output\B154_PRODUCTION\PRODUCTION_RESULT.json
pause
exit /b %RC%
