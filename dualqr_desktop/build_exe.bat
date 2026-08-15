@echo off
REM Run this ON WINDOWS, inside this folder, with a Python venv active.
REM PyInstaller builds a native binary for whatever OS it runs on, so the
REM .exe has to be built on a Windows machine - it can't be cross-compiled
REM from Linux/Mac.

pip install -r requirements.txt

pyinstaller --onefile --windowed --name "DualMessageQR" app.py

echo.
echo Done. Your app.exe is in the "dist" folder: dist\DualMessageQR.exe
pause
