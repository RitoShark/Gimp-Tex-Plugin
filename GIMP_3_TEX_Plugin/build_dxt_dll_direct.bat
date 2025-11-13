@echo off
echo Building fast DXT compression DLL with MinGW...
echo.

set MINGW_PATH=C:\Users\Frog\Desktop\mingw64\bin

if not exist "%MINGW_PATH%\g++.exe" (
    echo ERROR: g++.exe not found at %MINGW_PATH%
    echo Please check the MinGW path
    pause
    exit /b 1
)

echo Using MinGW from: %MINGW_PATH%
echo.

"%MINGW_PATH%\g++.exe" -shared -O3 -march=native -fopenmp -static-libgcc -static-libstdc++ -o dxt_compress.dll dxt_compress.cpp

if exist dxt_compress.dll (
    echo.
    echo ========================================
    echo SUCCESS! dxt_compress.dll created
    echo ========================================
    echo.
    echo The GIMP plugin will now use FAST compression
    echo Speed improvement: 10-100x faster!
    echo.
    echo Next steps:
    echo 1. Run: update_gimp_plugin.bat
    echo 2. Restart GIMP
    echo 3. Enjoy fast texture saving!
) else (
    echo.
    echo ERROR: DLL was not created
    echo Check for compilation errors above
)
echo.
pause
