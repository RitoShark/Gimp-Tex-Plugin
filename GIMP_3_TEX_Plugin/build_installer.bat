@echo off
echo ========================================
echo Building GIMP 3.0 TEX Plugin Installer
echo ========================================
echo.

REM Check if Inno Setup is installed
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%INNO_PATH%" (
    set INNO_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)

if not exist "%INNO_PATH%" (
    echo ERROR: Inno Setup not found!
    echo.
    echo Please install Inno Setup 6 from:
    echo https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)

echo Using Inno Setup: %INNO_PATH%
echo.

REM Check if required files exist
if not exist "gimp_tex_plugin_3.py" (
    echo ERROR: gimp_tex_plugin_3.py not found!
    pause
    exit /b 1
)

if not exist "close_gimp_tex_error.py" (
    echo WARNING: close_gimp_tex_error.py not found!
    echo The error dialog auto-closer will not be included.
    echo.
)

REM Build the installer
echo Building installer...
"%INNO_PATH%" "GIMP_3_TEX_Plugin_Setup.iss"

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS!
echo ========================================
echo.
echo Installer created: GIMP_3_TEX_Plugin_Setup.exe
echo.
pause
