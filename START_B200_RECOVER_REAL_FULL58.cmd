@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  ST2 Disc 1 Batch200 - Real Battle/Static 58/58 Recovery
echo ============================================================
echo.
echo Required in one input folder:
echo   - pristine Disc 1 BIN
echo   - ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip
echo   - ST2R41_BATCH110_PBOOK_BT_AND_FIVE_ASSET_INTEGRATION.zip
echo.
set "INPUT=%~1"
if "%INPUT%"=="" set "INPUT=%~dp0INPUT"
set "SRC=%INPUT%\015 Sakura Taisen 2 Disc 1 of 3 (J).bin"
set "B137=%INPUT%\ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip"
set "B110=%INPUT%\ST2R41_BATCH110_PBOOK_BT_AND_FIVE_ASSET_INTEGRATION.zip"

python "%~dp0tools\recover_real_full58.py" recover "%SRC%" "%B137%" "%B110%" --output-dir "%~dp0output\BATCH200_FULL58"
if errorlevel 1 (
  echo.
  echo Batch200 recovery FAILED.
  exit /b 1
)
echo.
echo Batch200 PASS. Exact assets are in output\BATCH200_FULL58\EXACT_58_ASSETS
exit /b 0
