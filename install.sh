#!/usr/bin/env bash
set -uo pipefail
IFS=$'\n\t'

# ── Root access ──
# Script needs root for: pacman, systemctl, system dotfiles (/etc/greetd/, etc.)
# Runs as your user with sudo for privileged commands, or directly as root.
if [[ $EUID -ne 0 ]] && ! sudo -v; then
    cat << 'EOF'

  ╔══════════════════════════════════════════════════╗
  ║  This script needs root access.                  ║
  ║                                                  ║
  ║  It installs packages, enables system services,  ║
  ║  and applies dotfiles to system paths            ║
  ║  (e.g. /etc/greetd/).                            ║
  ║                                                  ║
  ║  Run it with:  sudo ./install.sh                 ║
  ╚══════════════════════════════════════════════════╝
EOF
    exit 1
fi

# Pre-allocate state for the EXIT trap (must exist before anything can fail)
sudo_keepalive_pid=""
ERR_LOG="$(mktemp)"
errs=0

cleanup() {
    [[ -n "${ERR_LOG:-}" ]] && rm -f "$ERR_LOG"
    [[ -n "${sudo_keepalive_pid:-}" ]] && kill "$sudo_keepalive_pid" 2>/dev/null
}
trap cleanup EXIT

# Keep sudo alive when running as a regular user
if [[ $EUID -ne 0 ]]; then
    while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done &>/dev/null &
    sudo_keepalive_pid=$!
fi

# When invoked via sudo, remember the real user for user-context commands (chezmoi)
ORIGINAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
ORIGINAL_HOME="$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)"

if [[ -z "$ORIGINAL_HOME" || ! -d "$ORIGINAL_HOME" ]]; then
    echo "✗ Cannot resolve home directory for user '$ORIGINAL_USER'" >&2
    exit 1
fi

export PATH="$ORIGINAL_HOME/.local/bin:$PATH"

# 📦 PACKAGES — Edit these arrays to add/remove what gets installed
# ══════════════════════════════════════════════════════════════════════════════

PACMAN=(
    niri noctalia noctalia-greeter lxsession gnome-keyring
    xdg-desktop-portal-gnome  loupe kitty bottom chezmoi yazi
    icoutils lact gvfs-mtp zed paru python-mutagen nwg-look
    mpv mpv-mpris playerctl yt-dlp amberol mangohud chromium
    github-cli icoextract proton-cachyos-native winetricks
    ayugram-desktop qbittorrent aria2 blocky adw-gtk-theme

    baobab file-roller gnome-disk-utility lutris uv nodejs neovim
    rclone bleachbit
)

AUR=(
    qt6ct-kde mihomo-bin throne-bin omp-bin moonbit
    nautilus-open-any-terminal rar mcomix-rs-bin
)

DOTFILES_REPO="https://github.com/arg9244/dotfiles"

# ══════════════════════════════════════════════════════════════════════════════
# ⚙️  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[0;34m' N='\033[0m'
info() { echo -e "${B}•${N} $*"; }
ok()   { echo -e "${G}✓${N} $*"; }
warn() { echo -e "${Y}⚠${N} $*"; }
fail() { echo -e "${R}✗${N} $*"; }
head() { echo; echo "━━━ $* ━━━"; }

run() {
    local desc="$1"; shift
    if "$@"; then
        ok "$desc"
    else
        fail "$desc"
        echo "$desc" >> "$ERR_LOG"
        ((++errs)) || true
    fi
}

require() {
    local desc="$1"; shift
    if "$@"; then
        ok "$desc"
    else
        fail "$desc"
        echo "$desc (FATAL)" >> "$ERR_LOG"
        echo; warn "Fatal error — aborting"; cat "$ERR_LOG"
        exit 1
    fi
}

check() { command -v "$1" &>/dev/null; }

# Run a command as the original user (handles sudo ./install.sh case)
# Sets XDG_RUNTIME_DIR + DBUS_SESSION_BUS_ADDRESS so systemctl --user / gsettings work
as_user() {
    local user_uid user_runtime
    user_uid="$(id -u "$ORIGINAL_USER" 2>/dev/null || echo 0)"
    user_runtime="/run/user/$user_uid"

    if [[ "$EUID" -eq 0 && "$ORIGINAL_USER" != "root" ]]; then
        sudo -u "$ORIGINAL_USER" -H \
            env \
                PATH="$ORIGINAL_HOME/.local/bin:$PATH" \
                XDG_RUNTIME_DIR="$user_runtime" \
                DBUS_SESSION_BUS_ADDRESS="unix:path=$user_runtime/bus" \
            "$@"
    else
        PATH="$ORIGINAL_HOME/.local/bin:$PATH" "$@"
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CachyOS Post-Install Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Pre-flight ──
head "Pre-flight"
getent hosts archlinux.org >/dev/null 2>&1 || { fail "No internet (DNS lookup failed)"; exit 1; }
grep -Eq '^ID=(arch|cachyos)' /etc/os-release 2>/dev/null || warn "Not Arch/CachyOS?"
ok "Ready"

# ── 1. Pacman packages ──
head "1/4 — Pacman packages"
require "Update & install packages" sudo pacman -Syu --noconfirm --needed "${PACMAN[@]}"

# ── 2. AUR packages ──
head "2/4 — AUR packages"
if [[ ${#AUR[@]} -gt 0 ]]; then
    require "Install AUR packages" as_user env PARU_PAGER=cat paru -S --noconfirm --needed "${AUR[@]}"
else
    ok "No AUR packages to install"
fi

# ── 3. chezmoi dotfiles ──
head "3/4 — Dotfiles"

# Init / apply user dotfiles (as the original user, even if running via sudo)
CHEZMOI_SOURCE="$ORIGINAL_HOME/.local/share/chezmoi"
if [[ -d "$CHEZMOI_SOURCE" ]]; then
    run "chezmoi reapply" as_user bash -c "chezmoi reapply 2>&1 || chezmoi apply 2>&1"
else
    require "chezmoi init" as_user chezmoi init --apply "$DOTFILES_REPO"
fi

# Symlink greetd config from user config to system location
run "Create /etc/greetd directory" sudo mkdir -p /etc/greetd
if [[ -f "$ORIGINAL_HOME/.config/greetd/config.toml" ]]; then
    run "Symlink greetd config" sudo ln -sf "$ORIGINAL_HOME/.config/greetd/config.toml" /etc/greetd/config.toml
else
    warn "$ORIGINAL_HOME/.config/greetd/config.toml not found (skipping symlink)"
fi

# Symlink blocky config into /etc/blocky/
run "Create /etc/blocky directory" sudo mkdir -p /etc/blocky
if [[ -f "$ORIGINAL_HOME/.config/blocky/blocky.yml" ]]; then
    run "Symlink blocky.yml" sudo ln -sf "$ORIGINAL_HOME/.config/blocky/blocky.yml" /etc/blocky/blocky.yml
else
    warn "$ORIGINAL_HOME/.config/blocky/blocky.yml not found (skipping symlink)"
fi

# Symlink game performance sysctl config into /etc/sysctl.d/
run "Create /etc/sysctl.d directory" sudo mkdir -p /etc/sysctl.d
if [[ -f "$ORIGINAL_HOME/.config/sysctl.d/99-game-performance.conf" ]]; then
    run "Symlink 99-game-performance.conf" sudo ln -sf "$ORIGINAL_HOME/.config/sysctl.d/99-game-performance.conf" /etc/sysctl.d/99-game-performance.conf
else
    warn "$ORIGINAL_HOME/.config/sysctl.d/99-game-performance.conf not found (skipping symlink)"
fi

# Persist user local bin directories in .bashrc (written as the user, not root)
_bashrc="$ORIGINAL_HOME/.bashrc"
_path_line='export PATH="$HOME/.local/bin:$PATH"'
_marker="# path: user local bins"
if [[ ! -f "$_bashrc" ]]; then
    as_user touch "$_bashrc" || warn "Cannot create $_bashrc"
fi
if [[ -f "$_bashrc" ]] && ! grep -qF "$_marker" "$_bashrc"; then
    as_user bash -c "printf '\n%s\n%s\n' '$_marker' '$_path_line' >> '$_bashrc'"
fi

# Configure Nautilus terminal setting for user
run "Set Nautilus terminal to Kitty" as_user gsettings set com.github.stunkymonkey.nautilus-open-any-terminal terminal 'kitty'
run "Set GTK theme to adw-gtk3" as_user gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3'

# ── 4. Service management ──
head "4/4 — Service management"

# Enable user-level services (managed by chezmoi in dot_config/systemd/user/)
# Ensure aria2 session file and config directory exist before enabling the service
run "Create aria2 config dir" as_user mkdir -p "$ORIGINAL_HOME/.config/aria2"
run "Touch aria2 session file" as_user touch "$ORIGINAL_HOME/.config/aria2/aria2.session"
run "Enable aria2" as_user systemctl --user enable --now aria2.service

# Enable greetd (system-level display manager)
run "Disable other DMs" bash -c '
    for dm in sddm gdm lightdm lxdm ly; do
        systemctl is-enabled "$dm" &>/dev/null && sudo systemctl disable "$dm"
    done
' 2>/dev/null || true
run "Enable greetd" sudo systemctl enable greetd

# Deploy udev I/O scheduler rules
UDEV_SRC="$CHEZMOI_SOURCE/etc/udev/rules.d/60-ioschedulers.rules"
if [[ -f "$UDEV_SRC" ]]; then
    run "Deploy I/O scheduler rules" sudo cp "$UDEV_SRC" /etc/udev/rules.d/
    run "Reload udev rules" bash -c "sudo udevadm control --reload-rules && sudo udevadm trigger"
else
    warn "60-ioschedulers.rules not found in chezmoi source"
fi
- # --------------------------------------------------------------------------
- # Deploy Bluetooth fix for counterfeit CSR adapter (0a12:0001)
- # --------------------------------------------------------------------------
- BT_SRC="$CHEZMOI_SOURCE/etc/bluetooth"
- if [[ -f "$BT_SRC/main.conf" && -f "$BT_SRC/input.conf" ]]; then
-     echo ":: Deploying Counterfeit CSR Bluetooth Fix..."
-     run "Deploy bluetooth main.conf"   sudo cp "$BT_SRC/main.conf" /etc/bluetooth/
-     run "Deploy bluetooth input.conf"  sudo cp "$BT_SRC/input.conf" /etc/bluetooth/
-     run "Deploy bluetooth modprobe"    sudo cp "$CHEZMOI_SOURCE/etc/modprobe.d/bluetooth.conf" /etc/modprobe.d/
-     run "Deploy fix script"            sudo cp "$CHEZMOI_SOURCE/usr/local/bin/fix-csr-bluetooth.sh" /usr/local/bin/
-     run "Set script permissions"       sudo chmod 755 /usr/local/bin/fix-csr-bluetooth.sh
-     run "Deploy CSR udev rule"         sudo cp "$CHEZMOI_SOURCE/etc/udev/rules.d/99-csr-bluetooth.rules" /etc/udev/rules.d/
-     run "Deploy systemd service"       sudo cp "$CHEZMOI_SOURCE/etc/systemd/system/csr-bluetooth-fix.service" /etc/systemd/system/
-     run "Reload systemd daemon"        sudo systemctl daemon-reload
-     run "Reload udev rules"            bash -c "sudo udevadm control --reload-rules && sudo udevadm trigger"
-     run "Restart bluetooth"            sudo systemctl restart bluetooth
-     run "Enable CSR fix service"       sudo systemctl enable --now csr-bluetooth-fix.service
- fi

# HDD device variable – adjust if your drive is not /dev/sda
HDD_DEV="/dev/sda"
if [[ -b "$HDD_DEV" ]]; then
    run "Set APM + spin-down" sudo hdparm -B 255 -S 0 -W 0 "$HDD_DEV"
else
    warn "$HDD_DEV not present (skipping HDD power management)"
fi

echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ "$errs" -eq 0 ]]; then
    ok "All steps completed"
else
    warn "$errs non-fatal error(s)"
    cat "$ERR_LOG"
fi
echo "  Reboot or: sudo systemctl start greetd"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
