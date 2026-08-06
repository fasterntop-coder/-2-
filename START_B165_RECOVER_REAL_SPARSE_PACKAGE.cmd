@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
  echo 사용법: %~nx0 "순정 Disc1.bin" "sparse patch.zip"
  pause
  exit /b 1
)
if "%~2"=="" (
  echo sparse patch ZIP 경로가 필요합니다.
  pause
  exit /b 1
)

set "SOURCE=%~1"
set "PACKAGE=%~2"
set "OUT=%CD%\output\BATCH165_REAL_SPARSE_RECOVERY"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

%PY% tools\verify_sparse_package_mode1.py verify "%SOURCE%" "%PACKAGE%" --result "%OUT%\MODE1_EDC_ECC_AUDIT.json"
if errorlevel 1 goto FAIL
%PY% tools\recover_assets_from_sparse_packages.py recover "%SOURCE%" "%PACKAGE%" --output-dir "%OUT%\ASSETS"
if errorlevel 1 goto FAIL

echo.
echo PASS - exact assets: %OUT%\ASSETS
echo MODE1 audit: %OUT%\MODE1_EDC_ECC_AUDIT.json
pause
exit /b 0

:FAIL
echo.
echo FAIL - SHA / Expected Write / MODE1 EDC-ECC / re-extraction gate failed.
pause
exit /b 1
