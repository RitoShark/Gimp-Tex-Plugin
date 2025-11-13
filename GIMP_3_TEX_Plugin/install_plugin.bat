@echo off
echo ========================================
echo GIMP 3.0 TEX Plugin Updater
echo ========================================
echo.

REM Delete GIMP plugin cache
echo Step 1: Clearing GIMP plugin cache...
if exist "%APPDATA%\GIMP\3.0\pluginrc" (
    del "%APPDATA%\GIMP\3.0\pluginrc"
    echo   Cache cleared!
) else (
    echo   Cache file not found (this is OK)
)
echo.

REM Copy plugin to GIMP directory
echo Step 2: Copying plugin files...
if not exist "%APPDATA%\GIMP\3.0\plug-ins\" (
    echo ERROR: GIMP 3.0 plugin directory not found!
    echo Expected: %APPDATA%\GIMP\3.0\plug-ins\
    pause
    exit /b 1
)

REM Create plugin subfolder
if not exist "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\" (
    mkdir "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3"
)

copy /Y "gimp_tex_plugin_3.py" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\gimp_tex_plugin_3.py"
if errorlevel 1 (
    echo ERROR: Failed to copy plugin!
    pause
    exit /b 1
)
echo   Plugin copied!

REM Copy error closer if it exists
if exist "close_gimp_tex_error.py" (
    copy /Y "close_gimp_tex_error.py" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\close_gimp_tex_error.py"
    if errorlevel 1 (
        echo WARNING: Failed to copy error closer
    ) else (
        echo   Error closer copied!
    )
)

REM Copy fast compression DLL if it exists
if exist "dxt_compress.dll" (
    copy /Y "dxt_compress.dll" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\dxt_compress.dll"
    if errorlevel 1 (
        echo WARNING: Failed to copy dxt_compress.dll
    ) else (
        echo   dxt_compress.dll copied! (FAST compression enabled)
    )
    
    REM Copy MinGW runtime DLLs if they exist
    if exist "libwinpthread-1.dll" copy /Y "libwinpthread-1.dll" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\libwinpthread-1.dll" >nul 2>&1
    if exist "libgcc_s_seh-1.dll" copy /Y "libgcc_s_seh-1.dll" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\libgcc_s_seh-1.dll" >nul 2>&1
    if exist "libstdc++-6.dll" copy /Y "libstdc++-6.dll" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\libstdc++-6.dll" >nul 2>&1
    if exist "libgomp-1.dll" copy /Y "libgomp-1.dll" "%APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\libgomp-1.dll" >nul 2>&1
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
