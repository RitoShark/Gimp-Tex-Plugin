# -*- coding: utf-8 -*-
"""
tex_core.py - League of Legends TEX format handler

Handles TEX file reading/writing, DDS header conversion for GIMP's native
DDS loader, mipmap generation with Lanczos3 resampling, and BGRA8 conversion.

TEX Header (12 bytes):
  Offset 0:  uint32  signature   0x00584554 ("TEX\0")
  Offset 4:  uint16  width
  Offset 6:  uint16  height
  Offset 8:  uint8   unknown1    (always 1)
  Offset 9:  uint8   format      (10=DXT1, 12=DXT5, 20=BGRA8)
  Offset 10: uint8   unknown2    (always 0)
  Offset 11: uint8   mipmaps     (0 or 1)
  Offset 12: ...     data

Mipmaps are stored smallest-to-largest in TEX, largest-to-smallest in DDS.
"""

import struct
import math
import os
import tempfile

TEX_SIGNATURE = 0x00584554

# TEX format constants
FMT_DXT1 = 10
FMT_DXT5 = 12
FMT_BC7 = 13
FMT_BC5 = 14
FMT_BGRA8 = 20

# Block properties per format: (block_size, bytes_per_block)
BLOCK_INFO = {
    FMT_DXT1: (4, 8),
    FMT_DXT5: (4, 16),
    FMT_BC7: (4, 16),
    FMT_BC5: (4, 16),
    FMT_BGRA8: (1, 4),
}

# Block-compressed formats (require dimensions divisible by 4 + a compressor).
BLOCK_FORMATS = (FMT_DXT1, FMT_DXT5, FMT_BC7, FMT_BC5)

# DDS constants
DDS_MAGIC = 0x20534444  # "DDS "
DDS_HEADER_SIZE = 124
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_MIPMAPCOUNT = 0x20000
DDSD_LINEARSIZE = 0x80000
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_COMPLEX = 0x8
DDSCAPS_MIPMAP = 0x400000
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_ALPHAPIXELS = 0x1


class TexFile:
    """Represents a League of Legends .tex texture file."""

    __slots__ = ('width', 'height', 'format', 'mipmaps', 'data')

    def __init__(self, width=0, height=0, fmt=FMT_DXT5, mipmaps=False, data=b''):
        self.width = width
        self.height = height
        self.format = fmt
        self.mipmaps = mipmaps
        self.data = data  # raw compressed/uncompressed data (single blob)

    @staticmethod
    def read(path):
        """Read a TEX file from disk. Returns a TexFile instance."""
        with open(path, 'rb') as f:
            raw = f.read()
        return TexFile.from_bytes(raw, path)

    @staticmethod
    def from_bytes(raw, path='<memory>'):
        """Parse TEX from a bytes object."""
        if len(raw) < 12:
            raise ValueError('TEX file too small: {} bytes'.format(len(raw)))

        sig, width, height, unk1, fmt, unk2, mips = struct.unpack_from('<IHHBBBB', raw, 0)
        if sig != TEX_SIGNATURE:
            raise ValueError('Invalid TEX signature in {}: 0x{:08X}'.format(path, sig))
        if fmt not in BLOCK_INFO:
            raise ValueError('Unsupported TEX format: {}'.format(fmt))

        tex = TexFile(width, height, fmt, bool(mips))
        tex.data = raw[12:]
        return tex

    def write(self, path):
        """Write TEX file to disk."""
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    def to_bytes(self):
        """Serialize to TEX bytes."""
        header = struct.pack('<IHHBBBB',
                             TEX_SIGNATURE,
                             self.width, self.height,
                             1, self.format, 0,
                             1 if self.mipmaps else 0)
        return header + self.data

    def mipmap_count(self):
        """Calculate the number of mipmap levels for this texture."""
        if not self.mipmaps:
            return 1
        max_dim = max(self.width, self.height)
        if max_dim == 0:
            return 1
        return max_dim.bit_length()

    def mip_data_sizes(self):
        """Return list of (width, height, byte_size) for each mip level, largest first."""
        block_size, bpb = BLOCK_INFO[self.format]
        count = self.mipmap_count()
        levels = []
        for i in range(count):
            w = max(self.width >> i, 1)
            h = max(self.height >> i, 1)
            bw = (w + block_size - 1) // block_size
            bh = (h + block_size - 1) // block_size
            levels.append((w, h, bw * bh * bpb))
        return levels

    def get_largest_mip_data(self):
        """Extract the largest mipmap level data from the raw data blob.
        TEX stores mipmaps smallest-to-largest, so the largest is at the end."""
        if not self.mipmaps:
            return self.data

        levels = self.mip_data_sizes()  # largest first
        # Data is stored smallest-to-largest in the file,
        # so we need to skip past all smaller mips
        offset = 0
        for i in range(len(levels) - 1, 0, -1):
            offset += levels[i][2]

        largest_size = levels[0][2]
        return self.data[offset:offset + largest_size]

    def decompress_to_rgba(self):
        """Decompress texture data to RGBA bytes. Tries native C, falls back to Python."""
        data = self.get_largest_mip_data()
        w, h = self.width, self.height

        # Try native C decompression first (fast)
        try:
            from dxt_compress import native_decompress
            result = native_decompress(data, w, h, self.format)
            if result is not None:
                return result
        except Exception:
            pass

        # Pure Python fallback
        if self.format == FMT_BGRA8:
            rgba = bytearray(w * h * 4)
            for i in range(0, len(data) - 3, 4):
                rgba[i] = data[i + 2]      # R
                rgba[i + 1] = data[i + 1]  # G
                rgba[i + 2] = data[i]      # B
                rgba[i + 3] = data[i + 3]  # A
            return bytes(rgba)

        elif self.format == FMT_DXT1:
            return _decompress_dxt1(data, w, h)

        elif self.format == FMT_DXT5:
            return _decompress_dxt5(data, w, h)

        elif self.format == FMT_BC5:
            return _decompress_bc5(data, w, h)

        elif self.format == FMT_BC7:
            # BC7 decoding has no pure-Python fallback (too complex/slow); the
            # native DLL is required. native_decompress above handles it.
            raise ValueError(
                'BC7 decoding requires the native library (libdxtcompress). '
                'It was not found or failed to load.')

        else:
            raise ValueError('Cannot decompress format {}'.format(self.format))


def _decompress_dxt1(data, width, height):
    """Decompress DXT1/BC1 data to RGBA."""
    rgba = bytearray(width * height * 4)
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4

    for by in range(block_h):
        for bx in range(block_w):
            off = (by * block_w + bx) * 8
            if off + 8 > len(data):
                break

            c0 = data[off] | (data[off + 1] << 8)
            c1 = data[off + 2] | (data[off + 3] << 8)
            bits = data[off + 4] | (data[off + 5] << 8) | (data[off + 6] << 16) | (data[off + 7] << 24)

            # Decode RGB565
            r0 = ((c0 >> 11) & 0x1F); r0 = (r0 << 3) | (r0 >> 2)
            g0 = ((c0 >> 5) & 0x3F);  g0 = (g0 << 2) | (g0 >> 4)
            b0 = (c0 & 0x1F);         b0 = (b0 << 3) | (b0 >> 2)
            r1 = ((c1 >> 11) & 0x1F); r1 = (r1 << 3) | (r1 >> 2)
            g1 = ((c1 >> 5) & 0x3F);  g1 = (g1 << 2) | (g1 >> 4)
            b1 = (c1 & 0x1F);         b1 = (b1 << 3) | (b1 >> 2)

            colors = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
            if c0 > c1:
                colors.append(((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3, 255))
                colors.append(((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3, 255))
            else:
                colors.append(((r0+r1)//2, (g0+g1)//2, (b0+b1)//2, 255))
                colors.append((0, 0, 0, 0))

            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < width and y < height:
                        idx = (bits >> ((py * 4 + px) * 2)) & 3
                        pi = (y * width + x) * 4
                        c = colors[idx]
                        rgba[pi] = c[0]; rgba[pi+1] = c[1]
                        rgba[pi+2] = c[2]; rgba[pi+3] = c[3]

    return bytes(rgba)


def _decompress_dxt5(data, width, height):
    """Decompress DXT5/BC3 data to RGBA."""
    rgba = bytearray(width * height * 4)
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4

    for by in range(block_h):
        for bx in range(block_w):
            off = (by * block_w + bx) * 16
            if off + 16 > len(data):
                break

            # Alpha block
            a0 = data[off]; a1 = data[off + 1]
            abits = 0
            for i in range(6):
                abits |= data[off + 2 + i] << (i * 8)

            alphas = [a0, a1]
            if a0 > a1:
                for i in range(1, 7):
                    alphas.append(((7 - i) * a0 + i * a1) // 7)
            else:
                for i in range(1, 5):
                    alphas.append(((5 - i) * a0 + i * a1) // 5)
                alphas.append(0)
                alphas.append(255)

            # Color block
            c0 = data[off + 8] | (data[off + 9] << 8)
            c1 = data[off + 10] | (data[off + 11] << 8)
            bits = data[off + 12] | (data[off + 13] << 8) | (data[off + 14] << 16) | (data[off + 15] << 24)

            r0 = ((c0 >> 11) & 0x1F); r0 = (r0 << 3) | (r0 >> 2)
            g0 = ((c0 >> 5) & 0x3F);  g0 = (g0 << 2) | (g0 >> 4)
            b0 = (c0 & 0x1F);         b0 = (b0 << 3) | (b0 >> 2)
            r1 = ((c1 >> 11) & 0x1F); r1 = (r1 << 3) | (r1 >> 2)
            g1 = ((c1 >> 5) & 0x3F);  g1 = (g1 << 2) | (g1 >> 4)
            b1 = (c1 & 0x1F);         b1 = (b1 << 3) | (b1 >> 2)

            colors = [(r0, g0, b0), (r1, g1, b1),
                      ((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3),
                      ((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3)]

            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < width and y < height:
                        pidx = py * 4 + px
                        ci = (bits >> (pidx * 2)) & 3
                        ai = (abits >> (pidx * 3)) & 7
                        pi = (y * width + x) * 4
                        c = colors[ci]
                        rgba[pi] = c[0]; rgba[pi+1] = c[1]
                        rgba[pi+2] = c[2]; rgba[pi+3] = alphas[ai]

    return bytes(rgba)


def _decode_bc4_block(data, off):
    """Decode one 8-byte BC4 block into a list of 16 channel values."""
    e0, e1 = data[off], data[off + 1]
    vals = [e0, e1]
    if e0 > e1:
        for i in range(1, 7):
            vals.append(((7 - i) * e0 + i * e1) // 7)
    else:
        for i in range(1, 5):
            vals.append(((5 - i) * e0 + i * e1) // 5)
        vals.append(0)
        vals.append(255)
    bits = 0
    for i in range(6):
        bits |= data[off + 2 + i] << (i * 8)
    return [vals[(bits >> (i * 3)) & 0x7] for i in range(16)]


def _decompress_bc5(data, width, height):
    """Decompress BC5 (two BC4 blocks: R, G) to RGBA. Reconstructs the blue
    channel as the normal-map Z = sqrt(1 - x^2 - y^2); alpha forced opaque."""
    rgba = bytearray(width * height * 4)
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4
    for by in range(block_h):
        for bx in range(block_w):
            off = (by * block_w + bx) * 16
            if off + 16 > len(data):
                break
            red = _decode_bc4_block(data, off)
            green = _decode_bc4_block(data, off + 8)
            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < width and y < height:
                        idx = py * 4 + px
                        r = red[idx]
                        g = green[idx]
                        nx = r / 255.0 * 2.0 - 1.0
                        ny = g / 255.0 * 2.0 - 1.0
                        nz2 = 1.0 - nx * nx - ny * ny
                        nz = math.sqrt(nz2) if nz2 > 0 else 0.0
                        b = int((nz * 0.5 + 0.5) * 255.0 + 0.5)
                        b = 0 if b < 0 else (255 if b > 255 else b)
                        pi = (y * width + x) * 4
                        rgba[pi] = r
                        rgba[pi + 1] = g
                        rgba[pi + 2] = b
                        rgba[pi + 3] = 255
    return bytes(rgba)


def tex_to_dds_bytes(tex):
    """Convert a TexFile to DDS file bytes for GIMP's native DDS loader.
    Reverses mipmap order (TEX: small-to-large -> DDS: large-to-small)."""

    mip_count = tex.mipmap_count()
    levels = tex.mip_data_sizes()  # largest first

    # Build DDS pixel format
    if tex.format == FMT_DXT1:
        pf_flags = DDPF_FOURCC
        fourcc = b'DXT1'
        pf_rgb_bits = 0
        pf_rmask = pf_gmask = pf_bmask = pf_amask = 0
    elif tex.format == FMT_DXT5:
        pf_flags = DDPF_FOURCC
        fourcc = b'DXT5'
        pf_rgb_bits = 0
        pf_rmask = pf_gmask = pf_bmask = pf_amask = 0
    elif tex.format == FMT_BGRA8:
        pf_flags = DDPF_RGB | DDPF_ALPHAPIXELS
        fourcc = b'\x00\x00\x00\x00'
        pf_rgb_bits = 32
        pf_rmask = 0x00FF0000
        pf_gmask = 0x0000FF00
        pf_bmask = 0x000000FF
        pf_amask = 0xFF000000
    else:
        raise ValueError('Cannot convert TEX format {} to DDS'.format(tex.format))

    # DDS header flags (matches Aventurine's DDS_HEADER_FLAGS_TEXTURE = 0x1007)
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    caps = DDSCAPS_TEXTURE
    if tex.mipmaps and mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP

    # dwPitchOrLinearSize
    if tex.format in (FMT_DXT1, FMT_DXT5):
        flags |= DDSD_LINEARSIZE
        block_size, bpb = BLOCK_INFO[tex.format]
        pitch_or_linear_size = ((tex.width + 3) // 4) * ((tex.height + 3) // 4) * bpb
    else:
        pitch_or_linear_size = tex.width * 4

    # Pixel format struct (32 bytes)
    pixel_format = struct.pack('<II4sIIIII',
                               32,  # dwSize
                               pf_flags,
                               fourcc,
                               pf_rgb_bits,
                               pf_rmask, pf_gmask, pf_bmask, pf_amask)

    # DDS header (124 bytes total):
    #   7 uint32 fields (28) + dwReserved1[11] (44) = 72
    #   + pixel format (32) = 104
    #   + dwCaps..dwCaps4 (16) + dwReserved2 (4) = 124
    header = struct.pack('<IIIIIII44s',
                         DDS_HEADER_SIZE,       # dwSize = 124
                         flags,                 # dwFlags
                         tex.height,            # dwHeight
                         tex.width,             # dwWidth
                         pitch_or_linear_size,  # dwPitchOrLinearSize
                         0,                     # dwDepth
                         mip_count if tex.mipmaps else 0,  # dwMipMapCount
                         b'\x00' * 44)          # dwReserved1[11]

    header += pixel_format                      # ddspf (32 bytes)
    header += struct.pack('<IIIII',
                          caps,                 # dwCaps
                          0, 0, 0,              # dwCaps2, dwCaps3, dwCaps4
                          0)                    # dwReserved2

    assert len(header) == 124, 'DDS header is {} bytes, expected 124'.format(len(header))

    # Magic (4 bytes) + header (124 bytes) = 128 bytes total
    out = struct.pack('<I', DDS_MAGIC) + header

    # Reverse mipmap data: TEX stores small-to-large, DDS needs large-to-small
    if tex.mipmaps and mip_count > 1:
        # Split TEX data into mip chunks (stored small-to-large)
        tex_chunks = []
        offset = 0
        for i in range(len(levels) - 1, -1, -1):
            size = levels[i][2]
            tex_chunks.append(tex.data[offset:offset + size])
            offset += size

        # tex_chunks is now small-to-large, reverse for DDS (large-to-small)
        for chunk in reversed(tex_chunks):
            out += chunk
    else:
        out += tex.data

    return out


def tex_to_temp_dds(tex):
    """Convert TEX to a temporary DDS file on disk. Returns the temp file path.
    Caller is responsible for deleting the file."""
    dds_bytes = tex_to_dds_bytes(tex)
    fd, path = tempfile.mkstemp(suffix='.dds')
    try:
        os.write(fd, dds_bytes)
    finally:
        os.close(fd)
    return path


def rgba_to_tex_data(rgba, width, height, fmt, mipmaps=False, compressor=None):
    """Convert RGBA pixel data to TEX file data (header + compressed payload).

    Args:
        rgba: bytes, RGBA pixel data (width * height * 4 bytes)
        width: image width
        height: image height
        fmt: FMT_DXT1, FMT_DXT5, or FMT_BGRA8
        mipmaps: whether to generate mipmaps
        compressor: function(rgba_bytes, width, height, fmt) -> compressed_bytes
                    Required for DXT formats. Ignored for BGRA8.

    Returns:
        TexFile instance ready to write
    """
    if fmt in BLOCK_FORMATS and compressor is None:
        raise ValueError('Compressor function required for block-compressed formats')

    if fmt in BLOCK_FORMATS:
        if width % 4 != 0 or height % 4 != 0:
            raise ValueError(
                'Dimensions must be divisible by 4 for block compression. '
                'Got {}x{}, try {}x{}'.format(
                    width, height, ((width + 3) // 4) * 4, ((height + 3) // 4) * 4))

    tex = TexFile(width, height, fmt, mipmaps)

    # Edge-extend (alpha bleed) ONCE on the full-res image, before compression
    # AND before mipmap downsampling, so neither the BC block-average nor the
    # Lanczos downsample mixes transparent pixels' (often white) RGB into the
    # edges. This removes the white fringe around cutout/alpha-tested textures.
    rgba = _alpha_bleed(rgba, width, height)

    if not mipmaps:
        tex.data = _compress_level(rgba, width, height, fmt, compressor)
    else:
        # Generate mipmap chain and store smallest-to-largest
        mip_levels = _generate_mipmap_chain(rgba, width, height, fmt, compressor)
        # mip_levels is largest-to-smallest, reverse for TEX storage
        tex.data = b''.join(reversed(mip_levels))

    return tex


def _alpha_bleed(rgba, width, height):
    """Edge-extend (alpha bleed / dilation): fill the RGB of transparent pixels
    with the color of the nearest opaque pixel.

    Without this, fully-transparent pixels keep whatever RGB they had (often
    white in GIMP). BC1/BC3 averages RGB across each 4x4 block — including those
    transparent-but-white pixels — and mipmap downsampling mixes them in too, so
    a white halo bleeds along cutout edges. Bleeding the edge color into the
    transparent region removes the fringe; alpha is untouched.

    Multi-pass flood: each pass copies color from any opaque/already-filled
    neighbor into adjacent transparent pixels, until none remain (or it stalls).

    Uses the native DLL implementation when available (fast); otherwise the pure
    Python flood below.
    """
    try:
        from dxt_compress import alpha_bleed as _native_bleed
        native = _native_bleed(rgba, width, height)
        if native is not None:
            return native
    except Exception:
        pass

    buf = bytearray(rgba)
    # filled[i] = pixel i has valid RGB (originally opaque, or filled this run).
    filled = bytearray(width * height)
    any_transparent = False
    for p in range(width * height):
        if buf[p * 4 + 3] != 0:
            filled[p] = 1
        else:
            any_transparent = True
    if not any_transparent:
        return bytes(buf)

    neighbors = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))
    # Bound the passes so a fully/mostly transparent image can't loop forever.
    max_passes = max(width, height)
    for _ in range(max_passes):
        newly = []
        for y in range(height):
            row = y * width
            for x in range(width):
                p = row + x
                if filled[p]:
                    continue
                rs = gs = bs = cnt = 0
                for dx, dy in neighbors:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        np = ny * width + nx
                        if filled[np]:
                            o = np * 4
                            rs += buf[o]; gs += buf[o + 1]; bs += buf[o + 2]; cnt += 1
                if cnt:
                    o = p * 4
                    buf[o] = rs // cnt; buf[o + 1] = gs // cnt; buf[o + 2] = bs // cnt
                    newly.append(p)
        if not newly:
            break
        for p in newly:
            filled[p] = 1
    return bytes(buf)


def _compress_level(rgba, width, height, fmt, compressor):
    """Compress a single mip level. RGBA is expected to be already edge-extended
    (see _alpha_bleed, applied once up-front in rgba_to_tex_data)."""
    if fmt == FMT_BGRA8:
        return _rgba_to_bgra(rgba, width, height)
    else:
        return compressor(rgba, width, height, fmt)


def _rgba_to_bgra(rgba, width, height):
    """Convert RGBA bytes to BGRA bytes. Uses native DLL if available."""
    try:
        from dxt_compress import rgba_to_bgra
        return rgba_to_bgra(rgba, width * height)
    except Exception:
        pass
    # Pure Python fallback
    out = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        out[i] = rgba[i + 2]      # B
        out[i + 1] = rgba[i + 1]  # G
        out[i + 2] = rgba[i]      # R
        out[i + 3] = rgba[i + 3]  # A
    return bytes(out)


def _generate_mipmap_chain(rgba, width, height, fmt, compressor):
    """Generate all mipmap levels from largest to smallest.
    Returns list of compressed data chunks, largest first."""
    max_dim = max(width, height)
    mip_count = max_dim.bit_length()

    levels = []
    current_rgba = rgba
    current_w = width
    current_h = height

    for i in range(mip_count):
        compressed = _compress_level(current_rgba, current_w, current_h, fmt, compressor)
        levels.append(compressed)

        # Downsample for next level
        if current_w > 1 or current_h > 1:
            new_w = max(current_w // 2, 1)
            new_h = max(current_h // 2, 1)
            current_rgba = _downsample_lanczos3(current_rgba, current_w, current_h, new_w, new_h)
            current_w = new_w
            current_h = new_h

    return levels


def _downsample_lanczos3(rgba, src_w, src_h, dst_w, dst_h):
    """Downsample using native DLL if available, else pure Python."""
    try:
        from dxt_compress import downsample_lanczos3 as _native_downsample
        return _native_downsample(rgba, src_w, src_h, dst_w, dst_h)
    except Exception:
        pass
    return _downsample_lanczos3_pure(rgba, src_w, src_h, dst_w, dst_h)


def _lanczos_kernel(x, a=3.0):
    """Lanczos kernel function."""
    if x == 0.0:
        return 1.0
    if x < -a or x > a:
        return 0.0
    pix = math.pi * x
    return (math.sin(pix) / pix) * (math.sin(pix / a) / (pix / a))


def _downsample_lanczos3_pure(rgba, src_w, src_h, dst_w, dst_h):
    """Pure Python Lanczos3 downsampling fallback."""
    a = 3.0
    scale_x = src_w / dst_w
    scale_y = src_h / dst_h
    dst = bytearray(dst_w * dst_h * 4)

    for y in range(dst_h):
        src_y = (y + 0.5) * scale_y - 0.5
        y0 = max(0, int(math.floor(src_y - a)))
        y1 = min(src_h - 1, int(math.ceil(src_y + a)))

        for x in range(dst_w):
            src_x = (x + 0.5) * scale_x - 0.5
            x0 = max(0, int(math.floor(src_x - a)))
            x1 = min(src_w - 1, int(math.ceil(src_x + a)))

            r = g = b = al = 0.0
            weight_sum = 0.0

            for sy in range(y0, y1 + 1):
                wy = _lanczos_kernel(sy - src_y, a)
                for sx in range(x0, x1 + 1):
                    wx = _lanczos_kernel(sx - src_x, a)
                    w = wx * wy
                    idx = (sy * src_w + sx) * 4
                    r += rgba[idx] * w
                    g += rgba[idx + 1] * w
                    b += rgba[idx + 2] * w
                    al += rgba[idx + 3] * w
                    weight_sum += w

            dst_idx = (y * dst_w + x) * 4
            if weight_sum > 0:
                dst[dst_idx] = max(0, min(255, int(r / weight_sum + 0.5)))
                dst[dst_idx + 1] = max(0, min(255, int(g / weight_sum + 0.5)))
                dst[dst_idx + 2] = max(0, min(255, int(b / weight_sum + 0.5)))
                dst[dst_idx + 3] = max(0, min(255, int(al / weight_sum + 0.5)))

    return bytes(dst)
