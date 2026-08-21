#!/usr/bin/env python3
"""Universal RAR Backup & Restore Pro — Gruvbox Edition (GTK4 Background Analyzer)

A full-featured GUI for RAR game/folder compression and extraction with
Instant Background Heuristics, Multi-Part Volume Auto-Detection, Automatic
Embedded Recovery Record (-rr) Healing, .rev Volume Reconstruction, BLAKE3
integrity hashing, thermal cooldown, RAM caching, and SMART telemetry.
"""
__version__ = "3.8.0"

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio

import json
import os
import re
import sys
import time
import zlib
import shutil
import signal
import tempfile
import threading
import subprocess
from collections import defaultdict

# ─── Settings & Defaults ───────────────────────────────────────────────────

SETTINGS_DIR = os.path.expanduser("~/.config/rar-backup-gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

DEFAULT_SETTINGS = {
    # Compression Settings
    "SourceDir": "",
    "DestDir": "",
    "ArchivePrefix": "archive",
    "VolumeSize": "4000m",
    "EnableRecovery": True,
    "RecoveryRecord": "5%",
    "CompressionLevel": 0,  # 0 = Smart, 1..6 = Manual 0..5
    "SmartCutoff": "10%",   # Auto-tuned or custom input percentage
    "DictSize": 2,          # 0 = 32M, 1 = 64M, 2 = 128M, 3 = 256M, 4 = 1024M
    "Threads": "12",
    "StoreMask": "*.uab;*.pak;*.acb;*.awb;*.usm;*.bundle;*.assets;*.pck;*.bk2;*.mp4;*.webm;*.dll;*.exe;*.png;*.wav;*.ress;*.gz;*.zip;*.ushaderprecache;*.sig;*.bin;*.bytes",
    "GenBlake3": True,

    # Extraction Settings
    "ExtractArchive": "",
    "ExtractDest": "",
    "AutoRepair": True,     # Automatically repair with -rr or reconstruct with .rev
    "VerifyBlake3": True,
    "OverwriteMode": 0,     # 0=Overwrite, 1=Skip

    # Shared Hardware & Thermal
    "UseRamTmp": True,
    "CustomTmpDir": "/tmp",
    "IoniceMode": 1,        # 0=None, 1=Best Effort P7, 2=Idle
    "EnableCooldown": False,
    "CooldownSeconds": 180,
    "CheckFreeSpace": True,
}

# ─── Gruvbox Dark Theme CSS ────────────────────────────────────────────────

GRUVBOX_CSS = """
window, .frame, notebook, notebook > stack {
    background-color: #282828;
    color: #ebdbb2;
}
notebook header {
    background-color: #1d2021;
    border-bottom: 2px solid #3c3836;
}
notebook tab {
    background-color: #3c3836;
    color: #a89984;
    padding: 4px 10px;
    margin: 2px 2px 0 2px;
    border-radius: 4px 4px 0 0;
    font-weight: bold;
    border: 1px solid #504945;
    border-bottom: none;
}
notebook tab:checked {
    background-color: #282828;
    color: #fabd2f;
    border-top: 2px solid #fe8019;
}
notebook tab:hover {
    color: #ebdbb2;
}
frame {
    border: 1px solid #504945;
    border-radius: 5px;
    padding: 4px;
    margin: 2px 1px;
    background-color: #282828;
}
frame > label {
    color: #fabd2f;
    font-weight: bold;
}
entry {
    background-color: #3c3836;
    color: #ebdbb2;
    border: 1px solid #665c54;
    border-radius: 3px;
    padding: 3px 5px;
}
entry:focus {
    border-color: #fe8019;
}
entry:disabled {
    background-color: #282828;
    color: #7c6f64;
    border-color: #3c3836;
}
dropdown button, dropdown {
    background-color: #3c3836;
    color: #ebdbb2;
    border-color: #665c54;
}
dropdown:disabled {
    opacity: 0.45;
}
button {
    background-color: #458588;
    color: #ebdbb2;
    border: 1px solid #83a598;
    border-radius: 4px;
    padding: 4px 10px;
    font-weight: bold;
}
button:hover {
    background-color: #83a598;
    color: #1d2021;
}
button.start-btn {
    background-color: #98971a;
    color: #1d2021;
    border-color: #b8bb26;
}
button.start-btn:hover {
    background-color: #b8bb26;
    color: #1d2021;
}
button.cancel-btn {
    background-color: #cc241d;
    color: #ebdbb2;
    border-color: #fb4934;
}
button.cancel-btn:hover {
    background-color: #fb4934;
    color: #1d2021;
}
button:disabled {
    background-color: #3c3836;
    color: #7c6f64;
    border-color: #504945;
}
checkbutton label {
    color: #ebdbb2;
}
checkbutton:checked check {
    background-color: #fe8019;
    color: #282828;
}
textview, textview text {
    background-color: #1d2021;
    color: #ebdbb2;
    font-family: monospace;
    font-size: 8.5pt;
}
progressbar trough {
    background-color: #3c3836;
    border-radius: 3px;
}
progressbar progress {
    background-color: #fe8019;
    border-radius: 3px;
}
scrollbar slider {
    background-color: #504945;
}
"""

# ─── System & Telemetry Utilities ──────────────────────────────────────────

def human_bytes(b: float) -> str:
    if b >= 1073741824: return f"{b / 1073741824:.2f} GB"
    if b >= 1048576:    return f"{b / 1048576:.2f} MB"
    if b >= 1024:       return f"{b / 1024:.2f} KB"
    return f"{int(b)} B"

def human_seconds(s: int) -> str:
    s = max(0, int(s))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

def get_disk_temperature(dev_path: str) -> str:
    if not dev_path:
        return ""

    dev_base = os.path.basename(dev_path)

    # Layer 1: Kernel drivetemp / hwmon
    hwmon_dirs = [
        f"/sys/block/{dev_base}/device/hwmon",
        f"/sys/class/block/{dev_base}/device/hwmon",
    ]
    for hdir in hwmon_dirs:
        if os.path.exists(hdir):
            try:
                for sub in os.listdir(hdir):
                    tfile = os.path.join(hdir, sub, "temp1_input")
                    if os.path.exists(tfile):
                        with open(tfile, "r") as f:
                            val = int(f.read().strip())
                            return str(round(val / 1000.0))
            except Exception:
                pass

    try:
        for hw in os.listdir("/sys/class/hwmon"):
            hw_path = os.path.join("/sys/class/hwmon", hw)
            name_file = os.path.join(hw_path, "name")
            if os.path.exists(name_file):
                with open(name_file, "r") as f:
                    if "drivetemp" in f.read():
                        tfile = os.path.join(hw_path, "temp1_input")
                        if os.path.exists(tfile):
                            with open(tfile, "r") as f:
                                return str(round(int(f.read().strip()) / 1000.0))
    except Exception:
        pass

    # Layer 2: UDisks2 Daemon
    if shutil.which("udisksctl"):
        try:
            res = subprocess.run(["udisksctl", "info", "-b", dev_path], capture_output=True, text=True, timeout=1.2)
            for line in res.stdout.splitlines():
                if "SmartTemperature" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        k_val = float(parts[1].strip())
                        if k_val > 200:
                            return str(round(k_val - 273.15))
                elif "Temperature:" in line or "temperature:" in line.lower():
                    m = re.search(r'(\d+)\s*°?\s*C', line)
                    if m:
                        return m.group(1)
        except Exception:
            pass

    # Layer 3: smartctl
    if shutil.which("smartctl") and os.path.exists(dev_path):
        cmd_variants = [
            ["smartctl", "-n", "standby", "-A", "-d", "sat", dev_path],
            ["smartctl", "-n", "standby", "-A", "-d", "auto", dev_path],
            ["smartctl", "-n", "standby", "-A", dev_path],
        ]
        for cmd in cmd_variants:
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.2)
                for line in res.stdout.splitlines():
                    if re.search(r"Temperature_Celsius|Temperature_Composite|Current Drive Temperature|Temperature:", line, re.IGNORECASE):
                        parts = line.split()
                        if len(parts) >= 10 and parts[9].isdigit():
                            return parts[9]
                        elif len(parts) >= 2 and parts[-1].isdigit():
                            return parts[-1]
                        m = re.search(r'(\d+)\s*(?:C|Celsius)?', line)
                        if m:
                            return m.group(1)
            except Exception:
                pass

    return ""

def get_drive_device(target_dir: str) -> str:
    if not os.path.exists(target_dir):
        return ""
    try:
        res = subprocess.run(["df", target_dir], capture_output=True, text=True)
        lines = res.stdout.strip().splitlines()
        if len(lines) >= 2:
            dev = lines[1].split()[0]
            dev = re.sub(r'p\d+$', '', dev)
            dev = re.sub(r'\d+$', '', dev)
            if os.path.exists(dev):
                return dev
    except Exception:
        pass
    return ""

def get_free_bytes(path: str) -> int:
    try:
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize
    except Exception:
        return -1

def get_dir_size_and_count(path: str):
    total_bytes = 0
    count = 0
    for root, _, files in os.walk(path):
        for f in files:
            count += 1
            try:
                total_bytes += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    return total_bytes, count

# ─── Multi-Part Archive & Recovery Engine ───────────────────────────────────

def get_rar_archive_info(selected_path: str) -> dict:
    """
    Scans the parent directory of any chosen archive part, identifies all parts
    belonging to the set, verifies sequence continuity, resolves the true First Volume,
    locates any available .rev recovery files, and returns comprehensive volume set metadata.
    """
    if not selected_path or not os.path.exists(selected_path):
        return None

    selected_path = os.path.abspath(selected_path)
    arc_dir = os.path.dirname(selected_path)
    fname = os.path.basename(selected_path)

    try:
        dir_files = os.listdir(arc_dir)
    except Exception:
        dir_files = [fname]

    # Pattern 1: Modern New-style (<base>.part1.rar, <base>.part01.rar, etc.)
    m_part = re.search(r'^(.*)\.part(\d+)\.rar$', fname, re.IGNORECASE)

    # Pattern 2: Numbered split (<base>.rar.001 or <base>.001)
    m_num = re.search(r'^(.*)\.rar\.(\d+)$', fname, re.IGNORECASE)
    if not m_num:
        m_num = re.search(r'^(.*)\.(\d{3,})$', fname, re.IGNORECASE)

    # Pattern 3: Old-style (<base>.rar + <base>.r00, .r01, .s00...)
    m_old = re.search(r'^(.*)\.(rar|r\d+|s\d+|t\d+)$', fname, re.IGNORECASE)

    # Pattern 4: Direct .rev file chosen
    m_rev = re.search(r'^(.*)\.part(\d+)\.rev$', fname, re.IGNORECASE)
    if not m_rev:
        m_rev = re.search(r'^(.*)\.rev$', fname, re.IGNORECASE)

    first_volume = selected_path
    all_parts = [selected_path]
    missing_parts = []
    base_name = os.path.splitext(fname)[0]

    if m_part or m_rev:
        raw_base = (m_part or m_rev).group(1)
        base_name = raw_base
        pattern = re.compile(rf'^{re.escape(raw_base)}\.part(\d+)\.rar$', re.IGNORECASE)
        found = []
        for f in dir_files:
            m = pattern.search(f)
            if m:
                found.append((int(m.group(1)), os.path.join(arc_dir, f)))
        if found:
            found.sort(key=lambda x: x[0])
            all_parts = [p[1] for p in found]
            first_volume = all_parts[0]

            nums = [p[0] for p in found]
            start_num = 1 if (0 not in nums) else 0
            actual_set = set(nums)
            for exp in range(start_num, max(nums) + 1):
                if exp not in actual_set:
                    missing_parts.append(exp)

    elif m_num:
        raw_base = m_num.group(1)
        base_name = raw_base
        pattern = re.compile(rf'^{re.escape(raw_base)}(?:\.rar)?\.(\d+)$', re.IGNORECASE)
        found = []
        for f in dir_files:
            m = pattern.search(f)
            if m:
                found.append((int(m.group(1)), os.path.join(arc_dir, f)))
        if found:
            found.sort(key=lambda x: x[0])
            all_parts = [p[1] for p in found]
            first_volume = all_parts[0]

            nums = [p[0] for p in found]
            start_num = 1 if (0 not in nums) else 0
            actual_set = set(nums)
            for exp in range(start_num, max(nums) + 1):
                if exp not in actual_set:
                    missing_parts.append(exp)

    elif m_old:
        raw_base = m_old.group(1)
        base_name = raw_base
        main_rar = None
        r_parts = []
        for f in dir_files:
            if f.lower() == f"{raw_base.lower()}.rar":
                main_rar = os.path.join(arc_dir, f)
            else:
                m_r = re.search(rf'^{re.escape(raw_base)}\.([rst])(\d+)$', f, re.IGNORECASE)
                if m_r:
                    letter = m_r.group(1).lower()
                    seq_offset = 0 if letter == 'r' else (100 if letter == 's' else 200)
                    r_num = int(m_r.group(2)) + seq_offset
                    r_parts.append((r_num, os.path.join(arc_dir, f)))

        r_parts.sort(key=lambda x: x[0])
        if main_rar:
            all_parts = [main_rar] + [p[1] for p in r_parts]
            first_volume = main_rar
        elif r_parts:
            all_parts = [p[1] for p in r_parts]
            first_volume = all_parts[0]

    else:
        base_name = re.sub(r'\.rar$', '', fname, flags=re.IGNORECASE)
        all_parts = [selected_path]
        first_volume = selected_path

    # Discover any associated .rev recovery volumes
    rev_pattern = re.compile(rf'^{re.escape(base_name)}(?:\.part\d+)?\.rev$', re.IGNORECASE)
    rev_files = sorted([
        os.path.join(arc_dir, f) for f in dir_files
        if rev_pattern.search(f)
    ])

    total_compressed = sum(os.path.getsize(p) for p in all_parts if os.path.exists(p))

    return {
        "first_volume": first_volume,
        "all_parts": all_parts,
        "total_parts": len(all_parts),
        "total_compressed_bytes": total_compressed,
        "missing_parts": missing_parts,
        "base_name": base_name,
        "rev_files": rev_files,
        "arc_dir": arc_dir,
    }

def estimate_rar_uncompressed_size(first_vol: str, total_comp_bytes: int) -> int:
    """Accurately parses uncompressed payload size across multi-volume sets using 'rar/unrar v -v'."""
    rar_bin = shutil.which("rar") or shutil.which("unrar")
    if not rar_bin:
        return max(total_comp_bytes, int(total_comp_bytes * 1.25))

    try:
        res = subprocess.run(
            [rar_bin, "v", "-v", "-c-", "-idq", first_vol],
            capture_output=True,
            text=True,
            timeout=6.0
        )
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        for line in reversed(lines):
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                uncomp = int(parts[1])
                if uncomp > 0:
                    return uncomp
            m = re.search(r'(\d+)\s+bytes', line, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > 0:
                    return val
    except Exception:
        pass

    return max(total_comp_bytes, int(total_comp_bytes * 1.25))

def reconstruct_from_rev_volumes(arc_dir: str, first_rev: str, log_fn) -> bool:
    """Invokes 'rar rc' or 'unrar rc' to rebuild missing .rar volumes using parity .rev files."""
    rar_bin = shutil.which("rar") or shutil.which("unrar")
    if not rar_bin or not os.path.exists(first_rev):
        return False

    log_fn(f"\n⚡ RECONSTRUCTING MISSING PARTS using {os.path.basename(first_rev)}...\n")
    try:
        proc = subprocess.Popen(
            [rar_bin, "rc", "-y", first_rev],
            cwd=arc_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in proc.stdout:
            if any(k in line.lower() for k in ["reconstruct", "creating", "ok", "done", "volume"]):
                log_fn(f"   • {line.strip()}\n")
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        log_fn(f"❌ .rev reconstruction error: {e}\n")
        return False

def auto_repair_damaged_volumes(volume_paths: list, log_fn) -> list:
    """
    Executes 'rar r' on damaged volumes using embedded recovery records (-rr).
    Swaps fixed.*.rar files into place while preserving .corrupt backups.
    Returns list of successfully repaired volume paths.
    """
    rar_bin = shutil.which("rar")
    if not rar_bin:
        log_fn("⚠️ 'rar' binary not found. Cannot execute internal -rr repair.\n")
        return []

    repaired = []
    log_fn("\n🩹 AUTO-RECOVERY TRIGGERED: Applying Embedded Recovery Records (-rr)...\n")

    for vol in volume_paths:
        if not os.path.exists(vol):
            continue

        vdir = os.path.dirname(os.path.abspath(vol))
        vname = os.path.basename(vol)
        log_fn(f"   🔍 Scanning parity for: {vname} ... ")

        try:
            res = subprocess.run(
                [rar_bin, "r", "-y", "-idq", vname],
                cwd=vdir,
                capture_output=True,
                text=True,
                timeout=120.0
            )

            # Output file is fixed.<name> or rebuilt.<name>
            candidates = [
                os.path.join(vdir, f"fixed.{vname}"),
                os.path.join(vdir, f"rebuilt.{vname}")
            ]
            fixed_path = None
            for cand in candidates:
                if os.path.exists(cand) and os.path.getsize(cand) > 0:
                    fixed_path = cand
                    break

            if fixed_path:
                log_fn(f"REPAIRED! ✅\n")
                backup_path = os.path.join(vdir, f".{vname}.corrupt_bak")
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                shutil.move(vol, backup_path)
                shutil.move(fixed_path, vol)
                repaired.append(vol)
                log_fn(f"      → Swapped: {os.path.basename(fixed_path)} → {vname} (Original backed up)\n")
            else:
                log_fn("No recoverable parity record found.\n")
        except Exception as e:
            log_fn(f"Failed: {e}\n")

    return repaired

# ─── Advanced Compressibility Analyzer ───────────────────────────────────────

def sample_directory_extensions(source_dir: str):
    ext_files = defaultdict(list)
    ext_sizes = defaultdict(int)
    ext_counts = defaultdict(int)
    total_bytes = 0

    for root, _, files in os.walk(source_dir):
        for f in files:
            if f.startswith(".") or f.endswith("_checksums.b3") or f == "checksums.b3":
                continue
            ext = os.path.splitext(f)[1].lower() or "[no_ext]"
            full_p = os.path.join(root, f)
            try:
                sz = os.path.getsize(full_p)
                total_bytes += sz
                ext_sizes[ext] += sz
                ext_counts[ext] += 1
                if len(ext_files[ext]) < 3 and sz >= 2048:
                    ext_files[ext].append(full_p)
            except OSError:
                pass

    ext_stats = {}
    for ext, files in ext_files.items():
        total_orig = 0
        total_comp = 0
        for fpath in files:
            try:
                with open(fpath, "rb") as fp:
                    if os.path.getsize(fpath) > 8192:
                        fp.seek(2048)
                    chunk = fp.read(65536)
                    if chunk:
                        comp = zlib.compress(chunk, level=1)
                        total_orig += len(chunk)
                        total_comp += len(comp)
            except OSError:
                continue

        if total_orig > 0:
            ratio = total_comp / total_orig
            savings = max(0.0, (1.0 - ratio) * 100)
        else:
            ratio = 1.0
            savings = 0.0

        ext_stats[ext] = {
            "ratio": ratio,
            "savings": savings,
            "size": ext_sizes[ext],
            "count": ext_counts[ext]
        }

    return ext_stats, total_bytes

def calculate_smart_cutoff(ext_stats: dict) -> float:
    if not ext_stats:
        return 10.0

    marginal_heavy_savings = []
    for ext, data in ext_stats.items():
        if ext == "[no_ext]":
            continue
        if data["size"] > 1024 * 1024 * 1024 and 3.0 <= data["savings"] <= 16.0:
            marginal_heavy_savings.append(data["savings"])

    if marginal_heavy_savings:
        rec = max(marginal_heavy_savings) + 0.9
        return min(25.0, max(5.0, round(rec, 1)))

    return 10.0

# ─── Application Window ─────────────────────────────────────────────────────

class RarBackupWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="RAR Backup Pro — Gruvbox")
        self.set_default_size(600, 640)
        self.set_resizable(True)

        self._is_running = False
        self._current_job = "idle"
        self._cancel_requested = False
        self._current_process = None
        self._current_work_dir = ""

        # Pre-scan Analysis Cache
        self._analysis_cache_path = ""
        self._cached_ext_stats = {}
        self._cached_total_bytes = 0
        self._analysis_in_progress = False

        # Progress stats
        self._target_bytes = 0
        self._last_size = 0
        self._start_time = 0
        self._last_time = 0
        self._ema_rate = 0.0
        self._monitor_timer_id = None

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        main_box.set_margin_start(5)
        main_box.set_margin_end(5)
        main_box.set_margin_top(4)
        main_box.set_margin_bottom(5)
        self.set_child(main_box)

        # Header
        self._build_header(main_box)

        # Notebook Tabs
        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        self._notebook.set_vexpand(False)
        main_box.append(self._notebook)

        # Tabs
        self._build_tab_compression()
        self._build_tab_extraction()
        self._build_tab_hardware()

        # Shared Persistent Bottom Output
        self._build_shared_output(main_box)

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self, parent):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        parent.append(hbox)

        title = Gtk.Label()
        title.set_markup("<span size='medium' weight='bold' foreground='#fabd2f'>📦 RAR Backup Pro</span>")
        hbox.append(title)

        self._dep_label = Gtk.Label()
        self._dep_label.set_halign(Gtk.Align.END)
        self._dep_label.set_hexpand(True)
        self._dep_label.set_use_markup(True)
        self._update_dep_status()
        hbox.append(self._dep_label)

    def _update_dep_status(self):
        has_rar = shutil.which("rar") is not None
        has_unrar = shutil.which("unrar") is not None
        archiver_ok = has_rar or has_unrar
        archiver_name = "rar" if has_rar else ("unrar" if has_unrar else "rar/unrar")

        deps = [
            (archiver_name, archiver_ok, True),
            ("b3sum", shutil.which("b3sum") is not None, False),
            ("smartctl/udisks", shutil.which("smartctl") is not None or shutil.which("udisksctl") is not None, False),
            ("ionice", shutil.which("ionice") is not None, False),
        ]
        spans = []
        for name, ok, req in deps:
            color = "#b8bb26" if ok else ("#fb4934" if req else "#fe8019")
            spans.append(f'<span foreground="{color}">{name}</span>')
        self._dep_label.set_markup(" │ ".join(spans))

    # ── Tab 1: Compression ────────────────────────────────────────────────────

    def _build_tab_compression(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        vbox.set_margin_start(3)
        vbox.set_margin_end(3)
        vbox.set_margin_top(3)
        vbox.set_margin_bottom(3)
        self._notebook.append_page(vbox, Gtk.Label(label=" 🗜️ Compress "))

        # Target Path Inputs
        frame_targets = Gtk.Frame(label=" Paths & Naming ")
        vbox.append(frame_targets)

        grid_paths = Gtk.Grid(row_spacing=3, column_spacing=5)
        grid_paths.set_margin_start(3)
        grid_paths.set_margin_end(3)
        grid_paths.set_margin_top(3)
        grid_paths.set_margin_bottom(3)
        frame_targets.set_child(grid_paths)

        # Source
        grid_paths.attach(Gtk.Label(label="Source:"), 0, 0, 1, 1)
        self._src_entry = Gtk.Entry(hexpand=True)
        self._src_entry.set_placeholder_text("Select game or directory...")
        self._src_entry.set_tooltip_text("Directory to compress.")
        grid_paths.attach(self._src_entry, 1, 0, 1, 1)

        btn_src = Gtk.Button(label="Browse")
        btn_src.connect("clicked", self._on_browse_source)
        grid_paths.attach(btn_src, 2, 0, 1, 1)

        # Destination
        grid_paths.attach(Gtk.Label(label="Dest:"), 0, 1, 1, 1)
        self._dest_entry = Gtk.Entry(hexpand=True)
        self._dest_entry.set_placeholder_text("Target storage directory...")
        self._dest_entry.set_tooltip_text("Directory where the .rar archive will be saved.")
        grid_paths.attach(self._dest_entry, 1, 1, 1, 1)

        btn_dest = Gtk.Button(label="Browse")
        btn_dest.connect("clicked", lambda w: self._browse_dir(self._dest_entry, "Select Destination Folder"))
        grid_paths.attach(btn_dest, 2, 1, 1, 1)

        # Base Name
        grid_paths.attach(Gtk.Label(label="Archive:"), 0, 2, 1, 1)
        self._name_entry = Gtk.Entry(hexpand=True, text="archive")
        self._name_entry.set_tooltip_text("Base archive name (e.g., 'game' -> 'game.part1.rar').")
        grid_paths.attach(self._name_entry, 1, 2, 2, 1)

        # Format & Compression Options
        frame_params = Gtk.Frame(label=" Compression Settings ")
        vbox.append(frame_params)

        grid_params = Gtk.Grid(row_spacing=5, column_spacing=6)
        grid_params.set_margin_start(3)
        grid_params.set_margin_end(3)
        grid_params.set_margin_top(3)
        grid_params.set_margin_bottom(3)
        frame_params.set_child(grid_params)

        # Compression Levels
        grid_params.attach(Gtk.Label(label="Level:"), 0, 0, 1, 1)
        comp_levels = [
            "Smart (Auto)",
            "0 - Store",
            "1 - Fastest",
            "2 - Fast",
            "3 - Normal",
            "4 - Good",
            "5 - Best"
        ]
        self._comp_dropdown = Gtk.DropDown.new_from_strings(comp_levels)
        self._comp_dropdown.set_selected(0)
        self._comp_dropdown.connect("notify::selected", self._on_comp_level_changed)
        grid_params.attach(self._comp_dropdown, 1, 0, 1, 1)

        # Smart Cutoff Custom Input Field
        grid_params.attach(Gtk.Label(label="Smart Cutoff:"), 2, 0, 1, 1)
        self._cutoff_entry = Gtk.Entry(text="10%", width_chars=6)
        self._cutoff_entry.set_tooltip_text("File formats with compression savings below this % are stored uncompressed (-m0).")
        grid_params.attach(self._cutoff_entry, 3, 0, 1, 1)

        # Dictionary Size Dropdown (-md)
        grid_params.attach(Gtk.Label(label="Dict Size:"), 0, 1, 1, 1)
        dict_opts = ["32 MB", "64 MB", "128 MB (Rec)", "256 MB", "1024 MB (1GB)"]
        self._dict_dropdown = Gtk.DropDown.new_from_strings(dict_opts)
        self._dict_dropdown.set_selected(2)
        grid_params.attach(self._dict_dropdown, 1, 1, 1, 1)

        # Threads
        grid_params.attach(Gtk.Label(label="Threads:"), 2, 1, 1, 1)
        self._threads_entry = Gtk.Entry(text="12", width_chars=6)
        self._threads_entry.set_tooltip_text("Parallel compression threads (-mt).")
        grid_params.attach(self._threads_entry, 3, 1, 1, 1)

        # Volume Size
        grid_params.attach(Gtk.Label(label="Vol Split:"), 0, 2, 1, 1)
        self._vol_entry = Gtk.Entry(text="4000m")
        self._vol_entry.set_tooltip_text("Chunk split size (e.g. 4000m for 4GB chunks, 0 for single file).")
        grid_params.attach(self._vol_entry, 1, 2, 1, 1)

        # Recovery Record
        self._rr_check = Gtk.CheckButton(label="Recovery (-rr):")
        self._rr_check.set_tooltip_text("Embeds parity data to repair bit rot/corrupted volumes automatically upon extraction.")
        self._rr_check.connect("toggled", lambda w: self._rr_entry.set_sensitive(w.get_active()))
        grid_params.attach(self._rr_check, 2, 2, 1, 1)

        self._rr_entry = Gtk.Entry(text="5%", width_chars=6)
        grid_params.attach(self._rr_entry, 3, 2, 1, 1)

        # BLAKE3 Hash Generation
        self._b3_check = Gtk.CheckButton(label="BLAKE3 Checksums")
        self._b3_check.set_tooltip_text("Generates a checksums.b3 manifest inside destination folder.")
        self._b3_check.set_active(True)
        grid_params.attach(self._b3_check, 0, 3, 4, 1)

        # Store Mask
        grid_params.attach(Gtk.Label(label="Store Mask:"), 0, 4, 1, 1)
        self._mask_entry = Gtk.Entry(text=DEFAULT_SETTINGS["StoreMask"], hexpand=True)
        grid_params.attach(self._mask_entry, 1, 4, 3, 1)

        # Action Buttons
        act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        act_box.set_margin_top(2)
        vbox.append(act_box)

        self._comp_start_btn = Gtk.Button(label="🗜️ Start Compression", hexpand=True)
        self._comp_start_btn.add_css_class("start-btn")
        self._comp_start_btn.connect("clicked", self._on_start_compression)
        act_box.append(self._comp_start_btn)

    def _on_comp_level_changed(self, dropdown, param):
        is_smart = (dropdown.get_selected() == 0)
        self._cutoff_entry.set_sensitive(is_smart)
        self._mask_entry.set_sensitive(not is_smart)
        if is_smart:
            self._mask_entry.set_placeholder_text("[Auto-detected dynamically]")
        else:
            self._mask_entry.set_placeholder_text("*.pak;*.bundle;*.mp4...")

    # ── Tab 2: Extraction ─────────────────────────────────────────────────────

    def _build_tab_extraction(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        vbox.set_margin_start(3)
        vbox.set_margin_end(3)
        vbox.set_margin_top(3)
        vbox.set_margin_bottom(3)
        self._notebook.append_page(vbox, Gtk.Label(label=" 📂 Extract "))

        frame_ext = Gtk.Frame(label=" Extraction Paths ")
        vbox.append(frame_ext)

        grid = Gtk.Grid(row_spacing=5, column_spacing=5)
        grid.set_margin_start(3)
        grid.set_margin_end(3)
        grid.set_margin_top(3)
        grid.set_margin_bottom(3)
        frame_ext.set_child(grid)

        # Source Archive
        grid.attach(Gtk.Label(label="Archive:"), 0, 0, 1, 1)
        self._ext_src_entry = Gtk.Entry(hexpand=True)
        self._ext_src_entry.set_placeholder_text("Select any .rar, .part1.rar, .r00, or .rev file...")
        self._ext_src_entry.set_tooltip_text("Any archive part — first volume, all parts, and .rev files are resolved automatically.")
        grid.attach(self._ext_src_entry, 1, 0, 1, 1)

        btn_ext_src = Gtk.Button(label="Browse")
        btn_ext_src.connect("clicked", self._on_browse_extract_archive)
        grid.attach(btn_ext_src, 2, 0, 1, 1)

        # Destination Dir
        grid.attach(Gtk.Label(label="Extract To:"), 0, 1, 1, 1)
        self._ext_dest_entry = Gtk.Entry(hexpand=True)
        self._ext_dest_entry.set_placeholder_text("Target destination folder...")
        self._ext_dest_entry.set_tooltip_text("Location where files will be unpacked.")
        grid.attach(self._ext_dest_entry, 1, 1, 1, 1)

        btn_ext_dest = Gtk.Button(label="Browse")
        btn_ext_dest.connect("clicked", lambda w: self._browse_dir(self._ext_dest_entry, "Select Extraction Folder"))
        grid.attach(btn_ext_dest, 2, 1, 1, 1)

        # Overwrite Mode
        grid.attach(Gtk.Label(label="Conflict:"), 0, 2, 1, 1)
        overwrite_opts = ["Overwrite (-y)", "Skip (-o-)"]
        self._ext_overwrite_dropdown = Gtk.DropDown.new_from_strings(overwrite_opts)
        self._ext_overwrite_dropdown.set_selected(0)
        grid.attach(self._ext_overwrite_dropdown, 1, 2, 2, 1)

        # Auto-Repair & Reconstruct Feature Checkbox
        self._ext_auto_repair_check = Gtk.CheckButton(label="Auto-Repair & Reconstruct (-rr / .rev)")
        self._ext_auto_repair_check.set_tooltip_text(
            "Automatic Self-Healing:\n"
            "• Rebuilds missing volumes using .rev files.\n"
            "• Auto-repairs CRC/corrupt sectors using embedded -rr parity if extraction fails."
        )
        self._ext_auto_repair_check.set_active(True)
        grid.attach(self._ext_auto_repair_check, 0, 3, 3, 1)

        # Post-extraction BLAKE3 Verification
        self._ext_verify_b3 = Gtk.CheckButton(label="Auto-verify BLAKE3 Checksums")
        self._ext_verify_b3.set_tooltip_text("If checksums.b3 exists, runs 'b3sum --check' after extraction.")
        self._ext_verify_b3.set_active(True)
        grid.attach(self._ext_verify_b3, 0, 4, 3, 1)

        # Action Buttons
        act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        act_box.set_margin_top(2)
        vbox.append(act_box)

        self._ext_start_btn = Gtk.Button(label="📂 Start Extraction", hexpand=True)
        self._ext_start_btn.add_css_class("start-btn")
        self._ext_start_btn.connect("clicked", self._on_start_extraction)
        act_box.append(self._ext_start_btn)

    # ── Tab 3: Hardware & Thermal ──────────────────────────────────────────────

    def _build_tab_hardware(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_margin_start(3)
        vbox.set_margin_end(3)
        vbox.set_margin_top(3)
        vbox.set_margin_bottom(3)
        self._notebook.append_page(vbox, Gtk.Label(label=" ⚡ Hardware "))

        # RAM Cache Frame
        frame_ram = Gtk.Frame(label=" RAM & Disk Temp ")
        vbox.append(frame_ram)
        ram_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        ram_vbox.set_margin_start(3)
        ram_vbox.set_margin_end(3)
        ram_vbox.set_margin_top(3)
        ram_vbox.set_margin_bottom(3)
        frame_ram.set_child(ram_vbox)

        self._ram_tmp_check = Gtk.CheckButton(label="Use RAM cache (/dev/shm)")
        self._ram_tmp_check.set_tooltip_text("Stages volume files in RAM before committing to disk.")
        self._ram_tmp_check.connect("toggled", lambda w: self._custom_tmp_box.set_sensitive(not w.get_active()))
        ram_vbox.append(self._ram_tmp_check)

        self._custom_tmp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self._custom_tmp_box.append(Gtk.Label(label="Disk Temp:"))
        self._custom_tmp_entry = Gtk.Entry(hexpand=True, text="/tmp")
        self._custom_tmp_box.append(self._custom_tmp_entry)
        btn_tmp = Gtk.Button(label="Browse")
        btn_tmp.connect("clicked", lambda w: self._browse_dir(self._custom_tmp_entry, "Select Disk Cache"))
        self._custom_tmp_box.append(btn_tmp)
        ram_vbox.append(self._custom_tmp_box)

        # I/O Throttle Frame
        frame_io = Gtk.Frame(label=" I/O Scheduling & Cooldown ")
        vbox.append(frame_io)
        io_grid = Gtk.Grid(row_spacing=5, column_spacing=6)
        io_grid.set_margin_start(3)
        io_grid.set_margin_end(3)
        io_grid.set_margin_top(3)
        io_grid.set_margin_bottom(3)
        frame_io.set_child(io_grid)

        io_grid.attach(Gtk.Label(label="I/O Scheduling:"), 0, 0, 1, 1)
        ionice_modes = [
            "None (Max Speed)",
            "Best Effort P7 (Balanced)",
            "Idle (Background)"
        ]
        self._ionice_dropdown = Gtk.DropDown.new_from_strings(ionice_modes)
        self._ionice_dropdown.set_selected(1)
        self._ionice_dropdown.set_hexpand(True)
        io_grid.attach(self._ionice_dropdown, 1, 0, 3, 1)

        self._cooldown_check = Gtk.CheckButton(label="Thermal Cooldown:")
        self._cooldown_check.set_tooltip_text("Pauses execution after job to let disk temperature normalize.")
        self._cooldown_check.connect("toggled", lambda w: self._cooldown_entry.set_sensitive(w.get_active()))
        io_grid.attach(self._cooldown_check, 0, 1, 1, 1)

        self._cooldown_entry = Gtk.Entry(text="180", width_chars=6)
        io_grid.attach(self._cooldown_entry, 1, 1, 1, 1)

        self._space_check = Gtk.CheckButton(label="Pre-flight Space Check")
        self._space_check.set_tooltip_text("Verifies available space on destination drive before running.")
        self._space_check.set_active(True)
        io_grid.attach(self._space_check, 0, 2, 4, 1)

    # ── Shared Output Pane ────────────────────────────────────────────────────

    def _build_shared_output(self, parent):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(3)
        box.set_vexpand(True)
        parent.append(box)

        bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._cancel_btn = Gtk.Button(label="⏹ Cancel", sensitive=False)
        self._cancel_btn.add_css_class("cancel-btn")
        self._cancel_btn.connect("clicked", self._on_cancel_clicked)
        bar_box.append(self._cancel_btn)

        self._job_status_label = Gtk.Label(label="Status: Idle", hexpand=True)
        self._job_status_label.set_halign(Gtk.Align.END)
        bar_box.append(self._job_status_label)
        box.append(bar_box)

        # Progress bar
        self._progress_bar = Gtk.ProgressBar(show_text=True)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("Idle")
        box.append(self._progress_bar)

        # Compact stats
        self._stats_label = Gtk.Label(label="--/-- GB • -- MB/s • ETA: --:--:-- • Drive: --°C")
        self._stats_label.set_halign(Gtk.Align.CENTER)
        box.append(self._stats_label)

        # Activity Log
        frame_log = Gtk.Frame(label=" Activity Log ")
        frame_log.set_vexpand(True)
        box.append(frame_log)

        scroll = Gtk.ScrolledWindow(min_content_height=110)
        scroll.set_vexpand(True)
        frame_log.set_child(scroll)

        self._log_view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll.set_child(self._log_view)
        self._log_buffer = self._log_view.get_buffer()

    # ── Async Dialogs & Background Pre-Analysis ────────────────────────────────

    def _on_browse_source(self, btn):
        dialog = Gtk.FileDialog(title="Select Source Folder")
        def finish(d, res):
            try:
                folder = d.select_folder_finish(res)
                if folder:
                    path = folder.get_path()
                    self._src_entry.set_text(path)
                    base = os.path.basename(path.rstrip("/\\"))
                    if base:
                        clean = re.sub(r'[^a-zA-Z0-9_-]', '_', base).strip('_')
                        self._name_entry.set_text(clean)

                    self._trigger_background_preanalysis(path)
            except GLib.Error:
                pass
        dialog.select_folder(self, None, finish)

    def _trigger_background_preanalysis(self, source_path: str):
        if not source_path or not os.path.isdir(source_path):
            return

        self._analysis_in_progress = True
        self._job_status_label.set_text("Status: Analyzing source...")
        self._log_buffer.set_text("")
        self._log(f"🔍 Selected Source: {source_path}\n")
        self._log("⚡ Running instant background extension sampling...\n")

        def worker():
            ext_stats, total_bytes = sample_directory_extensions(source_path)
            self._cached_ext_stats = ext_stats
            self._cached_total_bytes = total_bytes
            self._analysis_cache_path = source_path
            self._analysis_in_progress = False

            rec_cutoff = calculate_smart_cutoff(ext_stats)
            GLib.idle_add(self._on_preanalysis_finished, ext_stats, total_bytes, rec_cutoff)

        threading.Thread(target=worker, daemon=True).start()

    def _on_preanalysis_finished(self, ext_stats: dict, total_bytes: int, rec_cutoff: float):
        self._job_status_label.set_text("Status: Ready")
        self._cutoff_entry.set_text(f"{rec_cutoff:.1f}%")

        self._log(f"\n🧠 Background Analysis Complete for {len(ext_stats)} unique extensions ({human_bytes(total_bytes)}):\n")
        sorted_exts = sorted(ext_stats.items(), key=lambda item: item[1]["size"], reverse=True)
        for ext, data in sorted_exts:
            tag = "Compress" if data["savings"] >= rec_cutoff or ext == "[no_ext]" else "Store (-m0)"
            self._log(f"   • {tag:<11}: *{ext:<12} (Saved {data['savings']:4.1f}% | {human_bytes(data['size'])})\n")

        self._log(f"\n💡 Auto-Tuned Smart Cutoff: {rec_cutoff:.1f}%\n")

    def _browse_dir(self, entry: Gtk.Entry, title: str):
        dialog = Gtk.FileDialog(title=title)
        cur = entry.get_text().strip()
        if cur and os.path.isdir(cur):
            dialog.set_initial_folder(Gio.File.new_for_path(cur))

        def finish(d, res):
            try:
                folder = d.select_folder_finish(res)
                if folder:
                    entry.set_text(folder.get_path())
            except GLib.Error:
                pass
        dialog.select_folder(self, None, finish)

    def _on_browse_extract_archive(self, btn):
        dialog = Gtk.FileDialog(title="Select Archive File")

        filt_rar = Gtk.FileFilter()
        filt_rar.set_name("RAR & Recovery Archives (*.rar, *.part*.rar, *.r00, *.rev, *.001)")
        filt_rar.add_pattern("*.rar")
        filt_rar.add_pattern("*.RAR")
        filt_rar.add_pattern("*.part*.rar")
        filt_rar.add_pattern("*.part*.RAR")
        filt_rar.add_pattern("*.r[0-9][0-9]")
        filt_rar.add_pattern("*.R[0-9][0-9]")
        filt_rar.add_pattern("*.rev")
        filt_rar.add_pattern("*.REV")
        filt_rar.add_pattern("*.001")
        filt_rar.add_suffix("rar")
        filt_rar.add_suffix("RAR")
        filt_rar.add_suffix("rev")

        filt_all = Gtk.FileFilter()
        filt_all.set_name("All Files (*)")
        filt_all.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt_rar)
        filters.append(filt_all)
        dialog.set_filters(filters)
        dialog.set_default_filter(filt_rar)

        def finish(d, res):
            try:
                file_obj = d.open_finish(res)
                if file_obj:
                    path = file_obj.get_path()
                    info = get_rar_archive_info(path)
                    if info:
                        first_vol = info["first_volume"]
                        self._ext_src_entry.set_text(first_vol)
                        if not self._ext_dest_entry.get_text().strip():
                            self._ext_dest_entry.set_text(os.path.dirname(first_vol))

                        self._log(f"\n📦 Selected Archive: {os.path.basename(path)}\n")
                        if info["total_parts"] > 1:
                            self._log(f"   • Multi-Part Volume Set: {info['total_parts']} parts detected ({human_bytes(info['total_compressed_bytes'])})\n")
                            self._log(f"   • Resolved First Volume: {os.path.basename(first_vol)}\n")
                            if info["missing_parts"]:
                                self._log(f"   ⚠️ WARNING: Missing part(s) in sequence: {info['missing_parts']}!\n")
                                if info["rev_files"]:
                                    self._log(f"   🩹 Found {len(info['rev_files'])} .rev Recovery Volume(s) for auto-reconstruction.\n")
                        else:
                            self._log(f"   • Single Volume Archive ({human_bytes(info['total_compressed_bytes'])})\n")
                    else:
                        self._ext_src_entry.set_text(path)
                        if not self._ext_dest_entry.get_text().strip():
                            self._ext_dest_entry.set_text(os.path.dirname(path))
            except GLib.Error:
                pass
        dialog.open(self, None, finish)

    def _log(self, text: str):
        GLib.idle_add(self._log_idle, text)

    def _log_idle(self, text: str):
        end = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end, text)
        mark = self._log_buffer.create_mark(None, self._log_buffer.get_end_iter(), False)
        self._log_view.scroll_mark_onscreen(mark)

    def _set_ui_busy(self, busy: bool, status: str = ""):
        self._is_running = busy
        self._comp_start_btn.set_sensitive(not busy)
        self._ext_start_btn.set_sensitive(not busy)
        self._cancel_btn.set_sensitive(busy)
        if status:
            self._job_status_label.set_text(f"Status: {status}")

    # ── Progress Poller ────────────────────────────────────────────────────────

    def _start_progress_monitor(self, target_dir: str, prefix: str, work_dir: str, target_bytes: int, drive_dev: str, is_extract: bool = False):
        self._target_bytes = target_bytes
        self._last_size = 0
        self._start_time = time.time()
        self._last_time = self._start_time
        self._ema_rate = 0.0

        def poll():
            if not self._is_running:
                return False

            now = time.time()
            if is_extract:
                current_size, _ = get_dir_size_and_count(target_dir)
            else:
                current_size = self._count_archive_bytes(target_dir, prefix, work_dir)

            elapsed = now - self._start_time
            delta_size = current_size - self._last_size
            delta_time = now - self._last_time

            if delta_time > 0 and delta_size >= 0:
                inst_rate = delta_size / delta_time
                self._ema_rate = (self._ema_rate * 0.7) + (inst_rate * 0.3)
            elif elapsed > 0:
                self._ema_rate = current_size / elapsed

            pct = 0.0
            if self._target_bytes > 0:
                pct = min(0.99, max(0.0, current_size / self._target_bytes))
            self._progress_bar.set_fraction(pct)
            self._progress_bar.set_text(f"{int(pct * 100)}%")

            rem_bytes = max(0, self._target_bytes - current_size)
            eta_str = human_seconds(rem_bytes / self._ema_rate) if self._ema_rate > 0 else "--:--:--"
            temp = get_disk_temperature(drive_dev)
            temp_str = f"{temp}°C" if temp else "--"

            self._stats_label.set_text(
                f"{human_bytes(current_size)}/{human_bytes(self._target_bytes)} • "
                f"{human_bytes(self._ema_rate)}/s • ETA: {eta_str} • "
                f"Drive: {temp_str}"
            )

            self._last_size = current_size
            self._last_time = now
            return True

        self._monitor_timer_id = GLib.timeout_add(1500, poll)

    def _stop_progress_monitor(self):
        if self._monitor_timer_id is not None:
            GLib.source_remove(self._monitor_timer_id)
            self._monitor_timer_id = None

    def _count_archive_bytes(self, archive_dir: str, prefix: str, work_dir: str) -> int:
        total = 0
        try:
            if os.path.exists(archive_dir):
                for f in os.listdir(archive_dir):
                    if f.startswith(prefix) and (f.endswith(".rar") or re.search(r'\.r\d+$', f, re.IGNORECASE)):
                        total += os.path.getsize(os.path.join(archive_dir, f))
            if work_dir and os.path.exists(work_dir):
                for root, _, files in os.walk(work_dir):
                    for f in files:
                        total += os.path.getsize(os.path.join(root, f))
        except Exception:
            pass
        return total

    # ── BLAKE3 Checksums ───────────────────────────────────────────────────────

    def _generate_blake3_manifest(self, source_dir: str, dest_dir: str, prefix: str) -> bool:
        if not shutil.which("b3sum"):
            self._log("⚠️ 'b3sum' not found. Skipping BLAKE3 generation.\n")
            return False

        manifest_path = os.path.join(dest_dir, f"{prefix}_checksums.b3")
        self._log(f"⚡ Generating BLAKE3 Manifest in Dest: {os.path.basename(manifest_path)}... ")

        file_list = []
        for root, _, files in os.walk(source_dir):
            for f in files:
                if f.startswith(".") or f.endswith("_checksums.b3") or f == "checksums.b3":
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, source_dir)
                file_list.append(rel_p)

        if not file_list:
            self._log("No files found.\n")
            return False

        try:
            with open(manifest_path, "w") as out_f:
                chunk_size = 200
                for i in range(0, len(file_list), chunk_size):
                    if self._cancel_requested:
                        return False
                    chunk = file_list[i:i + chunk_size]
                    res = subprocess.run(["b3sum"] + chunk, cwd=source_dir, capture_output=True, text=True)
                    if res.returncode == 0:
                        out_f.write(res.stdout)
                    else:
                        self._log(f"\n⚠️ Hash warning: {res.stderr}\n")
            self._log("Done.\n")
            return True
        except Exception as e:
            self._log(f"\n❌ BLAKE3 error: {e}\n")
            return False

    def _verify_blake3_manifest(self, dest_dir: str, archive_path: str) -> bool:
        if not shutil.which("b3sum"):
            self._log("⚠️ 'b3sum' not installed. Cannot verify checksums.\n")
            return False

        arc_info = get_rar_archive_info(archive_path)
        base_name = arc_info["base_name"] if arc_info else os.path.splitext(os.path.basename(archive_path))[0]
        archive_dir = os.path.dirname(os.path.abspath(archive_path))

        candidates = [
            os.path.join(dest_dir, f"{base_name}_checksums.b3"),
            os.path.join(dest_dir, "checksums.b3"),
            os.path.join(archive_dir, f"{base_name}_checksums.b3"),
            os.path.join(archive_dir, "checksums.b3"),
        ]

        manifest_path = None
        for cand in candidates:
            if os.path.exists(cand):
                manifest_path = cand
                break

        if not manifest_path:
            for d in [dest_dir, archive_dir]:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith(".b3") and (base_name.lower() in f.lower() or "checksum" in f.lower()):
                            manifest_path = os.path.join(d, f)
                            break
                if manifest_path:
                    break

        if not manifest_path:
            self._log("ℹ️ No '*_checksums.b3' manifest found. Skipping hash verification.\n")
            return True

        self._log(f"\n🔍 Verifying BLAKE3 with manifest: {os.path.basename(manifest_path)}...\n")
        try:
            proc = subprocess.Popen(["b3sum", "--check", manifest_path], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                if "FAILED" in line:
                    self._log(f"   ❌ {line}")
            proc.wait()
            if proc.returncode == 0:
                self._log("✅ BLAKE3 Integrity Verified: 100% match!\n")
                return True
            else:
                self._log("❌ BLAKE3 Verification Failed: Checksum mismatches found.\n")
                return False
        except Exception as e:
            self._log(f"❌ Verification error: {e}\n")
            return False

    # ── Execution Logic: Compression ──────────────────────────────────────────

    def _on_start_compression(self, btn):
        src_path = self._src_entry.get_text().strip()
        dest_path = self._dest_entry.get_text().strip()

        if not src_path or not os.path.exists(src_path):
            self._log("❌ Error: Valid Source directory required.\n")
            return
        if not dest_path:
            self._log("❌ Error: Destination directory required.\n")
            return

        self._save_settings()
        self._current_job = "compress"
        self._cancel_requested = False
        self._set_ui_busy(True, "Compressing")
        self._log("🚀 Initializing RAR Compression Job...\n")

        threading.Thread(target=self._run_compression, daemon=True).start()

    def _run_compression(self):
        settings = self._gather_settings()
        src_path = settings["SourceDir"]
        dest_path = settings["DestDir"]
        prefix = settings["ArchivePrefix"] or "archive"
        drive_dev = get_drive_device(dest_path)

        os.makedirs(dest_path, exist_ok=True)
        self._log(f"   Source:      {src_path}\n")
        self._log(f"   Destination: {dest_path}/\n")
        self._log(f"   Archive:     {prefix}.rar\n")

        # 1. BLAKE3 Checksums in destination folder
        if settings["GenBlake3"]:
            self._generate_blake3_manifest(src_path, dest_path, prefix)

        if self._cancel_requested:
            self._finish_all()
            return

        # 2. Heuristics & Instant Store Mask Calculation
        is_smart_mode = (settings["CompressionLevel"] == 0)
        selected_level = 1
        effective_store_mask = settings["StoreMask"]

        dict_sizes = ["32m", "64m", "128m", "256m", "1024m"]
        dict_flag = f"-md{dict_sizes[settings['DictSize']]}"

        m_pct = re.search(r'([\d\.]+)', settings["SmartCutoff"])
        parsed_pct = float(m_pct.group(1)) if m_pct else 10.0
        parsed_pct = min(99.0, max(0.1, parsed_pct))

        if is_smart_mode:
            if self._analysis_cache_path == src_path and self._cached_ext_stats:
                ext_stats = self._cached_ext_stats
                total_source_bytes = self._cached_total_bytes
            else:
                self._log("⚡ Running fast extension scan...\n")
                ext_stats, total_source_bytes = sample_directory_extensions(src_path)

            store_exts = []
            comp_bytes = 0
            incomp_bytes = 0

            for ext, data in ext_stats.items():
                if data["savings"] < parsed_pct and ext != "[no_ext]":
                    store_exts.append(f"*{ext}")
                    incomp_bytes += data["size"]
                else:
                    comp_bytes += data["size"]

            effective_store_mask = ";".join(sorted(store_exts)) if store_exts else ""
            self._log(f"\n🧠 Applied Smart Cutoff: {parsed_pct:.1f}%\n")
            self._log(f"   → Dynamic Incompressible: {len(store_exts)} exts ({human_bytes(incomp_bytes)})\n")
            self._log(f"   → Compressible Payload:   {len(ext_stats) - len(store_exts)} exts ({human_bytes(comp_bytes)})\n")

            if comp_bytes < 500 * 1024 * 1024:
                selected_level = 5
            elif comp_bytes < 4 * 1024 * 1024 * 1024:
                selected_level = 3
            else:
                selected_level = 1

            self._log(f"   → Settings: -m{selected_level} {dict_flag}\n\n")
        else:
            selected_level = settings["CompressionLevel"] - 1
            total_source_bytes, _ = get_dir_size_and_count(src_path)

        # 3. Targets and Pre-flight
        self._log("🔍 Calculating archive targets...")
        self._log(f" {human_bytes(total_source_bytes)}\n")

        rr_overhead = 0.0
        if settings["EnableRecovery"]:
            m = re.search(r'(\d+)', settings["RecoveryRecord"])
            if m and int(m.group(1)) > 0:
                rr_overhead = int(m.group(1)) / 100.0

        target_bytes = int(total_source_bytes * (1.0 + rr_overhead))

        if settings["CheckFreeSpace"]:
            free_bytes = get_free_bytes(dest_path)
            if free_bytes > 0 and free_bytes < target_bytes:
                self._log(f"⚠️ WARNING: Low destination free space!\n")
                self._log(f"   Required: ~{human_bytes(target_bytes)} | Free: {human_bytes(free_bytes)}\n")

        self._cleanup_partial_volumes(dest_path, prefix)

        # 4. Temp buffer
        if settings["UseRamTmp"]:
            tmp_root = "/dev/shm" if os.path.exists("/dev/shm") else "/tmp"
        else:
            tmp_root = settings["CustomTmpDir"] if os.path.exists(settings["CustomTmpDir"]) else "/tmp"

        work_dir = tempfile.mkdtemp(prefix=f"rar_{prefix}_", dir=tmp_root)
        self._current_work_dir = work_dir
        self._log(f"   Buffer: {work_dir} ({'RAM' if settings['UseRamTmp'] else 'Disk'})\n")

        archive_path = os.path.join(dest_path, f"{prefix}.rar")
        rar_cmd = [
            "rar", "a", "-y",
            f"-m{selected_level}",
            dict_flag,
            "-r", "-ep1", "-s-",
            f"-mt{settings['Threads']}",
            f"-w{work_dir}",
            "-idq",
        ]

        if effective_store_mask:
            rar_cmd.append(f"-ms{effective_store_mask}")

        vol_s = settings["VolumeSize"].strip()
        if vol_s and vol_s != "0" and vol_s.lower() != "none":
            rar_cmd.append(f"-v{vol_s}")

        if settings["EnableRecovery"] and rr_overhead > 0:
            rar_cmd.append(f"-rr{settings['RecoveryRecord']}")

        rar_cmd.extend([archive_path, "."])

        if settings["IoniceMode"] == 1 and shutil.which("ionice"):
            rar_cmd = ["ionice", "-c", "2", "-n", "7"] + rar_cmd
        elif settings["IoniceMode"] == 2 and shutil.which("ionice"):
            rar_cmd = ["ionice", "-c", "3"] + rar_cmd

        GLib.idle_add(self._start_progress_monitor, dest_path, prefix, work_dir, target_bytes, drive_dev, False)

        rc = 0
        try:
            self._current_process = subprocess.Popen(rar_cmd, cwd=src_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            stdout, _ = self._current_process.communicate()
            rc = self._current_process.returncode
        except Exception as e:
            rc = -1
            self._log(f"❌ Error: {e}\n")

        GLib.idle_add(self._stop_progress_monitor)

        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

        if self._cancel_requested or rc != 0:
            self._log("🧹 Cleaning partial archives...\n")
            self._cleanup_partial_volumes(dest_path, prefix)
            if self._cancel_requested:
                self._log("⏹ Compression cancelled.\n")
            else:
                self._log(f"❌ Compression failed (Code {rc}).\n")
        else:
            final_size = sum(
                os.path.getsize(os.path.join(dest_path, f))
                for f in os.listdir(dest_path)
                if f.startswith(prefix) and (f.endswith(".rar") or re.search(r'\.r\d+$', f, re.IGNORECASE))
            )
            saved = int(((total_source_bytes - final_size) / total_source_bytes) * 100) if total_source_bytes else 0
            self._log(f"✅ Success! Total Size: {human_bytes(final_size)} (Saved: {saved}%)\n")

            if settings["EnableCooldown"] and int(settings["CooldownSeconds"]) > 0 and not self._cancel_requested:
                self._run_cooldown(int(settings["CooldownSeconds"]), drive_dev)

        GLib.idle_add(self._finish_all)

    # ── Execution Logic: Extraction with Automatic Self-Healing ───────────────

    def _on_start_extraction(self, btn):
        rar_file = self._ext_src_entry.get_text().strip()
        dest_dir = self._ext_dest_entry.get_text().strip()

        if not rar_file or not os.path.exists(rar_file):
            self._log("❌ Error: Valid RAR archive file required.\n")
            return
        if not dest_dir:
            self._log("❌ Error: Extraction directory required.\n")
            return

        self._save_settings()
        self._current_job = "extract"
        self._cancel_requested = False
        self._set_ui_busy(True, "Extracting")
        self._log_buffer.set_text("")
        self._log("🚀 Initializing RAR Extraction Job...\n")

        threading.Thread(target=self._run_extraction, daemon=True).start()

    def _run_extraction(self):
        settings = self._gather_settings()
        rar_file = settings["ExtractArchive"]
        dest_dir = settings["ExtractDest"]
        drive_dev = get_drive_device(dest_dir)
        auto_repair_enabled = settings.get("AutoRepair", True)

        extract_bin = shutil.which("rar") or shutil.which("unrar")
        if not extract_bin:
            self._log("❌ Error: Neither 'rar' nor 'unrar' binary found in PATH.\n")
            GLib.idle_add(self._finish_all)
            return

        os.makedirs(dest_dir, exist_ok=True)

        # 1. Multi-part volume set auto-detection
        arc_info = get_rar_archive_info(rar_file)
        if not arc_info:
            self._log(f"❌ Error: Archive not readable.\n")
            GLib.idle_add(self._finish_all)
            return

        # 2. Check for missing volumes & auto-reconstruct with .rev parity
        if arc_info["missing_parts"] and auto_repair_enabled:
            if arc_info["rev_files"]:
                self._log(f"⚠️ Missing {len(arc_info['missing_parts'])} volume part(s): {arc_info['missing_parts']}\n")
                self._log(f"🩹 Triggering automatic reconstruction using {len(arc_info['rev_files'])} .rev file(s)...\n")
                ok = reconstruct_from_rev_volumes(arc_info["arc_dir"], arc_info["rev_files"][0], self._log)
                if ok:
                    self._log("✅ Missing volumes successfully reconstructed from .rev parity!\n")
                    # Refresh volume metadata after reconstruction
                    arc_info = get_rar_archive_info(rar_file)
                else:
                    self._log("⚠️ Could not reconstruct all missing volumes from .rev.\n")
            else:
                self._log(f"⚠️ WARNING: Missing part(s) in sequence: {arc_info['missing_parts']} (No .rev files available)\n")

        first_vol = arc_info["first_volume"]
        total_parts = arc_info["total_parts"]
        total_comp_bytes = arc_info["total_compressed_bytes"]

        self._log(f"   Archive:    {os.path.basename(first_vol)}\n")
        if total_parts > 1:
            self._log(f"   Volumes:    {total_parts} parts detected ({human_bytes(total_comp_bytes)})\n")
        self._log(f"   Extract To: {dest_dir}/\n")

        # 3. Target estimation
        self._log("🔍 Inspecting archive contents...")
        target_bytes = estimate_rar_uncompressed_size(first_vol, total_comp_bytes)
        self._log(f" Estimated Output: ~{human_bytes(target_bytes)}\n")

        if settings["CheckFreeSpace"]:
            free_bytes = get_free_bytes(dest_dir)
            if free_bytes > 0 and free_bytes < target_bytes:
                self._log(f"⚠️ WARNING: Low space on target partition!\n")
                self._log(f"   Required: ~{human_bytes(target_bytes)} | Free: {human_bytes(free_bytes)}\n")

        # 4. Extraction Execution Loop (with Auto-Repair Retry)
        max_attempts = 2 if auto_repair_enabled else 1
        extraction_success = False
        repaired_any = False

        for attempt in range(1, max_attempts + 1):
            if self._cancel_requested:
                break

            if settings["UseRamTmp"]:
                tmp_root = "/dev/shm" if os.path.exists("/dev/shm") else "/tmp"
            else:
                tmp_root = settings["CustomTmpDir"] if os.path.exists(settings["CustomTmpDir"]) else "/tmp"

            work_dir = tempfile.mkdtemp(prefix="rar_ext_", dir=tmp_root)
            self._current_work_dir = work_dir

            overwrite_flag = "-y" if settings["OverwriteMode"] == 0 else "-o-"
            rar_cmd = [
                extract_bin, "x", overwrite_flag,
                f"-w{work_dir}",
                "-idq",
                first_vol,
                dest_dir + os.sep
            ]

            if settings["IoniceMode"] == 1 and shutil.which("ionice"):
                rar_cmd = ["ionice", "-c", "2", "-n", "7"] + rar_cmd
            elif settings["IoniceMode"] == 2 and shutil.which("ionice"):
                rar_cmd = ["ionice", "-c", "3"] + rar_cmd

            GLib.idle_add(self._start_progress_monitor, dest_dir, "", work_dir, target_bytes, drive_dev, True)

            rc = 0
            stdout_lines = []
            try:
                self._current_process = subprocess.Popen(rar_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in self._current_process.stdout:
                    stdout_lines.append(line)
                self._current_process.wait()
                rc = self._current_process.returncode
            except Exception as e:
                rc = -1
                self._log(f"❌ Execution error: {e}\n")

            GLib.idle_add(self._stop_progress_monitor)

            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

            if rc == 0 and not self._cancel_requested:
                extraction_success = True
                break

            if self._cancel_requested:
                break

            # Attempt Auto-Recovery if failed on attempt 1
            if attempt == 1 and auto_repair_enabled:
                self._log(f"\n⚠️ Extraction encountered errors (Code {rc}).\n")
                # Look for corrupt parts mentioned in output or scan all volume parts
                repaired_list = auto_repair_damaged_volumes(arc_info["all_parts"], self._log)
                if repaired_list:
                    repaired_any = True
                    self._log("🔄 Retrying extraction with repaired volume files...\n")
                    continue
                else:
                    self._log("❌ Auto-Recovery could not fix the corruption (insufficient -rr parity).\n")
                    break
            else:
                self._log(f"❌ Extraction failed (Code {rc}).\n")

        # 5. Finalize Job
        if self._cancel_requested:
            self._log("⏹ Extraction cancelled.\n")
        elif extraction_success:
            final_bytes, count = get_dir_size_and_count(dest_dir)
            repair_note = " (with Auto-Repaired parity volumes)" if repaired_any else ""
            self._log(f"✅ Extraction Complete! {human_bytes(final_bytes)} ({count} files){repair_note}\n")

            if settings["VerifyBlake3"]:
                self._verify_blake3_manifest(dest_dir, first_vol)

            if settings["EnableCooldown"] and int(settings["CooldownSeconds"]) > 0 and not self._cancel_requested:
                self._run_cooldown(int(settings["CooldownSeconds"]), drive_dev)

        GLib.idle_add(self._finish_all)

    # ── Cooldown & Cleanup ─────────────────────────────────────────────────────

    def _run_cooldown(self, seconds: int, drive_dev: str):
        self._log(f"\n⏸ Cooldown: Resting drive for {seconds}s...\n")
        for remaining in range(seconds, 0, -1):
            if self._cancel_requested:
                break
            temp = get_disk_temperature(drive_dev)
            temp_str = f"{temp}°C" if temp else "--"
            pct = (seconds - remaining) / seconds
            GLib.idle_add(self._progress_bar.set_fraction, pct)
            GLib.idle_add(self._progress_bar.set_text, f"Cooldown... {remaining}s")
            GLib.idle_add(self._stats_label.set_text, f"Cooldown: {human_seconds(remaining)} • Drive: {temp_str}")
            time.sleep(1)
        self._log("✅ Drive cooldown completed.\n")

    def _cleanup_partial_volumes(self, archive_dir: str, prefix: str):
        if not os.path.exists(archive_dir):
            return
        for f in os.listdir(archive_dir):
            if f.startswith(prefix) and (f.endswith(".rar") or re.search(r'\.r\d+$', f, re.IGNORECASE)):
                try:
                    os.remove(os.path.join(archive_dir, f))
                except Exception:
                    pass

    def _on_cancel_clicked(self, btn):
        if not self._is_running:
            return
        self._cancel_requested = True
        self._log("\n⚠️ Terminating processes...\n")
        self._cancel_btn.set_sensitive(False)

        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.send_signal(signal.SIGTERM)
            except Exception:
                pass

    def _finish_all(self):
        self._stop_progress_monitor()
        self._set_ui_busy(False, "Idle")
        self._progress_bar.set_fraction(1.0 if not self._cancel_requested else 0.0)
        self._progress_bar.set_text("Done" if not self._cancel_requested else "Cancelled")
        self._log("\n✨ Job completed.\n")

    # ── Settings Persistence ───────────────────────────────────────────────────

    def _gather_settings(self) -> dict:
        return {
            "SourceDir": self._src_entry.get_text().strip(),
            "DestDir": self._dest_entry.get_text().strip(),
            "ArchivePrefix": self._name_entry.get_text().strip(),
            "VolumeSize": self._vol_entry.get_text().strip(),
            "EnableRecovery": self._rr_check.get_active(),
            "RecoveryRecord": self._rr_entry.get_text().strip(),
            "CompressionLevel": self._comp_dropdown.get_selected(),
            "SmartCutoff": self._cutoff_entry.get_text().strip() or "10%",
            "DictSize": self._dict_dropdown.get_selected(),
            "Threads": self._threads_entry.get_text().strip(),
            "StoreMask": self._mask_entry.get_text().strip(),
            "GenBlake3": self._b3_check.get_active(),

            "ExtractArchive": self._ext_src_entry.get_text().strip(),
            "ExtractDest": self._ext_dest_entry.get_text().strip(),
            "AutoRepair": self._ext_auto_repair_check.get_active(),
            "VerifyBlake3": self._ext_verify_b3.get_active(),
            "OverwriteMode": self._ext_overwrite_dropdown.get_selected(),

            "UseRamTmp": self._ram_tmp_check.get_active(),
            "CustomTmpDir": self._custom_tmp_entry.get_text().strip(),
            "IoniceMode": self._ionice_dropdown.get_selected(),
            "EnableCooldown": self._cooldown_check.get_active(),
            "CooldownSeconds": int(self._cooldown_entry.get_text().strip() or 0),
            "CheckFreeSpace": self._space_check.get_active(),
        }

    def _load_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    settings.update(json.load(f))
            except Exception:
                pass

        self._src_entry.set_text(settings.get("SourceDir", ""))
        self._dest_entry.set_text(settings.get("DestDir", ""))
        self._name_entry.set_text(settings.get("ArchivePrefix", "archive"))
        self._vol_entry.set_text(settings.get("VolumeSize", "4000m"))

        enable_rr = settings.get("EnableRecovery", True)
        self._rr_check.set_active(enable_rr)
        self._rr_entry.set_sensitive(enable_rr)
        self._rr_entry.set_text(settings.get("RecoveryRecord", "5%"))

        comp_lvl = int(settings.get("CompressionLevel", 0))
        self._comp_dropdown.set_selected(comp_lvl)
        self._cutoff_entry.set_text(str(settings.get("SmartCutoff", "10%")))
        self._dict_dropdown.set_selected(int(settings.get("DictSize", 2)))

        self._cutoff_entry.set_sensitive(comp_lvl == 0)
        self._mask_entry.set_sensitive(comp_lvl != 0)

        self._threads_entry.set_text(settings.get("Threads", "12"))
        self._mask_entry.set_text(settings.get("StoreMask", DEFAULT_SETTINGS["StoreMask"]))
        self._b3_check.set_active(settings.get("GenBlake3", True))

        self._ext_src_entry.set_text(settings.get("ExtractArchive", ""))
        self._ext_dest_entry.set_text(settings.get("ExtractDest", ""))
        self._ext_auto_repair_check.set_active(settings.get("AutoRepair", True))
        self._ext_verify_b3.set_active(settings.get("VerifyBlake3", True))
        self._ext_overwrite_dropdown.set_selected(int(settings.get("OverwriteMode", 0)))

        use_ram = settings.get("UseRamTmp", True)
        self._ram_tmp_check.set_active(use_ram)
        self._custom_tmp_box.set_sensitive(not use_ram)
        self._custom_tmp_entry.set_text(settings.get("CustomTmpDir", "/tmp"))

        self._ionice_dropdown.set_selected(int(settings.get("IoniceMode", 1)))

        enable_cd = settings.get("EnableCooldown", False)
        self._cooldown_check.set_active(enable_cd)
        self._cooldown_entry.set_sensitive(enable_cd)
        self._cooldown_entry.set_text(str(settings.get("CooldownSeconds", 180)))
        self._space_check.set_active(settings.get("CheckFreeSpace", True))

    def _save_settings(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._gather_settings(), f, indent=2)
        except Exception:
            pass

    def on_shutdown(self):
        self._save_settings()
        if self._current_process and self._current_process.poll() is None:
            self._current_process.terminate()

# ─── Application Runner ─────────────────────────────────────────────────────

class RarBackupApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.github.rar_backup_pro", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        try:
            provider.load_from_string(GRUVBOX_CSS)
        except AttributeError:
            provider.load_from_data(GRUVBOX_CSS.encode())

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def do_activate(self):
        if not self.window:
            self.window = RarBackupWindow(self)
        self.window.present()

    def do_shutdown(self):
        if self.window:
            self.window.on_shutdown()
        Gtk.Application.do_shutdown(self)

if __name__ == "__main__":
    app = RarBackupApplication()
    sys.exit(app.run(sys.argv))
