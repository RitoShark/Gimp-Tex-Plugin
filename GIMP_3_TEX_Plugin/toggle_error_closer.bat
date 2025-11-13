@echo off
echo ========================================
echo GIMP Error Closer Toggle
echo ========================================
echo.

REM Check if it's running
tasklist /FI "WINDOWTITLE eq GIMP TEX Error*" 2>NUL | find /I /N "python">NUL
if "%ERRORLEVEL%"=="0" (
    echo Error closer is currently RUNNING
    echo.
    echo Stopping it...
    taskkill /F /FI "WINDOWTITLE eq GIMP TEX Error*" >NUL 2>&1
    timeout /t 1 >NUL
    echo.
    echo ✓ Error closer STOPPED
    echo.
    echo Now you can see all error messages normally.
) else (
    echo Error closer is currently STOPPED
    echo.
    echo Starting it...
    start "GIMP TEX Error Closer" /MIN python close_gimp_tex_error.py
    timeout /t 1 >NUL
    echo.
    echo ✓ Error closer STARTED (running in background)
    echo.
    echo TEX loading errors will be auto-closed.
)

echo.
echo ========================================
pause
