@echo off
echo ========================================
echo GIMP 2.10 TEX Plugin Updater
echo ========================================
echo.

REM Delete GIMP plugin cache
echo Step 1: Clearing GIMP plugin cache...
if exist "%APPDATA%\GIMP\2.10\pluginrc" (
    del "%APPDATA%\GIMP\2.10\pluginrc"
    echo   Cache cleared!
) else (
    echo   Cache file not found (this is OK)
)
echo.

REM Copy plugin to GIMP directory
echo Step 2: Copying plugin files...
if not exist "%APPDATA%\GIMP\2.10\plug-ins\" (
    echo ERROR: GIMP 2.10 plugin directory not found!
    echo Expected: %APPDATA%\GIMP\2.10\plug-ins\
    pause
    exit /b 1
)

copy /Y "gimp_tex_plugin.py" "%APPDATA%\GIMP\2.10\plug-ins\gimp_tex_plugin.py"
if errorlevel 1 (
    echo ERROR: Failed to copy plugin!
    pause
    exit /b 1
)
echo   Plugin copied!

copy /Y "dds_to_tex.py" "%APPDATA%\GIMP\2.10\plug-ins\dds_to_tex.py"
if errorlevel 1 (
    echo WARNING: Failed to copy dds_to_tex.py
) else (
    echo   dds_to_tex.py copied!
)

if exist "dxt_compress.dll" (
    copy /Y "dxt_compress.dll" "%APPDATA%\GIMP\2.10\plug-ins\dxt_compress.dll"
    if errorlevel 1 (
        echo WARNING: Failed to copy dxt_compress.dll
    ) else (
        echo   dxt_compress.dll copied! (FAST compression enabled)
    )
    
    REM Copy MinGW runtime DLLs if they exist
    if exist "libwinpthread-1.dll" copy /Y "libwinpthread-1.dll" "%APPDATA%\GIMP\2.10\plug-ins\libwinpthread-1.dll" >nul 2>&1
    if exist "libgcc_s_seh-1.dll" copy /Y "libgcc_s_seh-1.dll" "%APPDATA%\GIMP\2.10\plug-ins\libgcc_s_seh-1.dll" >nul 2>&1
    if exist "libstdc++-6.dll" copy /Y "libstdc++-6.dll" "%APPDATA%\GIMP\2.10\plug-ins\libstdc++-6.dll" >nul 2>&1
) else (
    echo   dxt_compress.dll not found - will use slow Python compression
    echo   To enable fast compression, run: build_dxt_dll_direct.bat
)
echo.

echo ========================================
echo SUCCESS! Plugin updated.
echo Please restart GIMP for changes to take effect.
echo ========================================
pause
