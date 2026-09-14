#!/usr/bin/env python3
"""FFmpeg Professional Studio Wrapper — GTK4 Version

A modular, high-performance GUI wrapper for FFmpeg built with Python 3 + PyGObject (GTK4).
Features Two-Stage GPU Chunk Concatenation, automatic hardware detection (VAAPI, AMF, NVENC),
stream-copy remuxing, batch queue transcoding, and MediaInfo diagnostics.
"""
__version__ = "3.0.4"

import gi
import warnings

# Suppress GTK 4.10+ ComboBox deprecation warnings in console
warnings.filterwarnings("ignore", category=DeprecationWarning)

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio, Pango

import json
import os
import re
import sys
import time
import shutil
import signal
import tempfile
import subprocess
import threading

# ─── Constants & Settings ───────────────────────────────────────────────────

SETTINGS_DIR = os.path.expanduser("~/.config/ffmpeg-gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "InputMode": "Single File (Encode / Trim / Remux)",
    "OutputDir": os.path.expandvars("$HOME/Videos"),
    "OutputName": "output.mp4",
    "Container": "mp4",
    "HwBackend": "Auto-Detect",
    "HwDevice": "",
    "FullHwAccel": True,
    "VideoCodec": "copy",
    "RateControl": "CRF",
    "CrfValue": 23,
    "VideoBitrate": "4500k",
    "Preset": "medium",
    "Resolution": "Original",
    "Framerate": "Original",
    "PixelFormat": "Auto (Default)",
    "Threads": "Auto",
    "EnableTwoPass": False,
    "AudioCodec": "copy",
    "AudioBitrate": "192k",
    "AudioChannels": "Original",
    "AudioSampleRate": "Original",
    "AudioFilter": "None",
    "AudioStreamMap": "All Audio Tracks",
    "SubtitleMode": "Copy All Subtitles",
    "EnableCrop": False,
    "CropValue": "",
    "EnableTrim": False,
    "TrimStart": "00:00:00",
    "TrimEnd": "",
    "AudioOnly": False,
    "CustomArgs": "",
}

CONTAINERS = ["mp4", "mkv", "webm", "mov", "ts", "avi", "flv", "mp3", "m4a", "flac", "wav", "ogg"]

AUDIO_CODECS = [
    ("Direct Stream Copy (No Re-encoding)", "copy"),
    ("AAC (Advanced Audio Coding)", "aac"),
    ("Opus (Interactive & Music)", "libopus"),
    ("MP3 (LAME)", "libmp3lame"),
    ("FLAC (Lossless)", "flac"),
    ("AC-3 (Dolby Digital)", "ac3"),
    ("E-AC-3 (Dolby Digital Plus)", "eac3"),
    ("Vorbis", "libvorbis"),
    ("PCM 16-bit (Lossless WAV)", "pcm_s16le"),
    ("Disable Audio (Mute)", "none"),
]

AUDIO_MAP_OPTIONS = ["All Audio Tracks (-map 0:a?)", "Primary Audio Track Only (-map 0:a:0?)"]
SUBTITLE_OPTIONS = ["Copy All Subtitles (-c:s copy)", "Strip All Subtitles (-sn)", "Burn-in First Subtitle Track (Hardsub)"]
RESOLUTIONS = ["Original", "3840x2160 (4K)", "2560x1440 (2K QHD)", "1920x1080 (1080p FHD)", "1280x720 (720p HD)", "854x480 (480p SD)", "Custom"]
FRAMERATES = ["Original", "60", "59.94", "50", "30", "29.97", "25", "24", "23.976", "Custom"]
PIXEL_FORMATS = ["Auto (Default)", "yuv420p (Max Compatibility)", "yuv420p10le (10-bit)", "yuv444p (4:4:4)", "nv12 (Hardware Default)"]
AUDIO_BITRATES = ["Auto", "64k", "96k", "128k", "160k", "192k", "256k", "320k"]
AUDIO_SAMPLE_RATES = ["Original", "44100 Hz", "48000 Hz", "96000 Hz"]
AUDIO_CHANNELS = ["Original", "Stereo (2.0)", "5.1 Surround (6 ch)", "Mono (1.0)"]
AUDIO_FILTERS = [
    ("None", "none"),
    ("Loudness Normalization (EBU R128)", "loudnorm"),
    ("Boost Volume (+3 dB)", "volume=3dB"),
    ("Boost Volume (+6 dB)", "volume=6dB"),
    ("Reduce Volume (-3 dB)", "volume=-3dB"),
]
THREAD_LIMITS = ["Auto", "1", "2", "4", "6", "8", "12", "16"]

APP_CSS = """
.action-btn { padding: 8px 18px; font-weight: bold; }
.monospace-view { font-family: monospace, monospace; font-size: 11px; }
.progress-detail { font-size: 12px; margin-top: 2px; }
.dim-label { opacity: 0.75; font-size: 11px; }
.mediainfo-key { font-weight: bold; opacity: 0.85; }
"""

# ─── UI Factory Helpers ──────────────────────────────────────────────────────

class UI:
    """Widget creation helpers to minimize boilerplate."""

    @staticmethod
    def row(parent, label_text: str, widget: Gtk.Widget, sg: Gtk.SizeGroup = None) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        if sg:
            sg.add_widget(lbl)
        box.append(lbl)
        box.append(widget)
        parent.append(box)
        return box

    @staticmethod
    def combo(items, active: int = 0, changed_cb=None) -> Gtk.ComboBoxText:
        cb = Gtk.ComboBoxText()
        cb.set_hexpand(True)
        for item in items:
            text = item[0] if isinstance(item, tuple) else item
            cb.append_text(text)
        cb.set_active(active)
        if changed_cb:
            cb.connect("changed", changed_cb)
        return cb

    @staticmethod
    def frame(title: str, parent: Gtk.Box = None, spacing: int = 6) -> tuple[Gtk.Frame, Gtk.Box]:
        f = Gtk.Frame(label=f" {title} ")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        f.set_child(box)
        if parent:
            parent.append(f)
        return f, box

    @staticmethod
    def entry(text: str = "", placeholder: str = "", max_chars: int = None, hexpand: bool = True) -> Gtk.Entry:
        e = Gtk.Entry()
        if text:
            e.set_text(text)
        if placeholder:
            e.set_placeholder_text(placeholder)
        if max_chars:
            e.set_max_width_chars(max_chars)
        e.set_hexpand(hexpand)
        return e


# ─── Hardware & Probing Engine ──────────────────────────────────────────────

class HardwareManager:
    """Detects and formats active hardware encoders on the host system."""

    @staticmethod
    def clean_name(raw: str, dev_path: str = "") -> str:
        node = os.path.basename(dev_path) if dev_path else ""
        m_rad = re.search(r"\[Radeon\s+([^\]]+)\]", raw, re.I) or re.search(r"Radeon\s+([A-Za-z0-9\s]+)", raw, re.I)
        if m_rad:
            model = m_rad.group(1).split("/")[0].split("(")[0].strip()
            return f"AMD Radeon {model} ({node})" if node else f"AMD Radeon {model}"
        m_intel = re.search(r"\[(UHD|Iris|Arc|HD)\s*Graphics\s*([^\]]*)\]", raw, re.I)
        if m_intel:
            return f"Intel {m_intel.group(1)} {m_intel.group(2)} ({node})".strip()
        cleaned = re.sub(r"Advanced Micro Devices, Inc\. \[AMD/ATI\]", "AMD", raw)
        cleaned = re.sub(r"Intel Corporation", "Intel", cleaned)
        cleaned = re.sub(r"NVIDIA Corporation", "NVIDIA", cleaned)
        cleaned = re.sub(r"\(rev\s+[a-f0-9]+\)", "", cleaned).strip()
        return f"{cleaned[:26]}… ({node})" if len(cleaned) > 26 and node else f"{cleaned[:28]} ({node})".strip()

    @classmethod
    def probe_dri(cls):
        devs = []
        if not os.path.exists("/dev/dri"):
            return devs
        for entry in sorted(os.listdir("/dev/dri")):
            if entry.startswith("renderD"):
                p = os.path.join("/dev/dri", entry)
                dev_sys = f"/sys/class/drm/{entry}/device"
                raw, vendor = "GPU", ""
                try:
                    if os.path.exists(f"{dev_sys}/vendor"):
                        with open(f"{dev_sys}/vendor") as f:
                            vendor = f.read().strip().lower()
                    if os.path.exists(f"{dev_sys}/uevent"):
                        with open(f"{dev_sys}/uevent") as f:
                            for line in f:
                                if line.startswith("PCI_SLOT_NAME="):
                                    slot = line.split("=")[1].strip()
                                    res = subprocess.run(["lspci", "-s", slot], capture_output=True, text=True, timeout=2)
                                    if res.returncode == 0 and res.stdout:
                                        raw = res.stdout.strip().split(":")[-1].strip()
                                    break
                    if raw == "GPU":
                        raw = "AMD Radeon GPU" if "1002" in vendor else "Intel Graphics" if "8086" in vendor else "NVIDIA GPU"
                except Exception:
                    pass
                devs.append({"path": p, "vendor": vendor, "label": cls.clean_name(raw, p)})
        return devs

    @classmethod
    def probe_nvidia(cls):
        gpus = []
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    m = re.match(r"GPU (\d+):\s+(.+?)\s+\(UUID:", line)
                    if m:
                        gpus.append({"id": m.group(1), "label": f"GPU {m.group(1)}: {cls.clean_name(m.group(2))}"})
            except Exception:
                pass
        return gpus

    @classmethod
    def detect(cls):
        encoders = set()
        if shutil.which("ffmpeg"):
            try:
                res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=3)
                for line in res.stdout.splitlines():
                    m = re.match(r"\s*[VAFS.][F.][S.][X.][B.][D.]\s+(\S+)", line)
                    if m:
                        encoders.add(m.group(1))
            except Exception:
                pass

        dri_devs = cls.probe_dri()
        nv_gpus = cls.probe_nvidia()
        amd_gpus = [d for d in dri_devs if "1002" in d.get("vendor", "")]
        has_amf_lib = any(os.path.exists(p) for p in ["/usr/lib/libamfrt64.so", "/usr/lib/libamfrt64.so.1", "/usr/share/vulkan/icd.d/amd_pro_icd64.json"])

        backends = {"Stream Copy (Passthrough)": {"devices": [], "codecs": [("Direct Stream Copy (No Re-encoding)", "copy")], "presets": ["none"]}}

        if any(c in encoders for c in ["h264_vaapi", "hevc_vaapi", "av1_vaapi"]) and dri_devs:
            codecs = [("Direct Stream Copy (No Re-encoding)", "copy")]
            for tag, c in [("H.264 (VAAPI)", "h264_vaapi"), ("HEVC (VAAPI)", "hevc_vaapi"), ("AV1 (VAAPI)", "av1_vaapi")]:
                if c in encoders:
                    codecs.append((f"{tag} — {c}", c))
            backends["VAAPI (AMD & Intel Hardware)"] = {"devices": dri_devs, "codecs": codecs, "presets": ["default", "fast", "medium", "slow"]}

        if (any(c in encoders for c in ["h264_amf", "hevc_amf", "av1_amf"]) or has_amf_lib) and (amd_gpus or dri_devs):
            codecs = [("Direct Stream Copy (No Re-encoding)", "copy")]
            for tag, c in [("H.264 (AMF)", "h264_amf"), ("HEVC (AMF)", "hevc_amf"), ("AV1 (AMF)", "av1_amf")]:
                if c in encoders or has_amf_lib:
                    codecs.append((f"{tag} — {c}", c))
            backends["AMD (AMF Hardware)"] = {"devices": amd_gpus or dri_devs, "codecs": codecs, "presets": ["speed", "balanced", "quality"]}

        if any(c in encoders for c in ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]) and nv_gpus:
            codecs = [("Direct Stream Copy (No Re-encoding)", "copy")]
            for tag, c in [("H.264 (NVENC)", "h264_nvenc"), ("HEVC (NVENC)", "hevc_nvenc"), ("AV1 (NVENC)", "av1_nvenc")]:
                if c in encoders:
                    codecs.append((f"{tag} — {c}", c))
            backends["NVIDIA (NVENC Hardware)"] = {"devices": nv_gpus, "codecs": codecs, "presets": ["p1 (fastest)", "p2", "p3", "p4 (medium)", "p5", "p6", "p7 (slowest/best)"]}

        cpu_codecs = [("Direct Stream Copy (No Re-encoding)", "copy")]
        for tag, c in [("H.264 (AVC)", "libx264"), ("H.265 (HEVC)", "libx265"), ("AV1", "libsvtav1"), ("VP9", "libvpx-vp9"), ("Apple ProRes", "prores_ks")]:
            if c in encoders:
                cpu_codecs.append((f"{tag} — {c}", c))
        backends["CPU (Software)"] = {"devices": [], "codecs": cpu_codecs, "presets": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]}

        return backends


# ─── General Helpers & Probing ──────────────────────────────────────────────

def format_seconds(secs: float) -> str:
    secs = max(0.0, secs)
    return f"{int(secs // 3600):02d}:{int((secs % 3600) // 60):02d}:{int(secs % 60):02d}"


def parse_timestamp_to_seconds(ts: str) -> float:
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        if len(parts) == 1 and parts[0]:
            return float(parts[0])
    except ValueError:
        pass
    return 0.0


def probe_file(file_path: str):
    if not shutil.which("ffprobe") or not os.path.isfile(file_path):
        return None
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate,format_name,format_long_name:stream=index,codec_type,codec_name,codec_long_name,profile,width,height,r_frame_rate,pix_fmt,bit_rate,sample_rate,channels,channel_layout",
        "-of", "json", file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return json.loads(res.stdout) if res.returncode == 0 else None
    except Exception:
        return None


def copy_to_clipboard(text: str) -> bool:
    display = Gdk.Display.get_default()
    if display:
        try:
            clipboard = display.get_clipboard()
            if hasattr(clipboard, "set"):
                clipboard.set(text)
            elif hasattr(clipboard, "set_text"):
                clipboard.set_text(text)
        except Exception:
            pass
    for bin_name, args in [("wl-copy", ["wl-copy"]), ("xclip", ["xclip", "-selection", "clipboard"]), ("xsel", ["xsel", "--clipboard", "--input"])]:
        if shutil.which(bin_name):
            try:
                subprocess.run(args, input=text, text=True, timeout=1)
                return True
            except Exception:
                pass
    return True


# ─── MediaInfo Generator & Dialog ───────────────────────────────────────────

def build_mediainfo_text(info: dict, file_path: str) -> str:
    if not info:
        return "No MediaInfo Available."
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    lines = [
        "General",
        f"Complete name                            : {file_path}",
        f"Format                                   : {fmt.get('format_long_name', fmt.get('format_name', 'Unknown'))}",
        f"File size                                : {float(fmt.get('size', 0)) / (1024*1024):.2f} MiB",
        f"Duration                                 : {format_seconds(float(fmt.get('duration', 0)))}",
        f"Writing application                      : FFmpeg Studio Pro",
        ""
    ]
    for s in streams:
        c_type = s.get("codec_type", "").capitalize()
        lines.append(c_type)
        lines.append(f"Format                                   : {s.get('codec_long_name', s.get('codec_name', 'Unknown'))}")
        if s.get("profile"):
            lines.append(f"Format profile                           : {s.get('profile')}")
        if c_type == "Video":
            lines.append(f"Width x Height                           : {s.get('width')} x {s.get('height')} pixels")
            lines.append(f"Color space                              : {s.get('pix_fmt', 'Unknown')}")
        elif c_type == "Audio":
            lines.append(f"Channels                                 : {s.get('channels')} channels ({s.get('channel_layout', '')})")
            lines.append(f"Sampling rate                            : {float(s.get('sample_rate', 0))/1000:.1f} kHz")
        if s.get("bit_rate"):
            lines.append(f"Bit rate                                 : {round(float(s['bit_rate'])/1000):,} kb/s")
        lines.append("")
    return "\n".join(lines)


class MediaInfoDialog(Gtk.Window):
    def __init__(self, parent_win, output_path: str, elapsed: float):
        super().__init__()
        self.set_title("Conversion Complete — MediaInfo")
        self.set_transient_for(parent_win)
        self.set_modal(True)
        self.set_default_size(580, 620)

        self._path = output_path
        self._info = probe_file(output_path) or {}
        self._text = build_mediainfo_text(self._info, output_path)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(12)
        self.set_child(box)

        fmt = self._info.get("format", {})
        size_mb = float(fmt.get("size", 0)) / (1024 * 1024)
        lbl = Gtk.Label()
        lbl.set_use_markup(True)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_markup(
            f"<span foreground='#26a269' size='large'><b>✔ Conversion Finished Successfully</b></span>\n"
            f"<span size='small' opacity='0.8'>File: {os.path.basename(output_path)}  │  Size: {size_mb:.2f} MiB  │  Time: {format_seconds(elapsed)}</span>"
        )
        box.append(lbl)

        nb = Gtk.Notebook()
        nb.set_vexpand(True)
        box.append(nb)

        # Tab 1: Structured Grid
        sc_grid = Gtk.ScrolledWindow()
        sc_grid.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        grid_box.set_margin_top(6)
        sc_grid.set_child(grid_box)
        nb.append_page(sc_grid, Gtk.Label(label="Structured"))

        f_gen, b_gen = UI.frame("General", grid_box)
        grid = Gtk.Grid(row_spacing=4, column_spacing=12)
        b_gen.append(grid)
        self._add_row(grid, 0, "Format", fmt.get("format_long_name", "N/A"))
        self._add_row(grid, 1, "Duration", format_seconds(float(fmt.get("duration", 0))))
        self._add_row(grid, 2, "Size", f"{size_mb:.2f} MiB")

        for s in self._info.get("streams", []):
            ct = s.get("codec_type", "").capitalize()
            f_s, b_s = UI.frame(f"{ct} Stream", grid_box)
            g_s = Gtk.Grid(row_spacing=4, column_spacing=12)
            b_s.append(g_s)
            self._add_row(g_s, 0, "Codec", s.get("codec_long_name", s.get("codec_name", "N/A")))
            if ct == "Video":
                self._add_row(g_s, 1, "Resolution", f"{s.get('width')} x {s.get('height')}")
                self._add_row(g_s, 2, "Color Space", s.get("pix_fmt", "N/A"))
            elif ct == "Audio":
                self._add_row(g_s, 1, "Channels", f"{s.get('channels')} ({s.get('channel_layout', '')})")
                self._add_row(g_s, 2, "Sample Rate", f"{float(s.get('sample_rate', 0))/1000:.1f} kHz")

        # Tab 2: Text Report
        sc_text = Gtk.ScrolledWindow()
        sc_text.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        tv = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, left_margin=8, right_margin=8, top_margin=8)
        tv.get_buffer().set_text(self._text)
        sc_text.set_child(tv)
        nb.append_page(sc_text, Gtk.Label(label="MediaInfo Text"))

        # Actions
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        box.append(actions)

        btn_copy = Gtk.Button(label="Copy MediaInfo")
        btn_copy.connect("clicked", lambda b: (copy_to_clipboard(self._text), b.set_label("Copied!"), GLib.timeout_add(1500, lambda: (b.set_label("Copy MediaInfo"), False))))
        actions.append(btn_copy)

        btn_dir = Gtk.Button(label="Open Folder")
        btn_dir.connect("clicked", lambda b: subprocess.Popen(["xdg-open", os.path.dirname(self._path)]))
        actions.append(btn_dir)

        btn_play = Gtk.Button(label="Play Video")
        btn_play.add_css_class("suggested-action")
        btn_play.connect("clicked", lambda b: subprocess.Popen(["xdg-open", self._path]))
        actions.append(btn_play)

        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda b: self.destroy())
        actions.append(btn_close)

    def _add_row(self, grid, idx, k, v):
        k_lbl = Gtk.Label(label=k, halign=Gtk.Align.START)
        k_lbl.add_css_class("mediainfo-key")
        v_lbl = Gtk.Label(label=str(v), halign=Gtk.Align.START, selectable=True)
        grid.attach(k_lbl, 0, idx, 1, 1)
        grid.attach(v_lbl, 1, idx, 1, 1)


# ─── FFmpeg Command Builder ──────────────────────────────────────────────────

class CommandBuilder:
    """Builds optimized FFmpeg argument lists for single files and GPU chunk normalization."""

    @staticmethod
    def _apply_rate_control(args: list, settings: dict, hw_backend: str, v_codec: str):
        mode = settings.get("RateControl", "CRF")
        crf = str(settings.get("CrfValue", 23))
        br = settings.get("VideoBitrate", "4500k").strip() or "4500k"
        num_br = int(re.sub(r"[^\d]", "", br) or "4500")

        if mode == "CRF":
            if "NVENC" in hw_backend:
                args.extend(["-rc:v", "vbr", "-cq:v", crf, "-b:v", "0"])
            elif "VAAPI" in hw_backend:
                args.extend(["-rc_mode", "CQP", "-qp", crf])
            elif "AMF" in hw_backend:
                args.extend(["-rc", "0", "-qp_b", crf, "-qp_i", crf, "-qp_p", crf])
            else:
                args.extend(["-crf", crf])
        elif mode in ("CBR", "VBR"):
            if "AMF" in hw_backend:
                args.extend(["-rc", "cbr" if mode == "CBR" else "vbr_latency", "-b:v", br])
            else:
                buf = f"{num_br * 2}k"
                maxr = br if mode == "CBR" else f"{int(num_br * 1.5)}k"
                args.extend(["-b:v", br, "-maxrate", maxr, "-bufsize", buf])
                if mode == "CBR":
                    args.extend(["-minrate", br])
        elif mode == "Lossless":
            if "NVENC" in hw_backend:
                args.extend(["-tune", "lossless"])
            elif "libx264" in v_codec or "libx265" in v_codec:
                args.extend(["-crf", "0"])

    @staticmethod
    def _apply_preset(args: list, settings: dict, hw_backend: str):
        preset = settings.get("Preset", "").split()[0]
        if preset and preset not in ("none", "default"):
            if "NVENC" in hw_backend:
                args.extend(["-preset", preset])
            elif "AMF" in hw_backend:
                args.extend(["-quality", preset])
            elif "VAAPI" in hw_backend:
                args.extend(["-compression_level", "1" if preset == "fast" else "7"])
            else:
                args.extend(["-preset", preset])

    @classmethod
    def build_chunk_encode(cls, settings: dict, src_file: str, out_chunk: str, target_w: int, target_h: int, target_fps: str) -> list:
        """Stage 1: Pure GPU normalization of an individual video segment into temporary storage."""
        args = ["ffmpeg", "-hide_banner", "-y"]
        hw = settings.get("HwBackend", "CPU (Software)")
        dev = settings.get("HwDevice", "") or "/dev/dri/renderD128"
        v_codec = settings.get("VideoCodec", "libx264")

        # Full hardware decode pipeline on GPU VCN
        if "VAAPI" in hw:
            args.extend(["-vaapi_device", dev, "-hwaccel", "vaapi", "-hwaccel_device", dev, "-hwaccel_output_format", "vaapi"])
        elif "NVENC" in hw:
            args.extend(["-hwaccel", "cuda"])
            if dev.startswith("GPU"):
                args.extend(["-hwaccel_device", re.sub(r"[^\d]", "", dev)])
        elif "AMF" in hw:
            args.extend(["-hwaccel", "auto"])

        args.extend(["-i", src_file])

        # GPU VCN scale filter
        if "VAAPI" in hw:
            args.extend(["-vf", f"scale_vaapi=w={target_w}:h={target_h}"])
        else:
            args.extend(["-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1"])

        args.extend(["-r", target_fps, "-c:v", v_codec])
        cls._apply_rate_control(args, settings, hw, v_codec)
        cls._apply_preset(args, settings, hw)

        # Audio: Honor user's choice instead of forcing AAC
        a_codec = settings.get("AudioCodec", "copy")
        if a_codec == "none":
            args.append("-an")
        elif a_codec == "copy":
            args.extend(["-c:a", "copy"])
        else:
            args.extend(["-c:a", a_codec, "-b:a", settings.get("AudioBitrate", "192k"), "-ar", "48000", "-ac", "2"])

        args.append(out_chunk)
        return args

    @classmethod
    def build_single(cls, settings: dict, in_file: str, out_file: str, pass_num: int = 0, pass_log: str = None) -> list:
        """Builds standard single-file encode command."""
        args = ["ffmpeg", "-hide_banner", "-y"]
        hw = settings.get("HwBackend", "CPU (Software)")
        dev = settings.get("HwDevice", "") or "/dev/dri/renderD128"
        v_codec = settings.get("VideoCodec", "copy")
        full_hw = settings.get("FullHwAccel", True)
        is_copy = (v_codec == "copy")

        if not is_copy:
            if "VAAPI" in hw:
                args.extend(["-vaapi_device", dev])
                if full_hw:
                    args.extend(["-hwaccel", "vaapi", "-hwaccel_device", dev, "-hwaccel_output_format", "vaapi"])
            elif "NVENC" in hw and full_hw:
                args.extend(["-hwaccel", "cuda"])
                if dev.startswith("GPU"):
                    args.extend(["-hwaccel_device", re.sub(r"[^\d]", "", dev)])
            elif "AMF" in hw and full_hw:
                args.extend(["-hwaccel", "auto"])

        t = settings.get("Threads", "Auto")
        if t != "Auto":
            args.extend(["-threads", t])

        if settings.get("EnableTrim", False):
            s, e = settings.get("TrimStart", "").strip(), settings.get("TrimEnd", "").strip()
            if s:
                args.extend(["-ss", s])
            if e:
                args.extend(["-to", e])

        args.extend(["-i", in_file])

        # Explicit Stream Mapping (prevents accidental dropping of Opus or other tracks)
        amap = settings.get("AudioStreamMap", "All Audio Tracks")
        if "Primary" in amap:
            args.extend(["-map", "0:v:0?", "-map", "0:a:0?"])
        else:
            args.extend(["-map", "0:v?", "-map", "0:a?"])

        # Subtitles Handling
        sub_mode = settings.get("SubtitleMode", "Copy All Subtitles")
        if "Strip" in sub_mode:
            args.append("-sn")
        elif "Copy" in sub_mode:
            args.extend(["-map", "0:s?", "-c:s", "copy"])

        if settings.get("AudioOnly", False):
            args.append("-vn")
        else:
            if is_copy:
                args.extend(["-c:v", "copy"])
            else:
                args.extend(["-c:v", v_codec])
                cls._apply_preset(args, settings, hw)
                cls._apply_rate_control(args, settings, hw, v_codec)

                vf = []
                has_sw_filters = bool(settings.get("EnableCrop", False) and settings.get("CropValue", "").strip()) or ("Burn-in" in sub_mode)

                if "VAAPI" in hw and full_hw and not has_sw_filters:
                    res = settings.get("Resolution", "Original")
                    if res != "Original":
                        m = re.search(r"(\d+)x(\d+)", res)
                        if m:
                            vf.append(f"scale_vaapi=w={m.group(1)}:h={m.group(2)}")
                else:
                    if settings.get("EnableCrop", False) and settings.get("CropValue", "").strip():
                        vf.append(f"crop={settings['CropValue'].strip()}")
                    res = settings.get("Resolution", "Original")
                    if res != "Original":
                        m = re.search(r"(\d+)x(\d+)", res)
                        if m:
                            vf.append(f"scale={m.group(1)}:{m.group(2)}:force_original_aspect_ratio=decrease,pad={m.group(1)}:{m.group(2)}:(ow-iw)/2:(oh-ih)/2")
                    if "VAAPI" in hw:
                        vf.append("format=nv12,hwupload")

                if vf:
                    args.extend(["-vf", ",".join(vf)])

                fps = settings.get("Framerate", "Original")
                if fps != "Original":
                    args.extend(["-r", fps])

        # Audio Stream Configuration
        if pass_num == 1:
            args.append("-an")
        else:
            a_codec = settings.get("AudioCodec", "copy")
            if a_codec == "none":
                args.append("-an")
            elif a_codec == "copy":
                args.extend(["-c:a", "copy"])
            else:
                args.extend(["-c:a", a_codec])
                br = settings.get("AudioBitrate", "Auto")
                if br != "Auto":
                    args.extend(["-b:a", br])
                sr = settings.get("AudioSampleRate", "Original")
                if sr != "Original":
                    m_sr = re.search(r"(\d+)", sr)
                    if m_sr:
                        args.extend(["-ar", m_sr.group(1)])
                ch = settings.get("AudioChannels", "Original")
                if "Stereo" in ch:
                    args.extend(["-ac", "2"])
                elif "Mono" in ch:
                    args.extend(["-ac", "1"])
                elif "5.1" in ch:
                    args.extend(["-ac", "6"])
                flt = settings.get("AudioFilter", "none")
                if flt != "none":
                    args.extend(["-af", flt])

        if pass_num in (1, 2) and pass_log:
            args.extend(["-pass", str(pass_num), "-passlogfile", pass_log])
            if pass_num == 1:
                args.extend(["-f", "null", "/dev/null" if os.name != "nt" else "NUL"])
                return args

        cont = settings.get("Container", "mp4").lower()
        if cont in ("mp4", "mov"):
            args.extend(["-movflags", "+faststart"])

        extra = settings.get("CustomArgs", "").strip()
        if extra:
            args.extend(extra.split())

        args.append(out_file)
        return args


# ─── Main Window ─────────────────────────────────────────────────────────────

class FFmpegStudioWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("FFmpeg Studio")
        self.set_default_size(660, 880)

        self._process = None
        self._is_paused = False
        self._stopping_graceful = False
        self._source_duration = 0.0
        self._batch_files = []
        self._last_progress_log = 0.0
        self._hw_map = HardwareManager.detect()

        self._input_dialog = None
        self._out_dialog = None
        self._q_dialog = None

        self._build_ui()
        self._populate_hardware()
        self._load_settings()

        self.connect("close-request", self._on_close_request)

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.set_margin_start(10)
        root.set_margin_end(10)
        root.set_margin_top(6)
        root.set_margin_bottom(8)
        self.set_child(root)

        # Header
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="<b>FFmpeg Studio</b>", use_markup=True, halign=Gtk.Align.START)
        self._hw_badge = Gtk.Label(hexpand=True, halign=Gtk.Align.END, use_markup=True)
        hdr.append(title)
        hdr.append(self._hw_badge)
        root.append(hdr)

        # Scrolled Notebook
        sc = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        root.append(sc)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sc.set_child(content)

        nb = Gtk.Notebook()
        content.append(nb)

        # Tabs
        self._build_tab_source(nb)
        self._build_tab_video(nb)
        self._build_tab_audio(nb)
        self._build_tab_output(nb)

        # Progress Section
        p_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self._p_bar = Gtk.ProgressBar(show_text=True, text="0.0%")
        self._p_detail = Gtk.Label(use_markup=True, halign=Gtk.Align.CENTER, label="<i>Ready</i>")
        p_box.append(self._p_bar)
        p_box.append(self._p_detail)
        content.append(p_box)

        # Actions
        act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
        content.append(act_box)

        self._btn_start = Gtk.Button(label="Start Processing", css_classes=["suggested-action", "action-btn"])
        self._btn_start.connect("clicked", self._on_start_clicked)
        act_box.append(self._btn_start)

        self._btn_pause = Gtk.Button(label="Pause", sensitive=False, css_classes=["action-btn"])
        self._btn_pause.connect("clicked", self._on_pause_clicked)
        act_box.append(self._btn_pause)

        self._btn_cancel = Gtk.Button(label="Cancel", sensitive=False, css_classes=["destructive-action", "action-btn"])
        self._btn_cancel.connect("clicked", self._on_cancel_clicked)
        act_box.append(self._btn_cancel)

        btn_copy = Gtk.Button(label="Copy Command")
        btn_copy.connect("clicked", self._on_copy_cmd)
        act_box.append(btn_copy)

        # Diagnostics Terminal
        _, b_log = UI.frame("Diagnostics & Output Terminal", content)
        sc_log = Gtk.ScrolledWindow(min_content_height=140)
        sc_log.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._tv_log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, left_margin=6, right_margin=6)
        self._log_buf = self._tv_log.get_buffer()
        self._log_mark = self._log_buf.create_mark("end_mark", self._log_buf.get_end_iter(), False)
        sc_log.set_child(self._tv_log)
        b_log.append(sc_log)

    def _build_tab_source(self, nb):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6)
        nb.append_page(box, Gtk.Label(label="Source & Queue"))

        _, b_mode = UI.frame("Mode", box)
        self._mode_combo = UI.combo(["Single File (Encode / Trim / Remux)", "Batch Queue (Transcode Multiple)", "Merge Multiple Files (Concat)"], changed_cb=self._on_mode_changed)
        b_mode.append(self._mode_combo)

        # Single Frame
        self._f_single, b_s = UI.frame("Input Media File", box)
        r_file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        r_file.append(Gtk.Label(label="Source:"))
        self._in_entry = UI.entry(placeholder="Select video/audio file...")
        btn_browse = Gtk.Button(label="Browse")
        btn_browse.connect("clicked", self._on_browse_input)
        btn_probe = Gtk.Button(label="Probe")
        btn_probe.connect("clicked", self._on_probe_input)
        r_file.append(self._in_entry)
        r_file.append(btn_browse)
        r_file.append(btn_probe)
        b_s.append(r_file)

        self._lbl_probe = Gtk.Label(label="<i>No media probed yet</i>", use_markup=True, halign=Gtk.Align.START, css_classes=["dim-label"])
        b_s.append(self._lbl_probe)

        # Trim & Crop rows
        r_trim = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._chk_trim = Gtk.CheckButton(label="Trim:")
        self._trim_start = UI.entry(text="00:00:00", max_chars=10, hexpand=False)
        self._trim_end = UI.entry(placeholder="00:00:00", max_chars=10, hexpand=False)
        self._trim_start.set_sensitive(False)
        self._trim_end.set_sensitive(False)
        self._chk_trim.connect("toggled", lambda c: (self._trim_start.set_sensitive(c.get_active()), self._trim_end.set_sensitive(c.get_active())))
        r_trim.append(self._chk_trim)
        r_trim.append(self._trim_start)
        r_trim.append(Gtk.Label(label="to"))
        r_trim.append(self._trim_end)
        b_s.append(r_trim)

        r_crop = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._chk_crop = Gtk.CheckButton(label="Crop:")
        self._crop_entry = UI.entry(placeholder="w:h:x:y", max_chars=12, hexpand=True)
        self._crop_entry.set_sensitive(False)
        self._chk_crop.connect("toggled", lambda c: self._crop_entry.set_sensitive(c.get_active()))
        btn_crop = Gtk.Button(label="Detect Black Bars")
        btn_crop.connect("clicked", self._on_detect_crop)
        r_crop.append(self._chk_crop)
        r_crop.append(self._crop_entry)
        r_crop.append(btn_crop)
        b_s.append(r_crop)

        # Multi-File Queue Frame
        self._f_queue, b_q = UI.frame("Multi-File Queue", box)
        self._f_queue.set_visible(False)
        sc_q = Gtk.ScrolledWindow(min_content_height=120)
        sc_q.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._lb_queue = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        sc_q.set_child(self._lb_queue)
        b_q.append(sc_q)

        r_qact = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for lbl, cb in [("Add...", self._on_q_add), ("Remove", self._on_q_rm), ("Up", self._on_q_up), ("Down", self._on_q_dn), ("Clear", self._on_q_clr)]:
            b = Gtk.Button(label=lbl)
            b.connect("clicked", cb)
            r_qact.append(b)
        b_q.append(r_qact)

    def _build_tab_video(self, nb):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6)
        nb.append_page(box, Gtk.Label(label="Video & Hardware"))
        _, b_v = UI.frame("Hardware Acceleration & Video Encoding", box)
        sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        self._hw_combo = UI.combo([], changed_cb=self._on_hw_changed)
        UI.row(b_v, "Acceleration:", self._hw_combo, sg)

        self._hw_dev_combo = UI.combo([])
        self._r_dev = UI.row(b_v, "GPU Device:", self._hw_dev_combo, sg)

        self._chk_fullhw = Gtk.CheckButton(label="Full Hardware Acceleration (Decode + Encode on GPU)", active=True)
        b_v.append(self._chk_fullhw)

        self._vcodec_combo = UI.combo([], changed_cb=self._check_remux_state)
        UI.row(b_v, "Video Codec:", self._vcodec_combo, sg)

        self._vparams_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        b_v.append(self._vparams_box)

        # Rate Control
        r_rc = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._rc_combo = UI.combo(["CRF (Constant Quality)", "VBR (Variable Bitrate)", "CBR (Constant Bitrate)", "Lossless"], changed_cb=self._on_rc_changed)
        self._crf_spin = Gtk.SpinButton.new_with_range(0, 51, 1)
        self._crf_spin.set_value(23)
        self._vbr_entry = UI.entry(text="4500k", max_chars=8, hexpand=False)
        self._vbr_entry.set_visible(False)
        self._chk_twopass = Gtk.CheckButton(label="2-Pass", visible=False)
        r_rc.append(self._rc_combo)
        r_rc.append(self._crf_spin)
        r_rc.append(self._vbr_entry)
        r_rc.append(self._chk_twopass)
        UI.row(self._vparams_box, "Rate Control:", r_rc, sg)

        self._preset_combo = UI.combo([])
        UI.row(self._vparams_box, "Speed Preset:", self._preset_combo, sg)

        self._threads_combo = UI.combo(THREAD_LIMITS)
        UI.row(self._vparams_box, "CPU Threads:", self._threads_combo, sg)

        self._res_combo = UI.combo(RESOLUTIONS)
        UI.row(self._vparams_box, "Resolution:", self._res_combo, sg)

        self._fps_combo = UI.combo(FRAMERATES)
        UI.row(self._vparams_box, "Framerate:", self._fps_combo, sg)

        self._pix_combo = UI.combo(PIXEL_FORMATS)
        UI.row(self._vparams_box, "Pixel Format:", self._pix_combo, sg)

    def _build_tab_audio(self, nb):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6)
        nb.append_page(box, Gtk.Label(label="Audio & Subtitles"))
        _, b_a = UI.frame("Audio & Subtitle Track Management", box)
        sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        self._acodec_combo = UI.combo(AUDIO_CODECS, changed_cb=self._check_remux_state)
        UI.row(b_a, "Audio Codec:", self._acodec_combo, sg)

        self._chk_audonly = Gtk.CheckButton(label="Extract Audio Only (-vn)")
        b_a.append(self._chk_audonly)

        self._aparams_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        b_a.append(self._aparams_box)

        self._abit_combo = UI.combo(AUDIO_BITRATES, active=5)
        UI.row(self._aparams_box, "Bitrate:", self._abit_combo, sg)

        self._srate_combo = UI.combo(AUDIO_SAMPLE_RATES)
        UI.row(self._aparams_box, "Sample Rate:", self._srate_combo, sg)

        self._chan_combo = UI.combo(AUDIO_CHANNELS)
        UI.row(self._aparams_box, "Channels:", self._chan_combo, sg)

        self._afilt_combo = UI.combo(AUDIO_FILTERS)
        UI.row(self._aparams_box, "Volume / Norm:", self._afilt_combo, sg)

        self._amap_combo = UI.combo(AUDIO_MAP_OPTIONS)
        UI.row(b_a, "Track Mapping:", self._amap_combo, sg)

        self._sub_combo = UI.combo(SUBTITLE_OPTIONS)
        UI.row(b_a, "Subtitles:", self._sub_combo, sg)

    def _build_tab_output(self, nb):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6)
        nb.append_page(box, Gtk.Label(label="Output & Container"))
        _, b_o = UI.frame("Destination & Container", box)
        sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        self._cont_combo = UI.combo([c.upper() for c in CONTAINERS])
        UI.row(b_o, "Container:", self._cont_combo, sg)

        r_dir = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._out_dir_entry = UI.entry()
        btn_dir = Gtk.Button(label="Browse")
        btn_dir.connect("clicked", self._on_browse_output)
        r_dir.append(self._out_dir_entry)
        r_dir.append(btn_dir)
        UI.row(b_o, "Output Dir:", r_dir, sg)

        self._out_name_entry = UI.entry(text="output.mp4")
        UI.row(b_o, "File Name:", self._out_name_entry, sg)

        self._custom_entry = UI.entry(placeholder="e.g. -movflags +faststart")
        UI.row(b_o, "Custom Flags:", self._custom_entry, sg)

    # ── Population & Settings ────────────────────────────────────────────

    def _populate_hardware(self):
        self._hw_combo.remove_all()
        for name in self._hw_map:
            self._hw_combo.append_text(name)
        pref = next((b for b in self._hw_map if "VAAPI" in b or "AMF" in b or "NVENC" in b), "CPU (Software)")
        self._hw_combo.set_active(list(self._hw_map.keys()).index(pref))

        tags = []
        for b in self._hw_map:
            for tag in ["VAAPI", "AMF", "NVENC", "CPU"]:
                if tag in b and tag not in tags:
                    tags.append(tag)
        self._hw_badge.set_markup("  │  ".join(f'<span foreground="#26a269" font_weight="bold">{t}</span>' for t in tags))

    def _on_hw_changed(self, combo):
        backend = combo.get_active_text() or "CPU (Software)"
        info = self._hw_map.get(backend, {"devices": [], "codecs": [], "presets": []})

        self._hw_dev_combo.remove_all()
        devs = info.get("devices", [])
        if devs:
            self._r_dev.set_visible(True)
            for d in devs:
                self._hw_dev_combo.append_text(d.get("label", d.get("path", "Device")))
            self._hw_dev_combo.set_active(0)
        else:
            self._r_dev.set_visible(False)

        self._vcodec_combo.remove_all()
        for label, _ in info.get("codecs", []):
            self._vcodec_combo.append_text(label)
        self._vcodec_combo.set_active(0)

        self._preset_combo.remove_all()
        for p in info.get("presets", []):
            self._preset_combo.append_text(p)
        self._preset_combo.set_active(0)

        self._chk_twopass.set_visible("CPU" in backend and ("VBR" in self._rc_combo.get_active_text() or "CBR" in self._rc_combo.get_active_text()))
        self._check_remux_state()

    def _check_remux_state(self, *args):
        v_copy = "Copy" in (self._vcodec_combo.get_active_text() or "")
        a_copy = "Copy" in (self._acodec_combo.get_active_text() or "")
        self._vparams_box.set_sensitive(not v_copy)
        self._chk_fullhw.set_sensitive(not v_copy)
        self._aparams_box.set_sensitive(not a_copy)

    def _on_rc_changed(self, combo):
        txt = combo.get_active_text() or ""
        self._crf_spin.set_visible("CRF" in txt)
        self._vbr_entry.set_visible("VBR" in txt or "CBR" in txt)
        self._chk_twopass.set_visible("CPU" in (self._hw_combo.get_active_text() or "") and ("VBR" in txt or "CBR" in txt))

    def _on_mode_changed(self, combo):
        idx = combo.get_active()
        self._f_single.set_visible(idx == 0)
        self._f_queue.set_visible(idx in (1, 2))
        self._f_queue.set_label(" Batch Queue (Multiple Files) " if idx == 1 else " Merge Queue (Concat) ")

    def _gather_settings(self):
        s = dict(DEFAULT_SETTINGS)
        s["InputMode"] = self._mode_combo.get_active_text() or "Single File (Encode / Trim / Remux)"
        s["InputFile"] = self._in_entry.get_text().strip()
        s["OutputDir"] = self._out_dir_entry.get_text().strip() or os.path.expanduser("~/Videos")
        s["OutputName"] = self._out_name_entry.get_text().strip() or "output.mp4"
        s["Container"] = self._cont_combo.get_active_text() or "MP4"
        s["HwBackend"] = self._hw_combo.get_active_text() or "CPU (Software)"

        dev_lbl = self._hw_dev_combo.get_active_text() or ""
        m = re.search(r"(renderD\d+)", dev_lbl)
        s["HwDevice"] = f"/dev/dri/{m.group(1)}" if m else dev_lbl.split(":")[0].strip() if dev_lbl.startswith("GPU") else ""
        s["FullHwAccel"] = self._chk_fullhw.get_active()

        raw_vc = self._vcodec_combo.get_active_text() or "copy"
        s["VideoCodec"] = raw_vc.split("—")[1].strip() if "—" in raw_vc else "copy"
        s["RateControl"] = (self._rc_combo.get_active_text() or "CRF").split()[0].strip()
        s["CrfValue"] = int(self._crf_spin.get_value())
        s["VideoBitrate"] = self._vbr_entry.get_text().strip() or "4500k"
        s["Preset"] = self._preset_combo.get_active_text() or "medium"
        s["Threads"] = self._threads_combo.get_active_text() or "Auto"
        s["EnableTwoPass"] = self._chk_twopass.get_active()
        s["Resolution"] = self._res_combo.get_active_text() or "Original"
        s["Framerate"] = self._fps_combo.get_active_text() or "Original"
        s["PixelFormat"] = self._pix_combo.get_active_text() or "Auto (Default)"

        ac_idx = self._acodec_combo.get_active()
        s["AudioCodec"] = AUDIO_CODECS[ac_idx][1] if 0 <= ac_idx < len(AUDIO_CODECS) else "copy"
        s["AudioBitrate"] = self._abit_combo.get_active_text() or "Auto"
        s["AudioSampleRate"] = self._srate_combo.get_active_text() or "Original"
        s["AudioChannels"] = self._chan_combo.get_active_text() or "Original"
        af_idx = self._afilt_combo.get_active()
        s["AudioFilter"] = AUDIO_FILTERS[af_idx][1] if 0 <= af_idx < len(AUDIO_FILTERS) else "none"

        s["AudioStreamMap"] = self._amap_combo.get_active_text() or "All Audio Tracks"
        s["SubtitleMode"] = self._sub_combo.get_active_text() or "Copy All Subtitles"
        s["AudioOnly"] = self._chk_audonly.get_active()
        s["EnableTrim"] = self._chk_trim.get_active()
        s["TrimStart"] = self._trim_start.get_text().strip()
        s["TrimEnd"] = self._trim_end.get_text().strip()
        s["EnableCrop"] = self._chk_crop.get_active()
        s["CropValue"] = self._crop_entry.get_text().strip()
        s["CustomArgs"] = self._custom_entry.get_text().strip()
        return s

    def _set_combo_by_text(self, combo, val, items_list=None):
        if not val:
            return
        m = combo.get_model()
        if not m:
            return

        # Map short codec identifiers to display labels if tuple list provided
        if items_list:
            for item in items_list:
                if isinstance(item, tuple) and item[1] == val:
                    val = item[0]
                    break

        val_lower = val.lower()
        for i, row in enumerate(m):
            txt = row[0] or ""
            if txt == val or txt.lower().startswith(val_lower) or val_lower in txt.lower():
                combo.set_active(i)
                return

    def _load_settings(self):
        s = dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE) as f:
                    s.update(json.load(f))
            except Exception:
                pass
        self._in_entry.set_text("")
        self._out_dir_entry.set_text(s.get("OutputDir", DEFAULT_SETTINGS["OutputDir"]))
        self._out_name_entry.set_text(s.get("OutputName", DEFAULT_SETTINGS["OutputName"]))
        self._custom_entry.set_text(s.get("CustomArgs", ""))

        c_upper = s.get("Container", "mp4").upper()
        if c_upper in CONTAINERS:
            self._cont_combo.set_active(CONTAINERS.index(c_upper.lower()))

        self._set_combo_by_text(self._hw_combo, s.get("HwBackend"))
        self._set_combo_by_text(self._hw_dev_combo, s.get("HwDevice"))
        self._chk_fullhw.set_active(s.get("FullHwAccel", True))
        self._set_combo_by_text(self._vcodec_combo, s.get("VideoCodec", "copy"))
        self._set_combo_by_text(self._rc_combo, s.get("RateControl", "CRF"))
        self._crf_spin.set_value(s.get("CrfValue", 23))
        self._vbr_entry.set_text(s.get("VideoBitrate", "4500k"))
        self._set_combo_by_text(self._preset_combo, s.get("Preset", "medium"))
        self._set_combo_by_text(self._threads_combo, s.get("Threads", "Auto"))
        self._set_combo_by_text(self._res_combo, s.get("Resolution", "Original"))
        self._set_combo_by_text(self._fps_combo, s.get("Framerate", "Original"))
        self._set_combo_by_text(self._pix_combo, s.get("PixelFormat", "Auto (Default)"))

        # Correctly restore audio codec
        self._set_combo_by_text(self._acodec_combo, s.get("AudioCodec", "copy"), AUDIO_CODECS)
        self._set_combo_by_text(self._abit_combo, s.get("AudioBitrate", "192k"))
        self._set_combo_by_text(self._srate_combo, s.get("AudioSampleRate", "Original"))
        self._set_combo_by_text(self._chan_combo, s.get("AudioChannels", "Original"))
        self._set_combo_by_text(self._afilt_combo, s.get("AudioFilter", "None"), AUDIO_FILTERS)
        self._set_combo_by_text(self._amap_combo, s.get("AudioStreamMap"))
        self._set_combo_by_text(self._sub_combo, s.get("SubtitleMode"))

        self._chk_audonly.set_active(s.get("AudioOnly", False))
        self._chk_trim.set_active(s.get("EnableTrim", False))
        self._trim_start.set_text(s.get("TrimStart", "00:00:00"))
        self._trim_end.set_text(s.get("TrimEnd", ""))
        self._chk_crop.set_active(s.get("EnableCrop", False))
        self._crop_entry.set_text(s.get("CropValue", ""))
        self._check_remux_state()

    def _save_settings(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        try:
            s = self._gather_settings()
            s.pop("InputFile", None)
            with open(SETTINGS_FILE, "w") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

    def _on_close_request(self, win):
        self._save_settings()
        if self._process and self._process.poll() is None:
            try:
                self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        return False

    # ── Actions & Execution ──────────────────────────────────────────────

    def _on_copy_cmd(self, btn):
        s = self._gather_settings()
        out = os.path.join(s["OutputDir"], s["OutputName"])
        args = CommandBuilder.build_single(s, s["InputFile"] or "input.mp4", out)
        cmd = " ".join(f'"{a}"' if " " in a else a for a in args)
        copy_to_clipboard(cmd)
        self._append_log(f"[Studio] Copied command to clipboard:\n{cmd}\n\n")

    def _on_pause_clicked(self, btn):
        if not self._process or self._process.poll() is not None:
            return
        try:
            if not self._is_paused:
                os.kill(self._process.pid, signal.SIGSTOP)
                self._is_paused = True
                self._btn_pause.set_label("Resume")
                self._p_detail.set_markup("<b>[PAUSED]</b> Process suspended")
                self._append_log("\n[User] Process suspended (SIGSTOP).\n")
            else:
                os.kill(self._process.pid, signal.SIGCONT)
                self._is_paused = False
                self._btn_pause.set_label("Pause")
                self._p_detail.set_markup("<i>Resumed processing...</i>")
                self._append_log("\n[User] Process resumed (SIGCONT).\n")
        except Exception as e:
            self._append_log(f"Pause error: {e}\n")

    def _on_cancel_clicked(self, btn):
        if not self._process or self._process.poll() is not None:
            return
        if not self._stopping_graceful:
            self._stopping_graceful = True
            self._btn_cancel.set_label("Force Kill (SIGKILL)")
            self._append_log("\n[User] Gracefully stopping FFmpeg (flushing buffers)... Click again to Force Kill.\n")
            if self._is_paused:
                try:
                    os.kill(self._process.pid, signal.SIGCONT)
                except Exception:
                    pass
            try:
                self._process.send_signal(signal.SIGINT)
            except Exception:
                self._process.terminate()
        else:
            self._append_log("\n[User] Sending SIGKILL (Force termination)...\n")
            try:
                self._process.kill()
            except Exception:
                pass
            self._btn_cancel.set_sensitive(False)
            self._btn_pause.set_sensitive(False)

    def _on_start_clicked(self, btn):
        s = self._gather_settings()
        mode = s["InputMode"]
        if "Single" in mode and (not s["InputFile"] or not os.path.exists(s["InputFile"])):
            self._append_log("ERROR: Invalid input file specified.\n")
            return
        if ("Batch" in mode or "Concat" in mode) and not self._batch_files:
            self._append_log("ERROR: Queue is empty. Please add media files.\n")
            return

        os.makedirs(s["OutputDir"], exist_ok=True)
        self._save_settings()
        self._clear_log()
        self._btn_start.set_sensitive(False)
        self._btn_cancel.set_sensitive(True)
        self._btn_cancel.set_label("Cancel")
        self._stopping_graceful = False
        self._btn_pause.set_sensitive(True)
        self._btn_pause.set_label("Pause")
        self._is_paused = False

        threading.Thread(target=self._dispatch_job, args=(s,), daemon=True).start()

    # ── Concat Method 1: Two-Stage GPU Normalization Engine ──────────────

    def _get_target_resolution(self, s: dict, first_file: str) -> tuple[int, int]:
        res_opt = s.get("Resolution", "Original")
        if res_opt != "Original":
            m = re.search(r"(\d+)x(\d+)", res_opt)
            if m:
                return int(m.group(1)), int(m.group(2))
        p = probe_file(first_file) or {}
        v = next((st for st in p.get("streams", []) if st.get("codec_type") == "video"), {})
        return (int(v.get("width", 1920)) // 2) * 2, (int(v.get("height", 1080)) // 2) * 2

    def _get_target_fps(self, s: dict, first_file: str) -> str:
        fps_opt = s.get("Framerate", "Original")
        if fps_opt != "Original":
            return fps_opt
        p = probe_file(first_file) or {}
        v = next((st for st in p.get("streams", []) if st.get("codec_type") == "video"), {})
        raw = v.get("r_frame_rate", "60/1")
        if "/" in raw:
            n, d = raw.split("/")
            if float(d) > 0:
                return str(round(float(n) / float(d)))
        return "60"

    def _dispatch_job(self, s: dict):
        mode = s["InputMode"]
        start_time = time.time()
        completed, success = [], True

        if "Single" in mode:
            stem = os.path.splitext(os.path.basename(s["InputFile"]))[0]
            cont = s.get("Container", "mp4").lower()
            out_file = os.path.join(s["OutputDir"], s["OutputName"] if s["OutputName"].endswith(f".{cont}") else f"{stem}.{cont}")
            ok = self._execute_single(s["InputFile"], s, out_file)
            if ok:
                completed.append(out_file)
            else:
                success = False

        elif "Batch" in mode:
            total = len(self._batch_files)
            for idx, fpath in enumerate(self._batch_files, 1):
                GLib.idle_add(self._append_log, f"\n=== [Batch Queue: Item {idx}/{total}] ===\n")
                stem = os.path.splitext(os.path.basename(fpath))[0]
                out_path = os.path.join(s["OutputDir"], f"{stem}_transcoded.{s.get('Container', 'mp4').lower()}")
                ok = self._execute_single(fpath, s, out_path)
                if not ok:
                    success = False
                    break
                completed.append(out_path)

        elif "Concat" in mode:
            cont = s.get("Container", "mp4").lower()
            name = s["OutputName"] if s["OutputName"].endswith(f".{cont}") else f"{s['OutputName']}.{cont}"
            out_file = os.path.join(s["OutputDir"], name)
            v_codec, a_codec = s.get("VideoCodec", "copy"), s.get("AudioCodec", "copy")

            can_copy = (v_codec == "copy" and a_codec == "copy")
            if can_copy:
                codecs = {next((st.get("codec_name") for st in (probe_file(f) or {}).get("streams", []) if st.get("codec_type") == "video"), None) for f in self._batch_files}
                if len(codecs) > 1:
                    GLib.idle_add(self._append_log, f"ERROR: Differing codecs ({codecs}) cannot be stream-copied. Please choose a video encoder (e.g. HEVC or H.264) to merge.\n")
                    GLib.idle_add(self._on_done, False, [], 0)
                    return

                GLib.idle_add(self._append_log, "[Studio] Merging identical streams with Concat Demuxer (Stream Copy)...\n")
                fd, m_file = tempfile.mkstemp(prefix="concat_", suffix=".txt")
                with open(fd, "w") as f:
                    for item in self._batch_files:
                        escaped = item.replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                ok = self._run_proc(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", m_file, "-c", "copy", out_file], s)
                try:
                    os.remove(m_file)
                except Exception:
                    pass
                if ok:
                    completed.append(out_file)
                else:
                    success = False

            else:
                GLib.idle_add(self._append_log, "[Studio] Two-Stage GPU Merge: Normalizing segments...\n")
                tmp_dir = tempfile.mkdtemp(prefix="ff_chunks_")
                chunks = []
                try:
                    tw, th = self._get_target_resolution(s, self._batch_files[0])
                    tfps = self._get_target_fps(s, self._batch_files[0])
                    total = len(self._batch_files)

                    # Stage 1: GPU Transcode
                    for idx, src in enumerate(self._batch_files, 1):
                        c_path = os.path.join(tmp_dir, f"chunk_{idx:03d}.mp4")
                        GLib.idle_add(self._append_log, f"\n[Stage 1/2] GPU Transcoding Segment {idx}/{total}: {os.path.basename(src)}...\n")
                        p = probe_file(src)
                        self._source_duration = float(p.get("format", {}).get("duration", 0)) if p else 0.0

                        cmd = CommandBuilder.build_chunk_encode(s, src, c_path, tw, th, tfps)
                        if not self._run_proc(cmd, s):
                            success = False
                            break
                        chunks.append(c_path)

                    # Stage 2: Instant stream-copy stitch
                    if success and len(chunks) == total:
                        GLib.idle_add(self._append_log, "\n[Stage 2/2] Stitching normalized segments (Instant Concat Demuxer)...\n")
                        m_path = os.path.join(tmp_dir, "manifest.txt")
                        with open(m_path, "w") as f:
                            for c in chunks:
                                escaped = c.replace("'", "'\\''")
                                f.write(f"file '{escaped}'\n")

                        ok = self._run_proc(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", m_path, "-c", "copy", "-movflags", "+faststart", out_file], s)
                        if ok:
                            completed.append(out_file)
                        else:
                            success = False
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        elapsed = time.time() - start_time
        GLib.idle_add(self._on_done, success, completed, elapsed)

    def _execute_single(self, in_file: str, s: dict, out_file: str) -> bool:
        p = probe_file(in_file)
        self._source_duration = float(p.get("format", {}).get("duration", 0)) if p else 0.0
        is_twopass = s.get("EnableTwoPass") and s.get("RateControl") in ("VBR", "CBR") and "CPU" in s.get("HwBackend") and s.get("VideoCodec") != "copy"
        log_pfx = tempfile.mktemp(prefix="ff2p_") if is_twopass else None

        if is_twopass:
            GLib.idle_add(self._append_log, "[Studio] Pass 1 of 2 (Analysis pass)...\n")
            cmd1 = CommandBuilder.build_single(s, in_file, out_file, pass_num=1, pass_log=log_pfx)
            if not self._run_proc(cmd1, s):
                return False

        GLib.idle_add(self._append_log, f"[Studio] {'Pass 2 of 2...' if is_twopass else 'Processing...'}\n")
        cmd_final = CommandBuilder.build_single(s, in_file, out_file, pass_num=2 if is_twopass else 0, pass_log=log_pfx)
        ok = self._run_proc(cmd_final, s)

        if is_twopass and log_pfx:
            for ext in ["-0.log", "-0.log.mbtree"]:
                if os.path.exists(f"{log_pfx}{ext}"):
                    try:
                        os.remove(f"{log_pfx}{ext}")
                    except Exception:
                        pass
        return ok

    def _run_proc(self, args: list, s: dict) -> bool:
        try:
            cmd_str = " ".join(f'"{a}"' if " " in a else a for a in args)
            GLib.idle_add(self._append_log, f"Executing:\n{cmd_str}\n\n")

            env = os.environ.copy()
            if "AMF" in s.get("HwBackend", ""):
                for icd in ["/usr/share/vulkan/icd.d/amd_pro_icd64.json", "/etc/vulkan/icd.d/amd_pro_icd64.json"]:
                    if os.path.exists(icd):
                        env["VK_DRIVER_FILES"] = env["VK_ICD_FILENAMES"] = icd
                        break

            self._process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1, env=env)
            for line in self._process.stdout:
                GLib.idle_add(self._append_log, line)
            self._process.wait()
            return self._process.returncode == 0
        except Exception as e:
            GLib.idle_add(self._append_log, f"\nExecution Error: {e}\n")
            return False
        finally:
            self._process = None

    def _on_done(self, success: bool, out_files: list, elapsed: float):
        self._btn_start.set_sensitive(True)
        self._btn_cancel.set_sensitive(False)
        self._btn_cancel.set_label("Cancel")
        self._stopping_graceful = False
        self._btn_pause.set_sensitive(False)

        if success and out_files:
            self._p_bar.set_fraction(1.0)
            self._p_bar.set_text("100.0%")
            self._p_detail.set_markup("<b>Job Finished!</b>")
            target = out_files[-1]
            if os.path.exists(target):
                MediaInfoDialog(self, target, elapsed).present()
        else:
            msg = "<i>Process halted</i>" if self._stopping_graceful else "<span foreground='#c01c28'><b>Task Ended with Errors</b></span>"
            self._p_detail.set_markup(msg)
        return False

    # ── Queue & Dialog Handlers ──────────────────────────────────────────

    def _on_browse_input(self, btn):
        self._input_dialog = Gtk.FileChooserNative(
            title="Select Media File",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        def _on_resp(dlg, resp):
            if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
                self._in_entry.set_text(dlg.get_file().get_path())
                self._on_probe_input(None)
            dlg.destroy()
            self._input_dialog = None

        self._input_dialog.connect("response", _on_resp)
        self._input_dialog.show()

    def _on_probe_input(self, btn):
        p = self._in_entry.get_text().strip()
        info = probe_file(p) if os.path.exists(p) else None
        if not info:
            self._lbl_probe.set_markup("<span foreground='#c01c28'>File does not exist or unreadable!</span>")
            return
        fmt = info.get("format", {})
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
        v_str = f"{v.get('width')}x{v.get('height')} ({v.get('codec_name')})" if v else "No Video"
        a_str = a.get("codec_name", "None") if a else "No Audio"
        self._lbl_probe.set_markup(f"<b>Duration:</b> {format_seconds(float(fmt.get('duration', 0)))}  │  <b>Video:</b> {v_str}  │  <b>Audio:</b> {a_str}")

    def _on_detect_crop(self, btn):
        p = self._in_entry.get_text().strip()
        if not os.path.exists(p):
            self._append_log("ERROR: Select a valid media file to detect black bars.\n")
            return
        self._append_log("[Studio] Analyzing crop with cropdetect...\n")
        threading.Thread(target=self._crop_worker, args=(p,), daemon=True).start()

    def _crop_worker(self, path):
        try:
            res = subprocess.run(["ffmpeg", "-hide_banner", "-ss", "00:01:00", "-i", path, "-vframes", "25", "-vf", "cropdetect=24:16:0", "-f", "null", "-"], capture_output=True, text=True, timeout=12)
            crops = re.findall(r"crop=([0-9]+:[0-9]+:[0-9]+:[0-9]+)", res.stderr)
            if crops:
                best = max(set(crops), key=crops.count)
                GLib.idle_add(lambda: (self._chk_crop.set_active(True), self._crop_entry.set_text(best), self._append_log(f"[Studio] Detected crop: {best}\n"), False))
            else:
                GLib.idle_add(self._append_log, "[Studio] No black bars detected.\n")
        except Exception as e:
            GLib.idle_add(self._append_log, f"Crop detection error: {e}\n")

    def _on_browse_output(self, btn):
        self._out_dialog = Gtk.FileChooserNative(
            title="Select Output Folder",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select",
            cancel_label="_Cancel"
        )
        def _on_resp(dlg, resp):
            if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
                self._out_dir_entry.set_text(dlg.get_file().get_path())
            dlg.destroy()
            self._out_dialog = None

        self._out_dialog.connect("response", _on_resp)
        self._out_dialog.show()

    def _on_q_add(self, btn):
        self._q_dialog = Gtk.FileChooserNative(
            title="Add Media Files",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            select_multiple=True,
            accept_label="_Add",
            cancel_label="_Cancel"
        )
        def _res(dlg, resp):
            if resp == Gtk.ResponseType.ACCEPT:
                gfiles = dlg.get_files()
                if gfiles:
                    for i in range(gfiles.get_n_items()):
                        p = gfiles.get_item(i).get_path()
                        if p and p not in self._batch_files:
                            self._batch_files.append(p)
                            self._lb_queue.append(Gtk.Label(label=os.path.basename(p), halign=Gtk.Align.START, tooltip_text=p))
            dlg.destroy()
            self._q_dialog = None

        self._q_dialog.connect("response", _res)
        self._q_dialog.show()

    def _on_q_rm(self, btn):
        r = self._lb_queue.get_selected_row()
        if r:
            idx = r.get_index()
            self._lb_queue.remove(r)
            if 0 <= idx < len(self._batch_files):
                self._batch_files.pop(idx)

    def _on_q_up(self, btn):
        r = self._lb_queue.get_selected_row()
        if r and r.get_index() > 0:
            idx = r.get_index()
            self._batch_files[idx - 1], self._batch_files[idx] = self._batch_files[idx], self._batch_files[idx - 1]
            self._rebuild_queue_list(idx - 1)

    def _on_q_dn(self, btn):
        r = self._lb_queue.get_selected_row()
        if r and r.get_index() < len(self._batch_files) - 1:
            idx = r.get_index()
            self._batch_files[idx + 1], self._batch_files[idx] = self._batch_files[idx], self._batch_files[idx + 1]
            self._rebuild_queue_list(idx + 1)

    def _on_q_clr(self, btn):
        self._batch_files.clear()
        while True:
            row = self._lb_queue.get_row_at_index(0)
            if not row:
                break
            self._lb_queue.remove(row)

    def _rebuild_queue_list(self, select_idx: int):
        while True:
            row = self._lb_queue.get_row_at_index(0)
            if not row:
                break
            self._lb_queue.remove(row)
        for p in self._batch_files:
            self._lb_queue.append(Gtk.Label(label=os.path.basename(p), halign=Gtk.Align.START, tooltip_text=p))
        sel = self._lb_queue.get_row_at_index(select_idx)
        if sel:
            self._lb_queue.select_row(sel)

    def _parse_progress_line(self, line: str):
        m_time = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if m_time:
            secs = int(m_time.group(1)) * 3600 + int(m_time.group(2)) * 60 + float(m_time.group(3))
            fps = (re.search(r"fps=\s*([\d\.]+)", line) or [None, "0"])[1]
            speed = (re.search(r"speed=\s*([\d\.]+)x", line) or [None, "1.0"])[1] + "x"
            tot = self._source_duration
            if self._chk_trim.get_active():
                s = parse_timestamp_to_seconds(self._trim_start.get_text())
                e = parse_timestamp_to_seconds(self._trim_end.get_text())
                if e > s:
                    tot = e - s

            if tot > 0:
                frac = min(max(secs / tot, 0.0), 1.0)
                self._p_bar.set_fraction(frac)
                self._p_bar.set_text(f"{frac * 100:.1f}%")
                speed_num = float(speed.rstrip("x"))
                eta = format_seconds((tot - secs) / speed_num) if speed_num > 0 else "N/A"
                self._p_detail.set_markup(f"<b>Time:</b> {format_seconds(secs)} / {format_seconds(tot)}  │  <b>Speed:</b> {speed}  │  <b>FPS:</b> {fps}  │  <b>ETA:</b> {eta}")
            else:
                self._p_bar.pulse()
                self._p_detail.set_markup(f"<b>Time:</b> {format_seconds(secs)}  │  <b>Speed:</b> {speed}  │  <b>FPS:</b> {fps}")

    def _append_log(self, text: str):
        self._parse_progress_line(text)
        is_p = text.strip().startswith("frame=")
        now = time.time()
        if is_p:
            if now - self._last_progress_log < 0.7:
                return False
            self._last_progress_log = now

        if self._log_buf.get_line_count() > 2000:
            s_it = self._log_buf.get_start_iter()
            d_it = self._log_buf.get_iter_at_line(400)
            self._log_buf.delete(s_it, d_it)

        self._log_buf.insert(self._log_buf.get_end_iter(), text)
        self._log_buf.move_mark(self._log_mark, self._log_buf.get_end_iter())
        self._tv_log.scroll_mark_onscreen(self._log_mark)
        return False

    def _clear_log(self):
        self._log_buf.set_text("")


# ─── Application Main & Desktop Self-Install ─────────────────────────────────

_DESKTOP_ID = "ffmpeg_studio.desktop"
_ICON_NAME = "ffmpeg-gtk-pro"
_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="8" y="8" width="112" height="112" rx="24" fill="#1e1e24"/>
  <rect x="18" y="18" width="92" height="92" rx="16" fill="#26a269" opacity="0.9"/>
  <circle cx="44" cy="44" r="8" fill="#ffffff"/>
  <circle cx="84" cy="44" r="8" fill="#ffffff"/>
  <circle cx="44" cy="84" r="8" fill="#ffffff"/>
  <circle cx="84" cy="84" r="8" fill="#ffffff"/>
  <polygon points="54,64 78,50 78,78" fill="#ffffff"/>
</svg>"""

def ensure_self_install():
    try:
        if not sys.stdout.isatty():
            return
        a_dir = os.path.expanduser("~/.local/share/applications")
        i_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
        os.makedirs(a_dir, exist_ok=True)
        os.makedirs(i_dir, exist_ok=True)

        i_path = os.path.join(i_dir, f"{_ICON_NAME}.svg")
        d_path = os.path.join(a_dir, _DESKTOP_ID)

        if not os.path.exists(i_path):
            with open(i_path, "w") as f:
                f.write(_ICON_SVG)

        entry = (
            "[Desktop Entry]\nType=Application\nVersion=1.0\nName=FFmpeg Studio\nGenericName=Media Transcoder\n"
            f'Comment=Pro FFmpeg GUI with autodetected VAAPI, AMF, NVENC, and stream copy\nExec="{sys.executable}" "{os.path.abspath(__file__)}"\n'
            f"Icon={_ICON_NAME}\nTerminal=false\nCategories=AudioVideo;AudioVideoEditing;GTK;\nStartupWMClass=ffmpeg_studio\n"
        )
        with open(d_path, "w") as f:
            f.write(entry)

        subprocess.run(["update-desktop-database", "-q", a_dir], capture_output=True, timeout=3)
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", os.path.expanduser("~/.local/share/icons/hicolor")], capture_output=True, timeout=3)
    except Exception:
        pass


class FFmpegApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="ffmpeg_studio", flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(APP_CSS)
        else:
            provider.load_from_data(APP_CSS.encode())
        d = Gdk.Display.get_default()
        if d:
            Gtk.StyleContext.add_provider_for_display(d, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.props.active_window or FFmpegStudioWindow(application=self)
        win.present()


def main():
    if "--version" in sys.argv:
        print(f"ffmpeg-gtk-pro {__version__}")
        return 0
    ensure_self_install()
    return FFmpegApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
