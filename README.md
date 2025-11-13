Got it 😄 — here’s a **cleaner, professional Markdown version** with minimal emojis (kept only where they improve readability, not flair):

---

# GIMP 3.0 TEX Plugin v3.0

**Load & Export League of Legends `.tex` Texture Files**

> **Note:**
> GIMP 3.0 currently shows error dialogs when opening `.tex` files — but they still load correctly.
> This plugin includes an optional **auto-closer** that automatically dismisses those dialogs.

---

## Installation

1. Run the setup file for your GIMP version:

   * `GIMP_3_TEX_Plugin_Setup.exe` → for **GIMP 3.0**
   * `GIMP_2_TEX_Plugin_Setup.exe` → for **GIMP 2.10**

2. Follow the installer:

   * The installer auto-detects your GIMP installation
   * Check **“Install Error Dialog Auto-Closer”** (recommended)
   * Click **Install**

3. Restart GIMP if it’s running

4. Installation complete

---

## Usage

### Opening `.tex` Files

* Go to **File → Open** and select your `.tex` file
* Or drag and drop `.tex` files into GIMP

### Exporting as `.tex`

* Use **File → Export As**
* Enter a filename ending with `.tex`
* Or select **“League of Legends TEX”** from the file type dropdown

---

## Features

* Load **DXT1**, **DXT5**, and **BGRA8** texture formats
* Export images as `.tex` files
* Support for **mipmapped textures**
* Optional **auto-close** for GIMP 3.0 error dialogs

---

## Error Dialog Auto-Closer

### What It Does

* Automatically closes the **“GIMP Message”** dialog caused by a GIMP 3.0 Windows bug
* This is purely cosmetic; the files still load correctly

### Enable / Disable

* Enabled by default during installation
* To disable:

  * Delete `close_gimp_tex_error.py` from the plugin folder
  * Or reinstall without checking the auto-closer option

---

## Uninstallation

1. Open **Windows Settings → Apps → Installed Apps**
2. Find **“GIMP 3.0 TEX Plugin”**
3. Click **Uninstall**
4. Restart GIMP

---

## Requirements

* **GIMP 3.0** or later (includes Python support)
* **Windows 7** or later

---

## Troubleshooting

### Plugin doesn’t appear

* Make sure GIMP is fully closed and restart it
* Verify this folder exists:

  ```
  %APPDATA%\GIMP\3.0\plug-ins\gimp_tex_plugin_3\
  ```
* Check the log file:

  ```
  %USERPROFILE%\gimp_tex_plugin_3.log
  ```

### “GIMP 3.0 not found” during installation

* Ensure you have **GIMP 3.0**, not 2.10
* For GIMP 2.10, use `GIMP_TEX_Plugin_Setup.exe`

### Files won’t open

* Confirm the file is a valid **League of Legends `.tex`** file
* Check:

  ```
  %USERPROFILE%\gimp_tex_plugin_3.log
  ```

### Error dialog still appears

* Ensure the **auto-closer** is installed
* Check if it’s running:

  ```
  %USERPROFILE%\gimp_error_closer.log
  ```
* Restart GIMP

### Export not working

* Use **Export As** (not **Save**)
* Type `.tex` manually at the end of the filename

---

## Supported Formats

* DXT1 (compressed)
* DXT5 (compressed)
* BGRA8 (uncompressed)
* Files with or without mipmaps

---

## Log Files

* Main plugin log:

  ```
  %USERPROFILE%\gimp_tex_plugin_3.log
  ```
* Error closer log:

  ```
  %USERPROFILE%\gimp_error_closer.log
  ```

---

## Credits

* Original `.tex` logic by **LtMAO**

  * [GitHub: tarngaina/LtMAO](https://github.com/tarngaina/LtMAO)
* GIMP 3.0 version and auto-close feature developed for the **League of Legends modding community**

---

## Version History

**v3.0 (2024)**

* Full GIMP 3.0 support
* Auto-close error dialog feature
* Improved export handling
* Enhanced error reporting

**v1.0 (Original)**

* Initial GIMP 2.10 support
* Basic load/save functionality

---

Would you like me to format this as a **GitHub-ready README.md** (with proper code fences, section dividers, and link formatting)? I can make it copy-paste–ready for your repo.
