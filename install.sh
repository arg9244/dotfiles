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
if [[ $EUID -ne 0 ]]; then
    while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done &>/dev/null &
fi

# When invoked via sudo, remember the real user for user-context commands (chezmoi)
ORIGINAL_USER="${SUDO_USER:-$USER}"
ORIGINAL_HOME="$(eval echo ~$ORIGINAL_USER)"

# ══════════════════════════════════════════════════════════════════════════════
# 📦 PACKAGES — Edit these arrays to add/remove what gets installed
# ══════════════════════════════════════════════════════════════════════════════

PACMAN=(
    chromium kitty ntfs-3g nautilus file-roller mpv loupe timeshift
    git btop yazi python nodejs yt-dlp zed amberol ayugram-desktop
    chezmoi playerctl vkd3d lutris lxsession lact goverlay baobab
    github-cli mpv-mpris xdg-desktop-portal-gnome aria2-next-bin
)

AUR=(
    noctalia-git noctalia-greeter-git throne-bin mihomo-bin omp-bin ludusavi-bin
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
cleanup() { [[ -n "${ERR_LOG:-}" ]] && rm -f "$ERR_LOG"; kill %1 2>/dev/null; }
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
ping -c1 -W2 archlinux.org &>/dev/null || { fail "No internet"; exit 1; }
grep -qi "arch" /etc/os-release 2>/dev/null || warn "Not Arch/CachyOS?"
ok "Ready"

# ── 1. Pacman packages ──
head "1/5 — Pacman packages"
require "Update databases" sudo pacman -Sy --noconfirm
require "Install packages" sudo pacman -S --noconfirm --needed "${PACMAN[@]}"

# ── 2. AUR helper (paru) ──
head "2/5 — AUR helper (paru)"
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
head "3/5 — AUR packages"
if [[ ${#AUR[@]} -gt 0 ]]; then
    require "Install AUR packages" paru -S --noconfirm --needed "${AUR[@]}"
else
    ok "No AUR packages to install"
fi

# ── 4. cachyos-gaming-meta ──
head "4/5 — cachyos-gaming-meta"
args=()
for dep in "${GAMING_EXCLUDE[@]}"; do args+=("--assume-installed=${dep}=99.0"); done
require "Install meta-package" sudo pacman -S --noconfirm "${args[@]}" cachyos-gaming-meta

# ── 5. chezmoi dotfiles + services ──
head "5/5 — Dotfiles & services"

# Init / apply user dotfiles (as the original user, even if running via sudo)
CHEZMOI_SOURCE="$ORIGINAL_HOME/.local/share/chezmoi"
if [[ -d "$CHEZMOI_SOURCE" ]]; then
    run "chezmoi re-apply" as_user bash -c "chezmoi reapply 2>/dev/null || chezmoi apply"
else
    require "chezmoi init" as_user chezmoi init --apply "$DOTFILES_REPO"
fi

# Apply root-owned files (e.g. /etc/greetd/config.toml)
sudo chezmoi --source-path "$CHEZMOI_SOURCE" apply 2>/dev/null ||
    warn "System files not applied. Try: sudo chezmoi --source-path ~/.local/share/chezmoi apply"

# Enable greetd
run "Disable other DMs" bash -c '
    for dm in sddm gdm lightdm lxdm ly; do
        systemctl is-enabled "$dm" &>/dev/null && sudo systemctl disable "$dm"
    done
' 2>/dev/null || true
require "Enable greetd" sudo systemctl enable greetd

# Optional user services
command -v powerprofilesctl &>/dev/null &&
    ! systemctl is-enabled power-profiles-daemon &>/dev/null 2>&1 &&
    run "power-profiles-daemon" sudo systemctl enable power-profiles-daemon
command -v psd &>/dev/null &&
    ! systemctl --user is-enabled psd &>/dev/null 2>&1 &&
    run "psd (profile-sync-daemon)" systemctl --user enable psd

# Portal backends for niri (Wayland compositor)
# xdg-desktop-portal-wlr is incompatible with niri (not wlroots-based).
# Mask it so D-Bus never auto-activates it, and restart the portal to pick up gnome.
run "Mask incompatible portal backend (wlr)" systemctl --user mask xdg-desktop-portal-wlr 2>/dev/null || true
run "Restart portal to load gnome backend" systemctl --user restart xdg-desktop-portal 2>/dev/null || true

echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ "$errs" -eq 0 ]]; then
    ok "All steps completed"
else
    warn "$errs non-fatal error(s)"
    cat "$ERR_LOG"
fi
echo "  Reboot or: sudo systemctl start greetd"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
