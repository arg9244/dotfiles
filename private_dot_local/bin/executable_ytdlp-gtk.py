#!/usr/bin/env python3
"""yt-dlp Professional Wrapper — GTK3 Version

A full-featured GUI wrapper for yt-dlp built with Python 3 + PyGObject (GTK3).
Replicates all features from the original yt-dlp.bat Windows version.
"""
__version__ = "1.0.1"


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

import json
import os
import re
import sys
import shutil
import subprocess
import tempfile
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

DARK_CSS = """
window, .frame {
    background-color: #1e1e1e;
    color: #e0e0e0;
}
frame {
    border: 1px solid #444;
    border-radius: 4px;
    padding: 8px;
    margin: 4px 8px;
}
frame label {
    color: #e0e0e0;
    font-weight: bold;
}
.header-title {
    color: #007acc;
    font-size: 18px;
    font-weight: bold;
}
.header-status {
    font-size: 11px;
}
.status-ok {
    color: #4ec9b0;
}
.status-missing {
    color: #f44747;
}
status-warn {
    color: #cca700;
}
entry {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 4px;
}
combo text {
    background-color: #2d2d2d;
    color: #e0e0e0;
}
button {
    background-color: #007acc;
    color: white;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
button:hover {
    background-color: #1a8ad4;
}
button:disabled {
    background-color: #555;
    color: #999;
}
checkbutton label {
    color: #e0e0e0;
}
treeview, textview {
    background-color: #1a1a2e;
    color: #d4d4d4;
}
scrollbar {
    background-color: #2d2d2d;
}
progressbar trough {
    background-color: #2d2d2d;
}
progressbar progress {
    background-color: #007acc;
}
"""


def _has_ai_dub_indicator(info: str) -> bool:
    """Check if an audio track's MORE INFO text indicates an AI translation/dub.

    Detects patterns like:
    - "en - AI generated"  (language prefix + AI)
    - "AI dub" / "ai dub"
    - "AI dubbed" / "ai translated"
    - "Hindi (AI dubbed)"   (language name + AI dub marker)
    """
    info = info.lower()
    # "en - AI" or "es - AI" style language prefix
    if re.search(r"\b[a-z]{2}\s*-\s*ai\b", info):
        return True
    # "AI dub", "AI dubbed", "AI translated"
    if "ai dub" in info or "ai translat" in info:
        return True
    # "(AI dubbed)" or "(AI translated)" after a language name
    if re.search(r"\(ai\s*(dub|translat)", info):
        return True
    return False

# ─── Shared Helper Functions ─────────────────────────────────────────────────

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
    """Parse yt-dlp -F output into (video_list, audio_list, format_codecs).

    Each list item is a tuple (display_string, format_id).
    format_codecs maps format_id -> simplified codec string.

    AI-translated/dubbed audio tracks are filtered out by detecting
    dub markers (e.g. "en - AI generated", "AI dubbed") in MORE INFO.
    Tracks without dub markers are kept — including tracks without
    "original" text, which is not present on many non-dubbed videos.
    """
    video_list = []
    audio_list = []
    format_codecs = {}

    for line in raw_output.splitlines():
        line = line.strip()
        if not line or line.startswith("ID") or line.startswith("--"):
            continue

        # yt-dlp uses \u2502 (│) as delimiter with | as terminal fallback
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

        # Skip storyboards and MHTML
        if fmt_id.startswith("sb") or ext.lower() == "mhtml":
            continue
        rest_of_sec1 = " ".join(sec1[2:]).lower()
        if "storyboard" in rest_of_sec1 or "images" in rest_of_sec1:
            continue

        # Resolution / fps from section 1
        resolution = ""
        fps = ""
        # Look for NxN pattern
        res_found = False
        for tok in sec1[2:]:
            if re.match(r"\d+x\d+$", tok):
                resolution = tok
                res_found = True
                break
        if not res_found:
            # Check for "audio only" spanning multiple tokens
            combined = " ".join(sec1[2:]).lower()
            if "audio only" in combined:
                resolution = "audio only"
            else:
                resolution = " ".join(sec1[2:4]) if len(sec1) > 4 else " ".join(sec1[2:])

        # FPS: token after resolution if found
        if res_found:
            res_idx = sec1.index(resolution)
            if res_idx + 1 < len(sec1):
                fps_candidate = sec1[res_idx + 1]
                if re.match(r"\d+(\.\d+)?$", fps_candidate):
                    fps = fps_candidate

        filesize = sec2.strip()

        # Codecs from section 3
        def _is_codec_token(t):
            """Return True if token looks like a codec name (not keyword/bitrate/asr)."""
            low = t.lower()
            if low in ("video", "audio", "only"):
                return False
            if re.match(r"^\d+k$", low):    # bitrate like "128k", "2169k"
                return False
            if re.match(r"^\d+$", low):      # ASR like "48000", "44100"
                return False
            return True

        is_audio = "audio only" in resolution.lower()

        # ── Filter AI-translated/dubbed audio ─────────────────────────
        # Only exclude tracks with explicit AI-dub markers.
        # Many non-dubbed videos lack "original" text, so requiring it
        # would incorrectly filter out legitimate audio tracks.
        if is_audio:
            if _has_ai_dub_indicator(sec3_raw):
                continue  # skip AI-translated audio

        if is_audio:
            # Audio: first non-keyword/non-bitrate token is the audio codec
            raw_codec = "unknown"
            for t in sec3:
                if _is_codec_token(t):
                    raw_codec = t
                    break
            codec_display = simplify_codec(raw_codec)
            format_codecs[fmt_id] = codec_display
        else:
            # Video: first raw token is vcodec (before any filtering)
            v_raw = sec3[0] if sec3 else "unknown"
            v_codec = simplify_codec(v_raw)
            format_codecs[fmt_id] = v_codec

            # Find acodec: first subsequent token that passes codec filter
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

        # Build display string
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
    """Compute allowed remux containers based on selected codecs.

    video_codec and audio_codec are simplified codec strings or None.
    Returns a list of container option strings.
    """
    options = ["None"]

    if video_codec and audio_codec is not None:
        # Video + audio selected
        options.append("MKV")
        # WEBM: video in {vp9, vp8, av1} AND audio in {opus, vorbis, unknown, None}
        if video_codec in ("vp9", "vp8", "av1"):
            if audio_codec in ("opus", "vorbis", "unknown", None):
                options.append("WEBM")
        # MP4: video in {avc, hevc, av1} AND audio in {aac, mp3, unknown, None}
        if video_codec in ("avc", "hevc", "av1"):
            if audio_codec in ("aac", "mp3", "unknown", None):
                options.append("MP4")
    elif video_codec:
        # Video only selected
        options.append("MKV")
        if video_codec in ("vp9", "vp8", "av1"):
            options.append("WEBM")
        if video_codec in ("avc", "hevc", "av1"):
            options.append("MP4")
    elif audio_codec is not None:
        # Audio only selected
        options.append("MKA")
        if audio_codec in ("aac", "mp3", "unknown"):
            options.append("M4A")
        if audio_codec in ("opus", "vorbis", "unknown"):
            options.append("OGG")
        if audio_codec in ("opus", "unknown"):
            options.append("OPUS")
    else:
        # Neither selected
        options.extend(["MP4", "MKV", "WEBM"])

    return options


def build_download_args(settings, format_codecs, url):
    """Build yt-dlp command-line argument list from settings."""
    args = ["yt-dlp"]

    # Proxy
    proxy_type = settings.get("ProxyType", "None")
    proxy_addr = settings.get("ProxyAddr", "").strip()
    if proxy_type != "None" and proxy_addr:
        args.extend(["--proxy", f"{proxy_type.lower()}://{proxy_addr}"])

    # SSL
    if settings.get("IgnoreSSL", False):
        args.append("--no-check-certificate")

    # Cookies
    cookie_file = settings.get("CookieFile", "").strip()
    if cookie_file and os.path.isfile(cookie_file):
        args.extend(["--cookies", cookie_file])

    # Format selection
    vid = settings.get("VideoFormat", "None")
    aud = settings.get("AudioFormat", "None")

    if vid != "None" and aud != "None":
        # Strip display parts — extract just the format ID (first token)
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

    # Output
    out_dir = settings.get("OutputDir", "")
    out_name = settings.get("OutputName", "")
    if out_dir and out_name:
        full_output = os.path.join(out_dir, out_name)
        args.extend(["-o", full_output])

    # aria2
    if settings.get("UseAria2", False):
        aria_display = settings.get("AriaArgs", "")
        aria_flags = ARIA_SPEED_PRESETS.get(aria_display, "-c -j 4 -x 4 -s 4 -k 1M")
        # Add daemon-matching settings for consistency
        aria_extra = "--continue=true --check-integrity=true --auto-file-renaming=false --file-allocation=none"
        # Pass proxy to aria2 if set
        aria_proxy = ""
        if proxy_type != "None" and proxy_addr:
            aria_proxy = f" --all-proxy={proxy_type.lower()}://{proxy_addr}"
        aria_full = f"{aria_flags} {aria_extra}{aria_proxy}"
        args.extend(["--downloader", "aria2c", "--downloader-args", f"aria2c:{aria_full}"])

    # Metadata
    if settings.get("EmbedMetadata", False):
        args.append("--embed-metadata")

    # Thumbnail
    if settings.get("EmbedThumbnail", False):
        args.append("--embed-thumbnail")

    # Remux
    remux = settings.get("RemuxFormat", "None")
    if remux and remux != "None":
        remux_lower = remux.lower()
        if remux_lower in AUDIO_REMUX_CONTAINERS:
            args.append("-x")
            if remux_lower != "best":
                args.extend(["--audio-format", remux_lower])
        else:
            args.extend(["--remux-video", remux_lower])

    # URL last
    args.append(url)

    return args


def ensure_aria2_symlink():
    """Ensure aria2 is accessible for yt-dlp as 'aria2c'. Detects any variant.

    yt-dlp hardcodes EXE_NAME = 'aria2c'. If the system has aria2n or another
    variant but not aria2c, we create a symlink so yt-dlp can find it.
    Returns True if aria2c is now available.
    """
    if shutil.which("aria2c"):
        return True

    # Detect any aria2 variant on PATH
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
    """Check dependencies and return (name, level) tuples.

    Levels: 'ok' (green), 'missing' (red = required), 'warn' (yellow = optional).
    For aria2, the name includes the detected variant (aria2c/aria2n).
    """
    has_ytdlp = shutil.which("yt-dlp") is not None
    has_ffmpeg = shutil.which("ffmpeg") is not None

    # Detect aria2 variant
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


# ─── GTK Application ────────────────────────────────────────────────────────

class YtdlpApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="yt-dlp Professional Wrapper")
        self.set_default_size(650, 925)
        self.set_resizable(False)

        self.format_codecs = {}
        self.video_formats = []   # list of (display, id)
        self.audio_formats = []
        self.video_codecs = []    # list of unique codec strings
        self.audio_codecs = []    # list of unique codec strings
        self._downloading = False
        self._process = None

        self._apply_css()
        self._build_ui()
        self._load_settings()

        self.connect("destroy", self._on_destroy)

    # ── CSS ──────────────────────────────────────────────────────────────

    def _apply_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(DARK_CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_margin_start(8)
        main_box.set_margin_end(8)
        main_box.set_margin_top(4)
        main_box.set_margin_bottom(8)
        self.add(main_box)

        # 1. Header
        self._build_header(main_box)

        # 2. Target & Format
        self._build_target_format(main_box)

        # 3. Connection & Proxy
        self._build_connection_proxy(main_box)

        # 4. Output & Naming
        self._build_output_naming(main_box)

        # 5. Acceleration & Post-Processing
        self._build_acceleration(main_box)

        # 6. Start Download button
        self._build_download_button(main_box)

        # 7. Log
        self._build_log(main_box)

    def _build_header(self, parent):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(6)
        hbox.set_margin_bottom(8)
        parent.pack_start(hbox, False, False, 0)

        title = Gtk.Label()
        self._dep_label = Gtk.Label()
        self._dep_label.set_halign(Gtk.Align.END)
        self._dep_label.set_use_markup(True)
        self._update_dep_markup()
        hbox.pack_end(self._dep_label, False, False, 0)

    def _update_dep_markup(self):
        dep_parts, _ = get_dep_status()
        spans = []
        for name, level in dep_parts:
            color = "#4ec9b0" if level == "ok" else "#f44747" if level == "missing" else "#cca700"
            spans.append(f'<span foreground="{color}">{name}</span>')
        self._dep_label.set_markup("  │  ".join(spans))

    def _build_target_format(self, parent):
        frame = Gtk.Frame(label=" Target & Format ")
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(6)
        frame.add(vbox)

        # URL row
        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(url_row, False, False, 0)

        url_label = Gtk.Label(label="URL:")
        url_label.set_halign(Gtk.Align.START)
        url_row.pack_start(url_label, False, False, 0)

        self._url_entry = Gtk.Entry()
        self._url_entry.set_hexpand(True)
        self._url_entry.set_placeholder_text("Media or playlist URL...")
        url_row.pack_start(self._url_entry, True, True, 0)

        self._fetch_btn = Gtk.Button(label="Fetch")
        self._fetch_btn.connect("clicked", self._on_fetch_clicked)
        url_row.pack_start(self._fetch_btn, False, False, 0)

        # Format selectors — cascading codec + format pairs
        # Video row
        vid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(vid_row, False, False, 0)

        vid_label = Gtk.Label(label="Video:")
        vid_label.set_halign(Gtk.Align.START)
        vid_row.pack_start(vid_label, False, False, 0)

        self._video_codec_combo = Gtk.ComboBoxText()
        self._video_codec_combo.set_size_request(100, -1)
        self._video_codec_combo.append_text("All")
        self._video_codec_combo.set_active(0)
        self._video_codec_combo.connect("changed", self._on_video_codec_changed)
        vid_row.pack_start(self._video_codec_combo, False, False, 0)

        self._video_combo = Gtk.ComboBoxText()
        self._video_combo.set_hexpand(True)
        self._video_combo.append_text("None")
        self._video_combo.set_active(0)
        self._video_combo.connect("changed", self._on_format_changed)
        vid_row.pack_start(self._video_combo, True, True, 0)

        # Audio row
        aud_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(aud_row, False, False, 0)

        aud_label = Gtk.Label(label="Audio:")
        aud_label.set_halign(Gtk.Align.START)
        aud_row.pack_start(aud_label, False, False, 0)

        self._audio_codec_combo = Gtk.ComboBoxText()
        self._audio_codec_combo.set_size_request(100, -1)
        self._audio_codec_combo.append_text("All")
        self._audio_codec_combo.set_active(0)
        self._audio_codec_combo.connect("changed", self._on_audio_codec_changed)
        aud_row.pack_start(self._audio_codec_combo, False, False, 0)

        self._audio_combo = Gtk.ComboBoxText()
        self._audio_combo.set_hexpand(True)
        self._audio_combo.append_text("None")
        self._audio_combo.set_active(0)
        self._audio_combo.connect("changed", self._on_format_changed)
        aud_row.pack_start(self._audio_combo, True, True, 0)

        # Progress bar (hidden by default)
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_text("")
        self._pulse_id = None
        vbox.pack_start(self._progress_bar, False, False, 0)

    def _build_connection_proxy(self, parent):
        frame = Gtk.Frame(label=" Connection & Proxy ")
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(6)
        frame.add(vbox)

        # Proxy row
        proxy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(proxy_row, False, False, 0)

        proto_label = Gtk.Label(label="Protocol:")
        proto_label.set_halign(Gtk.Align.START)
        proxy_row.pack_start(proto_label, False, False, 0)

        self._proxy_type_combo = Gtk.ComboBoxText()
        for p in PROXY_PROTOCOLS:
            self._proxy_type_combo.append_text(p)
        self._proxy_type_combo.set_active(1)  # Default: HTTP
        proxy_row.pack_start(self._proxy_type_combo, False, False, 0)

        addr_label = Gtk.Label(label="Address:")
        addr_label.set_halign(Gtk.Align.START)
        proxy_row.pack_start(addr_label, False, False, 0)

        self._proxy_addr_entry = Gtk.Entry()
        self._proxy_addr_entry.set_hexpand(True)
        self._proxy_addr_entry.set_text("127.0.0.1:10810")
        proxy_row.pack_start(self._proxy_addr_entry, True, True, 0)

        # SSL checkbox
        self._ssl_check = Gtk.CheckButton(label="Ignore SSL/TLS Certificate Errors")
        self._ssl_check.set_active(True)
        vbox.pack_start(self._ssl_check, False, False, 0)

    def _build_output_naming(self, parent):
        frame = Gtk.Frame(label=" Output & Naming ")
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(6)
        frame.add(vbox)

        # Directory row
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(dir_row, False, False, 0)

        dir_label = Gtk.Label(label="Dir:")
        dir_label.set_halign(Gtk.Align.START)
        dir_row.pack_start(dir_label, False, False, 0)

        self._output_dir_entry = Gtk.Entry()
        self._output_dir_entry.set_hexpand(True)
        dir_row.pack_start(self._output_dir_entry, True, True, 0)

        browse_btn = Gtk.Button(label="Browse")
        browse_btn.connect("clicked", self._on_browse_clicked)
        dir_row.pack_start(browse_btn, False, False, 0)

        # Name template row
        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(name_row, False, False, 0)

        name_label = Gtk.Label(label="Name:")
        name_label.set_halign(Gtk.Align.START)
        name_row.pack_start(name_label, False, False, 0)

        self._output_name_entry = Gtk.Entry()
        self._output_name_entry.set_hexpand(True)
        name_row.pack_start(self._output_name_entry, True, True, 0)

        # Cookie file row
        cookie_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(cookie_row, False, False, 0)

        cookie_label = Gtk.Label(label="Cookie:")
        cookie_label.set_halign(Gtk.Align.START)
        cookie_row.pack_start(cookie_label, False, False, 0)

        self._cookie_entry = Gtk.Entry()
        self._cookie_entry.set_hexpand(True)
        self._cookie_entry.set_placeholder_text("/path/to/cookie.txt")
        cookie_row.pack_start(self._cookie_entry, True, True, 0)

    def _build_acceleration(self, parent):
        frame = Gtk.Frame(label=" Download Acceleration & Post-Processing ")
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_border_width(6)
        frame.add(vbox)

        # Remux row
        remux_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(remux_row, False, False, 0)

        remux_label = Gtk.Label(label="Remux:")
        remux_label.set_halign(Gtk.Align.START)
        remux_row.pack_start(remux_label, False, False, 0)

        self._remux_combo = Gtk.ComboBoxText()
        self._remux_combo.set_hexpand(True)
        for opt in ["None", "MP4", "MKV", "WEBM"]:
            self._remux_combo.append_text(opt)
        self._remux_combo.set_active(0)
        remux_row.pack_start(self._remux_combo, True, True, 0)

        # aria2c row
        aria_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(aria_row, False, False, 0)

        self._aria2_check = Gtk.CheckButton(label="Enable aria2")
        self._aria2_check.set_active(False)
        self._aria2_check.connect("toggled", self._on_aria_toggled)
        aria_row.pack_start(self._aria2_check, False, False, 0)

        speed_label = Gtk.Label(label="Speed:")
        speed_label.set_halign(Gtk.Align.START)
        aria_row.pack_start(speed_label, False, False, 0)

        self._aria_speed_combo = Gtk.ComboBoxText()
        self._aria_speed_combo.set_hexpand(True)
        for name in ARIA_SPEED_PRESETS:
            self._aria_speed_combo.append_text(name)
        self._aria_speed_combo.set_active(1)  # Default: Standard
        self._aria_speed_combo.set_sensitive(False)
        aria_row.pack_start(self._aria_speed_combo, True, True, 0)

        # Embed row
        embed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vbox.pack_start(embed_row, False, False, 0)

        self._embed_meta_check = Gtk.CheckButton(label="Embed Metadata")
        self._embed_meta_check.set_active(False)
        embed_row.pack_start(self._embed_meta_check, False, False, 0)

        self._embed_thumb_check = Gtk.CheckButton(label="Embed Thumbnail")
        self._embed_thumb_check.set_active(False)
        embed_row.pack_start(self._embed_thumb_check, False, False, 0)

    def _build_download_button(self, parent):
        self._download_btn = Gtk.Button(label="Start Download")
        self._download_btn.set_margin_top(4)
        self._download_btn.set_margin_bottom(4)
        self._download_btn.set_margin_start(40)
        self._download_btn.set_margin_end(40)
        self._download_btn.get_style_context().add_class("suggested-action")
        self._download_btn.connect("clicked", self._on_download_clicked)
        parent.pack_start(self._download_btn, False, False, 0)

    def _build_log(self, parent):
        frame = Gtk.Frame(label=" Output & Processing Log ")
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        parent.pack_start(frame, True, True, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(150)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        frame.add(scroll)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_cursor_visible(False)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_view.set_left_margin(8)
        self._log_view.set_right_margin(8)
        self._log_view.set_top_margin(4)
        self._log_view.set_bottom_margin(4)

        # Monospace font
        font_desc = "Monospace 10"
        self._log_view.modify_font(Pango.FontDescription(font_desc))

        # Dark background
        bg_color = Gdk.Color.parse("#1a1a2e")[1]
        self._log_view.modify_bg(Gtk.StateType.NORMAL, bg_color)
        fg_color = Gdk.Color.parse("#d4d4d4")[1]
        self._log_view.modify_fg(Gtk.StateType.NORMAL, fg_color)

        scroll.add(self._log_view)
        self._log_buffer = self._log_view.get_buffer()

    # ── Logging ──────────────────────────────────────────────────────────

    def _append_log(self, text):
        """Append text to log view (must be called from main thread via GLib.idle_add)."""
        end_iter = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end_iter, text)
        # Auto-scroll
        mark = self._log_buffer.create_mark(None, self._log_buffer.get_end_iter(), False)
        self._log_view.scroll_mark_onscreen(mark)

    def _clear_log(self):
        self._log_buffer.set_text("")

    # ── Settings ─────────────────────────────────────────────────────────

    def _load_settings(self):
        """Load settings from JSON file and populate widgets."""
        settings = dict(DEFAULT_SETTINGS)

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                settings.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass

        self._url_entry.set_text(settings.get("Url", ""))

        # Video format — set active by matching stored text
        self._set_combo_by_text(self._video_combo, settings.get("VideoFormat", "None"))
        self._set_combo_by_text(self._audio_combo, settings.get("AudioFormat", "None"))

        # Proxy
        proxy_type = settings.get("ProxyType", "HTTP")
        idx = PROXY_PROTOCOLS.index(proxy_type) if proxy_type in PROXY_PROTOCOLS else 1
        self._proxy_type_combo.set_active(idx)
        self._proxy_addr_entry.set_text(settings.get("ProxyAddr", ""))
        self._ssl_check.set_active(settings.get("IgnoreSSL", True))

        # Output
        self._output_dir_entry.set_text(settings.get("OutputDir", DEFAULT_SETTINGS["OutputDir"]))
        self._output_name_entry.set_text(settings.get("OutputName", DEFAULT_SETTINGS["OutputName"]))
        self._cookie_entry.set_text(settings.get("CookieFile", DEFAULT_SETTINGS["CookieFile"]))

        # Remux
        remux = settings.get("RemuxFormat", "None")
        self._set_combo_by_text(self._remux_combo, remux)

        # aria2c
        use_aria = settings.get("UseAria2", False)
        self._aria2_check.set_active(use_aria)
        self._aria_speed_combo.set_sensitive(use_aria)
        aria_name = settings.get("AriaArgs", "")
        self._set_combo_by_text(self._aria_speed_combo, aria_name)

        # Post-processing
        self._embed_meta_check.set_active(settings.get("EmbedMetadata", False))
        self._embed_thumb_check.set_active(settings.get("EmbedThumbnail", False))

    def _gather_settings(self):
        """Read current widget state into a settings dict."""
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
        """Save current settings to JSON file."""
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        settings = self._gather_settings()
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except OSError:
            pass

    # ── Combo Helpers ────────────────────────────────────────────────────

    def _set_combo_by_text(self, combo, text):
        """Set combo active item matching text, falling back to first item."""
        model = combo.get_model()
        if model is None:
            return
        for i, row in enumerate(model):
            if row[0] == text:
                combo.set_active(i)
                return
        # Try partial match for format strings (display text)
        for i, row in enumerate(model):
            if row[0].startswith(text.split()[0] if text.split() else ""):
                combo.set_active(i)
                return
        combo.set_active(0)

    def _get_combo_active_text(self, combo):
        """Get the text of the currently active combo item."""
        active = combo.get_active()
        if active < 0:
            return None
        model = combo.get_model()
        if model is None:
            return None
        return model[active][0]

    def _populate_combo(self, combo, items, keep_current=False):
        """Replace combo items. items is a list of (display, id) tuples."""
        current_text = self._get_combo_active_text(combo) if keep_current else None
        combo.remove_all()
        combo.append_text("None")
        for display, fmt_id in items:
            combo.append_text(display)
        combo.set_active(0)

        if keep_current and current_text:
            self._set_combo_by_text(combo, current_text)

    # ── Progress Bar ─────────────────────────────────────────────────────

    def _start_pulse(self):
        self._progress_bar.set_text("Working...")
        self._progress_bar.set_fraction(0.0)
        self._pulse_id = GLib.timeout_add(50, self._pulse_progress)

    def _pulse_progress(self):
        if self._pulse_id is None:
            return False
        self._progress_bar.pulse()
        return True

    def _stop_pulse(self):
        if self._pulse_id is not None:
            GLib.source_remove(self._pulse_id)
            self._pulse_id = None
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("")

    # ── Event Handlers ───────────────────────────────────────────────────

    def _on_destroy(self, widget):
        self._save_settings()
        if self._process and self._process.poll() is None:
            self._process.terminate()
        Gtk.main_quit()

    def _on_browse_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Output Directory",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        current_dir = self._output_dir_entry.get_text().strip()
        if current_dir and os.path.isdir(current_dir):
            dialog.set_current_folder(current_dir)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._output_dir_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _on_aria_toggled(self, checkbox):
        self._aria_speed_combo.set_sensitive(checkbox.get_active())

    def _on_format_changed(self, combo):
        """Update remux dropdown when video or audio format changes."""
        self._update_remux_dropdown()

    def _on_video_codec_changed(self, combo):
        """Filter video format dropdown by selected codec."""
        codec = self._get_combo_active_text(combo) or "All"
        self._filter_video_formats(codec)

    def _on_audio_codec_changed(self, combo):
        """Filter audio format dropdown by selected codec."""
        codec = self._get_combo_active_text(combo) or "All"
        self._filter_audio_formats(codec)

    def _filter_video_formats(self, codec):
        """Repopulate video combo showing only formats matching the codec."""
        current = self._get_combo_active_text(self._video_combo)
        self._video_combo.remove_all()
        self._video_combo.append_text("None")
        for display, fmt_id in self.video_formats:
            if codec == "All" or self.format_codecs.get(fmt_id, "") == codec:
                self._video_combo.append_text(display)
        # Restore previous selection if still visible
        if current and current != "None":
            self._set_combo_by_text(self._video_combo, current)
        if self._get_combo_active_text(self._video_combo) is None:
            self._video_combo.set_active(0)

    def _filter_audio_formats(self, codec):
        """Repopulate audio combo showing only formats matching the codec."""
        current = self._get_combo_active_text(self._audio_combo)
        self._audio_combo.remove_all()
        self._audio_combo.append_text("None")
        for display, fmt_id in self.audio_formats:
            if codec == "All" or self.format_codecs.get(fmt_id, "") == codec:
                self._audio_combo.append_text(display)
        # Restore previous selection if still visible
        if current and current != "None":
            self._set_combo_by_text(self._audio_combo, current)
        if self._get_combo_active_text(self._audio_combo) is None:
            self._audio_combo.set_active(0)

    def _update_remux_dropdown(self):
        """Recompute remux options based on current codec selections."""
        vid_text = self._get_combo_active_text(self._video_combo) or "None"
        aud_text = self._get_combo_active_text(self._audio_combo) or "None"

        # Extract format ID from display text (first token)
        v_id = vid_text.split()[0] if vid_text != "None" else None
        a_id = aud_text.split()[0] if aud_text != "None" else None

        v_codec = self.format_codecs.get(v_id) if v_id else None
        a_codec = self.format_codecs.get(a_id) if a_id else None

        options = compute_remux_options(v_codec, a_codec)

        # Save current selection
        current_remux = self._get_combo_active_text(self._remux_combo)

        # Rebuild combo
        self._remux_combo.remove_all()
        for opt in options:
            self._remux_combo.append_text(opt)

        # Restore if still valid, else select first
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
        self._clear_log()
        self._append_log("Fetching format list...\n")
        self._start_pulse()

        thread = threading.Thread(target=self._fetch_thread, args=(url,), daemon=True)
        thread.start()

    def _fetch_thread(self, url):
        settings = self._gather_settings()
        cmd = ["yt-dlp", "-F", url]

        # Proxy
        proxy_type = settings.get("ProxyType", "None")
        proxy_addr = settings.get("ProxyAddr", "").strip()
        if proxy_type != "None" and proxy_addr:
            cmd = ["yt-dlp", "--proxy", f"{proxy_type.lower()}://{proxy_addr}", "-F", url]

        # SSL
        if settings.get("IgnoreSSL", False):
            cmd.insert(1, "--no-check-certificate")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
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
        """Parse fetched output and populate format dropdowns. Called from main thread."""
        self._stop_pulse()

        video_list, audio_list, fmt_codecs = parse_formats(raw_output)
        self.video_formats = video_list
        self.audio_formats = audio_list
        self.format_codecs = fmt_codecs

        # Extract unique codecs for cascading filters
        v_codecs = sorted({fmt_codecs.get(fmt_id, "unknown") for _, fmt_id in video_list})
        a_codecs = sorted({fmt_codecs.get(fmt_id, "unknown") for _, fmt_id in audio_list})
        self.video_codecs = v_codecs
        self.audio_codecs = a_codecs

        self._append_log(raw_output)
        filtered_audio = len(self.audio_formats)
        self._append_log(f"\nFound {len(video_list)} video, {filtered_audio} audio format(s).\n")

        # Populate codec combos
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

        # Populate format combos (unfiltered initially)
        self._populate_combo(self._video_combo, video_list)
        self._populate_combo(self._audio_combo, audio_list)

        self._fetch_btn.set_sensitive(True)
        self._download_btn.set_sensitive(True)

        self._update_remux_dropdown()
        return False

    def _fetch_done(self, message):
        """Handle fetch error. Called from main thread."""
        self._stop_pulse()
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

        # Ensure output directory exists
        out_dir = settings.get("OutputDir", "")
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Ensure aria2c is available if needed
        if settings.get("UseAria2", False):
            if not ensure_aria2_symlink():
                self._append_log("WARNING: aria2 not found. Aria2 acceleration unavailable.\n")

        # Warn about missing mutagen for thumbnail embedding
        if settings.get("EmbedThumbnail", False):
            try:
                import mutagen
            except ImportError:
                self._append_log("WARNING: mutagen not installed. Thumbnail embedding will fail for opus/ogg/flac.\n")
                self._append_log("  Install with: sudo pacman -S python-mutagen\n\n")

        self._save_settings()
        self._clear_log()
        self._downloading = True
        self._download_btn.set_sensitive(False)
        self._fetch_btn.set_sensitive(False)
        self._start_pulse()

        args = build_download_args(settings, self.format_codecs, url)

        cmd_display = " ".join(args)
        self._append_log(f"Command: {cmd_display}\n\n")

        thread = threading.Thread(target=self._download_thread, args=(args,), daemon=True)
        thread.start()

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
            GLib.idle_add(self._append_log, f"\nProcess finished with exit code {rc}.\n")
        except FileNotFoundError:
            GLib.idle_add(self._append_log, "ERROR: yt-dlp not found. Install yt-dlp first.\n")
        except Exception as e:
            GLib.idle_add(self._append_log, f"\nERROR: {e}\n")
        finally:
            self._process = None
            GLib.idle_add(self._download_done)
        return False

    def _download_done(self):
        """Re-enable UI after download completes. Called from main thread."""
        self._stop_pulse()
        self._downloading = False
        self._download_btn.set_sensitive(True)
        self._fetch_btn.set_sensitive(True)
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if "--version" in sys.argv:
        print(f"ytdlp-gtk {__version__}")
        return
    app = YtdlpApp()
    app.show_all()
    # Hide progress bar initially
    app._progress_bar.hide()
    Gtk.main()


if __name__ == "__main__":
    main()
