#!/usr/bin/env python3
"""Gacha Game Update Manager (GTK4 Version)

A lightweight Linux update, patching, and integrity manager for Kuro Games
and other titles.
"""
__version__ = "2.9.0"

import gi
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk, Gio, GObject

import os
import re
import sys
import time
import json
import gzip
import shutil
import hashlib
import zipfile
import threading
import subprocess
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# ─── Game Configurations ────────────────────────────────────────────────────

GAMES_CONFIG = {
    "Wuthering Waves": {
        "id": "wuwa",
        "primary_url": "https://raw.githubusercontent.com/TwintailTeam/game-manifests/refs/heads/main/wuwa_global.json",
        "fallback_url": "https://prod-alicdn-gamestarter.kurogame.com/launcher/game/G153/50004_obOHXFrFanqsaIEOmuKroCcbZkQRBC7c/index.json",
    },
    "Punishing: Gray Raven": {
        "id": "pgr",
        "primary_url": "https://raw.githubusercontent.com/TwintailTeam/game-manifests/refs/heads/main/pgr_global.json",
        "fallback_url": "https://prod-alicdn-gamestarter.kurogame.com/pcstarter/prod/game/G148/50001_s4s1eG1rLq/index.json",
    }
}

SETTINGS_DIR = os.path.expanduser("~/.config/ggum")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

LOG_LEVELS = ["ALL", "INFO", "WARNING", "ERROR"]
DOWNLOAD_MANAGERS = ["aria2c", "Hydra"]

APP_CSS = """
.action-btn { padding: 5px 12px; font-weight: bold; }
.monospace-view { font-family: monospace, monospace; font-size: 11px; }
.dim-label { opacity: 0.75; font-size: 11px; }
"""

# ─── Helpers & Version Detection ────────────────────────────────────────────

def format_bytes(size: float) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PiB"


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/") if path else ""


def fetch_remote_json(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip",
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode("utf-8"))


def detect_game_version(game_id: str, game_dir: str) -> str:
    if not game_dir or not os.path.isdir(game_dir):
        return "Not Selected"

    if game_id == "pgr":
        v_json = os.path.join(game_dir, "version.json")
        if os.path.isfile(v_json):
            try:
                with open(v_json, "r", encoding="utf-8", errors="ignore") as f:
                    m = re.search(r"package_version\s*[:=]\s*[\"']?([0-9\.]+)[\"']?", f.read())
                    if m:
                        return m.group(1)
            except Exception:
                pass

        krsdk = os.path.join(game_dir, "PGR_Data", "Plugins", "KRSDKRes", "KRSDK.bin")
        if os.path.isfile(krsdk):
            try:
                with open(krsdk, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "KR_GameVersion=" in line:
                            return line.split("KR_GameVersion=")[1].strip()
            except Exception:
                pass

    if game_id == "wuwa":
        res_dir = os.path.join(game_dir, "Client", "Saved", "Resources")
        if os.path.isdir(res_dir):
            try:
                for root, _, files in os.walk(res_dir):
                    for fname in files:
                        if fname.startswith("ManifestResource_") and fname.endswith(".txt"):
                            m = re.search(r"ManifestResource_([0-9\.]+)\.txt", fname)
                            if m:
                                return m.group(1)
            except Exception:
                pass

        for root, _, files in os.walk(os.path.join(game_dir, "Client", "Saved")):
            if "MountResource.txt" in files:
                try:
                    with open(os.path.join(root, "MountResource.txt"), "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            m = re.search(r"Resource/([0-9\.]+)/pakchunk", line)
                            if m:
                                return m.group(1)
                except Exception:
                    pass
                break

    for candidate in [
        os.path.join(game_dir, "version.txt"),
        os.path.join(game_dir, "Client", "version.txt"),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r") as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass

    config_ini = os.path.join(game_dir, "config.ini")
    if os.path.isfile(config_ini):
        try:
            with open(config_ini, "r") as f:
                for line in f:
                    if "game_version" in line or "version" in line.lower():
                        parts = line.split("=")
                        if len(parts) == 2:
                            return parts[1].strip()
        except Exception:
            pass

    return "Unknown"


def write_metalink4(file_records: list[dict], output_path: str):
    root = ET.Element("metalink", xmlns="urn:ietf:params:xml:ns:metalink")
    ET.SubElement(root, "generator").text = "GGUM"

    for item in file_records:
        file_el = ET.SubElement(root, "file", name=item["name"])
        if item.get("size"):
            ET.SubElement(file_el, "size").text = str(item["size"])
        if item.get("md5"):
            ET.SubElement(file_el, "hash", type="md5").text = item["md5"]
        for prio, url in enumerate(item.get("urls", []), start=1):
            url_el = ET.SubElement(file_el, "url", priority=str(prio))
            url_el.text = url

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def copy_to_clipboard(text: str):
    display = Gdk.Display.get_default()
    if display:
        clipboard = display.get_clipboard()
        if hasattr(clipboard, "set"):
            clipboard.set(text)
        elif hasattr(clipboard, "set_text"):
            clipboard.set_text(text)
    for bin_name, args in [("wl-copy", ["wl-copy"]), ("xclip", ["xclip", "-selection", "clipboard"])]:
        if shutil.which(bin_name):
            try:
                subprocess.run(args, input=text, text=True, timeout=1)
                break
            except Exception:
                pass


# ─── Reusable Game Tab Component ────────────────────────────────────────────

class GameTab(Gtk.Box):
    def __init__(self, main_win, game_name: str, config: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self.main_win = main_win
        self.game_name = game_name
        self.config = config

        self.manifest_data = None
        self.resource_list = []
        self.cdn_mirrors = []
        self.issue_records = []

        self._build_tab_ui()

    def _build_tab_ui(self):
        # 1. Directory & Version Row
        r_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.append(r_top)

        lbl_folder = Gtk.Label(label="Game Folder:", halign=Gtk.Align.START)
        r_top.append(lbl_folder)

        self.entry_dir = Gtk.Entry(hexpand=True, placeholder_text="Select game folder via Browse...")
        btn_browse = Gtk.Button(label="Browse")
        btn_browse.connect("clicked", self._on_browse_dir)
        r_top.append(self.entry_dir)
        r_top.append(btn_browse)

        r_ver = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.append(r_ver)
        self.lbl_local_ver = Gtk.Label(use_markup=True, halign=Gtk.Align.START)
        self.lbl_remote_ver = Gtk.Label(use_markup=True, halign=Gtk.Align.START)
        r_ver.append(self.lbl_local_ver)
        r_ver.append(self.lbl_remote_ver)
        self._refresh_local_version_label()

        # 2. Consolidated Actions Row (Pipeline)
        r_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.append(r_actions)

        self.btn_check = Gtk.Button(label="Check", css_classes=["action-btn", "suggested-action"])
        self.btn_check.connect("clicked", self._on_check_updates)
        r_actions.append(self.btn_check)

        r_actions.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self.combo_dm = Gtk.ComboBoxText()
        for dm in DOWNLOAD_MANAGERS:
            self.combo_dm.append_text(dm)
        self.combo_dm.set_active(0)
        r_actions.append(self.combo_dm)

        self.btn_script = Gtk.Button(label="Download", sensitive=False, css_classes=["action-btn"])
        self.btn_script.connect("clicked", self._on_generate_script)
        r_actions.append(self.btn_script)

        # Dynamic Now / Later checkbox
        self.chk_now = Gtk.CheckButton(label="Now", active=True)
        self.chk_now.connect("toggled", lambda c: c.set_label("Now" if c.get_active() else "Later"))
        r_actions.append(self.chk_now)

        r_actions.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self.btn_patch = Gtk.Button(label="Patch", sensitive=False, css_classes=["action-btn"])
        self.btn_patch.connect("clicked", self._on_apply_patch)
        r_actions.append(self.btn_patch)

        self.btn_verify = Gtk.Button(label="Verify", sensitive=False, css_classes=["action-btn"])
        self.btn_verify.connect("clicked", self._on_verify_integrity)
        r_actions.append(self.btn_verify)

        # 3. Section Separator Line Break
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        self.append(sep)

        # 4. Interactive File Queue & Toolbar
        r_tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.append(r_tb)

        btn_sel_all = Gtk.Button(label="Select All")
        btn_sel_all.connect("clicked", lambda b: self._set_all_checked(True))
        r_tb.append(btn_sel_all)

        btn_sel_none = Gtk.Button(label="Select None")
        btn_sel_none.connect("clicked", lambda b: self._set_all_checked(False))
        r_tb.append(btn_sel_none)

        btn_expand = Gtk.Button(label="Expand All")
        btn_expand.connect("clicked", lambda b: self.tree_view.expand_all())
        r_tb.append(btn_expand)

        btn_collapse = Gtk.Button(label="Collapse All")
        btn_collapse.connect("clicked", lambda b: self.tree_view.collapse_all())
        r_tb.append(btn_collapse)

        self.lbl_sel_summary = Gtk.Label(label="Selected: 0 files (0 B)", halign=Gtk.Align.END, hexpand=True)
        r_tb.append(self.lbl_sel_summary)

        # TreeStore Model:
        # 0: bool (checked)
        # 1: str (status markup)
        # 2: str (filename / folder name)
        # 3: str (formatted size)
        # 4: GObject.TYPE_INT64 (raw size in bytes)
        # 5: str (last modified)
        # 6: float (raw mtime)
        # 7: object (raw dict record)
        self.tree_store = Gtk.TreeStore(bool, str, str, str, GObject.TYPE_INT64, str, float, object)

        sc_tree = Gtk.ScrolledWindow(min_content_height=200, vexpand=True)
        sc_tree.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.tree_view = Gtk.TreeView(model=self.tree_store)
        self.tree_view.set_headers_visible(True)
        sc_tree.set_child(self.tree_view)
        self.append(sc_tree)

        self._init_tree_columns()

    def _init_tree_columns(self):
        # 0: Checkbox
        r_toggle = Gtk.CellRendererToggle(xpad=8, ypad=4)
        r_toggle.connect("toggled", self._on_cell_toggled)
        col_check = Gtk.TreeViewColumn("", r_toggle, active=0)
        col_check.set_min_width(45)
        col_check.set_resizable(False)
        self.tree_view.append_column(col_check)

        # 1: Status (No icons)
        r_status = Gtk.CellRendererText(xpad=8)
        col_status = Gtk.TreeViewColumn("Status", r_status, markup=1)
        col_status.set_sort_column_id(1)
        col_status.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col_status.set_resizable(True)
        self.tree_view.append_column(col_status)

        # 2: Files (renamed from File / Folder)
        r_name = Gtk.CellRendererText(xpad=8)
        col_name = Gtk.TreeViewColumn("Files", r_name, text=2)
        col_name.set_sort_column_id(2)
        col_name.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col_name.set_resizable(True)
        col_name.set_expand(True)
        self.tree_view.append_column(col_name)

        # 3: Size
        r_size = Gtk.CellRendererText(xpad=8)
        col_size = Gtk.TreeViewColumn("Size", r_size, text=3)
        col_size.set_sort_column_id(4)
        col_size.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col_size.set_resizable(True)
        self.tree_view.append_column(col_size)

        # 5: Modified (renamed from Last Modified)
        r_mtime = Gtk.CellRendererText(xpad=8)
        col_mtime = Gtk.TreeViewColumn("Modified", r_mtime, text=5)
        col_mtime.set_sort_column_id(6)
        col_mtime.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col_mtime.set_resizable(True)
        self.tree_view.append_column(col_mtime)

    def _refresh_local_version_label(self):
        ver = detect_game_version(self.config["id"], self.entry_dir.get_text().strip())
        self.lbl_local_ver.set_markup(f"<b>Installed Version:</b> <tt>{ver}</tt>")

    def _on_browse_dir(self, btn):
        dialog = Gtk.FileChooserNative(
            title=f"Select {self.game_name} Folder",
            transient_for=self.main_win,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Select",
            cancel_label="_Cancel"
        )
        cur = self.entry_dir.get_text().strip()
        if cur and os.path.isdir(cur):
            dialog.set_current_folder(Gio.File.new_for_path(cur))

        def _resp(d, resp):
            if resp == Gtk.ResponseType.ACCEPT and d.get_file():
                self.entry_dir.set_text(d.get_file().get_path())
                self._refresh_local_version_label()
                self.main_win._save_settings()
            d.destroy()

        dialog.connect("response", _resp)
        dialog.show()

    def get_staging_dir(self) -> str:
        gdir = self.entry_dir.get_text().strip()
        return os.path.join(gdir, "staging") if gdir else os.path.expanduser("~/staging")

    # ── High-Performance Issue-Only TreeView Population ─────────────────

    def _populate_issues_tree(self, issues: list[tuple[dict, str]], total_manifest_count: int):
        self.tree_store.clear()
        folder_iters = {}

        if not issues:
            self.tree_store.append(
                None,
                [False, "<span foreground='#26a269'>Verified</span>", f"All {total_manifest_count:,} game files are intact on disk. No downloads required.", "0 B", 0, "", 0.0, None]
            )
            self._update_selection_summary()
            self.btn_script.set_sensitive(False)
            return

        for r, status_reason in issues:
            dest = normalize_path(r.get("dest", ""))
            size = int(r.get("size", 0))
            bname = os.path.basename(dest)
            dirname = os.path.dirname(dest) or "Root"

            color = "#c01c28" if "Corrupt" in status_reason or "Missing" in status_reason else "#d08b00"
            status_markup = f"<span foreground='{color}'>{status_reason}</span>"

            game_dir = self.entry_dir.get_text().strip()
            local_path = os.path.join(game_dir, dest) if game_dir else None

            mtime_str = "Not on disk"
            raw_mtime = 0.0
            if local_path and os.path.exists(local_path):
                raw_mtime = os.path.getmtime(local_path)
                mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(raw_mtime))

            if dirname not in folder_iters:
                parent_iter = self.tree_store.append(
                    None,
                    [True, "", dirname, "", 0, "", 0.0, None]
                )
                folder_iters[dirname] = parent_iter
            else:
                parent_iter = folder_iters[dirname]

            self.tree_store.append(
                parent_iter,
                [True, status_markup, bname, format_bytes(size), size, mtime_str, raw_mtime, r]
            )

        self._update_selection_summary()
        self.tree_view.expand_all()
        self.btn_script.set_sensitive(True)

    def _on_cell_toggled(self, renderer, path_str):
        tree_iter = self.tree_store.get_iter_from_string(path_str)
        curr_state = self.tree_store.get_value(tree_iter, 0)
        new_state = not curr_state

        self.tree_store.set_value(tree_iter, 0, new_state)

        if self.tree_store.iter_has_child(tree_iter):
            child_iter = self.tree_store.iter_children(tree_iter)
            while child_iter:
                self.tree_store.set_value(child_iter, 0, new_state)
                child_iter = self.tree_store.iter_next(child_iter)

        self._update_selection_summary()

    def _set_all_checked(self, state: bool):
        def _recurse(parent):
            c = self.tree_store.iter_children(parent)
            while c:
                self.tree_store.set_value(c, 0, state)
                if self.tree_store.iter_has_child(c):
                    _recurse(c)
                c = self.tree_store.iter_next(c)

        r = self.tree_store.get_iter_first()
        while r:
            self.tree_store.set_value(r, 0, state)
            _recurse(r)
            r = self.tree_store.iter_next(r)

        self._update_selection_summary()

    def _get_selected_records(self) -> list[dict]:
        selected = []
        def _recurse(parent):
            c = self.tree_store.iter_children(parent)
            while c:
                if not self.tree_store.iter_has_child(c):
                    if self.tree_store.get_value(c, 0):
                        record = self.tree_store.get_value(c, 7)
                        if record:
                            selected.append(record)
                else:
                    _recurse(c)
                c = self.tree_store.iter_next(c)

        r = self.tree_store.get_iter_first()
        while r:
            _recurse(r)
            r = self.tree_store.iter_next(r)
        return selected

    def _update_selection_summary(self):
        sel = self._get_selected_records()
        total_b = sum(int(r.get("size", 0)) for r in sel)
        self.lbl_sel_summary.set_text(f"Selected: {len(sel)} files ({format_bytes(total_b)})")

    # ── Update Checking (Primary + Fallback Pipeline) ────────────────────

    def _on_check_updates(self, btn):
        game_dir = self.entry_dir.get_text().strip()
        if not game_dir:
            self.main_win.log("WARNING", f"[{self.game_name}] Please select a game folder first.")

        self.btn_check.set_sensitive(False)
        self.btn_script.set_sensitive(False)
        self.main_win.log("INFO", f"[{self.game_name}] Checking for updates...")
        self.main_win.set_progress(0.0, "Checking manifest...")
        threading.Thread(target=self._worker_check, daemon=True).start()

    def _worker_check(self):
        urls = [self.config["primary_url"], self.config["fallback_url"]]
        data = None
        used_url = None

        for u in urls:
            try:
                data = fetch_remote_json(u)
                used_url = u
                break
            except Exception as e:
                GLib.idle_add(self.main_win.log, "WARNING", f"[{self.game_name}] Manifest failed on {u}: {e}")

        if not data:
            GLib.idle_add(self.main_win.log, "ERROR", f"[{self.game_name}] All manifest endpoints failed.")
            GLib.idle_add(self._on_check_done, False, "", [], [])
            return

        try:
            version = "Unknown"
            mirrors = []
            r_list = []
            base_rel = ""
            is_diff = False

            local_ver = detect_game_version(self.config["id"], self.entry_dir.get_text().strip())

            if "game_versions" in data:
                version = data.get("latest_version", "Unknown")
                latest_gv = data["game_versions"][0]
                meta = latest_gv.get("metadata", {})
                diffs = latest_gv.get("game", {}).get("diff", [])

                matching_diff = next((d for d in diffs if d.get("original_version") == local_ver), None)

                if matching_diff and matching_diff.get("file_url"):
                    diff_url = matching_diff["file_url"]
                    GLib.idle_add(self.main_win.log, "INFO", f"[{self.game_name}] Found incremental diff update from v{local_ver} -> v{version}!")
                    res_raw = fetch_remote_json(diff_url)
                    parsed = urllib.parse.urlparse(diff_url)
                    mirrors = [f"{parsed.scheme}://{parsed.netloc}"]
                    base_rel = matching_diff.get("file_path", "")
                    if base_rel.startswith("http"):
                        base_rel = urllib.parse.urlparse(base_rel).path.lstrip("/")
                    is_diff = True
                else:
                    index_file_url = meta.get("index_file", "")
                    res_raw = fetch_remote_json(index_file_url)
                    parsed = urllib.parse.urlparse(index_file_url)
                    mirrors = [f"{parsed.scheme}://{parsed.netloc}"]
                    base_rel = os.path.dirname(parsed.path.lstrip("/")).replace("resource/50015/4.7.0", "zip").replace("resource/50004/3.6.1", "zip")

                if isinstance(res_raw, dict):
                    r_list = res_raw.get("resource") or res_raw.get("resources") or []
                elif isinstance(res_raw, list):
                    r_list = res_raw

            elif "default" in data:
                ch_info = data.get("default", {})
                version = ch_info.get("version", "Unknown")
                cdn_entries = ch_info.get("cdnList", [])
                mirrors = [c["url"].rstrip("/") for c in cdn_entries if "url" in c]
                if not mirrors:
                    parsed = urllib.parse.urlparse(used_url)
                    mirrors = [f"{parsed.scheme}://{parsed.netloc}"]

                res_rel = ch_info.get("resources", "")
                base_rel = ch_info.get("resourcesBasePath", "").strip("/")
                res_url = f"{mirrors[0]}/{res_rel.lstrip('/')}"
                res_raw = fetch_remote_json(res_url)

                if isinstance(res_raw, dict):
                    r_list = res_raw.get("resource") or res_raw.get("resources") or []
                elif isinstance(res_raw, list):
                    r_list = res_raw

            self.cdn_mirrors = mirrors
            self.resource_list = r_list
            self.manifest_data = {
                "version": version,
                "base_path": base_rel,
            }

            game_dir = self.entry_dir.get_text().strip()
            issues = []

            if is_diff:
                for r in r_list:
                    issues.append((r, "Update Patch"))
            elif game_dir and os.path.isdir(game_dir):
                installed_map = {}
                for root, _, files in os.walk(game_dir):
                    for f in files:
                        full_p = os.path.join(root, f)
                        installed_map[f] = full_p
                        installed_map[f.lower()] = full_p

                for r in r_list:
                    dest = normalize_path(r.get("dest", ""))
                    exp_size = int(r.get("size", 0))
                    bname = os.path.basename(dest)

                    p = os.path.join(game_dir, dest)
                    if not os.path.exists(p):
                        p = installed_map.get(bname) or installed_map.get(bname.lower())

                    if not p or not os.path.exists(p):
                        issues.append((r, "Missing"))
                    elif exp_size > 0 and os.path.getsize(p) != exp_size:
                        issues.append((r, "Size Mismatch"))

            self.issue_records = issues
            GLib.idle_add(self._on_check_done, True, version, r_list, issues)
        except Exception as e:
            GLib.idle_add(self.main_win.log, "ERROR", f"[{self.game_name}] Check error: {e}")
            GLib.idle_add(self._on_check_done, False, "", [], [])

    def _on_check_done(self, success: bool, version: str, r_list: list, issues: list):
        self.btn_check.set_sensitive(True)
        if success:
            self.lbl_remote_ver.set_markup(f"<b>Remote Version:</b> <span foreground='#26a269'>{version}</span>")
            self.btn_patch.set_sensitive(True)
            self.btn_verify.set_sensitive(True)

            self._populate_issues_tree(issues, len(r_list))

            if issues:
                total_need = sum(int(r[0].get("size", 0)) for r in issues)
                self.main_win.log("WARNING", f"[{self.game_name}] Found {len(issues):,} files requiring download ({format_bytes(total_need)}). Checked in queue.")
                self.main_win.set_progress(1.0, f"{len(issues):,} files needed ({format_bytes(total_need)})")
            else:
                self.main_win.log("INFO", f"[{self.game_name}] All {len(r_list):,} files verified present on disk.")
                self.main_win.set_progress(1.0, "<span foreground='#26a269'>Game is up to date! (0 files needed)</span>")
        else:
            self.main_win.set_progress(0.0, "Check failed")

    # ── Universal Download Script Generation ────────────────────────────

    def _on_generate_script(self, btn):
        selected_records = self._get_selected_records()
        if not selected_records:
            self.main_win.log("WARNING", "No files selected. Check items in the list above to download.")
            return

        staging = self.get_staging_dir()
        os.makedirs(staging, exist_ok=True)
        meta_path = os.path.join(staging, "kuro_update.meta4")
        script_path = os.path.join(staging, "download.sh")

        base_path = self.manifest_data.get("base_path", "").strip("/")

        records = []
        for r in selected_records:
            dest = normalize_path(r.get("dest", ""))
            size = int(r.get("size", 0))
            md5 = r.get("md5", "")
            urls = [f"{m}/{base_path}/{dest}" for m in self.cdn_mirrors]

            records.append({
                "name": os.path.basename(dest),
                "size": size,
                "md5": md5,
                "urls": urls
            })

        write_metalink4(records, meta_path)

        dm_choice = self.combo_dm.get_active_text() or "aria2c"
        script_lines = ["#!/usr/bin/env sh", f"cd '{staging}' || exit 1", ""]

        if "aria2c" in dm_choice:
            cmd = f"aria2c -M '{meta_path}' -d '{staging}' --continue=true -x 16 -s 16 -j 4 --auto-file-renaming=false"
            script_lines.append(f"echo 'Starting aria2c download ({len(records)} files)...'")
            script_lines.append(f"{cmd}")
        else:  # Hydra
            cmd = f"hydra -P '{staging}' -c '{meta_path}' -x 16"
            script_lines.append(f"echo 'Starting Hydra download ({len(records)} files)...'")
            script_lines.append(f"{cmd}")

        script_lines.append("")
        script_lines.append("echo ''")
        script_lines.append("echo 'All downloads completed!'")

        with open(script_path, "w") as f:
            f.write("\n".join(script_lines) + "\n")
        os.chmod(script_path, 0o755)

        copy_to_clipboard(f"sh '{script_path}'")
        self.main_win.log("INFO", f"Generated Metalink 4: {meta_path}")
        self.main_win.log("INFO", f"Generated download script: {script_path}")

        # Auto-run in terminal if checked
        if self.chk_now.get_active():
            term = (
                shutil.which("kitty")
                or shutil.which("alacritty")
                or shutil.which("foot")
                or shutil.which("konsole")
                or shutil.which("gnome-terminal")
                or shutil.which("xterm")
            )
            if term:
                self.main_win.log("INFO", f"Spawning {dm_choice} download in {term}...")
                shell_cmd = f"sh '{script_path}'; echo ''; echo 'Press Enter to close.'; read line"
                subprocess.Popen([term, "-e", "sh", "-c", shell_cmd])
                self.main_win.set_progress(1.0, f"<span foreground='#26a269'>{dm_choice} Running in Terminal</span>")
                return

        self.main_win.set_progress(1.0, f"<span foreground='#26a269'>Script Generated ({os.path.basename(script_path)})</span>")

    # ── Patch Application (hdiffz) ───────────────────────────────────────

    def _on_apply_patch(self, btn):
        game_dir = self.entry_dir.get_text().strip()
        staging = self.get_staging_dir()

        if not os.path.isdir(game_dir):
            self.main_win.log("ERROR", "Invalid game folder.")
            return

        self.btn_patch.set_sensitive(False)
        self.main_win.set_progress(0.0, "Applying patches...")
        threading.Thread(target=self._worker_patch, args=(game_dir, staging), daemon=True).start()

    def _worker_patch(self, game_dir: str, staging: str):
        try:
            if not os.path.exists(staging):
                GLib.idle_add(self.main_win.log, "WARNING", "No staging directory found.")
                return

            files = os.listdir(staging)
            diffs = [f for f in files if f.endswith((".krdiff", ".krpdiff"))]
            zips = [f for f in files if f.endswith((".krzip", ".zip"))]
            paks = [f for f in files if f.endswith(".pak")]

            total = len(diffs) + len(zips) + len(paks)
            if total == 0:
                GLib.idle_add(self.main_win.log, "WARNING", "No patch files (.krdiff/.krzip/.pak) in staging.")
                return

            done = 0
            patch_bin = ["hpatchz", "-f"] if shutil.which("hpatchz") else ["hdiffz", "--patch", "-f"]

            file_map = {}
            for root, _, fs in os.walk(game_dir):
                for f in fs:
                    file_map[f] = os.path.join(root, f)

            for df in diffs:
                patch_file = os.path.join(staging, df)
                base_name = re.sub(r"\.(krdiff|krpdiff)$", "", df)
                target = file_map.get(base_name)

                if target:
                    tmp_out = f"{target}.new"
                    cmd = patch_bin + [target, patch_file, tmp_out]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0 and os.path.exists(tmp_out):
                        os.replace(tmp_out, target)
                        os.remove(patch_file)
                        GLib.idle_add(self.main_win.log, "INFO", f"Patched: {base_name}")
                    else:
                        GLib.idle_add(self.main_win.log, "ERROR", f"Diff error on {df}: {res.stderr}")
                else:
                    GLib.idle_add(self.main_win.log, "WARNING", f"Base file not found for {df}")

                done += 1
                GLib.idle_add(self.main_win.set_progress, done / total, f"Patching {done}/{total}")

            for zf in zips:
                zip_path = os.path.join(staging, zf)
                GLib.idle_add(self.main_win.log, "INFO", f"Extracting archive: {zf}")
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(game_dir)
                os.remove(zip_path)
                done += 1
                GLib.idle_add(self.main_win.set_progress, done / total, f"Extracting {done}/{total}")

            paks_dest = os.path.join(game_dir, "Client", "Content", "Paks")
            if not os.path.exists(paks_dest):
                paks_dest = game_dir

            for pf in paks:
                src_pak = os.path.join(staging, pf)
                dst_pak = os.path.join(paks_dest, pf)
                shutil.move(src_pak, dst_pak)
                done += 1
                GLib.idle_add(self.main_win.set_progress, done / total, f"Moved {pf}")

            if self.manifest_data and self.manifest_data.get("version"):
                try:
                    with open(os.path.join(game_dir, "version.txt"), "w") as f:
                        f.write(self.manifest_data["version"])
                except Exception:
                    pass
                GLib.idle_add(self._refresh_local_version_label)

            GLib.idle_add(self.main_win.log, "INFO", "All staging patches applied successfully.")
            GLib.idle_add(self.main_win.set_progress, 1.0, "<span foreground='#26a269'>Patching Complete!</span>")
        except Exception as e:
            GLib.idle_add(self.main_win.log, "ERROR", f"Patching error: {e}")
        finally:
            GLib.idle_add(lambda: self.btn_patch.set_sensitive(True))

    # ── Integrity Verification (True MD5 Hash Calculation) ───────────────

    def _on_verify_integrity(self, btn):
        game_dir = self.entry_dir.get_text().strip()
        if not os.path.isdir(game_dir) or not self.resource_list:
            self.main_win.log("WARNING", "Please select a valid game directory and fetch manifest first.")
            return

        self.btn_verify.set_sensitive(False)
        self.main_win.set_progress(0.0, "Verifying files...")
        threading.Thread(target=self._worker_verify, args=(game_dir,), daemon=True).start()

    def _worker_verify(self, game_dir: str):
        try:
            total = len(self.resource_list)
            GLib.idle_add(self.main_win.log, "INFO", f"[{self.game_name}] Indexing installed files on disk...")

            file_index = {}
            for root, _, files in os.walk(game_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    file_index[f] = full_p
                    file_index[f.lower()] = full_p

            GLib.idle_add(self.main_win.log, "INFO", f"[{self.game_name}] Computing MD5 hashes for {total:,} files...")

            mismatches = []
            start = time.time()
            hashed_bytes = 0

            for idx, r in enumerate(self.resource_list, start=1):
                dest = normalize_path(r.get("dest", ""))
                expected_md5 = r.get("md5", "").lower()
                expected_size = int(r.get("size", 0))
                bname = os.path.basename(dest)

                p = os.path.join(game_dir, dest)
                if not os.path.exists(p):
                    p = file_index.get(bname) or file_index.get(bname.lower())

                if not p or not os.path.exists(p):
                    mismatches.append((r, "Missing"))
                    continue

                if expected_size > 0 and os.path.getsize(p) != expected_size:
                    mismatches.append((r, "Size Mismatch"))
                    continue

                calc = hashlib.md5()
                with open(p, "rb") as f:
                    while chunk := f.read(524288):
                        calc.update(chunk)
                        hashed_bytes += len(chunk)

                if calc.hexdigest().lower() != expected_md5:
                    mismatches.append((r, "MD5 Corrupted"))

                if idx % 25 == 0 or idx == total:
                    elapsed = max(time.time() - start, 0.001)
                    GLib.idle_add(self.main_win.set_progress, idx / total, f"Verifying MD5: {idx}/{total} ({format_bytes(hashed_bytes / elapsed)}/s)")

            GLib.idle_add(self._on_verify_done, mismatches, total)
        finally:
            GLib.idle_add(lambda: self.btn_verify.set_sensitive(True))

    def _on_verify_done(self, mismatches: list, total: int):
        self._populate_issues_tree(mismatches, total)

        if not mismatches:
            self.main_win.log("INFO", f"[{self.game_name}] 100% Integrity Passed. All files are intact.")
            self.main_win.set_progress(1.0, "<span foreground='#26a269'><b>100% Verified &amp; Intact</b></span>")
        else:
            self.main_win.log("ERROR", f"[{self.game_name}] Integrity check failed on {len(mismatches)} files.")
            self.main_win.set_progress(1.0, f"<span foreground='#c01c28'><b>{len(mismatches)} Corrupted / Missing Files</b></span>")
            self.main_win.log("INFO", "Broken files are highlighted in the queue above. Click 'Download' to download and repair.")


# ─── Main Window ─────────────────────────────────────────────────────────────

class GgumWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("Gacha Game Update Manager")
        self.set_default_size(840, 720)

        self.patch_tool = "hpatchz" if shutil.which("hpatchz") else ("hdiffz" if shutil.which("hdiffz") else "hpatchz")
        self._raw_logs = []

        self._build_ui()
        self._load_settings()

        self.connect("close-request", self._on_close)

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin_start=8, margin_end=8, margin_top=6, margin_bottom=6)
        self.set_child(root)

        # Header: Title + Real-time Tool Status Indicators (Name only, no 'missing')
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.append(Gtk.Label(label="<b>Gacha Game Update Manager</b>", use_markup=True))

        has_patch = bool(shutil.which("hpatchz") or shutil.which("hdiffz"))
        has_hydra = bool(shutil.which("hydra"))
        has_aria2 = bool(shutil.which("aria2c"))

        c_patch = "#26a269" if has_patch else "#c01c28"
        c_hydra = "#26a269" if has_hydra else "#c01c28"
        c_aria2 = "#26a269" if has_aria2 else "#c01c28"

        badges = Gtk.Label(
            use_markup=True, halign=Gtk.Align.END, hexpand=True,
            label=f'<span foreground="{c_patch}" font_weight="bold">{self.patch_tool}</span>  │  '
                  f'<span foreground="{c_hydra}" font_weight="bold">hydra</span>  │  '
                  f'<span foreground="{c_aria2}" font_weight="bold">aria2c</span>'
        )
        hdr.append(badges)
        root.append(hdr)

        # Game Tabs Notebook
        self.notebook = Gtk.Notebook(vexpand=True)
        root.append(self.notebook)

        self.game_tabs = {}
        for game_title, cfg in GAMES_CONFIG.items():
            tab = GameTab(self, game_title, cfg)
            self.game_tabs[cfg["id"]] = tab
            self.notebook.append_page(tab, Gtk.Label(label=game_title))

        # Progress Section
        p_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.p_bar = Gtk.ProgressBar(show_text=True, text="0.0%")
        self.p_detail = Gtk.Label(use_markup=True, label="<i>Ready</i>")
        p_box.append(self.p_bar)
        p_box.append(self.p_detail)
        root.append(p_box)

        # Terminal Header with Filter
        term_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        term_hdr.append(Gtk.Label(label="<b>Log Output:</b>", use_markup=True))

        term_hdr.append(Gtk.Label(label="Filter:", halign=Gtk.Align.END, hexpand=True))
        self.combo_log_level = Gtk.ComboBoxText()
        for lvl in LOG_LEVELS:
            self.combo_log_level.append_text(lvl)
        self.combo_log_level.set_active(0)
        self.combo_log_level.connect("changed", self._on_log_level_changed)
        term_hdr.append(self.combo_log_level)

        btn_clear = Gtk.Button(label="Clear")
        btn_clear.connect("clicked", lambda b: self._clear_log())
        term_hdr.append(btn_clear)
        root.append(term_hdr)

        # Output Text View (180px - 1.5x height)
        sc = Gtk.ScrolledWindow(min_content_height=180, vexpand=True)
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.tv_log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, left_margin=6, right_margin=6)
        self.log_buf = self.tv_log.get_buffer()
        self.log_mark = self.log_buf.create_mark("end", self.log_buf.get_end_iter(), False)
        sc.set_child(self.tv_log)
        root.append(sc)

    def set_progress(self, frac: float, text: str):
        self.p_bar.set_fraction(max(0.0, min(1.0, frac)))
        self.p_bar.set_text(f"{frac * 100:.1f}%")
        self.p_detail.set_markup(text)

    def log(self, level: str, text: str):
        self._raw_logs.append((level, text))
        active_level = self.combo_log_level.get_active_text() or "ALL"
        if self._level_matches(level, active_level):
            self._append_to_textview(level, text)

    def _append_to_textview(self, level: str, text: str):
        prefix = f"[{level}] " if level != "INFO" else ""
        formatted = f"{prefix}{text}\n"
        self.log_buf.insert(self.log_buf.get_end_iter(), formatted)
        self.log_buf.move_mark(self.log_mark, self.log_buf.get_end_iter())
        self.tv_log.scroll_mark_onscreen(self.log_mark)

    def _level_matches(self, msg_level: str, filter_level: str) -> bool:
        if filter_level == "ALL":
            return True
        if filter_level == "INFO" and msg_level in ("INFO", "WARNING", "ERROR"):
            return True
        if filter_level == "WARNING" and msg_level in ("WARNING", "ERROR"):
            return True
        if filter_level == "ERROR" and msg_level == "ERROR":
            return True
        return False

    def _on_log_level_changed(self, combo):
        self.log_buf.set_text("")
        active_level = combo.get_active_text() or "ALL"
        for level, text in self._raw_logs:
            if self._level_matches(level, active_level):
                self._append_to_textview(level, text)

    def _clear_log(self):
        self._raw_logs.clear()
        self.log_buf.set_text("")

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                for gid, tab in self.game_tabs.items():
                    if gid in data:
                        saved_dir = data[gid].get("dir", "").strip()
                        if saved_dir:
                            tab.entry_dir.set_text(saved_dir)
                            tab._refresh_local_version_label()
            except Exception:
                pass

    def _save_settings(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        try:
            data = {
                gid: {"dir": tab.entry_dir.get_text().strip()}
                for gid, tab in self.game_tabs.items()
            }
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _on_close(self, win):
        self._save_settings()
        return False


# ─── Self-Installation (.desktop) ───────────────────────────────────────────

_DESKTOP_ID = "ggum.desktop"
_ICON_NAME = "ggum"
_ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="8" y="8" width="112" height="112" rx="26" fill="#1b1c20"/>
  <rect x="18" y="18" width="92" height="92" rx="18" fill="#3584e4" opacity="0.85"/>
  <polygon points="64,28 92,64 64,100 36,64" fill="#ffffff" opacity="0.9"/>
  <circle cx="64" cy="64" r="14" fill="#1b1c20"/>
  <polygon points="64,56 70,68 58,68" fill="#3584e4"/>
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
            "[Desktop Entry]\nType=Application\nVersion=1.0\nName=GGUM\nGenericName=Gacha Game Update Manager\n"
            "Comment=Gacha Game Update Manager\n"
            f'Exec="{sys.executable}" "{os.path.abspath(__file__)}"\nIcon={_ICON_NAME}\nTerminal=false\n'
            "Categories=Network;Utility;GTK;\nStartupWMClass=io.github.ggum\n"
        )
        with open(d_path, "w") as f:
            f.write(entry)

        subprocess.run(["update-desktop-database", "-q", a_dir], capture_output=True, timeout=3)
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", os.path.expanduser("~/.local/share/icons/hicolor")], capture_output=True, timeout=3)
    except Exception:
        pass


class GgumApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.ggum", flags=Gio.ApplicationFlags.FLAGS_NONE)

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
        win = self.props.active_window or GgumWindow(application=self)
        win.present()


def main():
    if "--version" in sys.argv:
        print(f"ggum {__version__}")
        return 0
    ensure_self_install()
    return GgumApplication().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
