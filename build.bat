@echo off
REM Build script for EverFlow - Windows
REM Creates a standalone .exe

echo === EverFlow Build Script (Windows) ===
echo.

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building executable...
python -m PyInstaller --clean EverFlow.spec

echo.
echo === Build Complete ===
echo App location: dist\EverFlow.exe
echo.
echo You can copy the .exe to any location or create a shortcut.
pause