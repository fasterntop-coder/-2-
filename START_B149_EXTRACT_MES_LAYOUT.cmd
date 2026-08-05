@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: %~nx0 ^<folder containing SYSTEM.MES, SYS14.MES and BATCH118_RECORD_AUDIT_458.csv^>
  exit /b 2
)

set "ROOT=%~1"
set "OUT=%ROOT%\B149_LAYOUT"
if not exist "%OUT%" mkdir "%OUT%"

python tools\extract_mes_fixed_layout.py extract --asset "%ROOT%\SYSTEM.MES" --audit "%ROOT%\BATCH118_RECORD_AUDIT_458.csv" --bank SYSTEM --expected-asset-sha256 943d6cf1fb996a416f90ad6e2bea2b147f4931623b480a1622cf200586ddd385 --output "%OUT%\SYSTEM_LAYOUT.json"
if errorlevel 1 exit /b %errorlevel%

python tools\extract_mes_fixed_layout.py extract --asset "%ROOT%\SYS14.MES" --audit "%ROOT%\BATCH118_RECORD_AUDIT_458.csv" --bank SYS14 --expected-asset-sha256 69f618f86010c35f28d20efc40a9374a3fc99e594cc7b110ad91c4fa36ce1f5a --output "%OUT%\SYS14_LAYOUT.json"
if errorlevel 1 exit /b %errorlevel%

echo PASS: exact SYSTEM and SYS14 fixed-allocation layouts extracted to "%OUT%"
