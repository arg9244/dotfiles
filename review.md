# Dotfiles Review — /home/reza/.local/share/chezmoi

Date: 2026-08-08
Scope: install.sh + tracked dotfiles under chezmoi source
Outcome: READ-ONLY review — no changes made

---

## 1. install.sh — Critical / Breakage Risk

| # | Severity | Issue | Detail |
|---|----------|-------|--------|
| 1 | **HIGH** | Blocky package not installed | `dot_config/blocky/blocky.yml` is tracked and symlinked to `/etc/blocky/blocky.yml`, but `blocky` is missing from both the `PACMAN` and `AUR` arrays. The config lands on disk but the resolver daemon is never installed, so the symlink is dead weight. |
| 2 | **HIGH** | Mount units not enabled for boot | `mount-media-c.service` and `mount-media-d.service` are copied to `/etc/systemd/system/` and restarted, but `systemctl enable` is never called. They will only run until next reboot. Add `run "Enable mount-media-c" sudo systemctl enable mount-media-c.service` (and D) after the `daemon-reload` step. |
| 3 | **MEDIUM** | Foot theme file missing from source | `dot_config/foot/foot.ini` has `include=~/.config/foot/themes/noctalia`, but `dot_config/foot/themes/noctalia` does not exist in the chezmoi source. Foot will fail to load the theme on a fresh apply. Either ship the theme file or drop the include. |
| 4 | **MEDIUM** | Blocky symlink points to chezmoi source, not deployed config | `ln -sf "$ORIGINAL_HOME/.local/share/chezmoi/dot_config/blocky/blocky.yml" /etc/blocky/blocky.yml`. Compare this to the sysctl line which correctly points to `~/.config/sysctl.d/...`. If the user edits `~/.config/blocky/blocky.yml`, `/etc/blocky/blocky.yml` will not reflect it. Consistency suggests symlinking to the deployed path (`~/.config/blocky/blocky.yml`) instead. |
| 5 | **LOW** | `pacman -Sy` before `-S` | `pacman -Sy --noconfirm` followed by `pacman -S --noconfirm --needed ...` is a partial-upgrade pattern. Modern pacman warns about this and it can lead to dependency mismatches on a rolling distro. Prefer a single `pacman -S --noconfirm --needed --asdeps ...` or at least `pacman -Syu` if you truly need a full sync. |
| 6 | **LOW** | `ayugram-desktop` in PACMAN array | This package is not in the standard Arch/CachyOS official repos; it lives in the AUR. It will fail to resolve in `pacman -S` and the whole `require` step will abort. Move it to the `AUR` array or confirm the repo source. |
| 7 | **LOW** | Comment/code mismatch for chezmoi re-apply | The header comment says `chezmoi re-apply` (hyphenated), but the executed command is `chezmoi reapply` (no hyphen). The code is correct for chezmoi ≥ 2.x; just fix the comment. |
| 8 | **INFO** | `set -uo pipefail` — no `-e` | The script intentionally uses `run`/`require` wrappers for error handling, so `-e` is not strictly needed. However, any future edit that adds a bare command outside those wrappers will silently continue on failure. Consider adding `-e` and using `|| true` only where continuation is intentional. |
| 9 | **INFO** | `HDD_DEV="/dev/sda"` hardcoded | The `hdparm` call at the bottom targets `/dev/sda` directly, but the SATA drive is already referenced by UUID in `mount-media-d.service` (`ata-WDC_WD3000FYYZ-...`). If the kernel names the SATA drive `/dev/sdb` (because an NVMe is `sda`), the hdparm call silently skips. Better to derive the device from the mount unit or use the same by-id path. |
| 10 | **INFO** | `sudo` keepalive background process | `while true; do sudo -n true; sleep 60; kill -0 "$$" ... &` is backgrounded. If the script is killed with SIGKILL, the trap cannot run and the loop becomes a zombie keepalive. Harmless but untidy. Consider `trap cleanup EXIT INT TERM` (already has EXIT) and accept that SIGKILL cannot be caught. |
| 11 | **INFO** | `mount-media-d.service` ExecStartPost runs even if mount fails | The `ExecStartPost` hdparm call is not conditional. If the ntfs-3g mount fails, hdparm still runs against the block device. Wrap it in `ExecStartPost=/bin/sh -c 'if mountpoint -q /media/D; then hdparm ...; fi'` or use a separate oneshot that `Requires=` the mount. |

---

## 2. Dotfiles — Machine-Specific / Portability

| # | Severity | File | Issue |
|---|----------|------|-------|
| 12 | **MEDIUM** | `dot_config/environment.d/00-path.conf` | Contains a hardcoded `/home/reza/.local/bin:/home/reza/.npm-global/bin:/home/reza/.bun/bin:...`. If this dotfile is applied on another machine or user account, the PATH is wrong. Use chezmoi templating (`{{ .chezmoi.homeDir }}`) or remove the file since `dot_config/fish/config.fish` already sets PATH dynamically. |
| 13 | **MEDIUM** | `dot_config/lact/ui.yaml` | `selected_gpu: 1002:73BF-1EAE:6705-0000:0a:00.0` is hardcoded to a specific RDNA 2 GPU. If the GPU is replaced or the PCI slot changes, LACT will fail to select the GPU. Acceptable for a personal repo, but worth flagging. |
| 14 | **LOW** | `dot_config/lact/LACT-profile-OC.json` | Same concern — overclock profiles are inherently machine-specific. If you ever clone this repo to a different rig, the profile will apply to the wrong device or fail silently. |

---

## 3. Dotfiles — Missing / Inconsistencies

| # | Severity | File | Issue |
|---|----------|------|-------|
| 15 | **LOW** | `dot_config/foot/foot.ini` | `include=~/.config/foot/themes/noctalia` references a theme file that is not present in the source tree. |
| 16 | **LOW** | `dot_config/niri/cfg/` | All includes use relative paths (`./cfg/animation.kdl`, etc.). This is correct *only* because chezmoi deploys the entire `dot_config/niri/` tree preserving the directory layout. If a future maintainer moves `config.kdl` or the `cfg/` directory, the includes break silently. |
| 17 | **INFO** | Top-level source | No `chezmoi.toml` found. Defaults are fine, but you may want to add `[data]` or `[encryption]` sections if you use `private_` files or want to pin a specific chezmoi version behavior. |

---

## 4. Positive Observations

- `private_` prefix is used correctly for secrets (`private_dot_omp/`, `private_dot_local/`, `private_goofcord/`, `private_lutris/`). Chezmoi will encrypt/gitignore these automatically.
- `.chezmoiignore` correctly excludes `install.sh`, `README.md`, and `etc/` from chezmoi's apply logic, while the script handles system paths manually.
- Mount units use `by-id` paths instead of `/dev/sdX`, which is robust against kernel device reordering.
- `RemainAfterExit=yes` + `Type=oneshot` is the correct pattern for persistent mount units.
- `cachyos-gaming-meta` excludes via `--assume-installed` is a clean way to prune the meta-package without forking it.
- The `as_user` helper correctly preserves user context when the script is invoked via `sudo`.
- `run` / `require` / `cleanup` pattern is well-structured and logs non-fatal errors without aborting the whole run.

---

## Summary Checklist

```
[ ] Move ayugram-desktop from PACMAN to AUR (or confirm repo)
[ ] Add blocky to PACMAN or AUR array
[ ] Enable mount-media-c.service and mount-media-d.service for boot
[ ] Fix blocky symlink to point at deployed ~/.config/blocky/blocky.yml
[ ] Add or remove foot/themes/noctalia theme file
[ ] Template /home/reza paths in environment.d/00-path.conf
[ ] Consider single-step pacman -S without separate -Sy
[ ] Wrap hdparm in ExecStartPost with mountpoint check (optional hardening)
[ ] Replace /dev/sda with by-id path or derive from mount unit
```

No files were modified. Let me know if you want patches for any of these.
