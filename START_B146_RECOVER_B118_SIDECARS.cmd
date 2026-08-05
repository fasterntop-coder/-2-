@echo off
chcp 65001 >nul
cd /d "%~dp0"
set ROOT=%~1
if "%ROOT%"=="" set ROOT=%USERPROFILE%\Downloads
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 tools\recover_b118_sidecars.py recover "%ROOT%" --output-dir output\B118_SIDECARS
) else (
  python tools\recover_b118_sidecars.py recover "%ROOT%" --output-dir output\B118_SIDECARS
)
pause
