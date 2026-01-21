<<<<<<< HEAD
# build_exe.bat
# Batch script to build Reality Collapsing into a Windows .exe using PyInstaller
# Usage: Double-click this file or run it in a terminal

@echo off
REM Ensure pip and pyinstaller are available
python -m pip install --upgrade pip
python -m pip install pyinstaller

REM Build the game into a single .exe (no console window), including assets folder, with custom name
python -m PyInstaller --onefile --windowed --icon="icon.ico" --add-data "assets;assets" --name "RealityCollapsing" main.py


REM Copy assets folder to dist (for safety, in case --add-data is not enough for dynamic loads)
xcopy assets dist\assets /E /I /Y

REM Notify user of output location
echo.
echo Build complete! Your .exe and assets are in the dist folder.
pause
=======
# build_exe.bat
# Batch script to build Reality Collapsing into a Windows .exe using PyInstaller
# Usage: Double-click this file or run it in a terminal

@echo off
REM Ensure pip and pyinstaller are available
python -m pip install --upgrade pip
python -m pip install pyinstaller

REM Build the game into a single .exe (no console window), including assets folder, with custom name
python -m PyInstaller --onefile --windowed --icon="icon.ico" --add-data "assets;assets" --name "RealityCollapsing" main.py


REM Copy assets folder to dist (for safety, in case --add-data is not enough for dynamic loads)
xcopy assets dist\assets /E /I /Y

REM Notify user of output location
echo.
echo Build complete! Your .exe and assets are in the dist folder.
pause
>>>>>>> 0b8b5b3ca9fbab68e9d89eabc877706fe3156be2
