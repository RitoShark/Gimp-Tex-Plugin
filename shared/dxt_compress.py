# -*- coding: utf-8 -*-
"""
dxt_compress.py - DXT compression via native C DLL with pure Python fallback

Loads dxt_compress.dll for fast BC1/BC3 compression with Floyd-Steinberg
dithering and perceptual/uniform error metrics. Falls back to a slow but
functional pure Python implementation if the DLL is not found.

Usage:
  from dxt_compress import compress_for_tex
  compressor = compress_for_tex(dither=True, perceptual=True)
"""

import ctypes
import os
import sys
import struct
import math

from tex_core import FMT_DXT1, FMT_DXT5, FMT_BC5, FMT_BC7, FMT_BGRA8

# ---------------------------------------------------------------------------
# Try to load the native DLL
# ---------------------------------------------------------------------------

_dll = None
_dll_init_done = False

def _log(msg):
    try:
        sys.stdout.write("[dxt_compress] {}\n".format(msg))
        sys.stdout.flush()
    except Exception:
        pass

def _find_dll():
    """Search for the native compression library."""
    if sys.platform == 'win32':
        lib_name = 'libdxtcompress.dll'
    elif sys.platform == 'darwin':
        lib_name = 'libdxtcompress.dylib'
    else:
        lib_name = 'libdxtcompress.so'

    search_dirs = [
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]
    for d in search_dirs:
        path = os.path.join(d, lib_name)
        _log("Checking: {} -> exists={}".format(path, os.path.exists(path)))
        if os.path.exists(path):
            return path
    return None

def _init_dll():
    global _dll, _dll_init_done

    # Only try once
    if _dll_init_done:
        return _dll

    _dll_init_done = True

    dll_path = _find_dll()
    if dll_path is None:
        _log("DLL not found, using pure Python fallback (SLOW)")
        return None

    try:
        _log("Loading DLL: {}".format(dll_path))
        _dll = ctypes.CDLL(dll_path)

        # void compress_bc1(const uint8_t *rgba, int width, int height,
        #                   uint8_t *output, int use_dithering, int use_perceptual)
        _dll.compress_bc1.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int
        ]
        _dll.compress_bc1.restype = None

        # void compress_bc3(const uint8_t *rgba, int width, int height,
        #                   uint8_t *output, int use_dithering, int use_perceptual)
        _dll.compress_bc3.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int
        ]
        _dll.compress_bc3.restype = None

        # void downsample_lanczos3(const uint8_t *src, int src_w, int src_h,
        #                          uint8_t *dst, int dst_w, int dst_h)
        _dll.downsample_lanczos3.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int
        ]
        _dll.downsample_lanczos3.restype = None

        # void rgba_to_bgra(const uint8_t *rgba, uint8_t *bgra, int num_pixels)
        _dll.rgba_to_bgra.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int
        ]
        _dll.rgba_to_bgra.restype = None

        # void decompress_bc1(const uint8_t *input, int width, int height, uint8_t *rgba)
        _dll.decompress_bc1.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
        ]
        _dll.decompress_bc1.restype = None

        # void decompress_bc3(const uint8_t *input, int width, int height, uint8_t *rgba)
        _dll.decompress_bc3.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
        ]
        _dll.decompress_bc3.restype = None

        # void decompress_bgra8(const uint8_t *input, int width, int height, uint8_t *rgba)
        _dll.decompress_bgra8.argtypes = [
            ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p
        ]
        _dll.decompress_bgra8.restype = None

        # void alpha_bleed(uint8_t *rgba, int width, int height)  [in place]
        # Optional: only present in DLLs built after the edge-extend fix.
        try:
            _dll.alpha_bleed.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
            _dll.alpha_bleed.restype = None
        except AttributeError:
            pass

        # BC5 + BC7 codecs. Optional: only present in DLLs built with the
        # bc7enc/BC5 support. Older DLLs simply won't expose these symbols.
        try:
            # void compress_bc5(const uint8_t *rgba, int w, int h, uint8_t *output)
            _dll.compress_bc5.argtypes = [
                ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
            _dll.compress_bc5.restype = None
            # void decompress_bc5(const uint8_t *input, int w, int h, uint8_t *rgba)
            _dll.decompress_bc5.argtypes = [
                ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
            _dll.decompress_bc5.restype = None
        except AttributeError:
            pass

        try:
            # void compress_bc7(const uint8_t *rgba, int w, int h, uint8_t *output,
            #                   int perceptual, int uber_level)
            _dll.compress_bc7.argtypes = [
                ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p,
                ctypes.c_int, ctypes.c_int]
            _dll.compress_bc7.restype = None
            # void decompress_bc7(const uint8_t *input, int w, int h, uint8_t *rgba)
            _dll.decompress_bc7.argtypes = [
                ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
            _dll.decompress_bc7.restype = None
        except AttributeError:
            pass

        _log("DLL loaded successfully - using FAST native compression")
        return _dll
    except Exception as e:
        _log("Failed to load DLL: {}".format(e))
        _dll = None
        return None


# ---------------------------------------------------------------------------
# Optional Windows-only GPU BC7 accelerator (Bc7Native.dll / DirectXTex)
# ---------------------------------------------------------------------------

_bc7_native = None
_bc7_native_init_done = False

def _init_bc7_native():
    """Load the optional Bc7Native.dll (DirectXTex GPU BC7 encoder). Windows only.
    Returns the loaded library if a GPU compute device is available, else None
    (callers fall back to the bc7enc CPU encoder in the main library)."""
    global _bc7_native, _bc7_native_init_done
    if _bc7_native_init_done:
        return _bc7_native
    _bc7_native_init_done = True

    if sys.platform != 'win32':
        return None

    for d in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        path = os.path.join(d, 'Bc7Native.dll')
        if not os.path.exists(path):
            continue
        try:
            dll = ctypes.CDLL(path)
            # int encode_bc7_gpu(uint8_t *out, const uint8_t *rgba,
            #                    uint32_t w, uint32_t h, uint32_t flags)
            dll.encode_bc7_gpu.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p,
                ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
            dll.encode_bc7_gpu.restype = ctypes.c_int
            # int gpu_available(void)
            dll.gpu_available.argtypes = []
            dll.gpu_available.restype = ctypes.c_int
            if dll.gpu_available() != 0:
                _log("Bc7Native.dll loaded - GPU BC7 path available")
                _bc7_native = dll
            else:
                _log("Bc7Native.dll present but no GPU device; using bc7enc CPU")
        except Exception as e:
            _log("Bc7Native.dll load failed ({}); using bc7enc CPU".format(e))
        break
    return _bc7_native


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_for_tex(dither=True, perceptual=True):
    """Return a compressor callback compatible with tex_core.rgba_to_tex_data()."""
    def _compressor(rgba, width, height, fmt):
        if fmt == FMT_DXT1:
            return compress_bc1(rgba, width, height, dither, perceptual)
        elif fmt == FMT_DXT5:
            return compress_bc3(rgba, width, height, dither, perceptual)
        elif fmt == FMT_BC5:
            return compress_bc5(rgba, width, height)
        elif fmt == FMT_BC7:
            return compress_bc7(rgba, width, height, perceptual=perceptual)
        else:
            raise ValueError('Compressor does not handle format {}'.format(fmt))
    return _compressor


def native_decompress(data, width, height, fmt):
    """Decompress DXT1/DXT5/BGRA8 via native DLL. Returns RGBA bytes or None if unavailable."""
    dll = _init_dll()
    if dll is None:
        return None
    out_size = width * height * 4
    output = ctypes.create_string_buffer(out_size)
    if fmt == FMT_DXT1:
        dll.decompress_bc1(bytes(data), width, height, output)
    elif fmt == FMT_DXT5:
        dll.decompress_bc3(bytes(data), width, height, output)
    elif fmt == FMT_BGRA8:
        dll.decompress_bgra8(bytes(data), width, height, output)
    elif fmt == FMT_BC5 and hasattr(dll, 'decompress_bc5'):
        dll.decompress_bc5(bytes(data), width, height, output)
    elif fmt == FMT_BC7 and hasattr(dll, 'decompress_bc7'):
        dll.decompress_bc7(bytes(data), width, height, output)
    else:
        return None
    return output.raw


def alpha_bleed(rgba, width, height):
    """Edge-extend transparent pixels' RGB from nearest opaque neighbors (kills
    the white fringe on cutout textures). Native if the DLL exports it, else None
    so callers fall back to the pure-Python implementation in tex_core."""
    dll = _init_dll()
    if dll is not None and hasattr(dll, 'alpha_bleed'):
        buf = ctypes.create_string_buffer(bytes(rgba), len(rgba))
        dll.alpha_bleed(buf, width, height)
        return buf.raw[:len(rgba)]
    return None


def rgba_to_bgra(rgba, num_pixels):
    """Swap R and B channels. Uses native DLL if available."""
    dll = _init_dll()
    if dll is not None:
        output = ctypes.create_string_buffer(num_pixels * 4)
        dll.rgba_to_bgra(bytes(rgba), output, num_pixels)
        return output.raw
    # Pure Python fallback
    out = bytearray(len(rgba))
    for i in range(0, num_pixels * 4, 4):
        out[i] = rgba[i + 2]
        out[i + 1] = rgba[i + 1]
        out[i + 2] = rgba[i]
        out[i + 3] = rgba[i + 3]
    return bytes(out)


def downsample_lanczos3(rgba, src_w, src_h, dst_w, dst_h):
    """Downsample RGBA image using Lanczos3 resampling."""
    dll = _init_dll()
    if dll is not None:
        out_size = dst_w * dst_h * 4
        output = ctypes.create_string_buffer(out_size)
        dll.downsample_lanczos3(bytes(rgba), src_w, src_h, output, dst_w, dst_h)
        return output.raw
    # Pure Python fallback imported from tex_core
    from tex_core import _downsample_lanczos3_pure
    return _downsample_lanczos3_pure(rgba, src_w, src_h, dst_w, dst_h)


def compress_bc1(rgba, width, height, dither=True, perceptual=True):
    """Compress RGBA data to BC1 (DXT1)."""
    dll = _init_dll()
    if dll is not None:
        _log("Compressing BC1 {}x{} via DLL".format(width, height))
        return _dll_compress_bc1(dll, rgba, width, height, dither, perceptual)
    _log("Compressing BC1 {}x{} via Python (slow!)".format(width, height))
    return _py_compress_bc1(rgba, width, height, dither, perceptual)


def compress_bc3(rgba, width, height, dither=True, perceptual=True):
    """Compress RGBA data to BC3 (DXT5)."""
    dll = _init_dll()
    if dll is not None:
        _log("Compressing BC3 {}x{} via DLL".format(width, height))
        return _dll_compress_bc3(dll, rgba, width, height, dither, perceptual)
    _log("Compressing BC3 {}x{} via Python (slow!)".format(width, height))
    return _py_compress_bc3(rgba, width, height, dither, perceptual)


def compress_bc5(rgba, width, height):
    """Compress RGBA data to BC5 (R,G channels). Native library only (no Python
    fallback). Used for tangent-space normal maps."""
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4
    out_size = block_w * block_h * 16
    dll = _init_dll()
    if dll is not None and hasattr(dll, 'compress_bc5'):
        _log("Compressing BC5 {}x{} via DLL".format(width, height))
        output = ctypes.create_string_buffer(out_size)
        dll.compress_bc5(bytes(rgba), width, height, output)
        return output.raw
    raise RuntimeError(
        'BC5 compression requires the native library (libdxtcompress).')


def compress_bc7(rgba, width, height, perceptual=True, uber_level=0):
    """Compress RGBA data to BC7. Prefers the optional Bc7Native.dll GPU encoder
    on Windows; otherwise uses the bc7enc CPU encoder in the main library."""
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4
    out_size = block_w * block_h * 16

    # Optional Windows GPU accelerator (DirectXTex via Bc7Native.dll).
    gpu = _init_bc7_native()
    if gpu is not None:
        try:
            output = ctypes.create_string_buffer(out_size)
            # flags = 0 -> DirectXTex default compression flags
            if gpu.encode_bc7_gpu(output, bytes(rgba), width, height, 0) != 0:
                _log("Compressing BC7 {}x{} via GPU (DirectXTex)".format(width, height))
                return output.raw
            _log("GPU BC7 encode failed; falling back to bc7enc CPU")
        except Exception as e:
            _log("GPU BC7 error ({}); falling back to bc7enc CPU".format(e))

    # Cross-platform CPU encoder (bc7enc) in the main library.
    dll = _init_dll()
    if dll is not None and hasattr(dll, 'compress_bc7'):
        _log("Compressing BC7 {}x{} via bc7enc CPU".format(width, height))
        output = ctypes.create_string_buffer(out_size)
        dll.compress_bc7(bytes(rgba), width, height, output,
                         int(perceptual), int(uber_level))
        return output.raw
    raise RuntimeError(
        'BC7 compression requires the native library (libdxtcompress with bc7enc).')


# ---------------------------------------------------------------------------
# Native DLL path
# ---------------------------------------------------------------------------

def _dll_compress_bc1(dll, rgba, width, height, dither, perceptual):
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4
    out_size = block_w * block_h * 8
    output = ctypes.create_string_buffer(out_size)
    dll.compress_bc1(bytes(rgba), width, height, output, int(dither), int(perceptual))
    return output.raw


def _dll_compress_bc3(dll, rgba, width, height, dither, perceptual):
    block_w = (width + 3) // 4
    block_h = (height + 3) // 4
    out_size = block_w * block_h * 16
    output = ctypes.create_string_buffer(out_size)
    dll.compress_bc3(bytes(rgba), width, height, output, int(dither), int(perceptual))
    return output.raw


# ---------------------------------------------------------------------------
# Pure Python fallback (slow but functional)
# ---------------------------------------------------------------------------

# Perceptual weightings from DirectXTex BC.cpp
_LUM_R = 0.2125 / 0.7154
_LUM_G = 1.0
_LUM_B = 0.0721 / 0.7154
_LUM_R_INV = 0.7154 / 0.2125
_LUM_B_INV = 0.7154 / 0.0721

def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def _encode_565(r, g, b):
    return ((int(_clamp01(r) * 31.0 + 0.5) << 11) |
            (int(_clamp01(g) * 63.0 + 0.5) << 5) |
            int(_clamp01(b) * 31.0 + 0.5))

def _decode_565(w):
    return ((w >> 11) & 31) / 31.0, ((w >> 5) & 63) / 63.0, (w & 31) / 31.0

def _propagate_error(er, eg, eb, i, dr, dg, db):
    if (i & 3) != 3 and i < 15:
        er[i+1] += dr * 0.4375; eg[i+1] += dg * 0.4375; eb[i+1] += db * 0.4375
    if i < 12:
        if (i & 3) != 0:
            er[i+3] += dr * 0.1875; eg[i+3] += dg * 0.1875; eb[i+3] += db * 0.1875
        er[i+4] += dr * 0.3125; eg[i+4] += dg * 0.3125; eb[i+4] += db * 0.3125
        if (i & 3) != 3:
            er[i+5] += dr * 0.0625; eg[i+5] += dg * 0.0625; eb[i+5] += db * 0.0625

def _optimize_rgb_py(cr, cg, cb, u_steps):
    xr=xg=xb=1.0; yr=yg=yb=0.0
    for i in range(16):
        if cr[i]<xr: xr=cr[i]
        if cg[i]<xg: xg=cg[i]
        if cb[i]<xb: xb=cb[i]
        if cr[i]>yr: yr=cr[i]
        if cg[i]>yg: yg=cg[i]
        if cb[i]>yb: yb=cb[i]
    abr=yr-xr; abg=yg-xg; abb=yb-xb
    fab=abr*abr+abg*abg+abb*abb
    if fab<1e-38: return xr,xg,xb,yr,yg,yb
    inv=1.0/fab; dr=abr*inv; dg=abg*inv; db=abb*inv
    mr=(xr+yr)*0.5; mg=(xg+yg)*0.5; mb=(xb+yb)*0.5
    fd=[0.0]*4
    for i in range(16):
        pr=(cr[i]-mr)*dr; pg=(cg[i]-mg)*dg; pb=(cb[i]-mb)*db
        f=pr+pg+pb; fd[0]+=f*f; f=pr+pg-pb; fd[1]+=f*f
        f=pr-pg+pb; fd[2]+=f*f; f=pr-pg-pb; fd[3]+=f*f
    mx=0
    for d in range(1,4):
        if fd[d]>fd[mx]: mx=d
    if mx&2: xg,yg=yg,xg
    if mx&1: xb,yb=yb,xb
    if fab<1.0/4096.0:
        return _clamp01(xr),_clamp01(xg),_clamp01(xb),_clamp01(yr),_clamp01(yg),_clamp01(yb)
    fs=float(u_steps-1)
    pC=[1.0,2/3,1/3,0.0] if u_steps==4 else [1.0,0.5,0.0]
    pD=[0.0,1/3,2/3,1.0] if u_steps==4 else [0.0,0.5,1.0]
    eps=(0.25/64.0)**2
    for _ in range(8):
        dxr=yr-xr; dxg=yg-xg; dxb=yb-xb
        fl=dxr*dxr+dxg*dxg+dxb*dxb
        if fl<1.0/4096.0: break
        sc=fs/fl; dxr*=sc; dxg*=sc; dxb*=sc
        sr=[xr*pC[s]+yr*pD[s] for s in range(u_steps)]
        sg=[xg*pC[s]+yg*pD[s] for s in range(u_steps)]
        sb=[xb*pC[s]+yb*pD[s] for s in range(u_steps)]
        d2x=d2y=dXr=dXg=dXb=dYr=dYg=dYb=0.0
        for p in range(16):
            dot=(cr[p]-xr)*dxr+(cg[p]-xg)*dxg+(cb[p]-xb)*dxb
            if dot<=0: ist=0
            elif dot>=fs: ist=u_steps-1
            else: ist=int(dot+0.5)
            dfr=sr[ist]-cr[p]; dfg=sg[ist]-cg[p]; dfb=sb[ist]-cb[p]
            fc=pC[ist]*0.125; fd2=pD[ist]*0.125
            d2x+=fc*pC[ist]; dXr+=fc*dfr; dXg+=fc*dfg; dXb+=fc*dfb
            d2y+=fd2*pD[ist]; dYr+=fd2*dfr; dYg+=fd2*dfg; dYb+=fd2*dfb
        if d2x>0: f=-1.0/d2x; xr+=dXr*f; xg+=dXg*f; xb+=dXb*f
        if d2y>0: f=-1.0/d2y; yr+=dYr*f; yg+=dYg*f; yb+=dYb*f
        if dXr*dXr<eps and dXg*dXg<eps and dXb*dXb<eps and dYr*dYr<eps and dYg*dYg<eps and dYb*dYb<eps: break
    return _clamp01(xr),_clamp01(xg),_clamp01(xb),_clamp01(yr),_clamp01(yg),_clamp01(yb)

def _encode_bc1_block_py(pcr, pcg, pcb, output, off, dither, perceptual):
    cr=[0.0]*16; cg=[0.0]*16; cb=[0.0]*16
    er=[0.0]*16; eg=[0.0]*16; eb=[0.0]*16
    for i in range(16):
        r,g,b=pcr[i],pcg[i],pcb[i]
        if dither: r+=er[i]; g+=eg[i]; b+=eb[i]
        cr[i]=int(r*31+0.5)/31.0; cg[i]=int(g*63+0.5)/63.0; cb[i]=int(b*31+0.5)/31.0
        if dither: _propagate_error(er,eg,eb,i,r-cr[i],g-cg[i],b-cb[i])
        if perceptual: cr[i]*=_LUM_R; cg[i]*=_LUM_G; cb[i]*=_LUM_B
    xr,xg,xb,yr,yg,yb=_optimize_rgb_py(cr,cg,cb,4)
    if perceptual:
        c_r,c_g,c_b=xr*_LUM_R_INV,xg,xb*_LUM_B_INV
        d_r,d_g,d_b=yr*_LUM_R_INV,yg,yb*_LUM_B_INV
    else: c_r,c_g,c_b,d_r,d_g,d_b=xr,xg,xb,yr,yg,yb
    wA=_encode_565(c_r,c_g,c_b); wB=_encode_565(d_r,d_g,d_b)
    if wA==wB:
        struct.pack_into('<HHI',output,off,wA,wB,0); return
    c_r,c_g,c_b=_decode_565(wA); d_r,d_g,d_b=_decode_565(wB)
    if perceptual:
        a_r,a_g,a_b=c_r*_LUM_R,c_g*_LUM_G,c_b*_LUM_B
        b_r,b_g,b_b=d_r*_LUM_R,d_g*_LUM_G,d_b*_LUM_B
    else: a_r,a_g,a_b,b_r,b_g,b_b=c_r,c_g,c_b,d_r,d_g,d_b
    if wA<wB:
        struct.pack_into('<HH',output,off,wB,wA)
        s0r,s0g,s0b=b_r,b_g,b_b; s1r,s1g,s1b=a_r,a_g,a_b
    else:
        struct.pack_into('<HH',output,off,wA,wB)
        s0r,s0g,s0b=a_r,a_g,a_b; s1r,s1g,s1b=b_r,b_g,b_b
    sr=[s0r,s1r,s0r+(s1r-s0r)/3,s0r+(s1r-s0r)*2/3]
    sg=[s0g,s1g,s0g+(s1g-s0g)/3,s0g+(s1g-s0g)*2/3]
    sb=[s0b,s1b,s0b+(s1b-s0b)/3,s0b+(s1b-s0b)*2/3]
    dr2=s1r-s0r; dg2=s1g-s0g; db2=s1b-s0b
    fl=dr2*dr2+dg2*dg2+db2*db2
    sc=3.0/fl if fl>0 else 0.0
    dr2*=sc; dg2*=sc; db2*=sc
    ps=[0,2,3,1]
    if dither: er=[0.0]*16; eg=[0.0]*16; eb=[0.0]*16
    dw=0
    for i in range(16):
        if perceptual: r,g,b=pcr[i]*_LUM_R,pcg[i]*_LUM_G,pcb[i]*_LUM_B
        else: r,g,b=pcr[i],pcg[i],pcb[i]
        if dither: r+=er[i]; g+=eg[i]; b+=eb[i]
        dot=(r-s0r)*dr2+(g-s0g)*dg2+(b-s0b)*db2
        if dot<=0: ist=0
        elif dot>=3.0: ist=1
        else: ist=ps[int(dot+0.5)]
        dw=(ist<<30)|(dw>>2)
        if dither: _propagate_error(er,eg,eb,i,r-sr[ist],g-sg[ist],b-sb[ist])
    struct.pack_into('<I',output,off+4,dw&0xFFFFFFFF)

def _encode_bc3_alpha_py(alphas, output, off):
    mn=255; mx=0
    for a in alphas:
        if a<mn: mn=a
        if a>mx: mx=a
    output[off]=mx; output[off+1]=mn
    pal=[mx,mn]+[0]*6
    if mx>mn:
        for i in range(1,7): pal[i+1]=(mx*(7-i)+mn*i+3)//7
    else:
        for i in range(1,5): pal[i+1]=(mx*(5-i)+mn*i+2)//5
        pal[6]=0; pal[7]=255
    bits=0
    for i in range(16):
        bd=abs(alphas[i]-pal[0]); bi=0
        for j in range(1,8):
            d=abs(alphas[i]-pal[j])
            if d<bd: bd=d; bi=j
        bits|=bi<<(i*3)
    for i in range(6): output[off+2+i]=(bits>>(i*8))&0xFF

def _py_compress_bc1(rgba, width, height, dither, perceptual):
    bw=(width+3)//4; bh=(height+3)//4
    out=bytearray(bw*bh*8)
    for by in range(bh):
        for bx in range(bw):
            cr=[0.0]*16; cg=[0.0]*16; cb=[0.0]*16
            for y in range(4):
                for x in range(4):
                    px,py2=bx*4+x,by*4+y
                    if px<width and py2<height:
                        pi=(py2*width+px)*4; idx=y*4+x
                        cr[idx]=rgba[pi]/255.0; cg[idx]=rgba[pi+1]/255.0; cb[idx]=rgba[pi+2]/255.0
            _encode_bc1_block_py(cr,cg,cb,out,(by*bw+bx)*8,dither,perceptual)
    return bytes(out)

def _py_compress_bc3(rgba, width, height, dither, perceptual):
    bw=(width+3)//4; bh=(height+3)//4
    out=bytearray(bw*bh*16)
    for by in range(bh):
        for bx in range(bw):
            cr=[0.0]*16; cg=[0.0]*16; cb=[0.0]*16; al=[255]*16
            for y in range(4):
                for x in range(4):
                    px,py2=bx*4+x,by*4+y
                    if px<width and py2<height:
                        pi=(py2*width+px)*4; idx=y*4+x
                        cr[idx]=rgba[pi]/255.0; cg[idx]=rgba[pi+1]/255.0
                        cb[idx]=rgba[pi+2]/255.0; al[idx]=rgba[pi+3]
            off=(by*bw+bx)*16
            _encode_bc3_alpha_py(al,out,off)
            _encode_bc1_block_py(cr,cg,cb,out,off+8,dither,perceptual)
    return bytes(out)
