#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP 3.0 Plugin for League of Legends .tex files

Supports loading and exporting DXT1, DXT5, and BGRA8 texture formats.

Features:
- Load TEX files: File > Open > select .tex file
- Export TEX files: File > Export As > choose .tex extension
- Auto-closes error dialogs (GIMP 3.0 Windows bug workaround)

Installation:
Windows: %APPDATA%\\GIMP\\3.0\\plug-ins\\gimp_tex_plugin_3\\
  - gimp_tex_plugin_3.py (main plugin)
  - close_gimp_tex_error.py (error dialog closer - auto-started)

Note: Both files must be in the same folder for auto-close to work.
"""

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, GimpUi, Gtk, GObject, GLib, Gegl
import struct
import sys
import os
import subprocess
import threading

# Set up logging
log_file = os.path.join(os.path.expanduser('~'), 'gimp_tex_plugin_3.log')
try:
    log_handle = open(log_file, 'a', encoding='utf-8')
    sys.stderr = log_handle
    sys.stdout = log_handle
    print("\n" + "="*60)
    print("GIMP 3.0 .tex plugin starting...")
    print(f"Python version: {sys.version}")
    sys.stdout.flush()
except Exception as e:
    pass

# Auto-start error dialog closer (workaround for GIMP 3.0 Windows bug)
_error_closer_process = None

def start_error_closer():
    """Start the error dialog closer script in background"""
    global _error_closer_process
    
    try:
        # Find the close_gimp_tex_error.py script in the same directory
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        closer_script = os.path.join(plugin_dir, 'close_gimp_tex_error.py')
        
        if os.path.exists(closer_script):
            print(f"Starting error dialog closer: {closer_script}")
            
            # Find Python executable - try multiple sources
            python_exe = None
            
            # 1. Try GIMP's Python (current executable)
            if sys.executable and os.path.exists(sys.executable):
                python_exe = sys.executable
                # Try pythonw.exe for no console window
                pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
                if os.path.exists(pythonw):
                    python_exe = pythonw
            
            # 2. Try GIMP's bin directory
            if not python_exe:
                gimp_bin = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'GIMP 3', 'bin', 'python.exe')
                if os.path.exists(gimp_bin):
                    python_exe = gimp_bin
            
            # 3. Try system Python
            if not python_exe:
                try:
                    result = subprocess.run(['where', 'python'], capture_output=True, text=True)
                    if result.returncode == 0:
                        python_exe = result.stdout.strip().split('\n')[0]
                except:
                    pass
            
            if python_exe:
                print(f"Using Python: {python_exe}")
                
                # Start the script in background (no window)
                if sys.platform == 'win32':
                    _error_closer_process = subprocess.Popen(
                        [python_exe, closer_script],
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    _error_closer_process = subprocess.Popen(
                        [python_exe, closer_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                
                print(f"Error dialog closer started (PID: {_error_closer_process.pid})")
                sys.stdout.flush()
            else:
                print("Warning: Could not find Python executable")
                sys.stdout.flush()
        else:
            print(f"Warning: Error closer script not found at {closer_script}")
            sys.stdout.flush()
    except Exception as e:
        print(f"Failed to start error dialog closer: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()

# Start error closer in a separate thread to avoid blocking
threading.Thread(target=start_error_closer, daemon=True).start()



# ============================================================================
# TEX Format
# ============================================================================

class TEXFormat:
    DXT1 = 10
    DXT5 = 12
    BGRA8 = 20


class TEX:
    def __init__(self):
        self.width = None
        self.height = None
        self.format = None
        self.mipmaps = False
        self.data = None
    
    def read(self, path):
        with open(path, 'rb') as f:
            signature, = struct.unpack('<I', f.read(4))
            if signature != 0x00584554:  # "TEX\0"
                raise Exception(f'Invalid .tex signature: {hex(signature)}')
            
            self.width, self.height = struct.unpack('<HH', f.read(4))
            unknown1, self.format, unknown2 = struct.unpack('<BBB', f.read(3))
            self.mipmaps, = struct.unpack('<?', f.read(1))
            
            # Read texture data with proper mipmap handling
            if self.mipmaps and self.format in (TEXFormat.DXT1, TEXFormat.DXT5, TEXFormat.BGRA8):
                # Calculate mipmap count
                mipmap_count = 32 - len(f'{max(self.width, self.height):032b}'.split('1', 1)[0])
                
                # Determine block size
                if self.format == TEXFormat.DXT1:
                    block_size = 4
                    bytes_per_block = 8
                elif self.format == TEXFormat.DXT5:
                    block_size = 4
                    bytes_per_block = 16
                else:  # BGRA8
                    block_size = 1
                    bytes_per_block = 4
                
                # Read all mipmaps (from smallest to largest)
                self.data = []
                for i in reversed(range(mipmap_count)):
                    current_width = max(self.width // (1 << i), 1)
                    current_height = max(self.height // (1 << i), 1)
                    block_width = (current_width + block_size - 1) // block_size
                    block_height = (current_height + block_size - 1) // block_size
                    current_size = bytes_per_block * block_width * block_height
                    data_chunk = f.read(current_size)
                    if len(data_chunk) < current_size:
                        raise Exception(f'Unexpected end of file while reading mipmap {i}')
                    self.data.append(data_chunk)
            else:
                # No mipmaps or unsupported format
                remaining_data = f.read()
                if not remaining_data:
                    raise Exception('No texture data found in file')
                self.data = [remaining_data]
        
        return self
    
    def write(self, path):
        with open(path, 'wb') as f:
            f.write(struct.pack('<I', 0x00584554))  # "TEX\0"
            f.write(struct.pack('<HH', self.width, self.height))
            f.write(struct.pack('<BBB', 1, self.format, 0))
            f.write(struct.pack('<?', self.mipmaps))
            f.write(self.data[0])


# ============================================================================
# DXT Decompression
# ============================================================================

def decompress_dxt5_block(block_data, x, y, width, height, pixels):
    """Decompress a 4x4 DXT5 block"""
    if len(block_data) < 16:
        return
    
    # Alpha values
    alpha0, alpha1 = block_data[0], block_data[1]
    alpha_bits = int.from_bytes(block_data[2:8], 'little')
    
    # Calculate alpha palette
    alphas = [alpha0, alpha1]
    if alpha0 > alpha1:
        for i in range(1, 7):
            alphas.append(((7 - i) * alpha0 + i * alpha1) // 7)
    else:
        for i in range(1, 5):
            alphas.append(((5 - i) * alpha0 + i * alpha1) // 5)
        alphas.extend([0, 255])
    
    # Color values
    color0 = int.from_bytes(block_data[8:10], 'little')
    color1 = int.from_bytes(block_data[10:12], 'little')
    color_bits = int.from_bytes(block_data[12:16], 'little')
    
    # Convert 565 to RGB
    r0, g0, b0 = ((color0 >> 11) & 0x1F) << 3, ((color0 >> 5) & 0x3F) << 2, (color0 & 0x1F) << 3
    r1, g1, b1 = ((color1 >> 11) & 0x1F) << 3, ((color1 >> 5) & 0x3F) << 2, (color1 & 0x1F) << 3
    
    colors = [
        (r0, g0, b0),
        (r1, g1, b1),
        ((r0 * 2 + r1) // 3, (g0 * 2 + g1) // 3, (b0 * 2 + b1) // 3),
        ((r0 + r1 * 2) // 3, (g0 + g1 * 2) // 3, (b0 + b1 * 2) // 3)
    ]
    
    # Decode pixels
    for py in range(4):
        for px in range(4):
            if x + px < width and y + py < height:
                idx = py * 4 + px
                alpha_idx = (alpha_bits >> (idx * 3)) & 7
                color_idx = (color_bits >> (idx * 2)) & 3
                pixel_idx = ((y + py) * width + (x + px)) * 4
                r, g, b = colors[color_idx]
                a = alphas[alpha_idx]
                pixels[pixel_idx:pixel_idx+4] = [r, g, b, a]


def decompress_dxt1_block(block_data, x, y, width, height, pixels):
    """Decompress a 4x4 DXT1 block"""
    if len(block_data) < 8:
        return
    
    # Color values
    color0 = int.from_bytes(block_data[0:2], 'little')
    color1 = int.from_bytes(block_data[2:4], 'little')
    color_bits = int.from_bytes(block_data[4:8], 'little')
    
    # Convert 565 to RGB
    r0, g0, b0 = ((color0 >> 11) & 0x1F) << 3, ((color0 >> 5) & 0x3F) << 2, (color0 & 0x1F) << 3
    r1, g1, b1 = ((color1 >> 11) & 0x1F) << 3, ((color1 >> 5) & 0x3F) << 2, (color1 & 0x1F) << 3
    
    # Interpolate colors
    if color0 > color1:
        colors = [
            (r0, g0, b0, 255),
            (r1, g1, b1, 255),
            ((r0 * 2 + r1) // 3, (g0 * 2 + g1) // 3, (b0 * 2 + b1) // 3, 255),
            ((r0 + r1 * 2) // 3, (g0 + g1 * 2) // 3, (b0 + b1 * 2) // 3, 255)
        ]
    else:
        colors = [
            (r0, g0, b0, 255),
            (r1, g1, b1, 255),
            ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255),
            (0, 0, 0, 0)
        ]
    
    # Decode pixels
    for py in range(4):
        for px in range(4):
            if x + px < width and y + py < height:
                idx = py * 4 + px
                color_idx = (color_bits >> (idx * 2)) & 3
                pixel_idx = ((y + py) * width + (x + px)) * 4
                r, g, b, a = colors[color_idx]
                pixels[pixel_idx:pixel_idx+4] = [r, g, b, a]


def decompress_tex_to_rgba(tex):
    """Decompress .tex data to RGBA"""
    width, height = tex.width, tex.height
    pixels = bytearray(width * height * 4)
    
    # Use the largest mipmap (last in list) or the only data
    if tex.mipmaps and len(tex.data) > 0:
        data = tex.data[-1]
    else:
        data = tex.data[0]
    
    if tex.format == TEXFormat.BGRA8:
        # Uncompressed BGRA to RGBA
        for i in range(0, len(data), 4):
            if i + 3 < len(data):
                pixels[i] = data[i + 2]    # R
                pixels[i + 1] = data[i + 1]  # G
                pixels[i + 2] = data[i]      # B
                pixels[i + 3] = data[i + 3]  # A
    
    elif tex.format == TEXFormat.DXT1:
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        
        for by in range(block_height):
            for bx in range(block_width):
                block_idx = (by * block_width + bx) * 8
                if block_idx + 8 <= len(data):
                    decompress_dxt1_block(data[block_idx:block_idx + 8], 
                                         bx * 4, by * 4, width, height, pixels)
    
    elif tex.format == TEXFormat.DXT5:
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        
        for by in range(block_height):
            for bx in range(block_width):
                block_idx = (by * block_width + bx) * 16
                if block_idx + 16 <= len(data):
                    decompress_dxt5_block(data[block_idx:block_idx + 16], 
                                         bx * 4, by * 4, width, height, pixels)
    else:
        raise Exception(f'Unsupported texture format: {tex.format}')
    
    return bytes(pixels)


# ============================================================================
# GIMP Plugin
# ============================================================================

class TexPlugin(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return False
    
    def do_query_procedures(self):
        print("do_query_procedures called")
        sys.stdout.flush()
        return ['file-tex-load', 'file-tex-export']
    
    def do_create_procedure(self, name):
        print(f"do_create_procedure called for: {name}")
        sys.stdout.flush()
        procedure = None
        
        if name == 'file-tex-load':
            procedure = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.load_tex, None)
            procedure.set_menu_label("League of Legends TEX")
            procedure.set_documentation("Load .tex texture files", "Loads DXT1/DXT5/BGRA8 textures", name)
            procedure.set_extensions("tex")
            
        elif name == 'file-tex-export':
            procedure = Gimp.ExportProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, False, self.export_tex, None)
            procedure.set_menu_label("League of Legends TEX")
            procedure.set_documentation("Export as .tex texture", "Exports image as TEX file (BGRA8)", name)
            procedure.set_image_types("*")
            procedure.set_extensions("tex")
        
        if procedure:
            procedure.set_attribution("LtMAO Team", "LtMAO Team", "2024")
        
        return procedure
    
    def load_tex(self, procedure, run_mode, file, args, config, data, *extra):
        print("="*60)
        print("load_tex called")
        sys.stdout.flush()
        
        if not file:
            print("ERROR: No file provided")
            sys.stdout.flush()
            error = GLib.Error.new_literal(GLib.quark_from_string("gimp-plug-in-error"), 0, "No file provided")
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        
        try:
            path = file.get_path()
            print(f"Loading: {path}")
            
            # Read and decompress TEX
            print("Reading TEX file...")
            tex = TEX().read(path)
            print(f"TEX: {tex.width}x{tex.height}, format={tex.format}, mipmaps={tex.mipmaps}")
            
            print("Decompressing...")
            rgba = decompress_tex_to_rgba(tex)
            print(f"Decompressed: {len(rgba)} bytes")
            
            # Create GIMP image
            print("Creating GIMP image...")
            image = Gimp.Image.new(tex.width, tex.height, Gimp.ImageBaseType.RGB)
            image.set_file(file)
            print(f"Image created: ID={image.get_id()}")
            
            print("Creating layer...")
            layer = Gimp.Layer.new(image, "Background", tex.width, tex.height, 
                                  Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
            image.insert_layer(layer, None, 0)
            print("Layer inserted")
            
            # Write pixels
            print("Writing pixels...")
            buffer = layer.get_buffer()
            rect = Gegl.Rectangle()
            rect.x, rect.y, rect.width, rect.height = 0, 0, tex.width, tex.height
            buffer.set(rect, "R'G'B'A u8", rgba)
            buffer.flush()
            layer.update(0, 0, tex.width, tex.height)
            print("Pixels written")
            
            # Display image
            print("Creating display...")
            Gimp.Display.new(image)
            print("Display created")
            
            # Return SUCCESS with image
            print("Returning image...")
            sys.stdout.flush()
            
            # Create proper return values for LoadProcedure
            retval = Gimp.ValueArray.new(2)
            retval.insert(0, GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS))
            retval.insert(1, GObject.Value(Gimp.Image, image))
            
            print("Load successful!")
            print("="*60)
            sys.stdout.flush()
            return retval
            
        except Exception as e:
            print(f"ERROR in load_tex: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            error = GLib.Error.new_literal(GLib.quark_from_string("gimp-plug-in-error"), 0, str(e))
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, error)
    

    
    def export_tex(self, procedure, run_mode, image, file, args, config, data, *extra):
        print("="*60)
        print("export_tex called")
        sys.stdout.flush()
        
        if not file:
            print("ERROR: No file provided")
            sys.stdout.flush()
            error = GLib.Error.new_literal(GLib.quark_from_string("gimp-plug-in-error"), 0, "No file provided")
            return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
        
        try:
            path = file.get_path()
            print(f"Exporting to: {path}")
            
            # Duplicate image to avoid modifying the original
            print("Duplicating image...")
            export_image = image.duplicate()
            
            # Merge all visible layers
            print("Merging visible layers...")
            merged = export_image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
            w, h = merged.get_width(), merged.get_height()
            print(f"Image size: {w}x{h}")
            
            # Get pixels - buffer.get() signature: (rectangle, scale, format, flags)
            print("Getting pixels...")
            buffer = merged.get_buffer()
            rect = Gegl.Rectangle()
            rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
            
            # buffer.get() returns the pixel data directly
            pixel_data = buffer.get(rect, 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)
            print(f"Got {len(pixel_data)} bytes of pixel data")
            
            # Convert RGBA to BGRA for TEX format
            print("Converting RGBA to BGRA...")
            bgra = bytearray(len(pixel_data))
            for i in range(0, len(pixel_data), 4):
                bgra[i] = pixel_data[i + 2]      # B
                bgra[i + 1] = pixel_data[i + 1]  # G
                bgra[i + 2] = pixel_data[i]      # R
                bgra[i + 3] = pixel_data[i + 3]  # A
            
            # Write TEX file
            print("Writing TEX file...")
            tex = TEX()
            tex.width, tex.height = w, h
            tex.format = TEXFormat.BGRA8
            tex.mipmaps = False
            tex.data = [bytes(bgra)]
            tex.write(path)
            
            # Clean up duplicate image
            export_image.delete()
            
            print(f"Export successful: {path}")
            print("="*60)
            sys.stdout.flush()
            
            # Return success
            retval = Gimp.ValueArray.new(1)
            retval.insert(0, GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS))
            return retval
            
        except Exception as e:
            print(f"ERROR in export_tex: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            error = GLib.Error.new_literal(GLib.quark_from_string("gimp-plug-in-error"), 0, str(e))
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, error)


Gimp.main(TexPlugin.__gtype__, sys.argv)
