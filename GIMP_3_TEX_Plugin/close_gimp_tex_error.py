#!/usr/bin/env python3
"""
Auto-close GIMP TEX error dialogs (using ctypes - no external dependencies)

This script monitors for GIMP error dialogs related to TEX file loading
and automatically closes them. This is a workaround for a GIMP 3.0 Windows bug.

SMART TIMING: Only activates 2 seconds after a TEX file is successfully loaded.
This prevents closing helpful validation messages during save operations.
"""

import ctypes
from ctypes import wintypes
import time
import sys
import os

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
    """Try to close a window using multiple aggressive methods"""
    try:
        # Method 1: Send WM_CLOSE immediately (fastest)
        user32.SendMessageW(hwnd, WM_CLOSE, 0, 0)
        
        # Method 2: Send Enter key (in case dialog needs confirmation)
        user32.SendMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
        user32.SendMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
        
        # Method 3: Force destroy if still visible
        if user32.IsWindowVisible(hwnd):
            user32.DestroyWindow(hwnd)
        
        return True
    except:
        return False

# Track recently closed windows to avoid spam
_recently_closed = {}
_close_cooldown = 2.0  # seconds

# Signal file for TEX load events
_signal_file = os.path.join(os.path.expanduser('~'), '.gimp_tex_load_signal')
_last_tex_load_time = 0
_activation_delay = 0.5  # Start closing errors 500ms after TEX load (fast!)
_deactivation_delay = 2.5  # Stop closing errors 2.5 seconds after TEX load (2 second window)

def check_tex_load_signal():
    """Check if a TEX file was recently loaded"""
    global _last_tex_load_time
    
    try:
        if os.path.exists(_signal_file):
            signal_time = os.path.getmtime(_signal_file)
            if signal_time > _last_tex_load_time:
                _last_tex_load_time = signal_time
                print(f"\n✓ TEX load detected at {time.strftime('%H:%M:%S', time.localtime(signal_time))}")
                print(f"  Error closer will activate in {_activation_delay} seconds...")
                sys.stdout.flush()
    except:
        pass

def is_error_closer_active():
    """Check if we're in the active window (2-5 seconds after TEX load)"""
    if _last_tex_load_time == 0:
        return False  # No TEX loaded yet
    
    time_since_load = time.time() - _last_tex_load_time
    
    # Active window: between 2 and 5 seconds after load
    is_active = _activation_delay <= time_since_load <= _deactivation_delay
    
    if is_active and time_since_load > _activation_delay + 0.1:  # Don't spam the first check
        # Show status occasionally
        if int(time_since_load * 10) % 10 == 0:  # Every 1 second
            remaining = _deactivation_delay - time_since_load
            print(f"  [Active: {remaining:.0f}s remaining]")
            sys.stdout.flush()
    
    return is_active

def find_and_close_gimp_tex_errors():
    """Find and close GIMP Message dialogs (simple and safe approach)"""
    global _recently_closed
    closed_count = 0
    current_time = time.time()
    
    # Check for TEX load signal
    check_tex_load_signal()
    
    # Only close errors if we're in the active window (2+ seconds after TEX load)
    if not is_error_closer_active():
        return 0  # Not active yet
    
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
            
            # We're in active mode (2+ seconds after TEX load)
            # Close all GIMP Message dialogs (they're all TEX loading spam at this point)
            
            print(f"✓ Found GIMP Message dialog: '{title}'")
            print(f"  Window: {hwnd}, Class: {class_name}")
            print(f"  Time since TEX load: {current_time - _last_tex_load_time:.1f}s")
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
    print("GIMP TEX Error Dialog Auto-Closer (Smart Mode)")
    print("="*60)
    print("\nWaiting for TEX file to be loaded...")
    print(f"Active window: {_activation_delay}s - {_deactivation_delay}s after TEX load")
    print("This prevents closing helpful validation messages!")
    print("\nRunning in background...\n")
    sys.stdout.flush()
    
    total_closed = 0
    check_interval = 0.01  # Check every 10ms (ultra-fast response)
    
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
