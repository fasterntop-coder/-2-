@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: %~nx0 ^<search-root-containing-B118-CSV-or-workbook^>
  exit /b 2
)
py -3 tools\recover_b118_character_maps.py recover "%~1" --output-dir output\B151_CHARACTER_MAPS
if errorlevel 1 exit /b %errorlevel%
echo.
echo PASS: exact SYSTEM/SYS14 character maps recovered to output\B151_CHARACTER_MAPS
endlocal
