@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo Sakura Taisen 2 Disc 1 - Batch145 checkpoint mosaic recovery
echo ============================================================
echo.
echo 이 저장소 또는 하위 폴더에 아래 자료를 가능한 만큼 둡니다.
echo - batch118_apply_to_original_bin.py
echo - 순정 Disc 1 BIN 또는 ZIP
echo - 과거 B110/B117/B118/B124/B127/B130 등의 BIN 또는 ZIP
echo - PATCH_SECTORS가 들어 있는 ZIP/폴더
echo.

set "MANIFEST=%~dp0batch118_apply_to_original_bin.py"
if not exist "%MANIFEST%" set "MANIFEST=%~dp0local\batch118_apply_to_original_bin.py"
if not exist "%MANIFEST%" (
  echo [차단] batch118_apply_to_original_bin.py가 없습니다.
  echo 저장소 루트 또는 local 폴더에 놓아주세요.
  pause
  exit /b 2
)

python "%~dp0tools\recover_checkpoint_mosaic.py" recover "%MANIFEST%" "%~dp0" --output-dir "%~dp0output\B145_MOSAIC"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [완료] output\B145_MOSAIC 결과를 확인하세요.
) else (
  echo [미완료] MOSAIC_RECOVERY_RESULT.json에 자산별 회수율과 누락 LBA가 기록되었습니다.
)
pause
exit /b %RC%
