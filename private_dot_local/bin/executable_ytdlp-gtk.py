#!/usr/bin/env python3
"""yt-dlp Professional Wrapper — GTK4 Version

A full-featured GUI wrapper for yt-dlp built with Python 3 + PyGObject (GTK4).
Follows system GTK theme styling (light/dark) with real-time detailed progress.
"""
__version__ = "1.2.0"

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio, Pango

import json
import os
import re
import sys
import shutil
import subprocess
import threading
import importlib.util

# ─── Constants ───────────────────────────────────────────────────────────────

SETTINGS_DIR = os.path.expanduser("~/.config/ytdlp-gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "Url": "",
    "VideoFormat": "None",
    "AudioFormat": "None",
    "ProxyType": "HTTP",
    "ProxyAddr": "127.0.0.1:10810",
    "IgnoreSSL": True,
    "OutputDir": os.path.expandvars("$HOME/Videos/YouTube"),
    "OutputName": "%(uploader)s - %(title)s [%(id)s] %(resolution)s_%(fps)sfps_%(vcodec)s_%(acodec)s.%(ext)s",
    "RemuxFormat": "None",
    "UseAria2": False,
    "AriaArgs": "Standard Optimized (4 connections - Recommended)",
    "EmbedMetadata": False,
    "EmbedThumbnail": False,
    "CookieFile": "",
}

ARIA_SPEED_PRESETS = {
    "Safe & Gentle (2 connections)": "-c -j 2 -x 2 -s 2 -k 1M",
    "Standard Optimized (4 connections - Recommended)": "-c -j 4 -x 4 -s 4 -k 1M",
    "High Speed (8 connections)": "-c -j 8 -x 8 -s 8 -k 1M",
}

PROXY_PROTOCOLS = ["None", "HTTP", "HTTPS", "SOCKS4", "SOCKS5"]

AUDIO_REMUX_CONTAINERS = {"mp3", "m4a", "flac", "aac", "opus", "ogg", "wav", "alac", "aiff", "vorbis", "best"}

APP_CSS = """
.download-btn {
    padding: 8px 24px;
    font-weight: bold;
}
.monospace-log {
    font-family: monospace;
}
.progress-detail {
    font-size: 12px;
    margin-top: 2px;
}
"""


def _has_ai_dub_indicator(info: str) -> bool:
    """Check if an audio track's MORE INFO text indicates an AI translation/dub."""
    info = info.lower()
    if re.search(r"\b[a-z]{2}\s*-\s*ai\b", info):
        return True
    if "ai dub" in info or "ai translat" in info:
        return True
    if re.search(r"\(ai\s*(dub|translat)", info):
        return True
    return False

# ─── Helper Functions ────────────────────────────────────────────────────────

def simplify_codec(codec_raw: str) -> str:
    c = codec_raw.lower()
    if "av01" in c or "av1" in c:
        return "av1"
    if "avc1" in c or "h264" in c:
        return "avc"
    if "vp9" in c or "vp09" in c:
        return "vp9"
    if "vp8" in c or "vp08" in c:
        return "vp8"
    if "hevc" in c or "h265" in c:
        return "hevc"
    if "mp4a" in c or "aac" in c:
        return "aac"
    if "opus" in c:
        return "opus"
    if "vorbis" in c:
        return "vorbis"
    if "mp3" in c:
        return "mp3"
    if "flac" in c:
        return "flac"
    return codec_raw


def simplify_resolution(res: str) -> str:
    if "audio only" in res.lower():
        return "Audio"
    m = re.search(r"(\d+)x(\d+)", res)
    if m:
        return f"{m.group(2)}p"
    return res


def simplify_filesize(s: str) -> str:
    m = re.search(r"~?(\d+(?:\.\d+)?)\s*(KiB|MiB|GiB|KB|MB|GB|B)", s)
    if m:
        prefix = "~" if "~" in s else ""
        return f"{prefix}{round(float(m.group(1)))}{m.group(2).replace('i', '')}"
    return "Unknown"


def parse_formats(raw_output: str):
    video_list = []
    audio_list = []
    format_codecs = {}

    for line in raw_output.splitlines():
        line = line.strip()
        if not line or line.startswith("ID") or line.startswith("--"):
            continue

        parts = re.split(r"[\u2502|]", line)
        if len(parts) < 3:
            continue

        sec1 = [t.strip() for t in parts[0].split()]
        sec2 = parts[1].strip()
        sec3_raw = parts[2].strip()
        sec3 = sec3_raw.split()

        if len(sec1) < 3:
            continue

        fmt_id = sec1[0]
        ext = sec1[1]

        if fmt_id.startswith("sb") or ext.lower() == "mhtml":
            continue
        rest_of_sec1 = " ".join(sec1[2:]).lower()
        if "storyboard" in rest_of_sec1 or "images" in rest_of_sec1:
            continue

        resolution = ""
        fps = ""
        res_found = False
        for tok in sec1[2:]:
            if re.match(r"\d+x\d+$", tok):
                resolution = tok
                res_found = True
                break
        if not res_found:
            combined = " ".join(sec1[2:]).lower()
            if "audio only" in combined:
                resolution = "audio only"
            else:
                resolution = " ".join(sec1[2:4]) if len(sec1) > 4 else " ".join(sec1[2:])

        if res_found:
            res_idx = sec1.index(resolution)
            if res_idx + 1 < len(sec1):
                fps_candidate = sec1[res_idx + 1]
                if re.match(r"\d+(\.\d+)?$", fps_candidate):
                    fps = fps_candidate

        filesize = sec2.strip()

        def _is_codec_token(t):
            low = t.lower()
            if low in ("video", "audio", "only"):
                return False
            if re.match(r"^\d+k$", low):
                return False
            if re.match(r"^\d+$", low):
                return False
            return True

        is_audio = "audio only" in resolution.lower()

        if is_audio and _has_ai_dub_indicator(sec3_raw):
            continue

        if is_audio:
            raw_codec = "unknown"
            for t in sec3:
                if _is_codec_token(t):
                    raw_codec = t
                    break
            codec_display = simplify_codec(raw_codec)
            format_codecs[fmt_id] = codec_display
        else:
            v_raw = sec3[0] if sec3 else "unknown"
            v_codec = simplify_codec(v_raw)
            format_codecs[fmt_id] = v_codec

            a_codec = None
            if sec3 and "video only" not in " ".join(sec3).lower():
                for t in sec3[1:]:
                    if _is_codec_token(t):
                        a_codec = simplify_codec(t)
                        break

            if a_codec:
                codec_display = f"{v_codec}+{a_codec}"
                format_codecs[f"{fmt_id}_audio"] = a_codec
            else:
                codec_display = v_codec

        res_display = simplify_resolution(resolution) if resolution else ""
        size_display = simplify_filesize(filesize) if filesize else "Unknown"

        display_parts = [fmt_id, ext]
        if codec_display:
            display_parts.append(codec_display)
        if res_display:
            display_parts.append(res_display)
        if fps:
            display_parts.append(f"{fps}fps")
        display_parts.append(size_display)
        display_str = "  ".join(display_parts)

        if is_audio:
            audio_list.append((display_str, fmt_id))
        else:
            video_list.append((display_str, fmt_id))

    return video_list, audio_list, format_codecs


def compute_remux_options(video_codec, audio_codec):
    options = ["None"]
    if video_codec and audio_codec is not None:
        options.append("MKV")
        if video_codec in ("vp9", "vp8", "av1"):
            if audio_codec in ("opus", "vorbis", "unknown", None):
                options.append("WEBM")
        if video_codec in ("avc", "hevc", "av1"):
            if audio_codec in ("aac", "mp3", "unknown", None):
                options.append("MP4")
    elif video_codec:
        options.append("MKV")
        if video_codec in ("vp9", "vp8", "av1"):
            options.append("WEBM")
        if video_codec in ("avc", "hevc", "av1"):
            options.append("MP4")
    elif audio_codec is not None:
        options.append("MKA")
        if audio_codec in ("aac", "mp3", "unknown"):
            options.append("M4A")
        if audio_codec in ("opus", "vorbis", "unknown"):
            options.append("OGG")
        if audio_codec in ("opus", "unknown"):
            options.append("OPUS")
    else:
        options.extend(["MP4", "MKV", "WEBM"])

    return options


def build_download_args(settings, format_codecs, url):
    args = ["yt-dlp", "--newline"]  # --newline ensures steady line-by-line output

    proxy_type = settings.get("ProxyType", "None")
    proxy_addr = settings.get("ProxyAddr", "").strip()
    if proxy_type != "None" and proxy_addr:
        args.extend(["--proxy", f"{proxy_type.lower()}://{proxy_addr}"])

    if settings.get("IgnoreSSL", False):
        args.append("--no-check-certificate")

    cookie_file = settings.get("CookieFile", "").strip()
    if cookie_file and os.path.isfile(cookie_file):
        args.extend(["--cookies", cookie_file])

    vid = settings.get("VideoFormat", "None")
    aud = settings.get("AudioFormat", "None")

    if vid != "None" and aud != "None":
        v_id = vid.split()[0] if vid else "None"
        a_id = aud.split()[0] if aud else "None"
        args.extend(["-f", f"{v_id}+{a_id}"])
    elif vid != "None":
        v_id = vid.split()[0] if vid else "None"
        args.extend(["-f", v_id])
    elif aud != "None":
        a_id = aud.split()[0] if aud else "None"
        args.extend(["-f", a_id])
    else:
        args.extend(["-f", "bestvideo+bestaudio/best"])

    out_dir = settings.get("OutputDir", "")
    out_name = settings.get("OutputName", "")
    if out_dir and out_name:
        full_output = os.path.join(out_dir, out_name)
        args.extend(["-o", full_output])

    if settings.get("UseAria2", False):
        aria_display = settings.get("AriaArgs", "")
        aria_flags = ARIA_SPEED_PRESETS.get(aria_display, "-c -j 4 -x 4 -s 4 -k 1M")
        aria_extra = "--continue=true --check-integrity=true --auto-file-renaming=false --file-allocation=none"
        aria_proxy = ""
        if proxy_type != "None" and proxy_addr:
            aria_proxy = f" --all-proxy={proxy_type.lower()}://{proxy_addr}"
        aria_full = f"{aria_flags} {aria_extra}{aria_proxy}"
        args.extend(["--downloader", "aria2c", "--downloader-args", f"aria2c:{aria_full}"])

    if settings.get("EmbedMetadata", False):
        args.append("--embed-metadata")

    if settings.get("EmbedThumbnail", False):
        args.append("--embed-thumbnail")

    remux = settings.get("RemuxFormat", "None")
    if remux and remux != "None":
        remux_lower = remux.lower()
        if remux_lower in AUDIO_REMUX_CONTAINERS:
            args.append("-x")
            if remux_lower != "best":
                args.extend(["--audio-format", remux_lower])
        else:
            args.extend(["--remux-video", remux_lower])

    args.append(url)
    return args


def ensure_aria2_symlink():
    if shutil.which("aria2c"):
        return True

    for name in ("aria2n", "aria2c-next"):
        bin_path = shutil.which(name)
        if bin_path:
            local_bin = os.path.expanduser("~/.local/bin")
            symlink_path = os.path.join(local_bin, "aria2c")
            if not os.path.exists(symlink_path):
                os.makedirs(local_bin, exist_ok=True)
                os.symlink(bin_path, symlink_path)
            if local_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")
            return True

    return False


def get_dep_status():
    has_ytdlp = shutil.which("yt-dlp") is not None
    has_ffmpeg = shutil.which("ffmpeg") is not None

    aria2_name = "aria2"
    aria2_bin = shutil.which("aria2c") or shutil.which("aria2n") or shutil.which("aria2c-next")
    if aria2_bin:
        aria2_name = os.path.basename(aria2_bin)

    has_mutagen = importlib.util.find_spec("mutagen") is not None
    has_deno = shutil.which("deno") is not None

    parts = []
    parts.append(("yt-dlp", "ok" if has_ytdlp else "missing"))
    parts.append(("ffmpeg", "ok" if has_ffmpeg else "missing"))
    parts.append((aria2_name, "ok" if aria2_bin else "warn"))
    parts.append(("mutagen", "ok" if has_mutagen else "warn"))
    parts.append(("deno", "ok" if has_deno else "warn"))

    return parts, not (has_ytdlp and has_ffmpeg)


# ─── GTK4 Application Window ────────────────────────────────────────────────

class YtdlpAppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("yt-dlp Professional Wrapper")
        self.set_default_size(660, 930)

        self.format_codecs = {}
        self.video_formats = []
        self.audio_formats = []
        self.video_codecs = []
        self.audio_codecs = []
        self._downloading = False
        self._process = None
        self._pulse_id = None

        self._build_ui()
        self._load_settings()

        self.connect("close-request", self._on_close_request)

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(12)
        self.set_child(main_box)

        self._build_header(main_box)
        self._build_target_format(main_box)
        self._build_connection_proxy(main_box)
        self._build_output_naming(main_box)
        self._build_acceleration(main_box)
        self._build_download_button(main_box)
        self._build_log(main_box)

    def _build_header(self, parent):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(2)
        hbox.set_margin_bottom(2)
        parent.append(hbox)

        title = Gtk.Label(label="<b>yt-dlp GUI</b>")
        title.set_use_markup(True)
        title.set_halign(Gtk.Align.START)
        hbox.append(title)

        self._dep_label = Gtk.Label()
        self._dep_label.set_hexpand(True)
        self._dep_label.set_halign(Gtk.Align.END)
        self._dep_label.set_use_markup(True)
        self._update_dep_markup()
        hbox.append(self._dep_label)

    def _update_dep_markup(self):
        dep_parts, _ = get_dep_status()
        spans = []
        for name, level in dep_parts:
            color = "#26a269" if level == "ok" else "#c01c28" if level == "missing" else "#d08b00"
            spans.append(f'<span foreground="{color}" font_weight="bold">{name}</span>')
        self._dep_label.set_markup("  │  ".join(spans))

    def _build_target_format(self, parent):
        frame = Gtk.Frame(label=" Target & Format ")
        parent.append(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.set_child(vbox)

        sg_labels = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        # URL row
        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(url_row)

        url_label = Gtk.Label(label="URL:")
        url_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(url_label)
        url_row.append(url_label)

        self._url_entry = Gtk.Entry()
        self._url_entry.set_hexpand(True)
        self._url_entry.set_placeholder_text("Media or playlist URL...")
        url_row.append(self._url_entry)

        self._fetch_btn = Gtk.Button(label="Fetch")
        self._fetch_btn.connect("clicked", self._on_fetch_clicked)
        url_row.append(self._fetch_btn)

        # Video row
        vid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(vid_row)

        vid_label = Gtk.Label(label="Video:")
        vid_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(vid_label)
        vid_row.append(vid_label)

        self._video_codec_combo = Gtk.ComboBoxText()
        self._video_codec_combo.set_size_request(100, -1)
        self._video_codec_combo.append_text("All")
        self._video_codec_combo.set_active(0)
        self._video_codec_combo.connect("changed", self._on_video_codec_changed)
        vid_row.append(self._video_codec_combo)

        self._video_combo = Gtk.ComboBoxText()
        self._video_combo.set_hexpand(True)
        self._video_combo.append_text("None")
        self._video_combo.set_active(0)
        self._video_combo.connect("changed", self._on_format_changed)
        vid_row.append(self._video_combo)

        # Audio row
        aud_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(aud_row)

        aud_label = Gtk.Label(label="Audio:")
        aud_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(aud_label)
        aud_row.append(aud_label)

        self._audio_codec_combo = Gtk.ComboBoxText()
        self._audio_codec_combo.set_size_request(100, -1)
        self._audio_codec_combo.append_text("All")
        self._audio_codec_combo.set_active(0)
        self._audio_codec_combo.connect("changed", self._on_audio_codec_changed)
        aud_row.append(self._audio_codec_combo)

        self._audio_combo = Gtk.ComboBoxText()
        self._audio_combo.set_hexpand(True)
        self._audio_combo.append_text("None")
        self._audio_combo.set_active(0)
        self._audio_combo.connect("changed", self._on_format_changed)
        aud_row.append(self._audio_combo)

        # ── Detailed Progress Section ─────────────────────────────────────
        self._progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self._progress_box.set_margin_top(4)
        self._progress_box.set_visible(False)
        vbox.append(self._progress_box)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_text("0.0%")
        self._progress_box.append(self._progress_bar)

        self._progress_detail_label = Gtk.Label()
        self._progress_detail_label.set_use_markup(True)
        self._progress_detail_label.set_halign(Gtk.Align.CENTER)
        self._progress_detail_label.add_css_class("progress-detail")
        self._progress_detail_label.set_markup("<i>Ready</i>")
        self._progress_box.append(self._progress_detail_label)

    def _build_connection_proxy(self, parent):
        frame = Gtk.Frame(label=" Connection & Proxy ")
        parent.append(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.set_child(vbox)

        proxy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(proxy_row)

        proto_label = Gtk.Label(label="Protocol:")
        proto_label.set_halign(Gtk.Align.START)
        proxy_row.append(proto_label)

        self._proxy_type_combo = Gtk.ComboBoxText()
        for p in PROXY_PROTOCOLS:
            self._proxy_type_combo.append_text(p)
        self._proxy_type_combo.set_active(1)
        proxy_row.append(self._proxy_type_combo)

        addr_label = Gtk.Label(label="Address:")
        addr_label.set_halign(Gtk.Align.START)
        proxy_row.append(addr_label)

        self._proxy_addr_entry = Gtk.Entry()
        self._proxy_addr_entry.set_hexpand(True)
        self._proxy_addr_entry.set_text("127.0.0.1:10810")
        proxy_row.append(self._proxy_addr_entry)

        self._ssl_check = Gtk.CheckButton(label="Ignore SSL/TLS Certificate Errors")
        self._ssl_check.set_active(True)
        vbox.append(self._ssl_check)

    def _build_output_naming(self, parent):
        frame = Gtk.Frame(label=" Output & Naming ")
        parent.append(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.set_child(vbox)

        sg_labels = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        # Directory row
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(dir_row)

        dir_label = Gtk.Label(label="Dir:")
        dir_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(dir_label)
        dir_row.append(dir_label)

        self._output_dir_entry = Gtk.Entry()
        self._output_dir_entry.set_hexpand(True)
        dir_row.append(self._output_dir_entry)

        browse_btn = Gtk.Button(label="Browse")
        browse_btn.connect("clicked", self._on_browse_clicked)
        dir_row.append(browse_btn)

        # Name row
        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(name_row)

        name_label = Gtk.Label(label="Name:")
        name_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(name_label)
        name_row.append(name_label)

        self._output_name_entry = Gtk.Entry()
        self._output_name_entry.set_hexpand(True)
        name_row.append(self._output_name_entry)

        # Cookie row
        cookie_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(cookie_row)

        cookie_label = Gtk.Label(label="Cookie:")
        cookie_label.set_halign(Gtk.Align.START)
        sg_labels.add_widget(cookie_label)
        cookie_row.append(cookie_label)

        self._cookie_entry = Gtk.Entry()
        self._cookie_entry.set_hexpand(True)
        self._cookie_entry.set_placeholder_text("/path/to/cookie.txt")
        cookie_row.append(self._cookie_entry)

    def _build_acceleration(self, parent):
        frame = Gtk.Frame(label=" Download Acceleration & Post-Processing ")
        parent.append(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.set_child(vbox)

        # Remux
        remux_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(remux_row)

        remux_label = Gtk.Label(label="Remux:")
        remux_label.set_halign(Gtk.Align.START)
        remux_row.append(remux_label)

        self._remux_combo = Gtk.ComboBoxText()
        self._remux_combo.set_hexpand(True)
        for opt in ["None", "MP4", "MKV", "WEBM"]:
            self._remux_combo.append_text(opt)
        self._remux_combo.set_active(0)
        remux_row.append(self._remux_combo)

        # aria2
        aria_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(aria_row)

        self._aria2_check = Gtk.CheckButton(label="Enable aria2")
        self._aria2_check.set_active(False)
        self._aria2_check.connect("toggled", self._on_aria_toggled)
        aria_row.append(self._aria2_check)

        speed_label = Gtk.Label(label="Speed:")
        speed_label.set_halign(Gtk.Align.START)
        aria_row.append(speed_label)

        self._aria_speed_combo = Gtk.ComboBoxText()
        self._aria_speed_combo.set_hexpand(True)
        for name in ARIA_SPEED_PRESETS:
            self._aria_speed_combo.append_text(name)
        self._aria_speed_combo.set_active(1)
        self._aria_speed_combo.set_sensitive(False)
        aria_row.append(self._aria_speed_combo)

        # Embed
        embed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        vbox.append(embed_row)

        self._embed_meta_check = Gtk.CheckButton(label="Embed Metadata")
        self._embed_meta_check.set_active(False)
        embed_row.append(self._embed_meta_check)

        self._embed_thumb_check = Gtk.CheckButton(label="Embed Thumbnail")
        self._embed_thumb_check.set_active(False)
        embed_row.append(self._embed_thumb_check)

    def _build_download_button(self, parent):
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_row.set_margin_top(4)
        action_row.set_margin_bottom(4)
        action_row.set_halign(Gtk.Align.CENTER)
        parent.append(action_row)

        self._download_btn = Gtk.Button(label="Start Download")
        self._download_btn.add_css_class("suggested-action")
        self._download_btn.add_css_class("download-btn")
        self._download_btn.connect("clicked", self._on_download_clicked)
        action_row.append(self._download_btn)

        self._cancel_btn = Gtk.Button(label="Cancel")
        self._cancel_btn.add_css_class("destructive-action")
        self._cancel_btn.add_css_class("download-btn")
        self._cancel_btn.set_sensitive(False)
        self._cancel_btn.connect("clicked", self._on_cancel_clicked)
        action_row.append(self._cancel_btn)

    def _build_log(self, parent):
        frame = Gtk.Frame(label=" Output & Processing Log ")
        frame.set_vexpand(True)
        parent.append(frame)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(160)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        frame.set_child(scroll)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_cursor_visible(False)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_view.set_left_margin(10)
        self._log_view.set_right_margin(10)
        self._log_view.set_top_margin(6)
        self._log_view.set_bottom_margin(6)
        self._log_view.add_css_class("monospace-log")

        scroll.set_child(self._log_view)
        self._log_buffer = self._log_view.get_buffer()

    # ── Progress and Output Parsing ──────────────────────────────────────

    def _parse_progress_line(self, line: str):
        """Parse yt-dlp / aria2 progress from stdout lines and update progress UI."""
        # 1. Native yt-dlp download progress:
        # e.g., "[download]  45.2% of ~ 266.44MiB at    5.42MiB/s ETA 00:27"
        # e.g., "[download]  10.0% of 100.00MiB at 2.50MiB/s ETA 00:36 (frag 2/20)"
        m_ytdlp = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+(?:~\s*)?(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)", line)
        if m_ytdlp:
            percent = float(m_ytdlp.group(1))
            size = m_ytdlp.group(2)
            speed = m_ytdlp.group(3)
            eta = m_ytdlp.group(4)
            fraction = min(max(percent / 100.0, 0.0), 1.0)

            self._progress_bar.set_fraction(fraction)
            self._progress_bar.set_text(f"{percent:.1f}%")
            self._progress_detail_label.set_markup(
                f"<b>Size:</b> {size}  │  <b>Speed:</b> {speed}  │  <b>ETA:</b> {eta}"
            )
            return

        # 2. aria2 progress line:
        # e.g., "[#547a11 12MiB/100MiB(12%) CN:4 DL:2.4MiB ETA:36s]"
        m_aria = re.search(r"\[#\w+\s+(\S+?)/(\S+?)\((\d+)%\)\s+.*?DL:(\S+?)(?:\s+ETA:(\S+?))?\]", line)
        if m_aria:
            dl_size = m_aria.group(1)
            total_size = m_aria.group(2)
            percent = float(m_aria.group(3))
            speed = m_aria.group(4)
            eta = m_aria.group(5) or "N/A"
            fraction = min(max(percent / 100.0, 0.0), 1.0)

            self._progress_bar.set_fraction(fraction)
            self._progress_bar.set_text(f"{percent:.1f}%")
            self._progress_detail_label.set_markup(
                f"<b>Size:</b> {dl_size} / {total_size}  │  <b>Speed:</b> {speed}  │  <b>ETA:</b> {eta}"
            )
            return

        # 3. Post-processing and stages detection
        if line.startswith("["):
            m_stage = re.match(r"\[(\w+)\]\s*(.*)", line)
            if m_stage:
                stage = m_stage.group(1)
                desc = m_stage.group(2).strip()
                if stage in ("Merger", "ExtractAudio", "EmbedThumbnail", "Metadata", "FixupM3u8", "FixupM4a"):
                    self._progress_bar.set_fraction(1.0)
                    self._progress_bar.set_text(f"Processing ({stage})")
                    self._progress_detail_label.set_markup(f"<i>{stage}: {GLib.markup_escape_text(desc[:60])}...</i>")

    def _append_log(self, text):
        end_iter = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end_iter, text)
        mark = self._log_buffer.create_mark(None, self._log_buffer.get_end_iter(), False)
        self._log_view.scroll_mark_onscreen(mark)
        self._parse_progress_line(text)
        return False

    def _clear_log(self):
        self._log_buffer.set_text("")

    # ── Settings ─────────────────────────────────────────────────────────

    def _load_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                settings.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass

        self._url_entry.set_text(settings.get("Url", ""))
        self._set_combo_by_text(self._video_combo, settings.get("VideoFormat", "None"))
        self._set_combo_by_text(self._audio_combo, settings.get("AudioFormat", "None"))

        proxy_type = settings.get("ProxyType", "HTTP")
        idx = PROXY_PROTOCOLS.index(proxy_type) if proxy_type in PROXY_PROTOCOLS else 1
        self._proxy_type_combo.set_active(idx)
        self._proxy_addr_entry.set_text(settings.get("ProxyAddr", ""))
        self._ssl_check.set_active(settings.get("IgnoreSSL", True))

        self._output_dir_entry.set_text(settings.get("OutputDir", DEFAULT_SETTINGS["OutputDir"]))
        self._output_name_entry.set_text(settings.get("OutputName", DEFAULT_SETTINGS["OutputName"]))
        self._cookie_entry.set_text(settings.get("CookieFile", DEFAULT_SETTINGS["CookieFile"]))

        remux = settings.get("RemuxFormat", "None")
        self._set_combo_by_text(self._remux_combo, remux)

        use_aria = settings.get("UseAria2", False)
        self._aria2_check.set_active(use_aria)
        self._aria_speed_combo.set_sensitive(use_aria)
        aria_name = settings.get("AriaArgs", "")
        self._set_combo_by_text(self._aria_speed_combo, aria_name)

        self._embed_meta_check.set_active(settings.get("EmbedMetadata", False))
        self._embed_thumb_check.set_active(settings.get("EmbedThumbnail", False))

    def _gather_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        settings["Url"] = self._url_entry.get_text().strip()
        settings["VideoFormat"] = self._get_combo_active_text(self._video_combo) or "None"
        settings["AudioFormat"] = self._get_combo_active_text(self._audio_combo) or "None"
        settings["ProxyType"] = PROXY_PROTOCOLS[self._proxy_type_combo.get_active()] if self._proxy_type_combo.get_active() >= 0 else "None"
        settings["ProxyAddr"] = self._proxy_addr_entry.get_text().strip()
        settings["IgnoreSSL"] = self._ssl_check.get_active()
        settings["OutputDir"] = self._output_dir_entry.get_text().strip() or DEFAULT_SETTINGS["OutputDir"]
        settings["OutputName"] = self._output_name_entry.get_text().strip() or DEFAULT_SETTINGS["OutputName"]
        settings["CookieFile"] = self._cookie_entry.get_text().strip()
        settings["RemuxFormat"] = self._get_combo_active_text(self._remux_combo) or "None"
        settings["UseAria2"] = self._aria2_check.get_active()
        settings["AriaArgs"] = self._get_combo_active_text(self._aria_speed_combo) or DEFAULT_SETTINGS["AriaArgs"]
        settings["EmbedMetadata"] = self._embed_meta_check.get_active()
        settings["EmbedThumbnail"] = self._embed_thumb_check.get_active()
        return settings

    def _save_settings(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        settings = self._gather_settings()
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except OSError:
            pass

    # ── Combo Helpers ────────────────────────────────────────────────────

    def _set_combo_by_text(self, combo, text):
        model = combo.get_model()
        if model is None:
            return
        for i, row in enumerate(model):
            if row[0] == text:
                combo.set_active(i)
                return
        prefix = text.split()[0] if text and text.split() else ""
        if prefix:
            for i, row in enumerate(model):
                if row[0] and row[0].startswith(prefix):
                    combo.set_active(i)
                    return
        combo.set_active(0)

    def _get_combo_active_text(self, combo):
        return combo.get_active_text()

    def _populate_combo(self, combo, items, keep_current=False):
        current_text = self._get_combo_active_text(combo) if keep_current else None
        combo.remove_all()
        combo.append_text("None")
        for display, fmt_id in items:
            combo.append_text(display)
        combo.set_active(0)

        if keep_current and current_text:
            self._set_combo_by_text(combo, current_text)

    # ── Progress Pulse & Reset ───────────────────────────────────────────

    def _start_fetch_pulse(self):
        self._progress_box.set_visible(True)
        self._progress_bar.set_text("Fetching formats...")
        self._progress_bar.set_fraction(0.0)
        self._progress_detail_label.set_markup("<i>Querying available streams from yt-dlp...</i>")
        if self._pulse_id is None:
            self._pulse_id = GLib.timeout_add(50, self._pulse_progress)

    def _start_download_progress(self):
        self._stop_pulse()
        self._progress_box.set_visible(True)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("0.0%")
        self._progress_detail_label.set_markup("<i>Initializing download stream...</i>")

    def _pulse_progress(self):
        if self._pulse_id is None:
            return False
        self._progress_bar.pulse()
        return True

    def _stop_pulse(self):
        if self._pulse_id is not None:
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None

    def _hide_progress(self):
        self._stop_pulse()
        self._progress_box.set_visible(False)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("")
        self._progress_detail_label.set_text("")

    # ── Event Handlers ───────────────────────────────────────────────────

    def _on_close_request(self, window):
        self._save_settings()
        if self._process and self._process.poll() is None:
            self._process.terminate()
        return False

    def _on_browse_clicked(self, button):
        dialog = Gtk.FileChooserNative(
            title="Select Output Directory",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Open",
            cancel_label="_Cancel",
        )
        current_dir = self._output_dir_entry.get_text().strip()
        if current_dir and os.path.isdir(current_dir):
            dialog.set_current_folder(Gio.File.new_for_path(current_dir))

        def _on_response(d, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                gfile = d.get_file()
                if gfile and gfile.get_path():
                    self._output_dir_entry.set_text(gfile.get_path())
            d.destroy()

        dialog.connect("response", _on_response)
        dialog.show()

    def _on_aria_toggled(self, checkbox):
        self._aria_speed_combo.set_sensitive(checkbox.get_active())

    def _on_format_changed(self, combo):
        self._update_remux_dropdown()

    def _on_video_codec_changed(self, combo):
        codec = self._get_combo_active_text(combo) or "All"
        self._filter_video_formats(codec)

    def _on_audio_codec_changed(self, combo):
        codec = self._get_combo_active_text(combo) or "All"
        self._filter_audio_formats(codec)

    def _filter_video_formats(self, codec):
        current = self._get_combo_active_text(self._video_combo)
        self._video_combo.remove_all()
        self._video_combo.append_text("None")
        for display, fmt_id in self.video_formats:
            if codec == "All" or self.format_codecs.get(fmt_id, "") == codec:
                self._video_combo.append_text(display)
        if current and current != "None":
            self._set_combo_by_text(self._video_combo, current)
        if self._get_combo_active_text(self._video_combo) is None:
            self._video_combo.set_active(0)

    def _filter_audio_formats(self, codec):
        current = self._get_combo_active_text(self._audio_combo)
        self._audio_combo.remove_all()
        self._audio_combo.append_text("None")
        for display, fmt_id in self.audio_formats:
            if codec == "All" or self.format_codecs.get(fmt_id, "") == codec:
                self._audio_combo.append_text(display)
        if current and current != "None":
            self._set_combo_by_text(self._audio_combo, current)
        if self._get_combo_active_text(self._audio_combo) is None:
            self._audio_combo.set_active(0)

    def _update_remux_dropdown(self):
        vid_text = self._get_combo_active_text(self._video_combo) or "None"
        aud_text = self._get_combo_active_text(self._audio_combo) or "None"

        v_id = vid_text.split()[0] if vid_text != "None" else None
        a_id = aud_text.split()[0] if aud_text != "None" else None

        v_codec = self.format_codecs.get(v_id) if v_id else None
        a_codec = self.format_codecs.get(a_id) if a_id else None

        options = compute_remux_options(v_codec, a_codec)
        current_remux = self._get_combo_active_text(self._remux_combo)

        self._remux_combo.remove_all()
        for opt in options:
            self._remux_combo.append_text(opt)

        if current_remux and current_remux in options:
            self._set_combo_by_text(self._remux_combo, current_remux)
        else:
            self._remux_combo.set_active(0)

    # ── Fetch ────────────────────────────────────────────────────────────

    def _on_fetch_clicked(self, button):
        url = self._url_entry.get_text().strip()
        if not url:
            self._append_log("ERROR: No URL entered.\n")
            return

        self._save_settings()
        self._fetch_btn.set_sensitive(False)
        self._download_btn.set_sensitive(False)
        self._cancel_btn.set_sensitive(False)
        self._clear_log()
        self._append_log("Fetching format list...\n")
        self._start_fetch_pulse()

        thread = threading.Thread(target=self._fetch_thread, args=(url,), daemon=True)
        thread.start()

    def _fetch_thread(self, url):
        settings = self._gather_settings()
        cmd = ["yt-dlp", "-F", url]

        proxy_type = settings.get("ProxyType", "None")
        proxy_addr = settings.get("ProxyAddr", "").strip()
        if proxy_type != "None" and proxy_addr:
            cmd = ["yt-dlp", "--proxy", f"{proxy_type.lower()}://{proxy_addr}", "-F", url]

        if settings.get("IgnoreSSL", False):
            cmd.insert(1, "--no-check-certificate")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout + result.stderr
        except FileNotFoundError:
            GLib.idle_add(self._fetch_done, "ERROR: yt-dlp not found. Install yt-dlp first.\n")
            return
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._fetch_done, "ERROR: Fetch timed out after 120 seconds.\n")
            return
        except Exception as e:
            GLib.idle_add(self._fetch_done, f"ERROR: {e}\n")
            return

        GLib.idle_add(self._fetch_parse, output)

    def _fetch_parse(self, raw_output):
        self._hide_progress()

        video_list, audio_list, fmt_codecs = parse_formats(raw_output)
        self.video_formats = video_list
        self.audio_formats = audio_list
        self.format_codecs = fmt_codecs

        v_codecs = sorted({fmt_codecs.get(fmt_id, "unknown") for _, fmt_id in video_list})
        a_codecs = sorted({fmt_codecs.get(fmt_id, "unknown") for _, fmt_id in audio_list})
        self.video_codecs = v_codecs
        self.audio_codecs = a_codecs

        self._append_log(raw_output)
        filtered_audio = len(self.audio_formats)
        self._append_log(f"\nFound {len(video_list)} video, {filtered_audio} audio format(s).\n")

        self._video_codec_combo.remove_all()
        self._video_codec_combo.append_text("All")
        for c in v_codecs:
            self._video_codec_combo.append_text(c)
        self._video_codec_combo.set_active(0)

        self._audio_codec_combo.remove_all()
        self._audio_codec_combo.append_text("All")
        for c in a_codecs:
            self._audio_codec_combo.append_text(c)
        self._audio_codec_combo.set_active(0)

        self._populate_combo(self._video_combo, video_list)
        self._populate_combo(self._audio_combo, audio_list)

        self._fetch_btn.set_sensitive(True)
        self._download_btn.set_sensitive(True)
        self._update_remux_dropdown()
        return False

    def _fetch_done(self, message):
        self._hide_progress()
        self._append_log(message)
        self._fetch_btn.set_sensitive(True)
        self._download_btn.set_sensitive(True)
        return False

    # ── Download ─────────────────────────────────────────────────────────

    def _on_download_clicked(self, button):
        settings = self._gather_settings()
        url = settings.get("Url", "").strip()
        if not url:
            self._append_log("ERROR: No URL entered.\n")
            return

        out_dir = settings.get("OutputDir", "")
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if settings.get("UseAria2", False):
            if not ensure_aria2_symlink():
                self._append_log("WARNING: aria2 not found. Aria2 acceleration unavailable.\n")

        if settings.get("EmbedThumbnail", False):
            try:
                import mutagen
            except ImportError:
                self._append_log("WARNING: mutagen not installed. Thumbnail embedding will fail for opus/ogg/flac.\n\n")

        self._save_settings()
        self._clear_log()
        self._downloading = True
        self._download_btn.set_sensitive(False)
        self._fetch_btn.set_sensitive(False)
        self._cancel_btn.set_sensitive(True)
        self._start_download_progress()

        args = build_download_args(settings, self.format_codecs, url)
        self._append_log(f"Command: {' '.join(args)}\n\n")

        thread = threading.Thread(target=self._download_thread, args=(args,), daemon=True)
        thread.start()

    def _on_cancel_clicked(self, button):
        if self._process and self._process.poll() is None:
            self._append_log("\n[User] Cancelling download process...\n")
            self._process.terminate()
            self._cancel_btn.set_sensitive(False)

    def _download_thread(self, args):
        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            for line in self._process.stdout:
                GLib.idle_add(self._append_log, line)
            self._process.wait()
            rc = self._process.returncode
            if rc == 0:
                GLib.idle_add(self._append_log, "\n[Finished] Download and processing completed successfully.\n")
            else:
                GLib.idle_add(self._append_log, f"\nProcess ended with exit code {rc}.\n")
        except FileNotFoundError:
            GLib.idle_add(self._append_log, "ERROR: yt-dlp not found. Install yt-dlp first.\n")
        except Exception as e:
            GLib.idle_add(self._append_log, f"\nERROR: {e}\n")
        finally:
            self._process = None
            GLib.idle_add(self._download_done)
        return False

    def _download_done(self):
        self._downloading = False
        self._download_btn.set_sensitive(True)
        self._fetch_btn.set_sensitive(True)
        self._cancel_btn.set_sensitive(False)
        if self._progress_bar.get_fraction() >= 1.0:
            self._progress_detail_label.set_markup("<b>Finished!</b>")
        else:
            self._progress_detail_label.set_markup("<i>Process halted</i>")
        return False


# ─── Self-Install (.desktop launcher, terminal runs only) ────────────────────

_DESKTOP_ID = "io.github.ytdlp_gui.desktop"
_ICON_NAME = "ytdlp-gtk"

_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <!-- Play button with download arrow -->
  <rect x="10" y="18" width="108" height="76" rx="20" fill="#cc241d"/>
  <polygon points="52,38 52,74 84,56" fill="#ffffff"/>
  <rect x="56" y="98" width="16" height="16" rx="3" fill="#ebdbb2"/>
  <polygon points="46,110 82,110 64,126" fill="#ebdbb2"/>
</svg>
"""


def _is_terminal_run():
    """True only when launched interactively (not via .desktop spawn)."""
    try:
        return bool((sys.stdout and sys.stdout.isatty()) or (sys.stderr and sys.stderr.isatty()))
    except Exception:
        return False


def ensure_self_install():
    """Install menu .desktop + generated SVG icon. No-op unless run from a TTY."""
    if not _is_terminal_run():
        return
    try:
        apps_dir = os.path.expanduser("~/.local/share/applications")
        icon_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
        os.makedirs(apps_dir, exist_ok=True)
        os.makedirs(icon_dir, exist_ok=True)

        icon_path = os.path.join(icon_dir, f"{_ICON_NAME}.svg")
        desktop_path = os.path.join(apps_dir, _DESKTOP_ID)
        exec_line = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

        entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            "Name=yt-dlp GUI\n"
            "GenericName=Video Downloader\n"
            "Comment=Download videos/audio via yt-dlp with format picking, proxy and aria2 acceleration\n"
            f"Exec={exec_line}\n"
            f"Icon={_ICON_NAME}\n"
            "Terminal=false\n"
            "Categories=Network;GTK;\n"
            "Keywords=youtube;download;video;audio;yt-dlp;\n"
            f"StartupWMClass=io.github.ytdlp_gui\n"
        )

        changed = False
        if not os.path.exists(icon_path):
            with open(icon_path, "w") as f:
                f.write(_ICON_SVG)
            changed = True

        current = ""
        if os.path.exists(desktop_path):
            with open(desktop_path, "r") as f:
                current = f.read()
        if current != entry:
            with open(desktop_path, "w") as f:
                f.write(entry)
            changed = True

        if changed:
            subprocess.run(
                ["update-desktop-database", "-q", apps_dir],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["gtk-update-icon-cache", "-q", "-f",
                 os.path.expanduser("~/.local/share/icons/hicolor")],
                capture_output=True, timeout=10,
            )
            print(f"[install] Menu entry ready: {desktop_path}")
    except Exception as e:
        # Cosmetic install must never prevent the app from launching.
        print(f"[install] skipped ({e})", file=sys.stderr)


# ─── Application Main ────────────────────────────────────────────────────────

class YtdlpApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.ytdlp_gui",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )


    def do_startup(self):
        Gtk.Application.do_startup(self)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(APP_CSS.encode())
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = YtdlpAppWindow(application=self)
        win.present()


def main():
    if "--version" in sys.argv:
        print(f"ytdlp-gtk {__version__}")
        return 0
    ensure_self_install()
    app = YtdlpApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
