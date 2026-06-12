#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GIMP 2.10 Plugin for League of Legends .tex files

Loads TEX files via GIMP's native DDS plugin (TEX->DDS header conversion).
Exports TEX files with DirectXTex BC1/BC3 compression, Floyd-Steinberg
dithering, and Lanczos3 mipmap generation.

Installation:
  Option A (installer): Puts files in plug-ins/gimp2_tex_libs/
  Option B (manual):    Put all files in %APPDATA%\\GIMP\\2.10\\plug-ins\\
"""

from gimpfu import *
import gimp
import os
import sys
import struct
import tempfile

# Add shared modules directory to path
plugin_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(plugin_dir, 'gimp2_tex_libs')
for d in [libs_dir, plugin_dir]:
    if os.path.isdir(d) and d not in sys.path:
        sys.path.insert(0, d)

from tex_core import (TexFile, tex_to_temp_dds, rgba_to_tex_data,
                      FMT_DXT1, FMT_DXT5, FMT_BGRA8, FMT_BC5, FMT_BC7, BLOCK_FORMATS)
from dxt_compress import compress_for_tex

# Logging
try:
    _log_path = os.path.join(os.path.expanduser('~'), 'gimp_tex_plugin.log')
    _log = open(_log_path, 'a')
    sys.stderr = _log
    sys.stdout = _log
except Exception:
    pass

FORMAT_NAMES = ["DXT1 (BC1, no alpha)", "DXT5 (BC3, with alpha)", "BGRA8 (uncompressed)",
                "BC7 (high quality, alpha)", "BC5 (normal maps, RG)"]
FORMAT_VALUES = [FMT_DXT1, FMT_DXT5, FMT_BGRA8, FMT_BC7, FMT_BC5]
METRIC_NAMES = ["Perceptual (recommended)", "Uniform"]


def _log_msg(msg):
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass


# ============================================================================
# Load TEX via DDS plugin
# ============================================================================

def _image_from_rgba(rgba, w, h):
    """Build a GIMP 2 RGBA image from raw RGBA bytes (row-major, R first)."""
    image = gimp.Image(w, h, RGB)
    layer = gimp.Layer(image, "Background", w, h, RGBA_IMAGE, 100, NORMAL_MODE)
    image.add_layer(layer, 0)
    rgn = layer.get_pixel_rgn(0, 0, w, h, True, False)
    rgn[0:w, 0:h] = bytes(rgba)
    layer.flush()
    layer.merge_shadow(True)
    layer.update(0, 0, w, h)
    return image


def tex_load(filename, raw_filename):
    """Load a TEX file. DXT1/DXT5/BGRA8 go through GIMP's native DDS loader;
    BC5/BC7 are decoded by our own native decoders (the DDS plugin's support for
    them varies by version)."""
    _log_msg("Loading TEX: {}".format(filename))

    tex = TexFile.read(filename)
    _log_msg("TEX: {}x{}, format={}, mipmaps={}".format(
        tex.width, tex.height, tex.format, tex.mipmaps))

    if tex.format in (FMT_BC5, FMT_BC7):
        _log_msg("Using built-in decompression for BC5/BC7")
        rgba = tex.decompress_to_rgba()
        image = _image_from_rgba(rgba, tex.width, tex.height)
        pdb.gimp_image_set_filename(image, filename)
        return image

    dds_path = tex_to_temp_dds(tex)
    _log_msg("Temp DDS: {}".format(dds_path))

    try:
        image = pdb.file_dds_load(dds_path, dds_path, 0, 0)
        _log_msg("DDS loaded, image ID={}".format(image.ID))
        pdb.gimp_image_set_filename(image, filename)
        return image
    finally:
        try:
            os.unlink(dds_path)
        except Exception:
            pass


# ============================================================================
# Export TEX - builds custom GIMP dialog
# ============================================================================

def tex_save_silent(image, drawable, filename, raw_filename):
    """Silent export with default/last-used settings. No dialog."""
    _log_msg("tex_save_silent called: {}".format(filename))
    fmt_idx, dithering, metric_idx, mipmaps = _load_settings()
    fmt = FORMAT_VALUES[fmt_idx]
    perceptual = (metric_idx == 0)
    _export_tex(image, drawable, filename, fmt, dithering, perceptual, mipmaps)


def tex_save_options(image, drawable, filename, raw_filename):
    """Export with options dialog."""
    _log_msg("tex_save_options called: {}".format(filename))

    try:
        import gtk
        import gimpui
    except ImportError:
        # No GTK, export with defaults
        _export_tex(image, drawable, filename, FMT_DXT5, True, True, False)
        return

    gimpui.gimp_ui_init()

    # Load last-used settings
    fmt_idx, dithering, metric_idx, mipmaps = _load_settings()

    def _open_help(help_id, help_data):
        import webbrowser
        webbrowser.open("https://github.com/LeagueToolkit/Gimp-Tex-Plugin#export-options")

    dlg = gimpui.Dialog("TEX Export Options", "tex-export", None, 0,
                        _open_help, "file-tex-save",
                        (gtk.STOCK_HELP, gtk.RESPONSE_HELP,
                         gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_SAVE, gtk.RESPONSE_OK))

    vbox = gtk.VBox(False, 12)
    vbox.set_border_width(12)
    dlg.vbox.pack_start(vbox)
    vbox.show()

    # Compression format combo
    table = gtk.Table(4, 2, False)
    table.set_row_spacings(6)
    table.set_col_spacings(6)
    vbox.pack_start(table, expand=False)
    table.show()

    label = gtk.Label("Compression:")
    label.set_alignment(0.0, 0.5)
    table.attach(label, 0, 1, 0, 1, xoptions=gtk.FILL)
    label.show()

    fmt_combo = gtk.combo_box_new_text()
    for name in FORMAT_NAMES:
        fmt_combo.append_text(name)
    fmt_combo.set_active(fmt_idx)
    table.attach(fmt_combo, 1, 2, 0, 1)
    fmt_combo.show()

    # Dithering toggle
    dither_check = gtk.CheckButton("Error diffusion dithering")
    dither_check.set_active(dithering)
    table.attach(dither_check, 0, 2, 1, 2)
    dither_check.show()

    # Error metric combo
    label2 = gtk.Label("Error metric:")
    label2.set_alignment(0.0, 0.5)
    table.attach(label2, 0, 1, 2, 3, xoptions=gtk.FILL)
    label2.show()

    metric_combo = gtk.combo_box_new_text()
    for name in METRIC_NAMES:
        metric_combo.append_text(name)
    metric_combo.set_active(metric_idx)
    table.attach(metric_combo, 1, 2, 2, 3)
    metric_combo.show()

    # Mipmaps toggle
    mip_check = gtk.CheckButton("Generate mipmaps")
    mip_check.set_active(mipmaps)
    table.attach(mip_check, 0, 2, 3, 4)
    mip_check.show()

    # Sensitivity rules
    def update_sensitivity(*args):
        is_dxt = fmt_combo.get_active() < 2
        dither_check.set_sensitive(is_dxt)
        metric_combo.set_sensitive(is_dxt and dither_check.get_active())

    fmt_combo.connect("changed", update_sensitivity)
    dither_check.connect("toggled", update_sensitivity)
    update_sensitivity()

    dlg.show()

    # Loop so Help button doesn't close the dialog
    while True:
        response = dlg.run()
        if response == gtk.RESPONSE_HELP:
            import webbrowser
            webbrowser.open("https://github.com/LeagueToolkit/Gimp-Tex-Plugin#export-options")
            continue
        break

    if response != gtk.RESPONSE_OK:
        dlg.destroy()
        return

    fmt_idx = fmt_combo.get_active()
    dithering = dither_check.get_active()
    metric_idx = metric_combo.get_active()
    mipmaps = mip_check.get_active()
    dlg.destroy()

    _save_settings(fmt_idx, dithering, metric_idx, mipmaps)

    # File chooser (since this is a menu item, not a save handler)
    file_dlg = gtk.FileChooserDialog(
        title="Export as .tex",
        action=gtk.FILE_CHOOSER_ACTION_SAVE,
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                 gtk.STOCK_SAVE, gtk.RESPONSE_OK))
    file_dlg.set_do_overwrite_confirmation(True)

    filt = gtk.FileFilter()
    filt.set_name("League of Legends TEX files")
    filt.add_pattern("*.tex")
    file_dlg.add_filter(filt)

    current_name = pdb.gimp_image_get_filename(image)
    if current_name:
        base = os.path.splitext(os.path.basename(current_name))[0]
        file_dlg.set_current_name(base + ".tex")
        file_dlg.set_current_folder(os.path.dirname(current_name))

    response = file_dlg.run()
    out_filename = file_dlg.get_filename()
    file_dlg.destroy()

    if response != gtk.RESPONSE_OK or not out_filename:
        return

    if not out_filename.lower().endswith('.tex'):
        out_filename += '.tex'

    fmt = FORMAT_VALUES[fmt_idx]
    perceptual = (metric_idx == 0)
    _export_tex(image, drawable, out_filename, fmt, dithering, perceptual, mipmaps)


_SETTINGS_KEY = "gimp-tex-plugin-settings"

def _load_settings():
    try:
        data = gimp.get_data(_SETTINGS_KEY)
        if data and len(data) >= 4:
            fmt_idx, dither, metric_idx, mips = struct.unpack('BBBB', data[:4])
            return fmt_idx, bool(dither), metric_idx, bool(mips)
    except Exception:
        pass
    return 1, True, 0, False  # DXT5, dithering, perceptual, no mipmaps

def _save_settings(fmt_idx, dither, metric_idx, mipmaps):
    try:
        gimp.set_data(_SETTINGS_KEY, struct.pack('BBBB', fmt_idx, int(dither), metric_idx, int(mipmaps)))
    except Exception:
        pass


def _export_tex(image, drawable, filename, fmt, dithering, perceptual, mipmaps):
    """Core export logic."""
    _log_msg("Exporting TEX: {} (fmt={}, dither={}, perceptual={}, mips={})".format(
        filename, fmt, dithering, perceptual, mipmaps))

    export_image = pdb.gimp_image_duplicate(image)

    if export_image.base_type != RGB:
        pdb.gimp_image_convert_rgb(export_image)

    # Merge layers but preserve alpha (flatten would destroy it)
    layer = pdb.gimp_image_merge_visible_layers(export_image, CLIP_TO_IMAGE)
    if layer.type != RGBA_IMAGE:
        pdb.gimp_layer_add_alpha(layer)
    w = layer.width
    h = layer.height

    if fmt in BLOCK_FORMATS:
        if w % 4 != 0 or h % 4 != 0:
            pdb.gimp_image_delete(export_image)
            gimp.message(
                "Image dimensions must be divisible by 4 for block compression.\n"
                "Current: {}x{}\n"
                "Resize to: {}x{}".format(
                    w, h, ((w + 3) // 4) * 4, ((h + 3) // 4) * 4))
            return

    rgn = layer.get_pixel_rgn(0, 0, w, h, False, False)
    rgba = bytearray(rgn[:, :])  # bytearray so indexing returns int on Python 2

    _log_msg("Got {}x{} RGBA data ({} bytes)".format(w, h, len(rgba)))

    compressor = compress_for_tex(dither=bool(dithering), perceptual=perceptual)
    tex = rgba_to_tex_data(rgba, w, h, fmt, mipmaps=bool(mipmaps), compressor=compressor)
    tex.write(filename)

    _log_msg("TEX written: {} bytes".format(os.path.getsize(filename)))
    pdb.gimp_image_delete(export_image)


# ============================================================================
# Registration
# ============================================================================

def register_handlers():
    _log_msg("Registering file handlers...")
    try:
        gimp.register_load_handler("file-tex-load", "tex", "")
        gimp.register_save_handler("file-tex-save", "tex", "")
        # Don't register options as file handler — it's a menu item only
        _log_msg("Handlers registered successfully")
    except Exception as e:
        _log_msg("Handler registration error: {}".format(str(e)))


register(
    "file-tex-load",
    "Load League of Legends .tex texture file",
    "Loads .tex files (DXT1/DXT5/BC5/BC7/BGRA8)",
    "LtMAO Team", "LtMAO Team", "2025",
    "League of Legends TEX",
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

# Silent save — default/last-used settings, no dialog
register(
    "file-tex-save",
    "Save as League of Legends .tex texture file",
    "Quick export using last-used or default settings (DXT5)",
    "LtMAO Team", "LtMAO Team", "2025",
    "League of Legends TEX",
    "RGB*, GRAY*, RGBA*",
    [
        (PF_IMAGE, "image", "Input image", None),
        (PF_DRAWABLE, "drawable", "Input drawable", None),
        (PF_STRING, "filename", "The name of the file", None),
        (PF_STRING, "raw-filename", "The name entered", None),
    ],
    [],
    tex_save_silent,
    menu="<Save>"
)

# Save with options — menu item under File, not a save handler
register(
    "file-tex-save-options",
    "Export as .tex (options)",
    "Export with compression format, dithering, and mipmap settings",
    "LtMAO Team", "LtMAO Team", "2025",
    "<Image>/File/Export as .tex (options)...",
    "RGB*, GRAY*, RGBA*",
    [],
    [],
    lambda image, drawable: tex_save_options(image, drawable, None, None)
)

_log_msg("About to call main()...")
main()
_log_msg("Plugin loaded successfully")
