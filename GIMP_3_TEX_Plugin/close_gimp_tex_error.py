#!/usr/bin/env python3
"""
Auto-close GIMP TEX error dialogs (using ctypes - no external dependencies)

This script monitors for GIMP error dialogs related to TEX file loading
and automatically closes them. This is a workaround for a GIMP 3.0 Windows bug.
"""

import ctypes
from ctypes import wintypes
import time
import sys

# Windows API constants
WM_CLOSE = 0x0010
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D
GW_CHILD = 5
GW_HWNDNEXT = 2

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Define callback type for EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

def get_window_text(hwnd):
    """Get window title text"""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value

def get_class_name(hwnd):
    """Get window class name"""
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value

def is_window_visible(hwnd):
    """Check if window is visible"""
    return user32.IsWindowVisible(hwnd)

def enum_child_windows(parent_hwnd):
    """Enumerate all child windows and get their text"""
    texts = []
    
    def callback(hwnd, lparam):
        text = get_window_text(hwnd)
        if text:
            texts.append(text)
        return True
    
    enum_func = EnumWindowsProc(callback)
    user32.EnumChildWindows(parent_hwnd, enum_func, 0)
    return texts

def close_window(hwnd):
    """Try to close a window using multiple methods"""
    try:
        # Method 1: Send Enter key
        user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
        user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
        time.sleep(0.01)
        
        # Method 2: Send WM_CLOSE
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True
    except:
        return False

# Track recently closed windows to avoid spam
_recently_closed = {}
_close_cooldown = 2.0  # seconds

def find_and_close_gimp_tex_errors():
    """Find and close GIMP Message dialogs (simple and safe approach)"""
    global _recently_closed
    closed_count = 0
    current_time = time.time()
    
    # Clean up old entries
    _recently_closed = {k: v for k, v in _recently_closed.items() if current_time - v < _close_cooldown}
    
    def enum_callback(hwnd, lparam):
        nonlocal closed_count
        
        if not is_window_visible(hwnd):
            return True
        
        # Get window info
        title = get_window_text(hwnd)
        class_name = get_class_name(hwnd)
        
        if not title:
            return True
        
        title_lower = title.lower()
        
        # ONLY close "GIMP Message" or "Mensaje de GIMP" style dialogs
        # These are the error message dialogs
        # Skip everything else (startup, main window, etc.)
        message_patterns = [
            ("gimp", "message"),      # English
            ("gimp", "mensaje"),      # Spanish  
            ("gimp", "mensagem"),     # Portuguese
            ("gimp", "meldung"),      # German
            ("gimp", "messaggio"),    # Italian
            ("gimp", "bericht"),      # Dutch
            ("gimp", "meddelande"),   # Swedish
            ("gimp", "melding"),      # Norwegian/Danish
            ("gimp", "viesti"),       # Finnish
        ]
        
        is_message_dialog = False
        for word1, word2 in message_patterns:
            if word1 in title_lower and word2 in title_lower:
                is_message_dialog = True
                break
        
        # Must be a message dialog with the right class
        if is_message_dialog and class_name == "gdkWindowToplevel":
            # Check if we recently closed this window
            if hwnd in _recently_closed:
                return True  # Skip, already closed recently
            
            print(f"✓ Found GIMP Message dialog: '{title}'")
            print(f"  Window: {hwnd}, Class: {class_name}")
            print(f"  Closing...")
            sys.stdout.flush()
            
            if close_window(hwnd):
                closed_count += 1
                _recently_closed[hwnd] = current_time
                print(f"  ✓ Closed!")
            else:
                print(f"  ✗ Failed to close")
            
            sys.stdout.flush()
        
        return True
    
    enum_func = EnumWindowsProc(enum_callback)
    user32.EnumWindows(enum_func, 0)
    
    return closed_count

def main():
    # Set up logging to file
    import os
    log_file = os.path.join(os.path.expanduser('~'), 'gimp_error_closer.log')
    try:
        log = open(log_file, 'a', encoding='utf-8')
        sys.stdout = log
        sys.stderr = log
    except:
        pass
    
    print("\n" + "="*60)
    print("GIMP TEX Error Dialog Auto-Closer")
    print("="*60)
    print("\nMonitoring for GIMP TEX error dialogs...")
    print("This will automatically close the annoying error messages.")
    print("Running in background...\n")
    sys.stdout.flush()
    
    total_closed = 0
    check_interval = 0.05  # Check every 50ms
    
    try:
        while True:
            closed = find_and_close_gimp_tex_errors()
            if closed > 0:
                total_closed += closed
                print(f"\n[Total dialogs closed: {total_closed}]\n")
                sys.stdout.flush()
            
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print(f"Stopped. Total dialogs closed: {total_closed}")
        print("="*60)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
