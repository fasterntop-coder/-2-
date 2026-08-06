@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH171_PBOOK_LEGACY_RECOVERY"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\recover_pbook_from_legacy_sector_package.py "%ROOT%" --output-dir "%OUT%" --build-disc
) else (
  python tools\recover_pbook_from_legacy_sector_package.py "%ROOT%" --output-dir "%OUT%" --build-disc
)
if errorlevel 1 goto :fail
echo.
echo PASS: %OUT%\BATCH171_RESULT.json
pause
exit /b 0
:fail
echo.
echo BLOCKED: exact pristine Disc, Batch110 patcher, or one or more exact 2352-byte sector sidecars are missing.
pause
exit /b 1
