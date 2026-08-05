@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ST2 Batch118 Exact Patch Recovery

set "MANIFEST=%~1"
if not defined MANIFEST set "MANIFEST=batch118_apply_to_original_bin.py"
set "ROOT=%~2"
if not defined ROOT set "ROOT=%~dp0"

if not exist "%MANIFEST%" (
  echo [ERROR] batch118_apply_to_original_bin.py not found.
  pause
  exit /b 2
)
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3 not found.
  pause
  exit /b 3
)

python "%~dp0tools\recover_exact_patch_from_manifest.py" recover "%MANIFEST%" "%ROOT%" --output-dir "%~dp0output\B118_EXACT_RECOVERY"
set "ERR=%ERRORLEVEL%"
if "%ERR%"=="0" (
  echo [PASS] Exact patch recovery completed.
) else (
  echo [BLOCKED] Exact patched-sector bytes were not found. See RECOVERY_RESULT.json.
)
pause
exit /b %ERR%
