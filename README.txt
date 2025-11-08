========================================
GIMP .tex Plugin - Installation Guide
========================================

This plugin allows GIMP to open and save League of Legends .tex texture files.

INSTALLATION:
-------------

1. Double-click "GIMP_TEX_Plugin_Setup.exe"

2. Follow the installation wizard:
   - Click "Next" on the welcome screen
   - The installer will automatically find your GIMP installation
   - Click "Install" to begin installation
   - Wait for installation to complete
   - Click "Finish"

3. Restart GIMP (close and reopen if it's running)

4. Done! The plugin is now installed and ready to use.

USAGE:
------

Opening .tex files:
  - File > Open (or drag-and-drop .tex files into GIMP)
  - Or use: Toolbox > File > Open .tex File

Saving as .tex:
  - File > Export As (change file extension to .tex)
  - Or use: Image > File > Save as .tex File

UNINSTALLATION:
---------------

1. Go to Control Panel > Programs > Uninstall a program
2. Find "GIMP .tex Plugin" in the list
3. Click "Uninstall"
4. Restart GIMP

REQUIREMENTS:
-------------

- GIMP 2.10 or later
- Windows 7 or later

TROUBLESHOOTING:
----------------

Plugin doesn't appear after installation:
  - Make sure GIMP is completely closed
  - Restart GIMP
  - Check GIMP's error console: Filters > Python-Fu > Console

"GIMP not found" error:
  - Make sure GIMP 2.10 is installed
  - The plugin directory should be at:
    %APPDATA%\GIMP\2.10\plug-ins\

Files won't open:
  - Make sure the .tex file is a valid League of Legends texture file
  - Check the log file: %USERPROFILE%\gimp_tex_plugin.log

SUPPORTED FORMATS:
------------------

- DXT1 compressed textures
- DXT5 compressed textures  
- BGRA8 uncompressed textures
- Files with or without mipmaps

For more information or support, check the plugin's log file:
%USERPROFILE%\gimp_tex_plugin.log
