@echo off
REM Run this ON WINDOWS, inside this folder, with a Python venv active.
REM PyInstaller builds a native binary for whatever OS it runs on, so the
REM .exe has to be built on a Windows machine - it can't be cross-compiled
REM from Linux/Mac.

pip install -r requirements.txt

REM --icon sets the .exe's own file/taskbar icon.
REM --add-data bundles the assets folder into the onefile build so the
REM in-app logo (assets/icon.png) is still found at runtime; the ";assets"
REM after the source path is where PyInstaller unpacks it inside the
REM bundle - app.py looks for it there via its resource_path() helper.
pyinstaller --onefile --windowed --name "DualMessageQR" --icon "assets\icon.ico" --add-data "assets;assets" app.py

echo.
echo Done. Your app.exe is in the "dist" folder: dist\DualMessageQR.exe
pause
