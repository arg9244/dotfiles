#!/usr/bin/env bash
# ==============================================================================
# USER CONFIGURATION (Edit your settings here)
# ==============================================================================
# Game Information
export GAME_NAME="Brown Dust II"
export GAME_EXE="/media/C/Games/Brown Dust 2/C/Browndust2/Browndust2/BrownDust2_10000002/BrownDust II.exe"
export WINEPREFIX=""
export GAMEID=""
export STORE=""
# Proton & Environment Settings
export PROTONPATH="/usr/share/steam/compatibilitytools.d/proton-cachyos-native"
# Controls Proton startup mode: "run" = normal, "waitforexitandrun" = verbose logs
export PROTON_VERB="run"
# Bypasses Anti-Cheat / Linux restrictions on games
export SteamOS=1
# Graphics & Performance
export DXVK_FRAME_RATE="165"
export PROTON_USE_OPTISCALER="0"
export PROTON_FSR4_INDICATOR="0"
export PROTON_FSR4_UPGRADE="0"
export PROTON_XESS_UPGRADE="0"
export AMD_VULKAN_ICD="RADV"
export MESA_SHADER_CACHE_MAX_SIZE="12G"
export PROTON_LOCAL_SHADER_CACHE="1"
export RADV_TEX_ANISO="16"
export ENABLE_LAYER_MESA_ANTI_LAG="1"
export PROTON_USE_NTSYNC="1"
export WINE_DISABLE_VULKAN_OPWR="1"
export PROTON_ENABLE_WAYLAND="1"
export PROTON_NO_WM_DECORATION="1"
export XDG_CURRENT_DESKTOP="steamcompmgr"
# Input, Overlays & Network
export PROTON_NO_STEAMINPUT="1"
export PROTON_PREFER_SDL="1"
export DXVK_HUD="0"
export MANGOHUD="1"
export all_proxy=""
# ==============================================================================
# SCRIPT LOGIC (Do not edit below unless modifying functionality)
# ==============================================================================
# ------------------------------------------------------------------------------
# 1. Dynamic Name & WINEPREFIX Resolution
# ------------------------------------------------------------------------------
if [ -n "$GAME_NAME" ]; then
    DISPLAY_NAME="$GAME_NAME"
elif [ -n "$GAME_EXE" ]; then
    DISPLAY_NAME="$(basename "$GAME_EXE" .exe)"
else
    DISPLAY_NAME="default_game"
fi
# Format name for Wine prefix directory inside ~/Games/ (lowercase, spaces to hyphens)
PREFIX_DIR_NAME="${DISPLAY_NAME,,}"
PREFIX_DIR_NAME="${PREFIX_DIR_NAME// /-}"
PREFIX_DIR_NAME="${PREFIX_DIR_NAME//[^a-z0-9_-]/}"
# If WINEPREFIX is empty, set default directory in ~/Games/
if [ -z "$WINEPREFIX" ]; then
    export WINEPREFIX="$HOME/Games/$PREFIX_DIR_NAME"
    mkdir -p "$WINEPREFIX"
fi
# ------------------------------------------------------------------------------
# 2. Application Shortcut & Icon Extraction (First-Run Check)
# ------------------------------------------------------------------------------
if [ -n "$GAME_EXE" ]; then
    SCRIPT_PATH="$(readlink -f "$0")"
    SAFE_NAME="${PREFIX_DIR_NAME}"
    DESKTOP_FILENAME="${SAFE_NAME}.desktop"

    APPS_DIR="$HOME/.local/share/applications"
    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
    DESKTOP_FILE_APP="$APPS_DIR/$DESKTOP_FILENAME"

    # Run setup if application shortcut doesn't exist yet
    if [ ! -f "$DESKTOP_FILE_APP" ]; then
        echo "[INFO] First run detected. Creating application menu shortcut for '$DISPLAY_NAME'..."
        mkdir -p "$APPS_DIR" "$ICON_DIR"

        ICON_PATH=""
        FINAL_ICON="$ICON_DIR/${SAFE_NAME}.png"

        # Extract icon directly from .exe using wrestool / icotool
        if command -v wrestool >/dev/null 2>&1 && command -v icotool >/dev/null 2>&1 && [ -f "$GAME_EXE" ]; then
            echo "[INFO] Extracting icon from $GAME_EXE..."
            TMP_DIR=$(mktemp -d)

            # Extract group icon resources (-t 14)
            wrestool -x -t 14 "$GAME_EXE" -o "$TMP_DIR" 2>/dev/null

            shopt -s nullglob
            ICO_FILES=("$TMP_DIR"/*.ico)

            # Fallback: if no group icons (-t 14) found, extract all icon types
            if [ ${#ICO_FILES[@]} -eq 0 ]; then
                wrestool -x "$GAME_EXE" -o "$TMP_DIR" 2>/dev/null
                ICO_FILES=("$TMP_DIR"/*.ico)
            fi

            if [ ${#ICO_FILES[@]} -gt 0 ]; then
                icotool -x -o "$TMP_DIR" "${ICO_FILES[@]}" 2>/dev/null
                PNG_FILES=("$TMP_DIR"/*.png)
                if [ ${#PNG_FILES[@]} -gt 0 ]; then
                    # Pick the largest extracted PNG (highest resolution)
                    LARGEST_PNG=$(ls -S "$TMP_DIR"/*.png 2>/dev/null | head -n 1)
                    if [ -n "$LARGEST_PNG" ] && [ -f "$LARGEST_PNG" ]; then
                        mv "$LARGEST_PNG" "$FINAL_ICON"
                        ICON_PATH="$FINAL_ICON"
                        echo "[INFO] Successfully extracted game icon to $FINAL_ICON"
                    fi
                fi
            fi
            shopt -u nullglob
            rm -rf "$TMP_DIR"
        fi

        # Refresh system icon cache so application menu registers the new icon
        touch "$HOME/.local/share/icons/hicolor" 2>/dev/null
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

        # Create .desktop File in ~/.local/share/applications/
        cat <<EOF > "$DESKTOP_FILE_APP"
[Desktop Entry]
Version=1.0
Type=Application
Name=${DISPLAY_NAME}
Comment=Launch ${DISPLAY_NAME} via UMU
Exec="${SCRIPT_PATH}" %u
Icon=${ICON_PATH}
Terminal=false
Categories=Game;
StartupNotify=true
EOF

        chmod +x "$DESKTOP_FILE_APP"

        echo "[SUCCESS] Created application menu shortcut:"
        echo "  - $DESKTOP_FILE_APP"
    fi
fi

# ------------------------------------------------------------------------------
# 3. Game Launch Execution
# ------------------------------------------------------------------------------
if [ -z "$GAME_EXE" ]; then
    echo "[ERROR] GAME_EXE is not set! Please edit the script to point to your game .exe."
    exit 1
fi

GAME_DIR="$(dirname "$GAME_EXE")"
if [ -d "$GAME_DIR" ]; then
    cd "$GAME_DIR" || exit 1
fi

if command -v game-performance >/dev/null 2>&1; then
    exec game-performance umu-run "$GAME_EXE" "$@"
else
    exec umu-run "$GAME_EXE" "$@"
fi
