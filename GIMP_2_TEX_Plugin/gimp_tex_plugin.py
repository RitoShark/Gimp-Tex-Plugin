#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GIMP Plugin for League of Legends .tex files
This plugin allows GIMP to load and save .tex texture files directly.

Installation:
1. Copy this file to GIMP's plugin directory:
   Windows: %APPDATA%\GIMP\2.10\plug-ins\gimp_tex_plugin.py
   Linux: ~/.config/GIMP/2.10/plug-ins/gimp_tex_plugin.py
   macOS: ~/Library/Application Support/GIMP/2.10/plug-ins/gimp_tex_plugin.py

2. Make sure the file is executable (Linux/macOS): chmod +x gimp_tex_plugin.py

3. Delete %APPDATA%\GIMP\2.10\pluginrc (Windows) to force re-registration

4. Restart GIMP

This plugin is completely self-contained and does not require any external dependencies.
"""

from gimpfu import *
import os
import struct
import math
import sys
from io import BytesIO

# Note: Numba support removed - GIMP uses its own Python environment
# For fast compression, the Python code has been optimized

# Redirect stdout/stderr to files for debugging
try:
    log_file = os.path.join(os.path.expanduser('~'), 'gimp_tex_plugin.log')
    sys.stderr = open(log_file, 'a')
    sys.stdout = open(log_file, 'a')
    sys.stderr.write("\n" + "="*50 + "\n")
    sys.stderr.write("GIMP .tex plugin: Starting...\n")
    sys.stderr.write("Imports successful\n")
    sys.stderr.flush()
except Exception as e:
    try:
        import sys
        sys.stderr.write("Could not open log file: {}\n".format(str(e)))
    except:
        pass

# ============================================================================
# Embedded .tex format handling code (from LtMAO/pyRitoFile)
# ============================================================================

class BytesStream:
    """Binary stream reader/writer for .tex files"""
    @staticmethod
    def reader(path, raw=False):
        return BytesStream(BytesIO(path) if raw else open(path, 'rb'))
    
    @staticmethod
    def writer(path, raw=False):
        return BytesStream(BytesIO() if raw else open(path, 'wb'))
    
    def __init__(self, f):
        self.stream = f
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def close(self):
        self.stream.close()
    
    def read(self, length):
        return self.stream.read(length)
    
    def read_b(self, count=1):
        return struct.unpack('<{}?'.format(count), self.stream.read(count))
    
    def read_u8(self, count=1):
        return struct.unpack('<{}B'.format(count), self.stream.read(count))
    
    def read_u16(self, count=1):
        return struct.unpack('<{}H'.format(count), self.stream.read(count*2))
    
    def read_u32(self, count=1):
        return struct.unpack('<{}I'.format(count), self.stream.read(count*4))
    
    def write(self, values):
        self.stream.write(values)
    
    def write_b(self, *values):
        self.stream.write(struct.pack('<{}?'.format(len(values)), *values))
    
    def write_u8(self, *values):
        self.stream.write(struct.pack('<{}B'.format(len(values)), *values))
    
    def write_u16(self, *values):
        self.stream.write(struct.pack('<{}H'.format(len(values)), *values))
    
    def write_u32(self, *values):
        self.stream.write(struct.pack('<{}I'.format(len(values)), *values))


class TEXFormat:
    """Texture format enumeration"""
    ETC1 = 1
    ETC2_EAC = 2
    ETC2 = 3
    DXT1 = 10
    DXT5 = 12
    BGRA8 = 20


class TEX:
    """League of Legends .tex file handler"""
    def __init__(self):
        self.signature = None
        self.width = None
        self.height = None
        self.format = None
        self.unknown1 = None
        self.unknown2 = None
        self.mipmaps = False
        self.data = None
    
    def read(self, path):
        """Read a .tex file"""
        with BytesStream.reader(path) as bs:
            # Read header
            self.signature, = bs.read_u32()
            if self.signature != 0x00584554:  # "TEX\0"
                raise Exception('Invalid .tex file signature: {}'.format(hex(self.signature)))
            
            self.width, self.height = bs.read_u16(2)
            self.unknown1, format_val, self.unknown2 = bs.read_u8(3)
            self.format = format_val
            self.mipmaps, = bs.read_b()
            
            # Read texture data
            if self.mipmaps and self.format in (TEXFormat.DXT1, TEXFormat.DXT5, TEXFormat.BGRA8):
                # Calculate mipmap count
                mipmap_count = 32 - len('{:032b}'.format(max(self.width, self.height)).split('1', 1)[0])
                
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
                
                # Read all mipmaps
                self.data = []
                for i in reversed(range(mipmap_count)):
                    current_width = max(self.width // (1 << i), 1)
                    current_height = max(self.height // (1 << i), 1)
                    block_width = (current_width + block_size - 1) // block_size
                    block_height = (current_height + block_size - 1) // block_size
                    current_size = bytes_per_block * block_width * block_height
                    data_chunk = bs.read(current_size)
                    if not isinstance(data_chunk, str):
                        data_chunk = str(data_chunk)
                    self.data.append(data_chunk)
            else:
                # No mipmaps or unsupported format
                data_chunk = bs.read(-1)
                if not isinstance(data_chunk, str):
                    data_chunk = str(data_chunk)
                self.data = [data_chunk]
        
        return self
    
    def write(self, path):
        """Write a .tex file"""
        with BytesStream.writer(path) as bs:
            bs.write_u32(0x00584554)  # "TEX\0"
            bs.write_u16(self.width, self.height)
            bs.write_u8(1, self.format, 0)
            bs.write_b(self.mipmaps)
            
            if self.mipmaps and self.format in (TEXFormat.DXT1, TEXFormat.DXT5, TEXFormat.BGRA8):
                for block_data in self.data:
                    bs.write(block_data)
            else:
                bs.write(self.data[0])


# ============================================================================
# DDS to TEX Converter
# ============================================================================

def convert_dds_to_tex(dds_path, tex_path):
    """Convert a DDS file to TEX format by extracting the compressed data"""
    try:
        with open(dds_path, 'rb') as f:
            # Read DDS header
            magic = f.read(4)
            if magic != b'DDS ':
                raise Exception("Not a valid DDS file")
            
            # Read DDS_HEADER (124 bytes)
            header_size = struct.unpack('<I', f.read(4))[0]
            flags = struct.unpack('<I', f.read(4))[0]
            height = struct.unpack('<I', f.read(4))[0]
            width = struct.unpack('<I', f.read(4))[0]
            pitch_or_linear_size = struct.unpack('<I', f.read(4))[0]
            depth = struct.unpack('<I', f.read(4))[0]
            mipmap_count = struct.unpack('<I', f.read(4))[0]
            
            # Skip reserved (44 bytes)
            f.read(44)
            
            # Read DDS_PIXELFORMAT (32 bytes)
            pf_size = struct.unpack('<I', f.read(4))[0]
            pf_flags = struct.unpack('<I', f.read(4))[0]
            fourcc = f.read(4)
            
            sys.stderr.write("  DDS format info: fourcc={}, flags={:#x}\n".format(repr(fourcc), pf_flags))
            sys.stderr.flush()
            
            # Determine format
            # Check for DXT formats
            if fourcc == b'DXT1':
                tex_format = TEXFormat.DXT1
            elif fourcc == b'DXT5':
                tex_format = TEXFormat.DXT5
            # Check for DX10 header (modern DDS format)
            elif fourcc == b'DX10':
                # Skip rest of pixel format (20 bytes)
                f.read(20)
                # Skip caps (16 bytes) and reserved2 (4 bytes)
                f.read(20)
                # Read DX10 header
                dxgi_format = struct.unpack('<I', f.read(4))[0]
                sys.stderr.write("  DX10 format: DXGI_FORMAT={}\n".format(dxgi_format))
                # DXGI_FORMAT_BC3_UNORM = 77 (DXT5)
                # DXGI_FORMAT_BC1_UNORM = 71 (DXT1)
                if dxgi_format == 77:
                    tex_format = TEXFormat.DXT5
                elif dxgi_format == 71:
                    tex_format = TEXFormat.DXT1
                else:
                    raise Exception("Unsupported DXGI format: {}".format(dxgi_format))
                # Skip rest of DX10 header (12 bytes)
                f.read(12)
                # Read compressed texture data
                compressed_data = f.read()
            # No FourCC - check flags for uncompressed format
            elif pf_flags & 0x40:  # DDPF_RGB
                raise Exception("Uncompressed RGB format not supported, need DXT1/DXT5")
            else:
                raise Exception("Unsupported DDS format: fourcc={}, flags={:#x}".format(repr(fourcc), pf_flags))
            
            if fourcc != b'DX10':
                # Skip rest of pixel format (20 bytes)
                f.read(20)
                # Skip caps (16 bytes) and reserved2 (4 bytes)
                f.read(20)
                # Read compressed texture data
                compressed_data = f.read()
        
        # Create TEX file
        tex = TEX()
        tex.width = width
        tex.height = height
        tex.format = tex_format
        tex.mipmaps = False
        tex.data = [compressed_data]
        tex.write(tex_path)
        
        return True
    except Exception as e:
        sys.stderr.write("  DDS to TEX conversion error: {}\n".format(str(e)))
        return False


# ============================================================================
# Fast DXT5 Compression (using compiled DLL if available)
# ============================================================================

_dxt_dll = None
_has_fast_compression = False

def init_fast_compression():
    """Initialize fast DXT compression library"""
    global _dxt_dll, _has_fast_compression
    
    if _has_fast_compression:
        return True
    
    try:
        import ctypes
        # Look for the DLL in the same directory as this script
        dll_dir = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.join(dll_dir, 'dxt_compress.dll')
        
        if os.path.exists(dll_path):
            _dxt_dll = ctypes.CDLL(dll_path)
            
            # Define function signatures
            _dxt_dll.compress_dxt5.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),  # rgba input
                ctypes.c_int,                     # width
                ctypes.c_int,                     # height
                ctypes.POINTER(ctypes.c_ubyte)    # output
            ]
            _dxt_dll.compress_dxt5.restype = None
            
            _has_fast_compression = True
            sys.stderr.write("Fast DXT compression DLL loaded!\n")
            sys.stderr.flush()
            return True
    except Exception as e:
        sys.stderr.write("Fast compression DLL not available: {}\n".format(str(e)))
        sys.stderr.flush()
    
    return False


def fast_compress_dxt5(rgba_data, width, height):
    """Fast DXT5 compression using compiled DLL (10-100x faster)"""
    if not _has_fast_compression:
        if not init_fast_compression():
            return None
    
    try:
        import ctypes
        # Calculate output size
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        output_size = block_width * block_height * 16
        
        # Prepare input/output buffers
        if isinstance(rgba_data, str):
            input_buffer = (ctypes.c_ubyte * len(rgba_data))(*[ord(c) for c in rgba_data])
        else:
            input_buffer = (ctypes.c_ubyte * len(rgba_data))(*rgba_data)
        
        output_buffer = (ctypes.c_ubyte * output_size)()
        
        # Call the DLL function
        _dxt_dll.compress_dxt5(input_buffer, width, height, output_buffer)
        
        # Convert back to bytes
        result = bytes(bytearray(output_buffer))
        return result
        
    except Exception as e:
        sys.stderr.write("Fast compression failed: {}\n".format(str(e)))
        sys.stderr.flush()
        return None


def fast_decompress_dxt1(compressed_data, width, height):
    """Fast DXT1 decompression using compiled DLL (10-100x faster)"""
    if not _has_fast_compression:
        if not init_fast_compression():
            return None
    
    try:
        import ctypes
        # Setup decompression function signature if not already done
        if not hasattr(_dxt_dll, '_decompress_dxt1_setup'):
            _dxt_dll.decompress_dxt1.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),  # compressed input
                ctypes.c_int,                     # width
                ctypes.c_int,                     # height
                ctypes.POINTER(ctypes.c_ubyte)    # rgba output
            ]
            _dxt_dll.decompress_dxt1.restype = None
            _dxt_dll._decompress_dxt1_setup = True
        
        # Prepare input/output buffers
        if isinstance(compressed_data, str):
            input_buffer = (ctypes.c_ubyte * len(compressed_data))(*[ord(c) for c in compressed_data])
        else:
            input_buffer = (ctypes.c_ubyte * len(compressed_data))(*compressed_data)
        
        output_size = width * height * 4
        output_buffer = (ctypes.c_ubyte * output_size)()
        
        # Call the DLL function
        _dxt_dll.decompress_dxt1(input_buffer, width, height, output_buffer)
        
        # Convert back to bytes
        result = bytes(bytearray(output_buffer))
        return result
        
    except Exception as e:
        sys.stderr.write("Fast DXT1 decompression failed: {}\n".format(str(e)))
        sys.stderr.flush()
        return None


def fast_decompress_dxt5(compressed_data, width, height):
    """Fast DXT5 decompression using compiled DLL (10-100x faster)"""
    if not _has_fast_compression:
        if not init_fast_compression():
            return None
    
    try:
        import ctypes
        # Setup decompression function signature if not already done
        if not hasattr(_dxt_dll, '_decompress_dxt5_setup'):
            _dxt_dll.decompress_dxt5.argtypes = [
                ctypes.POINTER(ctypes.c_ubyte),  # compressed input
                ctypes.c_int,                     # width
                ctypes.c_int,                     # height
                ctypes.POINTER(ctypes.c_ubyte)    # rgba output
            ]
            _dxt_dll.decompress_dxt5.restype = None
            _dxt_dll._decompress_dxt5_setup = True
        
        # Prepare input/output buffers
        if isinstance(compressed_data, str):
            input_buffer = (ctypes.c_ubyte * len(compressed_data))(*[ord(c) for c in compressed_data])
        else:
            input_buffer = (ctypes.c_ubyte * len(compressed_data))(*compressed_data)
        
        output_size = width * height * 4
        output_buffer = (ctypes.c_ubyte * output_size)()
        
        # Call the DLL function
        _dxt_dll.decompress_dxt5(input_buffer, width, height, output_buffer)
        
        # Convert back to bytes
        result = bytes(bytearray(output_buffer))
        return result
        
    except Exception as e:
        sys.stderr.write("Fast DXT5 decompression failed: {}\n".format(str(e)))
        sys.stderr.flush()
        return None


# ============================================================================
# DXT1/DXT5 Decompression
# ============================================================================

def decompress_dxt1_block(block_data, x, y, width, height, pixels):
    """Decompress a 4x4 DXT1 block"""
    try:
        if not isinstance(block_data, str):
            block_data = str(block_data)
        
        if len(block_data) < 8:
            return
        
        color0 = struct.unpack('<H', block_data[0:2])[0]
        color1 = struct.unpack('<H', block_data[2:4])[0]
        bits = struct.unpack('<I', block_data[4:8])[0]
    except:
        return
    
    # Convert 565 RGB to 888 RGB
    r0 = ((color0 >> 11) & 0x1F) << 3
    g0 = ((color0 >> 5) & 0x3F) << 2
    b0 = (color0 & 0x1F) << 3
    
    r1 = ((color1 >> 11) & 0x1F) << 3
    g1 = ((color1 >> 5) & 0x3F) << 2
    b1 = (color1 & 0x1F) << 3
    
    # Interpolate colors
    colors = [
        (r0, g0, b0, 255),
        (r1, g1, b1, 255),
        ((r0 * 2 + r1) // 3, (g0 * 2 + g1) // 3, (b0 * 2 + b1) // 3, 255) if color0 > color1 else ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255),
        ((r0 + r1 * 2) // 3, (g0 + g1 * 2) // 3, (b0 + b1 * 2) // 3, 255) if color0 > color1 else (0, 0, 0, 0)
    ]
    
    # Decode pixels
    for py in range(4):
        for px in range(4):
            if x + px < width and y + py < height:
                idx = (py * 4 + px)
                color_idx = (bits >> (idx * 2)) & 3
                pixel_idx = ((y + py) * width + (x + px)) * 4
                pixels[pixel_idx:pixel_idx+4] = struct.pack('BBBB', *colors[color_idx])


def decompress_dxt5_block(block_data, x, y, width, height, pixels):
    """Decompress a 4x4 DXT5 block"""
    try:
        if not isinstance(block_data, str):
            block_data = str(block_data)
        
        if len(block_data) < 16:
            return
        
        # Read alpha values
        alpha0 = ord(block_data[0])
        alpha1 = ord(block_data[1])
        alpha_bits_bytes = block_data[2:8]
        if len(alpha_bits_bytes) < 6:
            return
        alpha_bits = 0
        for i in range(6):
            alpha_bits |= (ord(alpha_bits_bytes[i]) << (i * 8))
    except:
        return
    
    # Calculate alpha palette
    alphas = [alpha0, alpha1]
    if alpha0 > alpha1:
        for i in range(1, 7):
            alphas.append(((7 - i) * alpha0 + i * alpha1) // 7)
    else:
        for i in range(1, 5):
            alphas.append(((5 - i) * alpha0 + i * alpha1) // 5)
        alphas.extend([0, 255])
    
    # Read color endpoints
    color0_bytes = block_data[8:10]
    color1_bytes = block_data[10:12]
    color_bits_bytes = block_data[12:16]
    
    if len(color0_bytes) != 2 or len(color1_bytes) != 2 or len(color_bits_bytes) != 4:
        return
    
    color0 = struct.unpack('<H', color0_bytes)[0]
    color1 = struct.unpack('<H', color1_bytes)[0]
    color_bits = struct.unpack('<I', color_bits_bytes)[0]
    
    # Convert 565 RGB to 888 RGB
    r0 = ((color0 >> 11) & 0x1F) << 3
    g0 = ((color0 >> 5) & 0x3F) << 2
    b0 = (color0 & 0x1F) << 3
    
    r1 = ((color1 >> 11) & 0x1F) << 3
    g1 = ((color1 >> 5) & 0x3F) << 2
    b1 = (color1 & 0x1F) << 3
    
    # Interpolate colors
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
                pixels[pixel_idx:pixel_idx+4] = struct.pack('BBBB', r, g, b, a)


def decompress_tex_to_rgba(tex):
    """Decompress .tex data to RGBA pixel array"""
    width = tex.width
    height = tex.height
    
    # When mipmaps exist, data[0] is the smallest mipmap, data[-1] is the largest (full resolution)
    # When no mipmaps, data[0] is the only data
    if tex.mipmaps and len(tex.data) > 0:
        data = tex.data[-1]  # Use the last (largest) mipmap
    else:
        data = tex.data[0]  # Use the only data available
    if not isinstance(data, str):
        data = str(data)
    
    if tex.format == TEXFormat.BGRA8:
        # BGRA8 is uncompressed - just copy with byte swap
        pixels = bytearray(width * height * 4)
        for i in range(0, len(data), 4):
            if i + 3 < len(data):
                pixels[i] = ord(data[i + 2])  # R
                pixels[i + 1] = ord(data[i + 1])  # G
                pixels[i + 2] = ord(data[i])  # B
                pixels[i + 3] = ord(data[i + 3])  # A
        return bytes(pixels)
    
    elif tex.format == TEXFormat.DXT1:
        # Try fast decompression first
        fast_result = fast_decompress_dxt1(data, width, height)
        if fast_result:
            sys.stderr.write("Using FAST DLL decompression (DXT1)\n")
            sys.stderr.flush()
            return fast_result
        
        # Fallback to Python
        sys.stderr.write("Using Python decompression (DXT1)\n")
        sys.stderr.flush()
        pixels = bytearray(width * height * 4)
        block_size = 8
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        
        for by in range(block_height):
            for bx in range(block_width):
                block_idx = (by * block_width + bx) * block_size
                if block_idx + block_size <= len(data):
                    block_data = data[block_idx:block_idx + block_size]
                    if len(block_data) == block_size:
                        decompress_dxt1_block(block_data, bx * 4, by * 4, width, height, pixels)
        return bytes(pixels)
    
    elif tex.format == TEXFormat.DXT5:
        # Try fast decompression first
        fast_result = fast_decompress_dxt5(data, width, height)
        if fast_result:
            sys.stderr.write("Using FAST DLL decompression (DXT5)\n")
            sys.stderr.flush()
            return fast_result
        
        # Fallback to Python
        sys.stderr.write("Using Python decompression (DXT5)\n")
        sys.stderr.flush()
        pixels = bytearray(width * height * 4)
        block_size = 16
        block_width = (width + 3) // 4
        block_height = (height + 3) // 4
        
        for by in range(block_height):
            for bx in range(block_width):
                block_idx = (by * block_width + bx) * block_size
                if block_idx + block_size <= len(data):
                    block_data = data[block_idx:block_idx + block_size]
                    if len(block_data) == block_size:
                        decompress_dxt5_block(block_data, bx * 4, by * 4, width, height, pixels)
        return bytes(pixels)
    
    else:
        raise Exception('Unsupported texture format: {}'.format(tex.format))
    
    return bytes(bytearray(width * height * 4))


# ============================================================================
# DXT Compression (for saving)
# ============================================================================

def compress_rgba_to_bgra8(pixels, width, height):
    """Convert RGBA pixels to BGRA8 format"""
    data = bytearray(width * height * 4)
    for i in range(0, len(pixels), 4):
        if i + 3 < len(pixels):
            r = ord(pixels[i]) if isinstance(pixels[i], str) else pixels[i]
            g = ord(pixels[i + 1]) if isinstance(pixels[i + 1], str) else pixels[i + 1]
            b = ord(pixels[i + 2]) if isinstance(pixels[i + 2], str) else pixels[i + 2]
            a = ord(pixels[i + 3]) if isinstance(pixels[i + 3], str) else pixels[i + 3]
            data[i] = b
            data[i + 1] = g
            data[i + 2] = r
            data[i + 3] = a
    return str(data)


def rgb888_to_565(r, g, b):
    """Convert 8-bit RGB to 5-6-5 format"""
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def compress_dxt5_block(pixels, x, y, width, height):
    """Compress a 4x4 RGBA block to DXT5 format"""
    block_pixels = []
    alphas = []
    
    for py in range(4):
        for px in range(4):
            px_x = x + px
            px_y = y + py
            if px_x < width and px_y < height:
                idx = (px_y * width + px_x) * 4
                if idx + 3 < len(pixels):
                    r = ord(pixels[idx]) if isinstance(pixels[idx], str) else pixels[idx]
                    g = ord(pixels[idx+1]) if isinstance(pixels[idx+1], str) else pixels[idx+1]
                    b = ord(pixels[idx+2]) if isinstance(pixels[idx+2], str) else pixels[idx+2]
                    a = ord(pixels[idx+3]) if isinstance(pixels[idx+3], str) else pixels[idx+3]
                    block_pixels.append((r, g, b))
                    alphas.append(a)
            else:
                block_pixels.append((0, 0, 0))
                alphas.append(0)
    
    alpha0 = min(alphas)
    alpha1 = max(alphas)
    
    alpha_palette = [alpha0, alpha1]
    if alpha0 > alpha1:
        for i in range(1, 7):
            alpha_palette.append(((7 - i) * alpha0 + i * alpha1) // 7)
    else:
        for i in range(1, 5):
            alpha_palette.append(((5 - i) * alpha0 + i * alpha1) // 5)
        alpha_palette.extend([0, 255])
    
    alpha_bits = 0
    for i, alpha in enumerate(alphas):
        best_idx = 0
        best_diff = abs(alpha - alpha_palette[0])
        for idx, pal_alpha in enumerate(alpha_palette):
            diff = abs(alpha - pal_alpha)
            if diff < best_diff:
                best_diff = diff
                best_idx = idx
        alpha_bits |= (best_idx << (i * 3))
    
    colors = [block_pixels[i] for i in range(16)]
    color0_rgb = min(colors, key=lambda c: sum(c))
    color1_rgb = max(colors, key=lambda c: sum(c))
    
    color0 = rgb888_to_565(color0_rgb[0], color0_rgb[1], color0_rgb[2])
    color1 = rgb888_to_565(color1_rgb[0], color1_rgb[1], color1_rgb[2])
    
    r0 = ((color0 >> 11) & 0x1F) << 3
    g0 = ((color0 >> 5) & 0x3F) << 2
    b0 = (color0 & 0x1F) << 3
    r1 = ((color1 >> 11) & 0x1F) << 3
    g1 = ((color1 >> 5) & 0x3F) << 2
    b1 = (color1 & 0x1F) << 3
    
    color_palette = [
        (r0, g0, b0),
        (r1, g1, b1),
        ((r0 * 2 + r1) // 3, (g0 * 2 + g1) // 3, (b0 * 2 + b1) // 3),
        ((r0 + r1 * 2) // 3, (g0 + g1 * 2) // 3, (b0 + b1 * 2) // 3)
    ]
    
    color_bits = 0
    for i, (r, g, b) in enumerate(block_pixels):
        best_idx = 0
        best_diff = (r - color_palette[0][0])**2 + (g - color_palette[0][1])**2 + (b - color_palette[0][2])**2
        for idx, (pr, pg, pb) in enumerate(color_palette):
            diff = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
            if diff < best_diff:
                best_diff = diff
                best_idx = idx
        color_bits |= (best_idx << (i * 2))
    
    block = bytearray(16)
    block[0] = alpha0
    block[1] = alpha1
    for i in range(6):
        block[2 + i] = (alpha_bits >> (i * 8)) & 0xFF
    block[8] = color0 & 0xFF
    block[9] = (color0 >> 8) & 0xFF
    block[10] = color1 & 0xFF
    block[11] = (color1 >> 8) & 0xFF
    for i in range(4):
        block[12 + i] = (color_bits >> (i * 8)) & 0xFF
    
    return str(block)


def compress_rgba_to_dxt5(pixels, width, height):
    """Compress RGBA pixels to DXT5 format"""
    block_width = (width + 3) // 4
    block_height = (height + 3) // 4
    compressed_data = bytearray(block_width * block_height * 16)
    
    for by in range(block_height):
        for bx in range(block_width):
            block = compress_dxt5_block(pixels, bx * 4, by * 4, width, height)
            block_idx = (by * block_width + bx) * 16
            for i in range(16):
                compressed_data[block_idx + i] = ord(block[i]) if isinstance(block[i], str) else block[i]
    
    return str(compressed_data)


# ============================================================================
# GIMP Plugin Functions
# ============================================================================

def tex_load(filename, raw_filename):
    """Load a .tex file into GIMP"""
    try:
        sys.stderr.write("\n" + "="*60 + "\n")
        sys.stderr.write("tex_load called: {}\n".format(filename))
        sys.stderr.flush()
        
        # Verify signature
        with open(filename, 'rb') as f:
            header = f.read(4)
            if len(header) < 4:
                return None
            signature = struct.unpack('<I', header)[0]
            if signature != 0x00584554:  # "TEX\0"
                return None
        
        # Read .tex file
        tex = TEX()
        tex.read(filename)
        
        sys.stderr.write("TEX file info: {}x{}, format={}, mipmaps={}\n".format(
            tex.width, tex.height, tex.format, tex.mipmaps))
        sys.stderr.flush()
        
        # Decompress to RGBA
        rgba_data = decompress_tex_to_rgba(tex)
        
        sys.stderr.write("Decompressed {} bytes (expected: {}x{}x4={})\n".format(
            len(rgba_data), tex.width, tex.height, tex.width * tex.height * 4))
        sys.stderr.flush()
        
        # Check first few pixels
        if len(rgba_data) >= 16:
            sys.stderr.write("First 4 pixels (RGBA): ")
            for i in range(4):
                idx = i * 4
                if idx + 3 < len(rgba_data):
                    r = ord(rgba_data[idx]) if isinstance(rgba_data[idx], str) else rgba_data[idx]
                    g = ord(rgba_data[idx+1]) if isinstance(rgba_data[idx+1], str) else rgba_data[idx+1]
                    b = ord(rgba_data[idx+2]) if isinstance(rgba_data[idx+2], str) else rgba_data[idx+2]
                    a = ord(rgba_data[idx+3]) if isinstance(rgba_data[idx+3], str) else rgba_data[idx+3]
                    sys.stderr.write("({},{},{},{}) ".format(r, g, b, a))
            sys.stderr.write("\n")
            sys.stderr.flush()
        
        # Create GIMP image - use RGB mode (GIMP will handle alpha in the layer)
        image = gimp.Image(tex.width, tex.height, RGB)
        image.filename = filename
        
        # Create layer with alpha channel
        layer = gimp.Layer(image, "Background", tex.width, tex.height, RGBA_IMAGE, 100, NORMAL_MODE)
        image.add_layer(layer, 0)
        
        # Set as active layer
        pdb.gimp_image_set_active_layer(image, layer)
        
        # Set pixel data using pixel region
        # Get writable pixel region
        pr = layer.get_pixel_rgn(0, 0, tex.width, tex.height, True, True)
        
        # Convert to string if needed (Python 2.7 compatibility)
        if isinstance(rgba_data, bytearray):
            rgba_data = str(rgba_data)
        elif not isinstance(rgba_data, str):
            rgba_data = str(rgba_data)
        
        # Ensure we have the right amount of data
        expected_size = tex.width * tex.height * 4
        if len(rgba_data) < expected_size:
            sys.stderr.write("WARNING: Not enough pixel data! Got {}, expected {}\n".format(
                len(rgba_data), expected_size))
            sys.stderr.flush()
            # Pad with transparent pixels
            rgba_data += '\x00' * (expected_size - len(rgba_data))
        elif len(rgba_data) > expected_size:
            rgba_data = rgba_data[:expected_size]
        
        # Write entire image at once to pixel region
        # The pixel region expects data in row-major order: RGBA bytes for each pixel, row by row
        # Format: [R,G,B,A, R,G,B,A, ...] for all pixels from top-left to bottom-right
        sys.stderr.write("Writing {} bytes to pixel region ({}x{} pixels)\n".format(
            len(rgba_data), tex.width, tex.height))
        sys.stderr.flush()
        
        pr[0:tex.width, 0:tex.height] = rgba_data
        
        sys.stderr.write("Pixel region write complete, flushing...\n")
        sys.stderr.flush()
        
        # Flush and update the layer
        layer.flush()
        layer.merge_shadow(True)
        layer.update(0, 0, tex.width, tex.height)
        
        sys.stderr.write("Layer update complete\n")
        sys.stderr.flush()
        
        # Verify the data was written correctly by reading it back
        pr_read = layer.get_pixel_rgn(0, 0, tex.width, tex.height, False, False)
        read_back = pr_read[0:tex.width, 0:1]  # Read first row
        if len(read_back) >= 16:
            sys.stderr.write("First row read back (RGBA): ")
            for i in range(4):
                idx = i * 4
                if idx + 3 < len(read_back):
                    r = ord(read_back[idx]) if isinstance(read_back[idx], str) else read_back[idx]
                    g = ord(read_back[idx+1]) if isinstance(read_back[idx+1], str) else read_back[idx+1]
                    b = ord(read_back[idx+2]) if isinstance(read_back[idx+2], str) else read_back[idx+2]
                    a = ord(read_back[idx+3]) if isinstance(read_back[idx+3], str) else read_back[idx+3]
                    sys.stderr.write("({},{},{},{}) ".format(r, g, b, a))
            sys.stderr.write("\n")
            sys.stderr.flush()
        
        sys.stderr.write("Load successful! Image: {}x{}\n".format(tex.width, tex.height))
        sys.stderr.flush()
        
        return image
        
    except Exception as e:
        sys.stderr.write("Error: {}\n".format(str(e)))
        import traceback
        sys.stderr.write(traceback.format_exc())
        sys.stderr.flush()
        raise


def tex_save(image, drawable, filename, raw_filename):
    """Save a GIMP image as a .tex file (via DDS for large images)"""
    try:
        sys.stderr.write("tex_save: {}\n".format(filename))
        sys.stderr.flush()
        
        # Ensure RGBA
        if drawable.is_rgb:
            if not drawable.has_alpha:
                drawable = pdb.gimp_layer_add_alpha(drawable)
        else:
            pdb.gimp_image_convert_rgb(image)
            drawable = pdb.gimp_image_get_active_drawable(image)
            if not drawable.has_alpha:
                drawable = pdb.gimp_layer_add_alpha(drawable)
        
        width = drawable.width
        height = drawable.height
        
        # Always use fast compression for all image sizes
        use_dds_method = False
        
        if False and use_dds_method:
            sys.stderr.write("Image size: {}x{} - Using FAST DDS method\n".format(width, height))
            sys.stderr.flush()
            
            # FAST METHOD: Export as DDS, convert to TEX, delete temp DDS
            import tempfile
            
            # Create temp DDS file
            temp_dds = tempfile.mktemp(suffix='.dds')
            sys.stderr.write("Step 1: Exporting to DDS using GIMP native plugin...\n")
            sys.stderr.flush()
            
            try:
                # Try to use GIMP's DDS plugin with DXT5 compression
                # Different GIMP versions have different procedure names
                dds_saved = False
                
                # Try method 1: file-dds-save (GIMP 2.10)
                try:
                    pdb.file_dds_save(
                        image, drawable, temp_dds, temp_dds,
                        1,  # compression: 0=None, 1=DXT1, 2=DXT3, 3=DXT5, 4=RXGB
                        1,  # mipmaps: 0=No mipmaps, 1=Generate mipmaps
                        0,  # savetype: 0=selected layer
                        0,  # format: 0=default
                        -1, # transparent_index
                        0,  # mipmap_filter
                        0,  # mipmap_wrap
                        0   # gamma_correct
                    )
                    dds_saved = True
                    sys.stderr.write("  DDS export complete (file-dds-save)!\n")
                except Exception as e1:
                    sys.stderr.write("  file-dds-save failed: {}\n".format(str(e1)))
                    
                    # Try method 2: Shorter parameter list
                    try:
                        pdb.file_dds_save(
                            image, drawable, temp_dds, temp_dds,
                            3,  # compression: 3=DXT5
                            0   # mipmaps: 0=no mipmaps
                        )
                        dds_saved = True
                        sys.stderr.write("  DDS export complete (6 params)!\n")
                    except Exception as e2:
                        sys.stderr.write("  6-param failed: {}\n".format(str(e2)))
                        
                        # Try method 3: Use gimp_file_save and hope for the best
                        try:
                            pdb.gimp_file_save(image, drawable, temp_dds, temp_dds)
                            dds_saved = True
                            sys.stderr.write("  DDS export complete (gimp_file_save)!\n")
                        except Exception as e3:
                            sys.stderr.write("  gimp_file_save failed: {}\n".format(str(e3)))
                
                if not dds_saved:
                    raise Exception("All DDS save methods failed")
                    
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write("  DDS export failed: {}\n".format(str(e)))
                sys.stderr.write("  Falling back to Python compression...\n")
                sys.stderr.flush()
                use_dds_method = False
            
            if use_dds_method:
                # Step 2: Convert DDS to TEX
                sys.stderr.write("Step 2: Converting DDS to TEX...\n")
                sys.stderr.flush()
                
                if convert_dds_to_tex(temp_dds, filename):
                    sys.stderr.write("  Conversion complete!\n")
                    sys.stderr.write("Save successful (FAST DDS method)!\n")
                    sys.stderr.flush()
                    
                    # Clean up temp DDS file
                    try:
                        if os.path.exists(temp_dds):
                            os.remove(temp_dds)
                            sys.stderr.write("  Temp DDS file deleted\n")
                    except Exception as e:
                        sys.stderr.write("  Warning: Could not delete temp DDS: {}\n".format(str(e)))
                    
                    sys.stderr.flush()
                    return
                else:
                    sys.stderr.write("  Conversion failed, falling back to Python compression...\n")
                    sys.stderr.flush()
                    use_dds_method = False
                    # Clean up temp file on error
                    try:
                        if os.path.exists(temp_dds):
                            os.remove(temp_dds)
                    except:
                        pass
        
        # DXT5 COMPRESSION - Always use fast compression
        if not use_dds_method:
            # Get pixel data (optimized)
            pr = drawable.get_pixel_rgn(0, 0, width, height, False, False)
            pixel_data = pr[0:width, 0:height]
            
            # Fast conversion to bytearray
            if isinstance(pixel_data, str):
                # Python 2 style string
                rgba_data = bytearray([ord(c) for c in pixel_data])
            else:
                # Already bytes
                rgba_data = bytearray(pixel_data)
            
            # Ensure we have the right amount of data
            expected_size = width * height * 4
            if len(rgba_data) < expected_size:
                # Pad with zeros if needed
                rgba_data.extend([0] * (expected_size - len(rgba_data)))
            
            # Try fast compression first (DLL)
            compressed_data = fast_compress_dxt5(rgba_data, width, height)
            
            if compressed_data:
                sys.stderr.write("Image {}x{} - FAST DLL compression\n".format(width, height))
                sys.stderr.flush()
            else:
                sys.stderr.write("Image {}x{} - Python compression (DLL not available)\n".format(width, height))
                sys.stderr.flush()
                compressed_data = compress_rgba_to_dxt5(str(rgba_data), width, height)
            
            # Create .tex file
            tex = TEX()
            tex.width = width
            tex.height = height
            tex.format = TEXFormat.DXT5
            tex.mipmaps = False
            tex.data = [compressed_data]
            tex.write(filename)
            sys.stderr.write("Save complete!\n")
            sys.stderr.flush()
        
        sys.stderr.write("Save complete!\n")
        sys.stderr.flush()
        
    except Exception as e:
        sys.stderr.write("Error: {}\n".format(str(e)))
        import traceback
        sys.stderr.write(traceback.format_exc())
        sys.stderr.flush()
        raise


def load_tex_file():
    """Manual load dialog"""
    try:
        import gtk
        dialog = gtk.FileChooserDialog(
            title="Open League of Legends .tex file",
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                     gtk.STOCK_OPEN, gtk.RESPONSE_OK)
        )
        
        filter_tex = gtk.FileFilter()
        filter_tex.set_name("League of Legends .tex files")
        filter_tex.add_pattern("*.tex")
        dialog.add_filter(filter_tex)
        
        filter_all = gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        
        if response == gtk.RESPONSE_OK and filename:
            image = tex_load(filename, filename)
            if image:
                gimp.Display(image)
                gimp.displays_flush()
    except Exception as e:
        pdb.gimp_message("Error: {}".format(str(e)))


def save_tex_file(image, drawable, *args):
    """Manual save dialog"""
    try:
        import gtk
        dialog = gtk.FileChooserDialog(
            title="Save as League of Legends .tex file",
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                     gtk.STOCK_SAVE, gtk.RESPONSE_OK)
        )
        
        filter_tex = gtk.FileFilter()
        filter_tex.set_name("League of Legends .tex files")
        filter_tex.add_pattern("*.tex")
        dialog.add_filter(filter_tex)
        
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        
        if response == gtk.RESPONSE_OK and filename:
            if not filename.lower().endswith('.tex'):
                filename += '.tex'
            tex_save(image, drawable, filename, filename)
            pdb.gimp_message("Saved: {}".format(filename))
    except Exception as e:
        pdb.gimp_message("Error: {}".format(str(e)))


# ============================================================================
# Registration - THIS IS THE KEY PART
# ============================================================================

def register_handlers():
    """Register file handlers after procedures are registered"""
    sys.stderr.write("Registering file handlers...\n")
    sys.stderr.flush()
    try:
        gimp.register_load_handler("file-tex-load", "tex", "")
        gimp.register_save_handler("file-tex-save", "tex", "")
        sys.stderr.write("Handlers registered successfully!\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write("Handler registration error: {}\n".format(str(e)))
        sys.stderr.flush()


# Register procedures
register(
    "file-tex-load",
    "Load League of Legends .tex texture file",
    "Loads .tex files with DXT1, DXT5, and BGRA8 support",
    "LtMAO Team",
    "LtMAO Team",
    "2024",
    "TEX texture",
    None,
    [
        (PF_STRING, "filename", "The name of the file to load", None),
        (PF_STRING, "raw-filename", "The name entered", None),
    ],
    [(PF_IMAGE, "image", "Output image")],
    tex_load,
    on_query=register_handlers,
    menu="<Load>"
)

register(
    "file-tex-save",
    "Save as League of Legends .tex texture file",
    "Saves images as .tex files (DXT5 format)",
    "LtMAO Team",
    "LtMAO Team",
    "2024",
    "TEX texture",
    "RGB*, GRAY*, RGBA*",
    [
        (PF_IMAGE, "image", "Input image", None),
        (PF_DRAWABLE, "drawable", "Input drawable", None),
        (PF_STRING, "filename", "The name of the file", None),
        (PF_STRING, "raw-filename", "The name entered", None),
    ],
    [],
    tex_save,
    menu="<Save>"
)

register(
    "python-fu-load-tex",
    "Open .tex File",
    "Open a League of Legends .tex texture file",
    "LtMAO Team",
    "LtMAO Team",
    "2024",
    "<Toolbox>/File/Open .tex File",
    "",
    [],
    [],
    load_tex_file
)

register(
    "python-fu-save-tex",
    "Save as .tex File",
    "Save the current image as a League of Legends .tex texture file",
    "LtMAO Team",
    "LtMAO Team",
    "2024",
    "<Image>/File/Save as .tex File",
    "RGB*, GRAY*, RGBA*",
    [],
    [],
    save_tex_file
)

sys.stderr.write("About to call main()...\n")
sys.stderr.flush()

main()

sys.stderr.write("Plugin loaded successfully!\n")
sys.stderr.flush()