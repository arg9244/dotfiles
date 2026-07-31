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

# Keep sudo alive when running as a regular user
sudo_keepalive_pid=""
if [[ $EUID -ne 0 ]]; then
    while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done &>/dev/null &
    sudo_keepalive_pid=$!
fi

# When invoked via sudo, remember the real user for user-context commands (chezmoi)
ORIGINAL_USER="${SUDO_USER:-$USER}"

ORIGINAL_HOME="$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)"
export PATH="$ORIGINAL_HOME/.local/bin:$PATH"
# 📦 PACKAGES — Edit these arrays to add/remove what gets installed
# ══════════════════════════════════════════════════════════════════════════════

PACMAN=(
    gnome-keyring xdg-desktop-portal-gnome komikku
    loupe baobab file-roller gnome-disk-utility lact
    ntfs-3g bottom lxsession goverlay vkd3d lutris
    kitty zed github-cli chezmoi ayugram-desktop niri
    mpv yt-dlp playerctl mpv-mpris amberol qbittorrent
)

AUR=(
    noctalia-git noctalia-greeter-git throne-bin
    mihomo-bin omp-bin ludusavi-bin goofcord-bin
    aria2-next-bin crunchycleaner-bin
)

# Dependencies to EXCLUDE when installing cachyos-gaming-meta
GAMING_EXCLUDE=( proton-cachyos-slr wine wine-cachyos-opt winetricks )

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

ERR_LOG="$(mktemp)"
errs=0

cleanup() { [[ -n "${ERR_LOG:-}" ]] && rm -f "$ERR_LOG"; [[ -n "${sudo_keepalive_pid:-}" ]] && kill "$sudo_keepalive_pid" 2>/dev/null; }
trap cleanup EXIT
run() {
    local desc="$1"; shift
    if "$@"; then ok "$desc"; else fail "$desc"; echo "$desc" >> "$ERR_LOG"; ((errs++)); fi
}

require() {
    local desc="$1"; shift
    if "$@"; then ok "$desc"; else fail "$desc"; echo "$desc (FATAL)" >> "$ERR_LOG"
        echo; warn "Fatal error — aborting"; cat "$ERR_LOG"; exit 1
    fi
}

check() { command -v "$1" &>/dev/null; }

# Run a command as the original user (handles sudo ./install.sh case)
as_user() {
    if [[ "$EUID" -eq 0 ]] && [[ "$ORIGINAL_USER" != "root" ]]; then
        sudo -u "$ORIGINAL_USER" -H "$@"
    else
        "$@"
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
ping -c1 -W2000 archlinux.org &>/dev/null || { fail "No internet"; exit 1; }
grep -qi "arch" /etc/os-release 2>/dev/null || warn "Not Arch/CachyOS?"
ok "Ready"

# ── 1. Pacman packages ──
head "1/6 — Pacman packages"
require "Update databases" sudo pacman -Sy --noconfirm
require "Install packages" sudo pacman -S --noconfirm --needed "${PACMAN[@]}"

# ── 2. AUR helper (paru) ──
head "2/6 — AUR helper (paru)"
if check paru; then
    ok "paru already installed"
else
    echo "  paru is needed for AUR packages."
    echo -n "  Install paru? [y/N] "
    read -r ans
    if [[ "$ans" =~ ^[Yy] ]]; then
        require "Install base-devel + git" sudo pacman -S --noconfirm --needed base-devel git
        d="$(mktemp -d)"
        git clone --depth=1 https://aur.archlinux.org/paru-bin.git "$d" &>/dev/null
        (cd "$d" && makepkg -si --noconfirm) &>/dev/null
        rm -rf "$d"
        ok "paru installed"
    else
        echo "  Install paru manually:"
        echo "    git clone https://aur.archlinux.org/paru.git"
        echo "    cd paru && makepkg -si"
        echo "  Then re-run this script."
        exit 1
    fi
fi

# ── 3. AUR packages ──
head "3/6 — AUR packages"
if [[ ${#AUR[@]} -gt 0 ]]; then
    require "Install AUR packages" paru -S --noconfirm --needed "${AUR[@]}"
else
    ok "No AUR packages to install"
fi

# ── 4. cachyos-gaming-meta ──
head "4/6 — cachyos-gaming-meta"
args=()
for dep in "${GAMING_EXCLUDE[@]}"; do args+=("--assume-installed=${dep}=99.0"); done
require "Install meta-package" sudo pacman -S --noconfirm "${args[@]}" cachyos-gaming-meta

# ── 5. chezmoi dotfiles ──
head "5/6 — Dotfiles"

# Init / apply user dotfiles (as the original user, even if running via sudo)
CHEZMOI_SOURCE="$ORIGINAL_HOME/.local/share/chezmoi"
if [[ -d "$CHEZMOI_SOURCE" ]]; then
    run "chezmoi re-apply" as_user bash -c "chezmoi reapply 2>&1 || chezmoi apply 2>&1"
else
    require "chezmoi init" as_user chezmoi init --apply "$DOTFILES_REPO"
fi

# Apply root-owned files (e.g. /etc/greetd/config.toml)
sudo chezmoi --source-path "$CHEZMOI_SOURCE" apply 2>&1 ||
    warn "System files not applied. Try: sudo chezmoi --source-path ~/.local/share/chezmoi apply"
# Persist user local bin directories in .bashrc
_bashrc="$ORIGINAL_HOME/.bashrc"
_path_line='export PATH="$HOME/.local/bin:$PATH"'
_marker="# path: user local bins"
if [[ -f "$_bashrc" ]] && ! grep -qF "$_marker" "$_bashrc"; then
    printf '\n%s\n%s\n' "$_marker" "$_path_line" >> "$_bashrc"
fi


# ── 6. Service management ──
head "6/6 — Service management"

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
# Ensure mount point directories exist before deploying mount services
run "Create mount point /media/C" sudo mkdir -p /media/C
run "Create mount point /media/D" sudo mkdir -p /media/D
# Deploy system mount services (managed by chezmoi in etc/systemd/system/)
for svc in mount-media-c.service mount-media-d.service; do
    CHEZMOI_SVC="$CHEZMOI_SOURCE/etc/systemd/system/$svc"
    if [[ -f "$CHEZMOI_SVC" ]]; then
        run "Deploy $svc" sudo cp "$CHEZMOI_SVC" /etc/systemd/system/
    else
        warn "$svc not found in chezmoi source"
    fi
done
run "Reload systemd" sudo systemctl daemon-reload
run "Restart mount services" sudo systemctl restart mount-media-c.service mount-media-d.service

# Deploy udev I/O scheduler rules
UDEV_SRC="$CHEZMOI_SOURCE/etc/udev/rules.d/60-ioschedulers.rules"
if [[ -f "$UDEV_SRC" ]]; then
    run "Deploy I/O scheduler rules" sudo cp "$UDEV_SRC" /etc/udev/rules.d/
    run "Reload udev rules" sudo udevadm control --reload-rules && sudo udevadm trigger
else
    warn "60-ioschedulers.rules not found in chezmoi source"
fi

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
