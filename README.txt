========================================
GIMP 3.0 TEX Plugin - Installation Guide
========================================

This plugin allows GIMP 3.0 to open and save League of Legends .tex texture files.

NEW IN VERSION 3.0:
-------------------
✓ Full GIMP 3.0 support
✓ Auto-close error dialogs (optional feature)
✓ Multi-language support (24+ languages)
✓ Improved stability and performance

INSTALLATION:
-------------

1. Double-click "GIMP_3_TEX_Plugin_Setup.exe"

2. Follow the installation wizard:
   - Click "Next" on the welcome screen
   - The installer will automatically find your GIMP 3.0 installation
   - Select additional features:
     • Error Dialog Auto-Closer (Recommended) - Automatically closes the 
       annoying error dialog that appears due to a GIMP 3.0 Windows bug
   - Click "Install" to begin installation
   - Wait for installation to complete
   - Click "Finish"

3. Restart GIMP (close and reopen if it's running)

4. Done! The plugin is now installed and ready to use.

USAGE:
------

Opening .tex files:
- File > Open > select your .tex file
- Or drag-and-drop .tex files into GIMP

Exporting as .tex:
- File > Export As > type filename with .tex extension
- Or select "League of Legends TEX" from file type dropdown

FEATURES:
---------

✓ Load DXT1, DXT5, and BGRA8 texture formats
✓ Export images as TEX files
✓ Support for mipmapped textures
✓ Auto-close error dialogs (optional)
✓ Works in all languages

ERROR DIALOG AUTO-CLOSER:
-------------------------

What it does:
- Automatically closes the "GIMP Message" error dialog that appears when 
  loading TEX files
- This is a workaround for a GIMP 3.0 Windows bug where the error appears 
  even though the file loads successfully
- Works in 24+ languages
- Runs silently in the background
- Only closes TEX-related error dialogs (safe for other GIMP operations)

How to enable/disable:
- Enabled by default during installation (checkbox)
- To disable: Uninstall and reinstall without the checkbox
- Or manually delete: %APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\close_gimp_tex_error.py

UNINSTALLATION:
---------------

1. Go to Windows Settings > Apps > Apps & features
2. Find "GIMP 3.0 TEX Plugin" in the list
3. Click "Uninstall"
4. Restart GIMP

REQUIREMENTS:
-------------

- GIMP 3.0 or later (includes Python - no separate installation needed!)
- Windows 7 or later

TROUBLESHOOTING:
----------------

Plugin doesn't appear after installation:
- Make sure GIMP is completely closed and restart it
- Check the plugin folder exists:
  %APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\
- Check the log file: %USERPROFILE%\gimp_tex_plugin_3.log

"GIMP 3.0 not found" error during installation:
- Make sure GIMP 3.0 is installed (not GIMP 2.10)
- For GIMP 2.10, use the old installer: GIMP_TEX_Plugin_Setup.exe

Files won't open:
- Make sure the .tex file is a valid League of Legends texture file
- Check the log file: %USERPROFILE%\gimp_tex_plugin_3.log

Error dialog still appears:
- Make sure the error closer was installed (check during setup)
- Check if it's running: %USERPROFILE%\gimp_error_closer.log
- Restart GIMP completely

Export not working:
- Use File > Export As (not Save)
- Make sure to type the .tex extension manually

SUPPORTED FORMATS:
------------------

- DXT1 compressed textures
- DXT5 compressed textures  
- BGRA8 uncompressed textures
- Files with or without mipmaps

LOG FILES:
----------

Main plugin log: %USERPROFILE%\gimp_tex_plugin_3.log
Error closer log: %USERPROFILE%\gimp_error_closer.log

CREDITS:
--------

Original plugin by LtMAO Team
GitHub: https://github.com/tarngaina/LtMAO

GIMP 3.0 version with auto-close feature
Developed with ❤️ for the League of Legends modding community

VERSION HISTORY:
----------------

v3.0 (2024)
- Full GIMP 3.0 support
- Auto-close error dialogs feature
- Multi-language support (24+ languages)
- Improved export functionality
- Better error handling

v1.0 (Original)
- GIMP 2.10 support
- Basic load/save functionality
