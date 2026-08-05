@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo 사용법: %~nx0 ^<과거 BIN/ZIP/자산 검색 폴더^>
  exit /b 2
)
python tools\recover_exact_assets_from_checkpoints.py recover manifests\BATCH183_187_EXACT_TARGETS.json "%~1" --output-dir output\B152_EXACT_ASSETS
exit /b %errorlevel%
