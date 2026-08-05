@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ST2 B140 PBOOK_BT exact search

echo ============================================================
echo  Sakura Taisen 2 - PBOOK_BT 높/낮 exact SHA search
echo ============================================================
echo.
set /p SYSTEM_FILE=한글 glyph가 포함된 SYSTEM 또는 MES 파일 경로: 
set /p PBOOK_FILE=순정 PBOOK_BT.CG 파일 경로: 

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python 3를 찾지 못했습니다.
  pause
  exit /b 3
)

python tools\run_pbook_bt_height_low.py --system "%SYSTEM_FILE%" --pbook "%PBOOK_FILE%" --output-dir output\B140
set ERR=%ERRORLEVEL%
echo.
if "%ERR%"=="0" (
  echo [완료] output\B140\PBOOK_BT_B140_EXACT.CG 와 결과 JSON을 확인하세요.
) else (
  echo [중단] output\B140\B140_RUN_RESULT.json 또는 GLYPH_EXTRACTION_RESULT.json을 확인하세요.
)
pause
exit /b %ERR%
