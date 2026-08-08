#!/usr/bin/env bash
# ==============================================================================
# Core Setup
# ==============================================================================
export WINEPREFIX=""
export PROTONPATH="/usr/share/steam/compatibilitytools.d/proton-cachyos-native"
export GAME_EXE=""
# Controls Proton startup mode: "run" = normal, "waitforexitandrun" = verbose logs
export PROTON_VERB="run"
# https://umu.openwinecomponents.org
export GAMEID=""
export STORE=""
# ==============================================================================
# Graphics & Performance
# ==============================================================================
export DXVK_FRAME_RATE="165"
export PROTON_USE_OPTISCALER="1"
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
# ==============================================================================
# Input, Overlays & Network
# ==============================================================================
export PROTON_NO_STEAMINPUT="1"
export PROTON_PREFER_SDL="1"
export DXVK_HUD="0"
export MANGOHUD="1"
export all_proxy=""
# ==============================================================================
# Launch
# ==============================================================================
exec game-performance umu-run "$GAME_EXE" "$@"
