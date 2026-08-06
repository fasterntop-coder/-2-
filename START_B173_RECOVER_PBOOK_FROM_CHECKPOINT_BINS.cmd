@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%~1"
if "%ROOT%"=="" set "ROOT=%CD%"
set "OUT=%CD%\output\BATCH173_CHECKPOINT_BIN_RECOVERY"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\recover_pbook_sectors_from_checkpoint_bins.py "%ROOT%" --output-dir "%OUT%" --build-disc
) else (
  python tools\recover_pbook_sectors_from_checkpoint_bins.py "%ROOT%" --output-dir "%OUT%" --build-disc
)
if errorlevel 1 goto :fail
echo.
echo PASS: %OUT%\BATCH173_RESULT.json
pause
exit /b 0
:fail
echo.
echo Batch173 blocked or failed. No output candidate should be trusted.
pause
exit /b 1
