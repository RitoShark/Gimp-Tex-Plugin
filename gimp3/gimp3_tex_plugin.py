#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIMP 3.x Plugin for League of Legends .tex files

Loads TEX files via GIMP's native DDS plugin (TEX->DDS header conversion).
Two export modes:
  - File > Export As (.tex) — silent, uses last-used settings
  - File > Export as .tex (options)... — dialog with compression settings

Installation:
  Copy all files to: %APPDATA%\\GIMP\\<version>\\plug-ins\\gimp3_tex_plugin\\
"""

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('GimpUi', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, GimpUi, Gtk, GObject, GLib, Gegl, Gio
import struct
import sys
import os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from tex_core import (TexFile, tex_to_temp_dds, rgba_to_tex_data,
                      FMT_DXT1, FMT_DXT5, FMT_BGRA8, FMT_BC5, FMT_BC7, BLOCK_FORMATS)
from dxt_compress import compress_for_tex

_log_path = os.path.join(os.path.expanduser('~'), 'gimp_tex_plugin_3.log')
try:
    _log = open(_log_path, 'a', encoding='utf-8')
    sys.stderr = _log
    sys.stdout = _log
except Exception:
    pass

FORMAT_NAMES = ["DXT1 (BC1, no alpha)", "DXT5 (BC3, with alpha)", "BGRA8 (uncompressed)",
                "BC7 (high quality, alpha)", "BC5 (normal maps, RG)"]
FORMAT_VALUES = [FMT_DXT1, FMT_DXT5, FMT_BGRA8, FMT_BC7, FMT_BC5]
METRIC_NAMES = ["Perceptual (recommended)", "Uniform"]

_SETTINGS_FILE = os.path.join(os.path.expanduser('~'), '.gimp_tex_export_settings')


def _log_msg(msg):
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _load_settings():
    try:
        with open(_SETTINGS_FILE, 'r') as f:
            parts = f.read().strip().split(',')
            if len(parts) >= 4:
                return int(parts[0]), parts[1] == '1', int(parts[2]), parts[3] == '1'
    except Exception:
        pass
    return 1, True, 0, False  # DXT5, dithering, perceptual, no mipmaps


def _save_settings(fmt_idx, dither, metric_idx, mipmaps):
    try:
        with open(_SETTINGS_FILE, 'w') as f:
            f.write('{},{},{},{}'.format(
                fmt_idx, '1' if dither else '0',
                metric_idx, '1' if mipmaps else '0'))
    except Exception:
        pass


# ============================================================================
# Load TEX
# ============================================================================

def load_tex(procedure, run_mode, file, metadata, flags, config, data):
    _log_msg("load_tex called")

    if not file:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("No file provided"))

    path = file.get_path()
    _log_msg("Loading: {}".format(path))

    try:
        tex = TexFile.read(path)
        _log_msg("TEX: {}x{}, format={}, mipmaps={}".format(
            tex.width, tex.height, tex.format, tex.mipmaps))

        image = None

        # Try DDS plugin first (fast, native decompression). BC5/BC7 are decoded
        # by our own native decoders instead, since GIMP's DDS plugin support for
        # them varies by version; route them straight to the built-in path.
        if tex.format in (FMT_BC5, FMT_BC7):
            pdb_proc = None
        else:
            pdb_proc = Gimp.get_pdb().lookup_procedure('file-dds-load')
        if pdb_proc is not None:
            _log_msg("Using DDS plugin to load")
            dds_path = tex_to_temp_dds(tex)
            try:
                dds_file = Gio.File.new_for_path(dds_path)
                pdb_config = pdb_proc.create_config()
                pdb_config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
                pdb_config.set_property('file', dds_file)
                pdb_config.set_property('load-mipmaps', False)
                pdb_config.set_property('flip-image', False)

                result = pdb_proc.run(pdb_config)
                status = result.index(0)
                if status == Gimp.PDBStatusType.SUCCESS:
                    image = result.index(1)
                else:
                    _log_msg("DDS plugin failed with status {}, falling back".format(status))
            finally:
                try:
                    os.unlink(dds_path)
                except Exception:
                    pass

        # Fallback: decompress directly in Python
        if image is None:
            _log_msg("Using built-in decompression")
            rgba = tex.decompress_to_rgba()

            image = Gimp.Image.new(tex.width, tex.height, Gimp.ImageBaseType.RGB)
            layer = Gimp.Layer.new(image, "Background", tex.width, tex.height,
                                   Gimp.ImageType.RGBA_IMAGE, 100.0,
                                   Gimp.LayerMode.NORMAL)
            image.insert_layer(layer, None, 0)

            buffer = layer.get_buffer()
            rect = Gegl.Rectangle()
            rect.x, rect.y, rect.width, rect.height = 0, 0, tex.width, tex.height
            buffer.set(rect, "R'G'B'A u8", rgba)
            buffer.flush()

        image.set_file(file)
        _log_msg("Load successful!")

        return Gimp.ValueArray.new_from_values([
            GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
            GObject.Value(Gimp.Image, image),
        ]), flags

    except Exception as e:
        _log_msg("ERROR: {}".format(e))
        import traceback
        traceback.print_exc()
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(e)))


# ============================================================================
# Export TEX — silent (last-used / default settings)
# ============================================================================

def export_tex(procedure, run_mode, image, file, options, metadata, config, data):
    _log_msg("export_tex (silent) called")

    fmt_idx, dithering, metric_idx, mipmaps = _load_settings()
    fmt = FORMAT_VALUES[fmt_idx]
    perceptual = (metric_idx == 0)

    return _do_export(procedure, image, file, fmt, dithering, perceptual, mipmaps)


# ============================================================================
# Export TEX (options) — File menu item with dialog + file chooser
# ============================================================================

def export_tex_options(procedure, run_mode, image, *args):
    _log_msg("export_tex_options called")

    fmt_idx, dithering, metric_idx, mipmaps = _load_settings()

    GimpUi.init("file-tex-export-options")

    dlg = GimpUi.Dialog(title="TEX Export Options", role="tex-export")
    dlg.add_button("Help", Gtk.ResponseType.HELP)
    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dlg.add_button("Next", Gtk.ResponseType.OK)

    content = dlg.get_content_area()
    content.set_spacing(8)
    content.set_margin_start(12)
    content.set_margin_end(12)
    content.set_margin_top(12)
    content.set_margin_bottom(8)

    hbox1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    label1 = Gtk.Label(label="Compression:")
    label1.set_xalign(0)
    fmt_combo = Gtk.ComboBoxText()
    for name in FORMAT_NAMES:
        fmt_combo.append_text(name)
    fmt_combo.set_active(fmt_idx)
    hbox1.pack_start(label1, False, False, 0)
    hbox1.pack_start(fmt_combo, True, True, 0)
    content.pack_start(hbox1, False, False, 0)

    dither_check = Gtk.CheckButton(label="Error diffusion dithering")
    dither_check.set_active(dithering)
    content.pack_start(dither_check, False, False, 0)

    hbox2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    label2 = Gtk.Label(label="Error metric:")
    label2.set_xalign(0)
    metric_combo = Gtk.ComboBoxText()
    for name in METRIC_NAMES:
        metric_combo.append_text(name)
    metric_combo.set_active(metric_idx)
    hbox2.pack_start(label2, False, False, 0)
    hbox2.pack_start(metric_combo, True, True, 0)
    content.pack_start(hbox2, False, False, 0)

    mip_check = Gtk.CheckButton(label="Generate mipmaps")
    mip_check.set_active(mipmaps)
    content.pack_start(mip_check, False, False, 0)

    def update_sensitivity(*args):
        is_dxt = fmt_combo.get_active() < 2
        dither_check.set_sensitive(is_dxt)
        metric_combo.set_sensitive(is_dxt and dither_check.get_active())

    fmt_combo.connect("changed", update_sensitivity)
    dither_check.connect("toggled", update_sensitivity)
    update_sensitivity()

    dlg.show_all()

    while True:
        response = dlg.run()
        if response == Gtk.ResponseType.HELP:
            import webbrowser
            webbrowser.open("https://github.com/LeagueToolkit/Gimp-Tex-Plugin#export-options")
            continue
        break

    if response != Gtk.ResponseType.OK:
        dlg.destroy()
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)

    fmt_idx = fmt_combo.get_active()
    dithering = dither_check.get_active()
    metric_idx = metric_combo.get_active()
    mipmaps = mip_check.get_active()
    dlg.destroy()

    _save_settings(fmt_idx, dithering, metric_idx, mipmaps)

    # File chooser
    file_dlg = Gtk.FileChooserDialog(
        title="Export as .tex",
        action=Gtk.FileChooserAction.SAVE)
    file_dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    file_dlg.add_button("Export", Gtk.ResponseType.OK)
    file_dlg.set_do_overwrite_confirmation(True)

    filt = Gtk.FileFilter()
    filt.set_name("League of Legends TEX files")
    filt.add_pattern("*.tex")
    file_dlg.add_filter(filt)

    img_file = image.get_file()
    if img_file:
        img_path = img_file.get_path()
        if img_path:
            base = os.path.splitext(os.path.basename(img_path))[0]
            file_dlg.set_current_name(base + ".tex")
            file_dlg.set_current_folder(os.path.dirname(img_path))

    response = file_dlg.run()
    if response != Gtk.ResponseType.OK:
        file_dlg.destroy()
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, None)

    filename = file_dlg.get_filename()
    file_dlg.destroy()

    if not filename.lower().endswith('.tex'):
        filename += '.tex'

    fmt = FORMAT_VALUES[fmt_idx]
    perceptual = (metric_idx == 0)
    out_file = Gio.File.new_for_path(filename)

    return _do_export(procedure, image, out_file, fmt, dithering, perceptual, mipmaps)


# ============================================================================
# Shared export logic
# ============================================================================

def _do_export(procedure, image, file, fmt, dithering, perceptual, mipmaps):
    if not file:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR, GLib.Error("No file provided"))

    try:
        path = file.get_path()
        _log_msg("Exporting: {} (fmt={}, dither={}, perceptual={}, mips={})".format(
            path, fmt, dithering, perceptual, mipmaps))

        export_image = image.duplicate()
        merged = export_image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        w = merged.get_width()
        h = merged.get_height()

        if fmt in BLOCK_FORMATS and (w % 4 != 0 or h % 4 != 0):
            export_image.delete()
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error(
                    "Dimensions must be divisible by 4 for block compression.\n"
                    "Current: {}x{}, resize to: {}x{}".format(
                        w, h, ((w + 3) // 4) * 4, ((h + 3) // 4) * 4)))

        buffer = merged.get_buffer()
        rect = Gegl.Rectangle()
        rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
        rgba = buffer.get(rect, 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.CLAMP)

        compressor = compress_for_tex(dither=dithering, perceptual=perceptual)
        tex = rgba_to_tex_data(bytes(rgba), w, h, fmt,
                               mipmaps=mipmaps, compressor=compressor)
        tex.write(path)
        _log_msg("TEX written: {} bytes".format(os.path.getsize(path)))

        export_image.delete()

        return Gimp.ValueArray.new_from_values([
            GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS)
        ])

    except Exception as e:
        _log_msg("ERROR: {}".format(e))
        import traceback
        traceback.print_exc()
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(e)))


# ============================================================================
# Plugin class
# ============================================================================

class TexPlugin(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['file-tex-load', 'file-tex-export', 'file-tex-export-options']

    def do_create_procedure(self, name):
        _log_msg("do_create_procedure: {}".format(name))

        if name == 'file-tex-load':
            procedure = Gimp.LoadProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, load_tex, None)
            procedure.set_menu_label("League of Legends TEX")
            procedure.set_documentation(
                "Load League of Legends .tex texture files",
                "Loads DXT1/DXT5/BC5/BC7/BGRA8 textures", name)
            procedure.set_extensions("tex")
            procedure.set_attribution("LtMAO Team", "LtMAO Team", "2025")
            return procedure

        elif name == 'file-tex-export':
            procedure = Gimp.ExportProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, False,
                export_tex, None)
            procedure.set_menu_label("League of Legends TEX")
            procedure.set_documentation(
                "Export as .tex (default settings)",
                "Quick export with last-used settings (default: DXT5 + dithering)", name)
            procedure.set_image_types("*")
            procedure.set_extensions("tex")
            procedure.set_attribution("LtMAO Team", "LtMAO Team", "2025")
            return procedure

        elif name == 'file-tex-export-options':
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN,
                export_tex_options, None)
            procedure.set_menu_label("Export as .tex (options)...")
            procedure.set_documentation(
                "Export as .tex with compression options",
                "Choose format, dithering, error metric, and mipmaps",
                "https://github.com/LeagueToolkit/Gimp-Tex-Plugin#export-options")
            procedure.set_image_types("*")
            procedure.add_menu_path("<Image>/File")
            procedure.set_attribution("LtMAO Team", "LtMAO Team", "2025")
            return procedure

        return None


Gimp.main(TexPlugin.__gtype__, sys.argv)
