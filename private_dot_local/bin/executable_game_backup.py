#!/usr/bin/env python3
"""Game Backup — GTK4 Version

Unified, single-file game save and mod backup manager for Linux/Wine/Proton gaming.
Auto-scans game installations and .gbak archives using Zstandard and PAR2 parity.
"""
__version__ = "2.1.1"

import gi
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio

import json
import os
import re
import sys
import time
import shutil
import tempfile
import subprocess
import threading
from datetime import datetime

# ─── Configuration Paths ────────────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.config/game-backup")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_GAMES_DIR = "/media/C/Games" if os.path.isdir("/media/C/Games") else os.path.expanduser("~/Games")
DEFAULT_BACKUP_DIR = os.path.expanduser("~/Documents/GameBackups")

DEFAULT_CONFIG = {
    "games_dir": DEFAULT_GAMES_DIR,
    "backups_dir": DEFAULT_BACKUP_DIR,
    "default_zstd": "3",
    "default_parity": "10",
    "game_overrides": {},
}

APP_CSS = """
.action-btn { padding: 6px 18px; font-weight: bold; }
.monospace-view { font-family: monospace, monospace; font-size: 11px; }
.progress-detail { font-size: 11px; margin-top: 2px; }
.card-box { padding: 8px; border-radius: 6px; background-color: alpha(currentColor, 0.04); margin-bottom: 4px; }
"""

# ─── UI Helpers ─────────────────────────────────────────────────────────────

class UI:
    @staticmethod
    def row(parent, label_text: str, widget: Gtk.Widget, sg: Gtk.SizeGroup = None) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        if sg:
            sg.add_widget(lbl)
        box.append(lbl)
        box.append(widget)
        parent.append(box)
        return box

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


# ─── Dependency Checker ─────────────────────────────────────────────────────

def get_dep_status():
    has_tar = shutil.which("tar") is not None
    has_zstd = shutil.which("zstd") is not None
    has_par2 = shutil.which("par2") is not None or shutil.which("par2create") is not None
    parts = [
        ("tar", "ok" if has_tar else "missing"),
        ("zstd", "ok" if has_zstd else "missing"),
        ("par2", "ok" if has_par2 else "missing"),
    ]
    return parts, not (has_tar and has_zstd and has_par2)


# ─── Scanner & Parser Engine ────────────────────────────────────────────────

class BackupEngine:
    @staticmethod
    def normalize_slug(name: str) -> str:
        return name.replace(" ", "_").replace("/", "_")

    @staticmethod
    def parse_save_txt(game_dir: str) -> list[str]:
        save_txt_path = os.path.join(game_dir, "save.txt")
        if not os.path.isfile(save_txt_path):
            return []
        resolved = []
        game_dir_abs = os.path.abspath(game_dir)
        with open(save_txt_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if os.path.isabs(line):
                    abs_line = os.path.abspath(line)
                    if abs_line.startswith(game_dir_abs):
                        rel = os.path.relpath(abs_line, game_dir_abs)
                    else:
                        rel = line
                else:
                    rel = line
                full = os.path.join(game_dir_abs, rel)
                if os.path.exists(full) and rel not in resolved:
                    resolved.append(rel)
        if "save.txt" not in resolved and os.path.exists(save_txt_path):
            resolved.append("save.txt")
        return resolved

    @classmethod
    def scan_environment(cls, games_dir: str, backups_dir: str) -> list[dict]:
        games_dict = {}

        # 1. Scan active game installations
        if os.path.isdir(games_dir):
            try:
                for entry in sorted(os.listdir(games_dir)):
                    full_p = os.path.join(games_dir, entry)
                    if os.path.isdir(full_p):
                        save_txt = os.path.join(full_p, "save.txt")
                        has_save = os.path.isfile(save_txt)
                        items = cls.parse_save_txt(full_p) if has_save else []
                        slug = cls.normalize_slug(entry)
                        games_dict[slug] = {
                            "name": entry,
                            "slug": slug,
                            "path": full_p,
                            "has_dir": True,
                            "has_save": has_save,
                            "item_count": len(items),
                            "latest_backup": None,
                            "backup_size_mb": 0.0,
                            "all_backups": [],
                        }
            except Exception:
                pass

        # 2. Scan backup archives
        if os.path.isdir(backups_dir):
            try:
                for f in sorted(os.listdir(backups_dir)):
                    if f.endswith(".gbak"):
                        m = re.match(r"^(.*?)_(\d{4}-\d{2}-\d{2}_\d{6})\.gbak$", f)
                        if m:
                            slug, ts_str = m.group(1), m.group(2)
                            f_path = os.path.join(backups_dir, f)
                            sz_mb = os.path.getsize(f_path) / (1024 * 1024)
                            try:
                                dt = datetime.strptime(ts_str, "%Y-%m-%d_%H%M%S")
                                fmt_date = dt.strftime("%Y-%m-%d %H:%M")
                            except ValueError:
                                fmt_date = ts_str

                            if slug not in games_dict:
                                pretty_name = slug.replace("_", " ")
                                games_dict[slug] = {
                                    "name": pretty_name,
                                    "slug": slug,
                                    "path": os.path.join(games_dir, pretty_name),
                                    "has_dir": False,
                                    "has_save": False,
                                    "item_count": 0,
                                    "latest_backup": None,
                                    "backup_size_mb": 0.0,
                                    "all_backups": [],
                                }

                            games_dict[slug]["all_backups"].append((f_path, fmt_date, sz_mb))
                            games_dict[slug]["latest_backup"] = fmt_date
                            games_dict[slug]["backup_size_mb"] = sz_mb
            except Exception:
                pass

        return list(games_dict.values())


# ─── Main GUI Window ─────────────────────────────────────────────────────────

class GameBackupWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Game Backup")
        self.set_default_size(700, 800)

        self._config = dict(DEFAULT_CONFIG)
        self._games_list = []
        self._process = None

        self._games_dialog = None
        self._backups_dialog = None

        self._load_config()
        self._build_ui()
        self._rescan_games()

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
        title = Gtk.Label(label="<b>Game Backup</b>", use_markup=True, halign=Gtk.Align.START)
        self._dep_badge = Gtk.Label(hexpand=True, halign=Gtk.Align.END, use_markup=True)
        self._update_dep_badge()
        hdr.append(title)
        hdr.append(self._dep_badge)
        root.append(hdr)

        # Notebook
        self._nb = Gtk.Notebook()
        root.append(self._nb)

        self._build_tab_manager()
        self._build_tab_settings()

        # Action Buttons (Same row above progress bar)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
        btn_box.set_margin_top(4)
        btn_box.set_margin_bottom(2)
        root.append(btn_box)

        self._btn_backup = Gtk.Button(label="Backup", css_classes=["suggested-action", "action-btn"])
        self._btn_backup.connect("clicked", self._on_backup_clicked)
        btn_box.append(self._btn_backup)

        self._btn_restore = Gtk.Button(label="Restore", css_classes=["action-btn"])
        self._btn_restore.connect("clicked", self._on_restore_clicked)
        btn_box.append(self._btn_restore)

        self._btn_verify = Gtk.Button(label="Verify", css_classes=["action-btn"])
        self._btn_verify.connect("clicked", self._on_verify_clicked)
        btn_box.append(self._btn_verify)

        self._btn_refresh = Gtk.Button(label="Refresh", css_classes=["action-btn"])
        self._btn_refresh.connect("clicked", lambda b: self._rescan_games())
        btn_box.append(self._btn_refresh)

        self._btn_cancel = Gtk.Button(label="Cancel", sensitive=False, css_classes=["destructive-action", "action-btn"])
        self._btn_cancel.connect("clicked", self._on_cancel_clicked)
        btn_box.append(self._btn_cancel)

        # Progress Section
        p_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._p_bar = Gtk.ProgressBar(show_text=True, text="0%")
        self._p_detail = Gtk.Label(use_markup=True, halign=Gtk.Align.CENTER, label="<i>Ready</i>")
        p_box.append(self._p_bar)
        p_box.append(self._p_detail)
        root.append(p_box)

        # Compact Diagnostics Log
        _, b_log = UI.frame("Log", root)
        sc_log = Gtk.ScrolledWindow(min_content_height=80, max_content_height=90)
        sc_log.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._tv_log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, left_margin=4, right_margin=4)
        self._log_buf = self._tv_log.get_buffer()
        self._log_mark = self._log_buf.create_mark("end_mark", self._log_buf.get_end_iter(), False)
        sc_log.set_child(self._tv_log)
        b_log.append(sc_log)

    def _update_dep_badge(self):
        parts, _ = get_dep_status()
        spans = []
        for name, level in parts:
            color = "#26a269" if level == "ok" else "#c01c28"
            spans.append(f'<span foreground="{color}" font_weight="bold">{name}</span>')
        self._dep_badge.set_markup("  │  ".join(spans))

    def _build_tab_manager(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6)
        self._nb.append_page(box, Gtk.Label(label="Manager"))

        self._lbl_env_info = Gtk.Label(halign=Gtk.Align.START, use_markup=True)
        box.append(self._lbl_env_info)

        # Management List
        sc_list = Gtk.ScrolledWindow(min_content_height=300, vexpand=True)
        sc_list.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self._lb_games = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        sc_list.set_child(self._lb_games)
        box.append(sc_list)

    def _build_tab_settings(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8)
        self._nb.append_page(box, Gtk.Label(label="Settings"))

        _, b_paths = UI.frame("Directory Structure", box)
        sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        # Games Dir
        r_g = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._entry_games_dir = UI.entry(text=self._config["games_dir"])
        btn_browse_g = Gtk.Button(label="Browse")
        btn_browse_g.connect("clicked", self._on_browse_games_dir)
        r_g.append(self._entry_games_dir)
        r_g.append(btn_browse_g)
        UI.row(b_paths, "Games:", r_g, sg)

        # Backups Dir
        r_b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._entry_backups_dir = UI.entry(text=self._config["backups_dir"])
        btn_browse_b = Gtk.Button(label="Browse")
        btn_browse_b.connect("clicked", self._on_browse_backups_dir)
        r_b.append(self._entry_backups_dir)
        r_b.append(btn_browse_b)
        UI.row(b_paths, "Backups:", r_b, sg)

        # Default Parameters
        _, b_params = UI.frame("Global Compression & Parity Defaults", box)
        self._entry_def_zstd = UI.entry(text=self._config.get("default_zstd", "3"), placeholder="1-19 (Default 3)", max_chars=12, hexpand=False)
        UI.row(b_params, "Zstd Level:", self._entry_def_zstd, sg)

        self._entry_def_parity = UI.entry(text=self._config.get("default_parity", "10"), placeholder="1-50% (Default 10)", max_chars=12, hexpand=False)
        UI.row(b_params, "PAR2 Parity %:", self._entry_def_parity, sg)

        # Save Settings Action
        r_act = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END, margin_top=8)
        btn_save = Gtk.Button(label="Save", css_classes=["suggested-action", "action-btn"])
        btn_save.connect("clicked", self._on_save_settings_clicked)
        r_act.append(btn_save)
        box.append(r_act)

    # ── Settings & Configuration Persistence ────────────────────────────────

    def _load_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self._config.update(data)
            except Exception:
                pass
        else:
            self._save_config()

    def _save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception:
            pass

    def _on_save_settings_clicked(self, btn):
        g_dir = self._entry_games_dir.get_text().strip()
        b_dir = self._entry_backups_dir.get_text().strip()
        z_def = self._entry_def_zstd.get_text().strip() or "3"
        p_def = self._entry_def_parity.get_text().strip() or "10"

        self._config["games_dir"] = g_dir
        self._config["backups_dir"] = b_dir
        self._config["default_zstd"] = z_def
        self._config["default_parity"] = p_def
        self._save_config()

        self._append_log("[Settings] Settings saved successfully.\n")
        self._rescan_games()
        self._nb.set_current_page(0)

    # ── Scanning & UI Population ────────────────────────────────────────────

    def _rescan_games(self):
        g_dir = self._config.get("games_dir", DEFAULT_GAMES_DIR)
        b_dir = self._config.get("backups_dir", DEFAULT_BACKUP_DIR)

        while True:
            row = self._lb_games.get_row_at_index(0)
            if not row:
                break
            self._lb_games.remove(row)

        self._games_list = BackupEngine.scan_environment(g_dir, b_dir)

        g_found = sum(1 for g in self._games_list if g["has_dir"])
        b_found = sum(1 for g in self._games_list if g["latest_backup"])
        
        # Valid Pango markup (using alpha instead of class)
        self._lbl_env_info.set_markup(
            f"<span alpha='70%'>Games: <b>{g_dir}</b> ({g_found} detected)  │  Backups: <b>{b_dir}</b> ({b_found} snapshots)</span>"
        )

        overrides = self._config.get("game_overrides", {})

        for g in self._games_list:
            slug = g["slug"]
            ov = overrides.get(slug, {})
            zstd_val = ov.get("zstd", self._config.get("default_zstd", "3"))
            parity_val = ov.get("parity", self._config.get("default_parity", "10"))

            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, css_classes=["card-box"])
            card._game_data = g

            # Only pre-check if game has save.txt OR already has a backup
            should_check = g["has_save"] or bool(g["latest_backup"])
            chk = Gtk.CheckButton()
            chk.set_active(should_check)
            card._chk = chk
            card.append(chk)

            # Metadata info
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            lbl_title = Gtk.Label(label=f"<b>{g['name']}</b>", use_markup=True, halign=Gtk.Align.START)
            info_box.append(lbl_title)

            # Fixed Pango markup: use foreground instead of class attribute
            if g["has_dir"] and g["has_save"]:
                stat = f"<span foreground='#26a269' weight='bold'>✔ save.txt ({g['item_count']} items)</span>"
            elif g["has_dir"]:
                stat = "<span foreground='#c01c28' weight='bold'>✖ No save.txt</span>"
            else:
                stat = "<span foreground='#e5a50a' weight='bold'>Archive Only</span>"

            b_stat = f"Last: {g['latest_backup']} ({g['backup_size_mb']:.1f} MB)" if g["latest_backup"] else "No backup"
            lbl_sub = Gtk.Label(halign=Gtk.Align.START)
            lbl_sub.set_markup(f"{stat}  │  <span alpha='70%'>{b_stat}</span>")
            info_box.append(lbl_sub)
            card.append(info_box)

            # Per-Game Parameter Text Boxes
            card._zstd_entry = UI.entry(text=str(zstd_val), placeholder="Zstd", max_chars=6, hexpand=False)
            card.append(card._zstd_entry)

            card._parity_entry = UI.entry(text=str(parity_val), placeholder="PAR2", max_chars=6, hexpand=False)
            card.append(card._parity_entry)

            self._lb_games.append(card)

    def _sync_card_overrides(self):
        idx = 0
        overrides = self._config.get("game_overrides", {})
        while True:
            row = self._lb_games.get_row_at_index(idx)
            if not row:
                break
            card = row.get_child()
            if hasattr(card, "_game_data"):
                slug = card._game_data["slug"]
                z = card._zstd_entry.get_text().strip() or self._config.get("default_zstd", "3")
                p = card._parity_entry.get_text().strip() or self._config.get("default_parity", "10")
                overrides[slug] = {"zstd": z, "parity": p}
            idx += 1
        self._config["game_overrides"] = overrides
        self._save_config()

    def _get_selected_games(self) -> list[tuple[dict, str, str]]:
        self._sync_card_overrides()
        selected = []
        idx = 0
        while True:
            row = self._lb_games.get_row_at_index(idx)
            if not row:
                break
            card = row.get_child()
            if hasattr(card, "_game_data") and card._chk.get_active():
                z = card._zstd_entry.get_text().strip() or self._config.get("default_zstd", "3")
                p = card._parity_entry.get_text().strip() or self._config.get("default_parity", "10")
                selected.append((card._game_data, z, p))
            idx += 1
        return selected

    # ── Operations: Backup, Restore, Verify ─────────────────────────────────

    def _on_backup_clicked(self, btn):
        targets = self._get_selected_games()
        valid = [t for t in targets if t[0]["has_dir"] and t[0]["has_save"]]
        if not valid:
            self._append_log("ERROR: No valid games with save.txt checked for backup.\n")
            return

        _, has_missing = get_dep_status()
        if has_missing:
            self._append_log("ERROR: Missing required system utilities (tar, zstd, or par2).\n")
            return

        self._clear_log()
        self._set_busy(True)
        threading.Thread(target=self._backup_worker, args=(valid,), daemon=True).start()

    def _backup_worker(self, targets: list):
        b_dir = self._config.get("backups_dir", DEFAULT_BACKUP_DIR)
        os.makedirs(b_dir, exist_ok=True)
        total = len(targets)

        for idx, (g, z_lvl, par_ratio) in enumerate(targets, 1):
            gdir = g["path"]
            slug = g["slug"]
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            final_pkg = os.path.join(b_dir, f"{slug}_{timestamp}.gbak")

            GLib.idle_add(self._update_status, (idx - 1) / total, f"[{idx}/{total}] Backing up {g['name']}...")
            GLib.idle_add(self._append_log, f"\n=== [Backup {idx}/{total}: {slug}] ===\n")

            items = BackupEngine.parse_save_txt(gdir)
            if not items:
                GLib.idle_add(self._append_log, f"Skipping {g['name']}: save.txt missing or empty.\n")
                continue

            tmp_dir = tempfile.mkdtemp(prefix="gbak_stage_")
            payload = os.path.join(tmp_dir, "data.tar.zst")

            try:
                # 1. Zstandard Tar Compression
                tar_cmd = ["tar", "-I", f"zstd -T0 -{z_lvl}", "-cf", payload, "-C", gdir] + items
                if not self._run_proc(tar_cmd):
                    GLib.idle_add(self._append_log, "Compression error.\n")
                    continue

                # 2. PAR2 Parity Recovery Creation (Fixed arguments and cwd)
                par_bin = "par2create" if shutil.which("par2create") else "par2"
                par_cmd = [par_bin, "c", f"-r{par_ratio}", "-q", "data.tar.zst.par2", "data.tar.zst"]
                if not self._run_proc(par_cmd, cwd=tmp_dir):
                    GLib.idle_add(self._append_log, "Parity generation error.\n")
                    continue

                # 3. Bundle payload and parity into a single .gbak container
                stage_files = os.listdir(tmp_dir)
                bundle_cmd = ["tar", "-cf", final_pkg, "-C", tmp_dir] + stage_files
                if not self._run_proc(bundle_cmd):
                    GLib.idle_add(self._append_log, "Packaging error.\n")
                    continue

                mb = os.path.getsize(final_pkg) / (1024 * 1024)
                GLib.idle_add(self._append_log, f"Created {os.path.basename(final_pkg)} ({mb:.2f} MiB)\n")

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        GLib.idle_add(self._finish_job, True, "All selected backups complete!")
        GLib.idle_add(self._rescan_games)

    def _on_restore_clicked(self, btn):
        targets = self._get_selected_games()
        valid = [t for t in targets if t[0]["all_backups"]]
        if not valid:
            self._append_log("ERROR: No checked games have available backups to restore.\n")
            return

        self._clear_log()
        self._set_busy(True)
        threading.Thread(target=self._restore_worker, args=(valid, True), daemon=True).start()

    def _on_verify_clicked(self, btn):
        targets = self._get_selected_games()
        valid = [t for t in targets if t[0]["all_backups"]]
        if not valid:
            self._append_log("ERROR: No checked games have backups to verify.\n")
            return

        self._clear_log()
        self._set_busy(True)
        threading.Thread(target=self._restore_worker, args=(valid, False), daemon=True).start()

    def _restore_worker(self, targets: list, do_restore: bool):
        total = len(targets)
        action_name = "Restoring" if do_restore else "Verifying"

        for idx, (g, _, _) in enumerate(targets, 1):
            latest_archive = g["all_backups"][-1][0]
            dest_dir = g["path"]

            GLib.idle_add(self._update_status, (idx - 1) / total, f"[{idx}/{total}] {action_name} {g['name']}...")
            GLib.idle_add(self._append_log, f"\n=== [{action_name} {idx}/{total}: {g['name']}] ===\n")

            tmp_dir = tempfile.mkdtemp(prefix="gbak_restore_")
            try:
                # 1. Unpack .gbak bundle
                if not self._run_proc(["tar", "-xf", latest_archive, "-C", tmp_dir]):
                    GLib.idle_add(self._append_log, "Failed to read .gbak package.\n")
                    continue

                par2_idx = "data.tar.zst.par2"
                if not os.path.isfile(os.path.join(tmp_dir, par2_idx)):
                    GLib.idle_add(self._append_log, "PAR2 index missing from archive.\n")
                    continue

                # 2. Verify PAR2 (with cwd=tmp_dir)
                par_bin = "par2verify" if shutil.which("par2verify") else "par2"
                if not self._run_proc([par_bin, "v", "-q", par2_idx], cwd=tmp_dir):
                    GLib.idle_add(self._append_log, "Damage detected! Attempting PAR2 repair...\n")
                    rep_bin = "par2repair" if shutil.which("par2repair") else "par2"
                    if not self._run_proc([rep_bin, "r", par2_idx], cwd=tmp_dir):
                        GLib.idle_add(self._append_log, "Archive corrupted beyond repair!\n")
                        continue
                    GLib.idle_add(self._append_log, "Repaired damaged blocks successfully.\n")
                else:
                    GLib.idle_add(self._append_log, "Archive verified: 100% healthy.\n")

                if not do_restore:
                    continue

                # 3. Extract to target game directory
                os.makedirs(dest_dir, exist_ok=True)
                payload = os.path.join(tmp_dir, "data.tar.zst")
                if not self._run_proc(["tar", "-I", "zstd", "-xf", payload, "-C", dest_dir]):
                    GLib.idle_add(self._append_log, "Restoration extract error.\n")
                    continue

                GLib.idle_add(self._append_log, f"SUCCESS: Restored files to {dest_dir}\n")

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        msg = "Restoration complete!" if do_restore else "Verification complete!"
        GLib.idle_add(self._finish_job, True, msg)
        GLib.idle_add(self._rescan_games)

    # ── Subprocess Runner & UI Sync ─────────────────────────────────────────

    def _run_proc(self, args: list, cwd: str = None) -> bool:
        cmd_str = " ".join(f'"{a}"' if " " in a else a for a in args)
        GLib.idle_add(self._append_log, f"> {cmd_str}\n")
        try:
            self._process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1, cwd=cwd
            )
            for line in self._process.stdout:
                GLib.idle_add(self._append_log, line)
            self._process.wait()
            return self._process.returncode == 0
        except Exception as e:
            GLib.idle_add(self._append_log, f"Error: {e}\n")
            return False
        finally:
            self._process = None

    def _on_cancel_clicked(self, btn):
        if self._process and self._process.poll() is None:
            self._append_log("\n[User] Cancelling...\n")
            self._process.kill()

    def _set_busy(self, busy: bool):
        self._btn_backup.set_sensitive(not busy)
        self._btn_restore.set_sensitive(not busy)
        self._btn_verify.set_sensitive(not busy)
        self._btn_refresh.set_sensitive(not busy)
        self._btn_cancel.set_sensitive(busy)

    def _update_status(self, frac: float, text: str):
        self._p_bar.set_fraction(frac)
        self._p_bar.set_text(f"{int(frac * 100)}%")
        self._p_detail.set_markup(f"<b>{text}</b>")
        return False

    def _finish_job(self, success: bool, message: str):
        self._set_busy(False)
        self._p_bar.set_fraction(1.0 if success else 0.0)
        self._p_bar.set_text("100%" if success else "Failed")
        color = "#26a269" if success else "#c01c28"
        self._p_detail.set_markup(f"<span foreground='{color}' weight='bold'>{message}</span>")
        return False

    def _append_log(self, text: str):
        self._log_buf.insert(self._log_buf.get_end_iter(), text)
        self._log_buf.move_mark(self._log_mark, self._log_buf.get_end_iter())
        self._tv_log.scroll_mark_onscreen(self._log_mark)
        return False

    def _clear_log(self):
        self._log_buf.set_text("")

    def _on_close_request(self, win):
        self._sync_card_overrides()
        if self._process and self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass
        return False

    # ── Folder Browser Dialogs ──────────────────────────────────────────────

    def _on_browse_games_dir(self, btn):
        self._games_dialog = Gtk.FileChooserNative(
            title="Select Games Directory", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        def _resp(dlg, resp):
            if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
                self._entry_games_dir.set_text(dlg.get_file().get_path())
            dlg.destroy()
        self._games_dialog.connect("response", _resp)
        self._games_dialog.show()

    def _on_browse_backups_dir(self, btn):
        self._backups_dialog = Gtk.FileChooserNative(
            title="Select Backups Directory", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        def _resp(dlg, resp):
            if resp == Gtk.ResponseType.ACCEPT and dlg.get_file():
                self._entry_backups_dir.set_text(dlg.get_file().get_path())
            dlg.destroy()
        self._backups_dialog.connect("response", _resp)
        self._backups_dialog.show()


# ─── Desktop Integration & Self-Install ──────────────────────────────────────

_DESKTOP_ID = "game_backup.desktop"
_ICON_NAME = "game-backup"
_MIME_XML_NAME = "game-backup.xml"

_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1f232a"/>
      <stop offset="100%" stop-color="#14171c"/>
    </linearGradient>
    <linearGradient id="shield" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3584e4"/>
      <stop offset="100%" stop-color="#1c71d8"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="112" height="112" rx="28" fill="url(#bg)"/>
  <path d="M 64 20 L 98 34 C 98 74 64 104 64 104 C 64 104 30 74 30 34 Z" fill="url(#shield)" opacity="0.95"/>
  <path d="M 46 54 C 42 54 40 58 42 66 L 46 76 C 48 80 54 80 58 76 L 62 72 L 66 72 L 70 76 C 74 80 80 80 82 76 L 86 66 C 88 58 86 54 82 54 Z" fill="#ffffff"/>
  <path d="M 50 60 L 54 60 L 54 64 L 50 64 Z M 52 58 L 52 66 Z" stroke="#1c71d8" stroke-width="2"/>
  <circle cx="74" cy="61" r="2" fill="#1c71d8"/>
  <circle cx="78" cy="65" r="2" fill="#1c71d8"/>
</svg>"""

_MIME_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-gbak">
    <comment>Game Backup Archive</comment>
    <glob pattern="*.gbak"/>
    <icon name="game-backup"/>
  </mime-type>
</mime-info>
"""

def ensure_self_install():
    try:
        if not sys.stdout.isatty():
            return
        a_dir = os.path.expanduser("~/.local/share/applications")
        i_dir = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
        m_dir = os.path.expanduser("~/.local/share/mime/packages")
        os.makedirs(a_dir, exist_ok=True)
        os.makedirs(i_dir, exist_ok=True)
        os.makedirs(m_dir, exist_ok=True)

        i_path = os.path.join(i_dir, f"{_ICON_NAME}.svg")
        d_path = os.path.join(a_dir, _DESKTOP_ID)
        m_path = os.path.join(m_dir, _MIME_XML_NAME)

        with open(i_path, "w") as f:
            f.write(_ICON_SVG)

        with open(m_path, "w") as f:
            f.write(_MIME_XML)

        entry = (
            "[Desktop Entry]\nType=Application\nVersion=1.0\nName=Game Backup\nGenericName=Game Backup Utility\n"
            f'Comment=Self-healing single-file game save and mod backup manager\nExec="{sys.executable}" "{os.path.abspath(__file__)}" %f\n'
            f"Icon={_ICON_NAME}\nTerminal=false\nCategories=Utility;GTK;\nMimeType=application/x-gbak;\nStartupWMClass=game_backup\n"
        )
        with open(d_path, "w") as f:
            f.write(entry)

        subprocess.run(["update-desktop-database", "-q", a_dir], capture_output=True, timeout=3)
        subprocess.run(["update-mime-database", os.path.expanduser("~/.local/share/mime")], capture_output=True, timeout=3)
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", os.path.expanduser("~/.local/share/icons/hicolor")], capture_output=True, timeout=3)
    except Exception:
        pass


class GameBackupApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.gamebackup",
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS.encode())
        d = Gdk.Display.get_default()
        if d:
            Gtk.StyleContext.add_provider_for_display(d, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.props.active_window or GameBackupWindow(application=self)
        win.present()

    def do_open(self, files, n_files, hint):
        win = self.props.active_window or GameBackupWindow(application=self)
        win.present()


def main():
    if "--version" in sys.argv:
        print(f"game-backup {__version__}")
        return 0
    ensure_self_install()
    return GameBackupApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())