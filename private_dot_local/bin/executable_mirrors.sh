#!/usr/bin/env bash
#
# arch-mirror-manager.sh
# Enterprise-grade Arch Linux mirror optimizer, security hardener,
# and self-updating rankmirrors automation suite.
#

set -uo pipefail

# --------------------------------------------------------------------------- #
# Paths & Configuration Defaults
# --------------------------------------------------------------------------- #
PACMAN_MIRRORLIST="/etc/pacman.d/mirrorlist"
PACMAN_CONF="/etc/pacman.conf"
BACKUP_DIR="/var/backups/arch-mirrors"
UPSTREAM_URL="https://archlinux.org/mirrorlist/all/"

DEFAULT_TOP_N=10
DEFAULT_TIMEOUT=8
MAX_FRESHNESS_HOURS=12          # Reject mirrors older than N hours

# Terminal Colors
C_RESET=$'\033[0m'
C_BOLD=$'\033[1m'
C_RED=$'\033[0;31m'
C_GREEN=$'\033[0;32m'
C_YELLOW=$'\033[0;33m'
C_BLUE=$'\033[0;34m'
C_MAGENTA=$'\033[0;35m'
C_CYAN=$'\033[0;36m'
C_GRAY=$'\033[0;90m'

# Temporary file tracking & cleanup
TEMP_FILES=()
cleanup() {
  local f
  for f in "${TEMP_FILES[@]:-}"; do
    [[ -f "$f" ]] && rm -f "$f" 2>/dev/null || true
  done
}
trap cleanup EXIT

# --------------------------------------------------------------------------- #
# Logging & Helper Utilities
# --------------------------------------------------------------------------- #
log_info()    { printf "%s[+]%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
log_warn()    { printf "%s[!]%s %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
log_err()     { printf "%s[-]%s %s\n" "$C_RED" "$C_RESET" "$*" >&2; }
log_sec()     { printf "%s[SEC]%s %s\n" "$C_MAGENTA$C_BOLD" "$C_RESET" "$*"; }
log_section() { printf "\n%s=== %s ===%s\n" "$C_CYAN$C_BOLD" "$*" "$C_RESET"; }

is_root() { [[ ${EUID} -eq 0 ]]; }

check_dependencies() {
  local missing=()
  for cmd in curl awk sed date grep mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done

  if ! command -v rankmirrors >/dev/null 2>&1; then
    missing+=("rankmirrors (Install with: sudo pacman -S pacman-contrib)")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_err "Missing essential dependencies:"
    for m in "${missing[@]}"; do
      printf "  - %s\n" "$m"
    done
    exit 1
  fi
}

# --------------------------------------------------------------------------- #
# Security, Crypto & Freshness Verification
# --------------------------------------------------------------------------- #
check_mirror_freshness() {
  local base_url="$1"
  local clean_url="${base_url%%/\$repo*}"
  clean_url="${clean_url%/}"
  local update_url="${clean_url}/lastupdate"

  local body
  body=$(curl -fsSL --max-time "$DEFAULT_TIMEOUT" "$update_url" 2>/dev/null || true)
  body="${body//$'\r'/}"
  body="${body%$'\n'}"
  [[ -z "$body" ]] && { echo "-1"; return 0; }

  local last_unix now_unix age_hours
  if [[ "$body" =~ ^[0-9]+$ ]]; then
    last_unix="$body"
  else
    last_unix=$(date -u -d "$body" +%s 2>/dev/null || echo "0")
  fi
  [[ "$last_unix" -eq 0 ]] && { echo "-1"; return 0; }

  now_unix=$(date -u +%s)
  age_hours=$(( (now_unix - last_unix) / 3600 ))
  (( age_hours < 0 )) && age_hours=0
  echo "$age_hours"
}

audit_and_harden_crypto() {
  log_section "System Security & Cryptographic Audit"

  if [[ ! -f "$PACMAN_CONF" ]]; then
    log_err "Configuration file ${PACMAN_CONF} not found."
    return 1
  fi

  local siglevel_status="OK"
  local keyring_held="NO"

  local sig_line
  sig_line=$(grep -E '^[[:space:]]*SigLevel[[:space:]]*=' "$PACMAN_CONF" | head -n1 || true)
  if [[ "$sig_line" =~ Never|TrustAll ]]; then
    siglevel_status="${C_RED}DANGEROUS (${sig_line})${C_RESET}"
  elif [[ -z "$sig_line" ]]; then
    siglevel_status="${C_YELLOW}DEFAULT (Unset in [options])${C_RESET}"
  else
    siglevel_status="${C_GREEN}SECURE (${sig_line})${C_RESET}"
  fi

  if grep -E '^[[:space:]]*IgnorePkg[[:space:]]*=.*archlinux-keyring' "$PACMAN_CONF" >/dev/null 2>&1; then
    keyring_held="${C_YELLOW}YES (archlinux-keyring locked)${C_RESET}"
  fi

  printf "  %sSigLevel Policy:%s     %b\n" "$C_BOLD" "$C_RESET" "$siglevel_status"
  printf "  %sKeyring Pinning:%s     %b\n" "$C_BOLD" "$C_RESET" "$keyring_held"
  printf "\n"

  printf "Security Actions:\n"
  printf "  %s1)%s Enforce 'SigLevel = Required DatabaseOptional' (Recommended)\n" "$C_CYAN" "$C_RESET"
  printf "  %s2)%s Hold archlinux-keyring (Prevent key tampering on untrusted mirrors)\n" "$C_CYAN" "$C_RESET"
  printf "  %s3)%s Unhold archlinux-keyring (Allow upstream key updates)\n" "$C_CYAN" "$C_RESET"
  printf "  %sq)%s Return to main menu\n\n" "$C_CYAN" "$C_RESET"

  printf "Choice > "
  read -r sec_opt

  case "$sec_opt" in
    1)
      create_backup
      local tmp; tmp=$(mktemp); TEMP_FILES+=("$tmp")
      awk '
        BEGIN { in_opt=0; set_sigs=0 }
        /^SigLevel[[:space:]]*=/ { if(in_opt){ print "SigLevel = Required DatabaseOptional"; set_sigs=1; next } }
        /^\[options\]/           { print; in_opt=1; if(!set_sigs){ print "SigLevel = Required DatabaseOptional"; set_sigs=1 }; next }
        /^\[.*\]/                { in_opt=0; print; next }
        { print }
      ' "$PACMAN_CONF" > "$tmp"
      sudo cp "$tmp" "$PACMAN_CONF"
      log_sec "SigLevel successfully hardened in $PACMAN_CONF!"
      ;;
    2)
      create_backup
      local tmp; tmp=$(mktemp); TEMP_FILES+=("$tmp")
      awk '
        BEGIN { in_opt=0; set_ign=0 }
        /^IgnorePkg[[:space:]]*=.*archlinux-keyring/ { set_ign=1 }
        /^\[options\]/ { print; in_opt=1; if(!set_ign){ print "IgnorePkg = archlinux-keyring"; set_ign=1 }; next }
        /^\[.*\]/      { in_opt=0; print; next }
        { print }
      ' "$PACMAN_CONF" > "$tmp"
      sudo cp "$tmp" "$PACMAN_CONF"
      log_sec "archlinux-keyring is now locked in $PACMAN_CONF."
      ;;
    3)
      create_backup
      local tmp; tmp=$(mktemp); TEMP_FILES+=("$tmp")
      sed '/^[[:space:]]*IgnorePkg[[:space:]]*=.*archlinux-keyring/d' "$PACMAN_CONF" > "$tmp"
      sudo cp "$tmp" "$PACMAN_CONF"
      log_sec "archlinux-keyring unlocked. Standard updates enabled."
      ;;
    *) return 0 ;;
  esac
}

# --------------------------------------------------------------------------- #
# Embedded Mirror Database Handler & Self-Updater
# --------------------------------------------------------------------------- #
extract_embedded_mirrors() {
  local script_path; script_path=$(realpath "$0")
  awk '
    /^# === BEGIN EMBEDDED MIRRORLIST DATA ===/ { in_data=1; next }
    /^# === END EMBEDDED MIRRORLIST DATA ===/   { in_data=0 }
    in_data { print }
  ' "$script_path"
}

get_database_stats() {
  local script_path; script_path=$(realpath "$0")
  local total_servers countries last_update

  last_update=$(awk '/^# Last Updated:/ { $1=""; $2=""; print $0 }' "$script_path" | head -n1 | sed 's/^[[:space:]]*//')
  [[ -z "$last_update" ]] && last_update="Initial bundle"

  total_servers=$(extract_embedded_mirrors | grep -c '^[[:space:]]*#\?Server[[:space:]]*=' || echo 0)
  countries=$(extract_embedded_mirrors | grep -c '^## [^#]' || echo 0)

  printf "%sTotal Mirrors:%s %d | %sRegions:%s %d | %sLast Sync:%s %s\n" \
    "$C_BOLD" "$C_RESET" "$total_servers" "$C_BOLD" "$C_RESET" "$countries" "$C_BOLD" "$C_RESET" "$last_update"
}

self_update_mirrors() {
  log_section "Updating Embedded Mirror Database"
  local script_path; script_path=$(realpath "$0")

  local tmp_dl tmp_script
  tmp_dl=$(mktemp); TEMP_FILES+=("$tmp_dl")
  tmp_script=$(mktemp); TEMP_FILES+=("$tmp_script")

  log_info "Fetching latest global mirrorlist from ${UPSTREAM_URL} ..."
  if ! curl -fsSL --max-time 20 "$UPSTREAM_URL" -o "$tmp_dl"; then
    log_err "Network error: Failed to download upstream mirrorlist."
    return 1
  fi

  local count
  count=$(grep -c "Server" "$tmp_dl" || echo 0)
  if [[ "$count" -lt 50 ]]; then
    log_err "Received malformed payload ($count mirrors found). Aborting."
    return 1
  fi

  # Append custom unregistered intranet mirrors so they are never lost on self-update
  {
    echo ""
    echo "## Iran (Intranet Fallbacks & Community)"
    echo "#Server = https://mirror.0-1.ir/archlinux/\$repo/os/\$arch"
    echo "#Server = https://mirror.0-1.cloud/archlinux/\$repo/os/\$arch"
    echo "#Server = https://linux-mirror.liara.ir/archlinux/\$repo/os/\$arch"
    echo "#Server = https://mirror.famaserver.com/archlinux/\$repo/os/\$arch"
  } >> "$tmp_dl"

  local sync_time; sync_time=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

  awk -v data_file="$tmp_dl" -v sync_time="$sync_time" '
    BEGIN { in_data=0 }
    /^# === BEGIN EMBEDDED MIRRORLIST DATA ===/ {
      print "# === BEGIN EMBEDDED MIRRORLIST DATA ===";
      print "# Last Updated: " sync_time;
      while ((getline line < data_file) > 0) {
        print line;
      }
      close(data_file);
      in_data=1;
      next;
    }
    /^# === END EMBEDDED MIRRORLIST DATA ===/ { in_data=0 }
    !in_data { print }
  ' "$script_path" > "$tmp_script"

  if ! bash -n "$tmp_script"; then
    log_err "Sanity check failed: Syntax error generated. Aborting self-update."
    return 1
  fi

  chmod --reference="$script_path" "$tmp_script" 2>/dev/null || chmod +x "$tmp_script"

  if [[ -w "$script_path" ]]; then
    mv "$tmp_script" "$script_path"
  else
    log_warn "Elevated privileges required to write to ${script_path}"
    sudo mv "$tmp_script" "$script_path"
  fi

  log_info "Self-update successful! Reloading process..."
  sleep 1
  exec "$script_path" "$@"
}

# --------------------------------------------------------------------------- #
# Filtering & Country Utilities
# --------------------------------------------------------------------------- #
filter_mirrors() {
  local target_country="$1"  # "ALL", "IRAN_ALL", or Country Name
  local proto="$2"           # "https", "http", or "all"

  extract_embedded_mirrors | awk -v tgt="$target_country" -v p_mode="$proto" '
    BEGIN { in_country = (tgt == "ALL" ? 1 : 0) }

    /^## / {
      c_name = substr($0, 4);
      if (tgt == "ALL") {
        in_country = 1;
      } else if (tgt == "IRAN_ALL") {
        in_country = (tolower(c_name) ~ /iran/) ? 1 : 0;
      } else {
        in_country = (tolower(c_name) == tolower(tgt)) ? 1 : 0;
      }
      next;
    }

    in_country && /^[[:space:]]*#?[[:space:]]*Server[[:space:]]*=/ {
      line = $0;
      sub(/^[[:space:]]*#?[[:space:]]*Server[[:space:]]*=[[:space:]]*/, "", line);
      url = line;

      if (p_mode == "https" && url !~ /^https:\/\//) next;
      if (p_mode == "http" && url !~ /^http:\/\//) next;

      print "Server = " url;
    }
  '
}

list_available_countries() {
  extract_embedded_mirrors | awk '/^## [^#]/ { print substr($0, 4) }' | sort -u
}

# --------------------------------------------------------------------------- #
# Backup & Restore Operations
# --------------------------------------------------------------------------- #
create_backup() {
  [[ ! -f "$PACMAN_MIRRORLIST" ]] && return 0
  local ts; ts=$(date -u +%Y%m%d_%H%M%S)
  sudo mkdir -p "$BACKUP_DIR"
  sudo cp -a "$PACMAN_MIRRORLIST" "${BACKUP_DIR}/mirrorlist.${ts}.bak"
  [[ -f "$PACMAN_CONF" ]] && sudo cp -a "$PACMAN_CONF" "${BACKUP_DIR}/pacman.conf.${ts}.bak"
  log_info "Backup saved to ${BACKUP_DIR}/"
}

restore_backup_menu() {
  log_section "Restore Previous Mirrorlist"
  if [[ ! -d "$BACKUP_DIR" ]]; then
    log_warn "No backups found at ${BACKUP_DIR}"
    return 0
  fi

  local backups=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && backups+=("$line")
  done < <(ls -t "${BACKUP_DIR}"/mirrorlist.*.bak 2>/dev/null || true)

  if [[ ${#backups[@]} -eq 0 ]]; then
    log_warn "No mirrorlist backups available."
    return 0
  fi

  printf "Available backups:\n\n"
  local i=1
  for b in "${backups[@]}"; do
    printf "  %s%2d)%s %s\n" "$C_CYAN" "$i" "$C_RESET" "$(basename "$b")"
    ((i++))
  done
  printf "  %sq)%s Cancel\n\n" "$C_CYAN" "$C_RESET"

  printf "Choice > "
  read -r b_choice
  [[ "$b_choice" =~ ^[qQ]$ ]] && return 0

  if [[ "$b_choice" =~ ^[0-9]+$ ]] && (( b_choice >= 1 && b_choice <= ${#backups[@]} )); then
    local selected="${backups[$((b_choice-1))]}"
    log_info "Restoring: $selected -> $PACMAN_MIRRORLIST"
    sudo cp -a "$selected" "$PACMAN_MIRRORLIST"
    log_info "Restore successful."
  else
    log_err "Invalid selection."
  fi
}

# --------------------------------------------------------------------------- #
# Benchmarking Engine (rankmirrors Only)
# --------------------------------------------------------------------------- #
run_benchmark() {
  local country="$1"
  local proto="$2"
  local top_n="$3"
  local dry_run="${4:-false}"
  local enforce_freshness="${5:-true}"

  log_section "Running Mirror Benchmark & Freshness Gate"
  log_info "Engine: ${C_BOLD}rankmirrors${C_RESET} | Target: ${C_BOLD}${country}${C_RESET} | Proto: ${C_BOLD}${proto}${C_RESET} | Top: ${C_BOLD}${top_n}${C_RESET}"

  local raw_input
  raw_input=$(mktemp); TEMP_FILES+=("$raw_input")
  filter_mirrors "$country" "$proto" > "$raw_input"

  local count; count=$(grep -c "^Server" "$raw_input" || echo 0)
  if [[ "$count" -eq 0 ]]; then
    log_err "No candidate mirrors found matching criteria."
    return 1
  fi

  log_info "Extracted $count candidate mirrors. Checking freshness (<= ${MAX_FRESHNESS_HOURS}h)..."

  local verified_input
  verified_input=$(mktemp); TEMP_FILES+=("$verified_input")

  if [[ "$enforce_freshness" == "true" ]]; then
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      local s_url="${line#*Server = }"
      local age
      age=$(check_mirror_freshness "$s_url")
      if [[ "$age" -ge 0 && "$age" -le "$MAX_FRESHNESS_HOURS" ]]; then
        printf "%s\n" "$line" >> "$verified_input"
      elif [[ "$age" -gt "$MAX_FRESHNESS_HOURS" ]]; then
        log_warn "Filtered stale mirror (${age}h old): $s_url"
      else
        log_warn "Filtered unreachable mirror: $s_url"
      fi
    done < "$raw_input"
  else
    cp "$raw_input" "$verified_input"
  fi

  local v_count; v_count=$(grep -c "^Server" "$verified_input" || echo 0)
  if [[ "$v_count" -eq 0 ]]; then
    log_warn "Zero mirrors passed freshness gate. Testing all candidates anyway..."
    cp "$raw_input" "$verified_input"
  else
    log_info "$v_count mirrors verified fresh."
  fi

  local ranked_output
  ranked_output=$(mktemp); TEMP_FILES+=("$ranked_output")

  log_info "Testing mirror latency with rankmirrors (timeout: ${DEFAULT_TIMEOUT}s)..."
  if ! rankmirrors -n "$top_n" -m "$DEFAULT_TIMEOUT" "$verified_input" > "$ranked_output"; then
    log_err "rankmirrors failed to benchmark the servers."
    return 1
  fi

  local passed; passed=$(grep -c '^[[:space:]]*Server' "$ranked_output" || echo 0)
  if [[ "$passed" -eq 0 ]]; then
    log_err "No responsive mirrors found during testing."
    return 1
  fi

  printf "\n%s=== Benchmark Results (%d Ranked Mirrors) ===%s\n" "$C_GREEN$C_BOLD" "$passed" "$C_RESET"
  cat "$ranked_output"
  printf "%s================================================%s\n\n" "$C_GREEN" "$C_RESET"

  if [[ "$dry_run" == "true" ]]; then
    log_info "Dry-run complete. System mirrorlist was NOT modified."
    return 0
  fi

  # Explicit user prompt (NO automatic saving)
  printf "%sApply and save these mirrors to %s?%s [y/N] > " "$C_BOLD" "$PACMAN_MIRRORLIST" "$C_RESET"
  read -r confirm
  if [[ "$confirm" =~ ^[yY]([eE][sS])?$ ]]; then
    create_backup
    log_info "Writing to $PACMAN_MIRRORLIST..."
    {
      echo "## Generated by arch-mirror-manager.sh on $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
      echo "## Engine: rankmirrors | Target: ${country} | Freshness: <= ${MAX_FRESHNESS_HOURS}h"
      echo ""
      cat "$ranked_output"
    } | sudo tee "$PACMAN_MIRRORLIST" >/dev/null
    log_info "Mirrorlist updated successfully!"
  else
    log_warn "Cancelled. No changes written to mirrorlist."
  fi
}

# --------------------------------------------------------------------------- #
# Menu Wizards
# --------------------------------------------------------------------------- #
view_active_mirrorlist_with_health() {
  log_section "Current Active Mirrorlist Health Probe"
  if [[ ! -f "$PACMAN_MIRRORLIST" ]]; then
    log_err "${PACMAN_MIRRORLIST} does not exist."
    return 1
  fi

  printf "  %-3s %-60s %s\n" "#" "MIRROR URL" "STATUS / FRESHNESS"
  printf "  %-3s %-60s %s\n" "---" "------------------------------------------------------------" "------------------"

  local i=1
  while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*Server[[:space:]]*=[[:space:]]*(https?://[^ ]+) ]]; then
      local url="${BASH_REMATCH[1]}"
      local age; age=$(check_mirror_freshness "$url")
      local age_str
      if [[ "$age" -ge 0 ]]; then
        age_str="${C_GREEN}${age}h old (Synced)${C_RESET}"
      else
        age_str="${C_RED}Unreachable / No timestamp${C_RESET}"
      fi
      printf "  %2d) %-60s %b\n" "$i" "$url" "$age_str"
      ((i++))
    fi
  done < "$PACMAN_MIRRORLIST"
  printf "\n"
}

country_benchmark_wizard() {
  local is_dry_run="$1"
  log_section "Country-Specific Mirror Selection"

  local countries=()
  while IFS= read -r c; do
    [[ -n "$c" ]] && countries+=("$c")
  done < <(list_available_countries)

  local i=1
  for c in "${countries[@]}"; do
    printf "%2d) %-25s " "$i" "$c"
    (( i % 3 == 0 )) && printf "\n"
    ((i++))
  done
  printf "\n\n"

  printf "Enter country number or name > "
  read -r c_choice

  local chosen_country="ALL"
  if [[ "$c_choice" =~ ^[0-9]+$ ]] && (( c_choice >= 1 && c_choice <= ${#countries[@]} )); then
    chosen_country="${countries[$((c_choice-1))]}"
  elif [[ -n "$c_choice" ]]; then
    chosen_country="$c_choice"
  fi

  run_benchmark "$chosen_country" "https" "$DEFAULT_TOP_N" "$is_dry_run" true
}

custom_benchmark_wizard() {
  local is_dry_run="$1"
  log_section "Custom Benchmark Wizard"

  local proto="https"
  printf "Select Protocol:\n"
  printf "  1) HTTPS only (Recommended)\n"
  printf "  2) HTTP only\n"
  printf "  3) All protocols\n"
  printf "Choice [1-3, default: 1] > "
  read -r p_choice
  case "$p_choice" in
    2) proto="http" ;;
    3) proto="all" ;;
    *) proto="https" ;;
  esac

  printf "\nNumber of top mirrors to keep [default: %d] > " "$DEFAULT_TOP_N"
  read -r top_n
  top_n="${top_n:-$DEFAULT_TOP_N}"

  run_benchmark "ALL" "$proto" "$top_n" "$is_dry_run" true
}

# --------------------------------------------------------------------------- #
# Main Interactive Menu Loop (0 to 9 + q)
# --------------------------------------------------------------------------- #
main_menu() {
  while true; do
    printf "\n%s╔═══════════════════════════════════════════════════════════════════╗%s\n" "$C_CYAN$C_BOLD" "$C_RESET"
    printf "%s║         Arch Linux Mirror Manager & Security Suite (rankmirrors)  ║%s\n" "$C_CYAN$C_BOLD" "$C_RESET"
    printf "%s╚═══════════════════════════════════════════════════════════════════╝%s\n" "$C_CYAN$C_BOLD" "$C_RESET"
    get_database_stats
    printf "\n"
    printf "  %s0)%s 🛡️  System Security Audit & Hardening (SigLevel / Keyring)\n" "$C_MAGENTA$C_BOLD" "$C_RESET"
    printf "  %s1)%s ⚡ Express Rank (Fastest Worldwide HTTPS, Top %d)\n" "$C_GREEN$C_BOLD" "$C_RESET" "$DEFAULT_TOP_N"
    printf "  %s2)%s 🎯 Custom Benchmark (Protocol & Limits)\n" "$C_GREEN" "$C_RESET"
    printf "  %s3)%s 🇮🇷 Emergency Intranet Mode (Iran Official & Community Fallbacks)\n" "$C_YELLOW$C_BOLD" "$C_RESET"
    printf "  %s4)%s 🌍 Filter & Benchmark by Specific Country / Region\n" "$C_GREEN" "$C_RESET"
    printf "  %s5)%s 🧪 Dry-Run Benchmark (Test Only, No Changes)\n" "$C_YELLOW" "$C_RESET"
    printf "  %s6)%s 📋 View Active Mirrorlist & Health / Freshness Probe\n" "$C_BLUE" "$C_RESET"
    printf "  %s7)%s 💾 Restore Mirrorlist from Backup\n" "$C_BLUE" "$C_RESET"
    printf "  %s8)%s 🔄 Self-Update Embedded Mirror Database from Arch Upstream\n" "$C_CYAN" "$C_RESET"
    printf "  %s9)%s 🚀 Synchronize Pacman Databases (sudo pacman -Syy)\n" "$C_CYAN" "$C_RESET"
    printf "  %sq)%s 🚪 Exit\n\n" "$C_RED" "$C_RESET"

    printf "Select an option [0-9/q] > "
    read -r opt

    case "$opt" in
      0) audit_and_harden_crypto ;;
      1) run_benchmark "ALL" "https" "$DEFAULT_TOP_N" false true ;;
      2) custom_benchmark_wizard false ;;
      3)
        log_info "Testing Iran official and intranet fallback mirrors..."
        run_benchmark "IRAN_ALL" "https" 5 false true
        ;;
      4) country_benchmark_wizard false ;;
      5) custom_benchmark_wizard true ;;
      6) view_active_mirrorlist_with_health ;;
      7) restore_backup_menu ;;
      8) self_update_mirrors ;;
      9)
        log_info "Refreshing pacman databases..."
        sudo pacman -Syy
        ;;
      q|Q)
        log_info "Exiting."
        break
        ;;
      *)
        log_err "Invalid selection. Please choose an option from 0-9 or q."
        ;;
    esac
  done
}

# --------------------------------------------------------------------------- #
# Entry Point
# --------------------------------------------------------------------------- #
check_dependencies
main_menu "$@"
exit 0

# === BEGIN EMBEDDED MIRRORLIST DATA ===
# Last Updated: 2026-08-21 02:13:19 UTC
##
## Arch Linux repository mirrorlist
## Generated on 2026-08-21
##

## Worldwide
#Server = https://fastly.mirror.pkgbuild.com/$repo/os/$arch
#Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
#Server = https://ftpmirror.infania.net/mirror/archlinux/$repo/os/$arch
#Server = http://mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch

## Albania
#Server = https://al.arch.niranjan.co/$repo/os/$arch

## Argentina
#Server = https://archlinux.juancho.com.ar/$repo/os/$arch

## Armenia
#Server = http://mirrors.teamcloud.am/archlinux/$repo/os/$arch
#Server = https://mirrors.teamcloud.am/archlinux/$repo/os/$arch

## Australia
#Server = https://mirror.aarnet.edu.au/pub/archlinux/$repo/os/$arch
#Server = http://au.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://au.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.digitalpacific.com.au/$repo/os/$arch
#Server = https://archlinux.mirror.digitalpacific.com.au/$repo/os/$arch
#Server = http://gsl-syd.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://gsl-syd.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://ftp.iinet.net.au/pub/archlinux/$repo/os/$arch
#Server = http://mirror.internode.on.net/pub/archlinux/$repo/os/$arch
#Server = https://au.arch.niranjan.co/$repo/os/$arch
#Server = http://syd.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://syd.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = http://ftp.swin.edu.au/archlinux/$repo/os/$arch

## Austria
#Server = http://mirror.alwyzon.net/archlinux/$repo/os/$arch
#Server = https://mirror.alwyzon.net/archlinux/$repo/os/$arch
#Server = http://at.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://at.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.digitalnova.at/archlinux/$repo/os/$arch
#Server = http://mirror.easyname.at/archlinux/$repo/os/$arch
#Server = https://at.arch.mirror.kescher.at/$repo/os/$arch
#Server = https://at.arch.niranjan.co/$repo/os/$arch
#Server = https://at-vie.soulharsh007.dev/archlinux/$repo/os/$arch

## Azerbaijan
#Server = http://mirror.ourhost.az/archlinux/$repo/os/$arch
#Server = https://mirror.ourhost.az/archlinux/$repo/os/$arch
#Server = http://mirror.yer.az/archlinux/$repo/os/$arch
#Server = https://mirror.yer.az/archlinux/$repo/os/$arch

## Bangladesh
#Server = http://mirror.limda.net/archlinux/$repo/os/$arch
#Server = https://mirror.limda.net/archlinux/$repo/os/$arch
#Server = http://mirror.xeonbd.com/archlinux/$repo/os/$arch
#Server = https://mirror.xeonbd.com/archlinux/$repo/os/$arch

## Belarus
#Server = http://ftp.byfly.by/pub/archlinux/$repo/os/$arch
#Server = http://mirror.datacenter.by/pub/archlinux/$repo/os/$arch

## Belgium
#Server = http://mirror.1ago.be/archlinux/$repo/os/$arch
#Server = https://mirror.1ago.be/archlinux/$repo/os/$arch
#Server = http://mirror.jonas-prz.be/$repo/os/$arch
#Server = https://mirror.jonas-prz.be/$repo/os/$arch
#Server = https://archlinux.mirror-services.net/archlinux/$repo/os/$arch
#Server = http://mirror.tiguinet.net/arch/$repo/os/$arch
#Server = https://mirror.tiguinet.net/arch/$repo/os/$arch

## Brazil
#Server = http://archlinux.c3sl.ufpr.br/$repo/os/$arch
#Server = https://archlinux.c3sl.ufpr.br/$repo/os/$arch
#Server = http://br.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://br.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.ufam.edu.br/archlinux/$repo/os/$arch
#Server = http://mirror.ufscar.br/archlinux/$repo/os/$arch
#Server = https://mirror.ufscar.br/archlinux/$repo/os/$arch
#Server = http://mirrors.ic.unicamp.br/archlinux/$repo/os/$arch
#Server = https://mirrors.ic.unicamp.br/archlinux/$repo/os/$arch

## Bulgaria
#Server = http://mirror.host.ag/archlinux/$repo/os/$arch
#Server = http://mirror.telepoint.bg/archlinux/$repo/os/$arch
#Server = https://mirror.telepoint.bg/archlinux/$repo/os/$arch
#Server = http://mirrors.uni-plovdiv.net/archlinux/$repo/os/$arch
#Server = https://mirrors.uni-plovdiv.net/archlinux/$repo/os/$arch

## Cambodia
#Server = http://mirror.sabay.com.kh/archlinux/$repo/os/$arch
#Server = https://mirror.sabay.com.kh/archlinux/$repo/os/$arch

## Canada
#Server = http://mirror.0xem.ma/arch/$repo/os/$arch
#Server = https://mirror.0xem.ma/arch/$repo/os/$arch
#Server = https://mirror.acadielinux.ca/mirror/arch/$repo/os/$arch
#Server = https://arch.mirror.winslow.cloud/$repo/os/$arch
#Server = http://ca.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://ca.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.cpsc.ucalgary.ca/mirror/archlinux.org/$repo/os/$arch
#Server = https://mirror.cpsc.ucalgary.ca/mirror/archlinux.org/$repo/os/$arch
#Server = http://mirror.csclub.uwaterloo.ca/archlinux/$repo/os/$arch
#Server = https://mirror.csclub.uwaterloo.ca/archlinux/$repo/os/$arch
#Server = http://mirror2.evolution-host.com/archlinux/$repo/os/$arch
#Server = https://mirror2.evolution-host.com/archlinux/$repo/os/$arch
#Server = https://stygian.failzero.net/mirror/archlinux/$repo/os/$arch
#Server = https://mirror.franscorack.com/archlinux/$repo/os/$arch
#Server = http://mirror.its.dal.ca/archlinux/$repo/os/$arch
#Server = http://ca.mirror.cx/archlinux/$repo/os/$arch
#Server = https://ca.mirror.cx/archlinux/$repo/os/$arch
#Server = http://mirror.quantum5.ca/archlinux/$repo/os/$arch
#Server = https://mirror.quantum5.ca/archlinux/$repo/os/$arch
#Server = https://ca.mirrors.mk/archlinux/$repo/os/$arch
#Server = http://muug.ca/mirror/archlinux/$repo/os/$arch
#Server = https://muug.ca/mirror/archlinux/$repo/os/$arch
#Server = http://mirrors.pablonara.com/archlinux/$repo/os/$arch
#Server = https://mirrors.pablonara.com/archlinux/$repo/os/$arch
#Server = https://upstream-1.pablonara.com/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.rafal.ca/$repo/os/$arch
#Server = http://mirror.scd31.com/arch/$repo/os/$arch
#Server = https://mirror.scd31.com/arch/$repo/os/$arch
#Server = http://archlinux-mirror.techticity.com/$repo/os/$arch
#Server = https://archlinux-mirror.techticity.com/$repo/os/$arch
#Server = http://mirror.xenyth.net/archlinux/$repo/os/$arch
#Server = https://mirror.xenyth.net/archlinux/$repo/os/$arch

## Chile
#Server = http://mirror.anquan.cl/archlinux/$repo/os/$arch
#Server = https://mirror.anquan.cl/archlinux/$repo/os/$arch
#Server = http://elmirror.cl/archlinux/$repo/os/$arch
#Server = https://elmirror.cl/archlinux/$repo/os/$arch
#Server = http://mirror.hnd.cl/archlinux/$repo/os/$arch
#Server = https://mirror.hnd.cl/archlinux/$repo/os/$arch
#Server = http://mirror.ufro.cl/archlinux/$repo/os/$arch
#Server = https://mirror.ufro.cl/archlinux/$repo/os/$arch

## China
#Server = http://mirrors.163.com/archlinux/$repo/os/$arch
#Server = http://mirrors.aliyun.com/archlinux/$repo/os/$arch
#Server = https://mirrors.aliyun.com/archlinux/$repo/os/$arch
#Server = http://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.bfsu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.cqu.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.cqu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.hit.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.hit.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.hust.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.hust.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.jcut.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.jcut.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.jlu.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.jlu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.jxust.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.jxust.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirror.lzu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.neusoft.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.neusoft.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.nju.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.nju.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirror.nyist.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirror.nyist.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.qlu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.shanghaitech.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.shanghaitech.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.sjtug.sjtu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.wsyu.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.wsyu.edu.cn/archlinux/$repo/os/$arch
#Server = https://mirrors.xjtu.edu.cn/archlinux/$repo/os/$arch
#Server = http://mirrors.zju.edu.cn/archlinux/$repo/os/$arch

## Colombia
#Server = http://mirrors.atlas.net.co/archlinux/$repo/os/$arch
#Server = https://mirrors.atlas.net.co/archlinux/$repo/os/$arch
#Server = http://edgeuno-bog2.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://edgeuno-bog2.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://mirrors.udenar.edu.co/archlinux/$repo/os/$arch

## Croatia
#Server = http://archlinux.iskon.hr/$repo/os/$arch

## Czechia
#Server = http://mirror.dkm.cz/archlinux/$repo/os/$arch
#Server = https://mirror.dkm.cz/archlinux/$repo/os/$arch
#Server = http://ftp.fi.muni.cz/pub/linux/arch/$repo/os/$arch
#Server = http://ftp.linux.cz/pub/linux/arch/$repo/os/$arch
#Server = http://gluttony.sin.cvut.cz/arch/$repo/os/$arch
#Server = https://gluttony.sin.cvut.cz/arch/$repo/os/$arch
#Server = http://mirror.it4i.cz/arch/$repo/os/$arch
#Server = https://mirror.it4i.cz/arch/$repo/os/$arch
#Server = http://archlinux.nic.cz/archlinux/$repo/os/$arch
#Server = https://archlinux.nic.cz/archlinux/$repo/os/$arch
#Server = http://ftp.sh.cvut.cz/arch/$repo/os/$arch
#Server = https://ftp.sh.cvut.cz/arch/$repo/os/$arch
#Server = http://mirror.vpsfree.cz/archlinux/$repo/os/$arch

## Denmark
#Server = http://mirrors.dotsrc.org/archlinux/$repo/os/$arch
#Server = https://mirrors.dotsrc.org/archlinux/$repo/os/$arch
#Server = http://mirror.group.one/archlinux/$repo/os/$arch
#Server = https://mirror.group.one/archlinux/$repo/os/$arch
#Server = https://mirror.it-privat.dk/arch/$repo/os/$arch

## Ecuador
#Server = http://mirror.cedia.org.ec/archlinux/$repo/os/$arch
#Server = https://mirror.linux.ec/archlinux/$repo/os/$arch

## Estonia
#Server = http://mirror.cspacehostings.com/archlinux/$repo/os/$arch
#Server = https://mirror.cspacehostings.com/archlinux/$repo/os/$arch
#Server = http://mirrors.xtom.ee/archlinux/$repo/os/$arch
#Server = https://mirrors.xtom.ee/archlinux/$repo/os/$arch

## Finland
#Server = https://archlinux.doridian.net/$repo/os/$arch
#Server = http://cdnmirror.com/archlinux/$repo/os/$arch
#Server = https://cdnmirror.com/archlinux/$repo/os/$arch
#Server = https://dornogal.falcao.org/archlinux/$repo/os/$arch
#Server = https://mirror.falcao.org/archlinux/$repo/os/$arch
#Server = http://arch.mirror.far.fi/$repo/os/$arch
#Server = http://mirror.5i.fi/archlinux/$repo/os/$arch
#Server = https://mirror.5i.fi/archlinux/$repo/os/$arch
#Server = https://fi.arch.niranjan.co/$repo/os/$arch
#Server = https://mirror.srv.fail/archlinux/$repo/os/$arch
#Server = http://mirrors.vpspulse.com/archlinux/$repo/os/$arch
#Server = https://mirrors.vpspulse.com/archlinux/$repo/os/$arch
#Server = http://mirror.wuki.li/archlinux/$repo/os/$arch
#Server = https://mirror.wuki.li/archlinux/$repo/os/$arch
#Server = http://arch.yhtez.xyz/$repo/os/$arch
#Server = https://arch.yhtez.xyz/$repo/os/$arch

## France
#Server = http://mirror.archlinux.ikoula.com/archlinux/$repo/os/$arch
#Server = https://elda.asgardius.company/archlinux/$repo/os/$arch
#Server = http://mirror.bakertelekom.fr/Arch/$repo/os/$arch
#Server = https://mirror.bakertelekom.fr/Arch/$repo/os/$arch
#Server = http://mirror.fr.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = https://mirror.fr.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = http://fr.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://fr.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://mirror.cosmiclinux.com/archlinux/$repo/os/$arch
#Server = http://mirror.cyberbits.eu/archlinux/$repo/os/$arch
#Server = https://mirror.cyberbits.eu/archlinux/$repo/os/$arch
#Server = http://archlinux.datagr.am/$repo/os/$arch
#Server = https://mirrors.eric.ovh/arch/$repo/os/$arch
#Server = http://mirrors.gandi.net/archlinux/$repo/os/$arch
#Server = https://mirrors.gandi.net/archlinux/$repo/os/$arch
#Server = http://archmirror.hogwarts.fr/$repo/os/$arch
#Server = https://archmirror.hogwarts.fr/$repo/os/$arch
#Server = http://mirror.its-tps.fr/archlinux/$repo/os/$arch
#Server = https://mirror.its-tps.fr/archlinux/$repo/os/$arch
#Server = https://mirrors.jtremesay.org/archlinux/$repo/os/$arch
#Server = http://mirror.lastmikoi.net/archlinux/$repo/os/$arch
#Server = http://archlinux.mailtunnel.eu/$repo/os/$arch
#Server = https://archlinux.mailtunnel.eu/$repo/os/$arch
#Server = http://f.matthieul.dev/mirror/archlinux/$repo/os/$arch
#Server = https://f.matthieul.dev/mirror/archlinux/$repo/os/$arch
#Server = http://mir.archlinux.fr/$repo/os/$arch
#Server = http://mirror.oldsql.cc/archlinux/$repo/os/$arch
#Server = https://mirror.oldsql.cc/archlinux/$repo/os/$arch
#Server = http://archlinux.mirrors.ovh.net/archlinux/$repo/os/$arch
#Server = https://archlinux.mirrors.ovh.net/archlinux/$repo/os/$arch
#Server = http://mirror.peeres-telecom.fr/archlinux/$repo/os/$arch
#Server = https://mirror.peeres-telecom.fr/archlinux/$repo/os/$arch
#Server = http://mirror.rznet.fr/archlinux/$repo/os/$arch
#Server = https://mirror.rznet.fr/archlinux/$repo/os/$arch
#Server = http://fr.mirror.shibe.party/archlinux/$repo/os/$arch
#Server = https://fr.mirror.shibe.party/archlinux/$repo/os/$arch
#Server = https://mirror.smayzy.ovh/archlinux/$repo/os/$arch
#Server = http://arch.syxpi.fr/arch/$repo/os/$arch
#Server = https://arch.syxpi.fr/arch/$repo/os/$arch
#Server = https://mirror.thekinrar.fr/archlinux/$repo/os/$arch
#Server = http://mirror.theo546.fr/archlinux/$repo/os/$arch
#Server = https://mirror.theo546.fr/archlinux/$repo/os/$arch
#Server = http://mirror.trap.moe/archlinux/$repo/os/$arch
#Server = https://mirror.trap.moe/archlinux/$repo/os/$arch
#Server = http://ftp.u-strasbg.fr/linux/distributions/archlinux/$repo/os/$arch
#Server = https://ftp.u-strasbg.fr/linux/distributions/archlinux/$repo/os/$arch
#Server = https://mirror.wormhole.eu/archlinux/$repo/os/$arch
#Server = http://arch.yourlabs.org/$repo/os/$arch
#Server = https://arch.yourlabs.org/$repo/os/$arch

## Georgia
#Server = http://archlinux.grena.ge/$repo/os/$arch
#Server = https://archlinux.grena.ge/$repo/os/$arch

## Germany
#Server = http://mirror.23m.com/archlinux/$repo/os/$arch
#Server = https://mirror.23m.com/archlinux/$repo/os/$arch
#Server = http://ftp.agdsn.de/pub/mirrors/archlinux/$repo/os/$arch
#Server = https://ftp.agdsn.de/pub/mirrors/archlinux/$repo/os/$arch
#Server = http://mirrors.aminvakil.com/archlinux/$repo/os/$arch
#Server = https://mirrors.aminvakil.com/archlinux/$repo/os/$arch
#Server = http://artfiles.org/archlinux.org/$repo/os/$arch
#Server = https://mirror.bethselamin.de/$repo/os/$arch
#Server = http://de.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://de.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.clientvps.com/archlinux/$repo/os/$arch
#Server = https://mirror.clientvps.com/archlinux/$repo/os/$arch
#Server = http://mirror.cmt.de/archlinux/$repo/os/$arch
#Server = https://mirror.cmt.de/archlinux/$repo/os/$arch
#Server = http://os.codefionn.eu/archlinux/$repo/os/$arch
#Server = https://os.codefionn.eu/archlinux/$repo/os/$arch
#Server = http://mirror-de-1.cutie.dating/archlinux/$repo/os/$arch
#Server = https://mirror-de-1.cutie.dating/archlinux/$repo/os/$arch
#Server = http://mirror.diyarciftci.xyz/archlinux/$repo/os/$arch
#Server = https://mirror.diyarciftci.xyz/archlinux/$repo/os/$arch
#Server = https://mirror.dogado.de/archlinux/$repo/os/$arch
#Server = http://ftp.fau.de/archlinux/$repo/os/$arch
#Server = https://ftp.fau.de/archlinux/$repo/os/$arch
#Server = https://pkg.fef.moe/archlinux/$repo/os/$arch
#Server = https://dist-mirror.fem.tu-ilmenau.de/archlinux/$repo/os/$arch
#Server = http://mirrors.foxmire.space/archlinux/$repo/os/$arch
#Server = https://mirrors.foxmire.space/archlinux/$repo/os/$arch
#Server = https://berlin.mirror.pkgbuild.com/$repo/os/$arch
#Server = https://frankfurt.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://ftp.gwdg.de/pub/linux/archlinux/$repo/os/$arch
#Server = https://files.hadiko.de/pub/dists/arch/$repo/os/$arch
#Server = http://ftp.hosteurope.de/mirror/ftp.archlinux.org/$repo/os/$arch
#Server = http://ftp-stud.hs-esslingen.de/pub/Mirrors/archlinux/$repo/os/$arch
#Server = http://mirror.hugo-betrugo.de/archlinux/$repo/os/$arch
#Server = https://mirror.hugo-betrugo.de/archlinux/$repo/os/$arch
#Server = http://mirror.informatik.tu-freiberg.de/arch/$repo/os/$arch
#Server = https://mirror.informatik.tu-freiberg.de/arch/$repo/os/$arch
#Server = http://mirror.as20647.net/archlinux/$repo/os/$arch
#Server = http://mirror.ipb.de/archlinux/$repo/os/$arch
#Server = https://mirror.as20647.net/archlinux/$repo/os/$arch
#Server = https://mirror.ipb.de/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.iphh.net/$repo/os/$arch
#Server = http://mirrors.janbruckner.de/archlinux/$repo/os/$arch
#Server = https://mirrors.janbruckner.de/archlinux/$repo/os/$arch
#Server = http://arch.jensgutermuth.de/$repo/os/$arch
#Server = https://arch.jensgutermuth.de/$repo/os/$arch
#Server = https://de.arch.mirror.kescher.at/$repo/os/$arch
#Server = http://mirror.kumi.systems/archlinux/$repo/os/$arch
#Server = https://mirror.kumi.systems/archlinux/$repo/os/$arch
#Server = http://mirror.fra10.de.leaseweb.net/archlinux/$repo/os/$arch
#Server = https://mirror.fra10.de.leaseweb.net/archlinux/$repo/os/$arch
#Server = http://arch.ljkx.org/$repo/os/$arch
#Server = https://arch.ljkx.org/$repo/os/$arch
#Server = http://mirror.metalgamer.eu/archlinux/$repo/os/$arch
#Server = https://mirror.metalgamer.eu/archlinux/$repo/os/$arch
#Server = http://mirror.lcarilla.de/archlinux/$repo/os/$arch
#Server = https://mirror.lcarilla.de/archlinux/$repo/os/$arch
#Server = https://de.mirrors.mk/archlinux/$repo/os/$arch
#Server = http://mirror.moson.org/arch/$repo/os/$arch
#Server = https://mirror.moson.org/arch/$repo/os/$arch
#Server = http://mirrors.n-ix.net/archlinux/$repo/os/$arch
#Server = https://mirrors.n-ix.net/archlinux/$repo/os/$arch
#Server = http://mirror.netcologne.de/archlinux/$repo/os/$arch
#Server = https://mirror.netcologne.de/archlinux/$repo/os/$arch
#Server = https://de.arch.niranjan.co/$repo/os/$arch
#Server = http://mirrors.niyawe.de/archlinux/$repo/os/$arch
#Server = https://mirrors.niyawe.de/archlinux/$repo/os/$arch
#Server = http://packages.oth-regensburg.de/archlinux/$repo/os/$arch
#Server = https://packages.oth-regensburg.de/archlinux/$repo/os/$arch
#Server = http://arch.owochle.app/$repo/os/$arch
#Server = https://arch.owochle.app/$repo/os/$arch
#Server = http://mirror.pagenotfound.de/archlinux/$repo/os/$arch
#Server = https://mirror.pagenotfound.de/archlinux/$repo/os/$arch
#Server = http://arch.phinau.de/$repo/os/$arch
#Server = https://arch.phinau.de/$repo/os/$arch
#Server = https://mirror.pseudoform.org/$repo/os/$arch
#Server = http://mirrors.purring.online/arch/$repo/os/$arch
#Server = https://mirrors.purring.online/arch/$repo/os/$arch
#Server = https://archlinux.richard-neumann.de/$repo/os/$arch
#Server = http://archlinux.roshak.xyz/$repo/os/$arch
#Server = https://archlinux.roshak.xyz/$repo/os/$arch
#Server = http://ftp.halifax.rwth-aachen.de/archlinux/$repo/os/$arch
#Server = https://ftp.halifax.rwth-aachen.de/archlinux/$repo/os/$arch
#Server = http://linux.rz.rub.de/archlinux/$repo/os/$arch
#Server = http://mirror.selfnet.de/archlinux/$repo/os/$arch
#Server = https://mirror.selfnet.de/archlinux/$repo/os/$arch
#Server = http://de.mirror.shibe.party/archlinux/$repo/os/$arch
#Server = https://de.mirror.shibe.party/archlinux/$repo/os/$arch
#Server = https://de-nue.soulharsh007.dev/archlinux/$repo/os/$arch
#Server = http://ftp.spline.inf.fu-berlin.de/mirrors/archlinux/$repo/os/$arch
#Server = https://ftp.spline.inf.fu-berlin.de/mirrors/archlinux/$repo/os/$arch
#Server = http://mirror.sunred.org/archlinux/$repo/os/$arch
#Server = https://mirror.sunred.org/archlinux/$repo/os/$arch
#Server = http://archlinux.thaller.ws/$repo/os/$arch
#Server = https://archlinux.thaller.ws/$repo/os/$arch
#Server = http://arch.mirror.cloud.thatcyberlynx.de/$repo/os/$arch
#Server = https://arch.mirror.cloud.thatcyberlynx.de/$repo/os/$arch
#Server = http://ftp.tu-chemnitz.de/pub/linux/archlinux/$repo/os/$arch
#Server = https://ftp.tu-chemnitz.de/pub/linux/archlinux/$repo/os/$arch
#Server = http://mirror.ubrco.de/archlinux/$repo/os/$arch
#Server = https://mirror.ubrco.de/archlinux/$repo/os/$arch
#Server = http://ftp.uni-bayreuth.de/linux/archlinux/$repo/os/$arch
#Server = http://ftp.uni-hannover.de/archlinux/$repo/os/$arch
#Server = http://ftp.uni-kl.de/pub/linux/archlinux/$repo/os/$arch
#Server = https://arch.unixpeople.org/$repo/os/$arch
#Server = http://mirror.wtnet.de/archlinux/$repo/os/$arch
#Server = https://mirror.wtnet.de/archlinux/$repo/os/$arch
#Server = http://mirrors.xtom.de/archlinux/$repo/os/$arch
#Server = https://mirrors.xtom.de/archlinux/$repo/os/$arch

## Greece
#Server = http://ftp.cc.uoc.gr/mirrors/linux/archlinux/$repo/os/$arch
#Server = https://repo.greeklug.gr/data/pub/linux/archlinux/$repo/os/$arch
#Server = http://ftp.otenet.gr/linux/archlinux/$repo/os/$arch

## Hong Kong
#Server = https://hk.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror-hk.koddos.net/archlinux/$repo/os/$arch
#Server = https://mirror-hk.koddos.net/archlinux/$repo/os/$arch
#Server = http://hkg.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://hkg.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://arch-mirror.wtako.net/$repo/os/$arch
#Server = http://mirror.xtom.com.hk/archlinux/$repo/os/$arch
#Server = https://mirror.xtom.com.hk/archlinux/$repo/os/$arch

## Hungary
#Server = https://ftp.ek-cer.hu/pub/mirrors/ftp.archlinux.org/$repo/os/$arch
#Server = http://hu.mirror.frigyes.dev/archlinux/$repo/os/$arch
#Server = https://hu.mirror.frigyes.dev/archlinux/$repo/os/$arch
#Server = http://archmirror.hbit.sztaki.hu/archlinux/$repo/os/$arch

## Iceland
#Server = http://is.mirror.flokinet.net/archlinux/$repo/os/$arch
#Server = https://is.mirror.flokinet.net/archlinux/$repo/os/$arch

## India
#Server = http://mirror.4v1.in/archlinux/$repo/os/$arch
#Server = https://mirror.4v1.in/archlinux/$repo/os/$arch
#Server = https://mirrors.abhy.me/archlinux/$repo/os/$arch
#Server = https://mirror.del2.albony.in/archlinux/$repo/os/$arch
#Server = https://mirror.maa.albony.in/archlinux/$repo/os/$arch
#Server = https://mirror.bom.kat.cx/archlinux/$repo/os/$arch
#Server = http://in.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://in.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://mirror.dawn.org.in/arch/$repo/os/$arch
#Server = http://in-mirror.garudalinux.org/archlinux/$repo/os/$arch
#Server = https://in-mirror.garudalinux.org/archlinux/$repo/os/$arch
#Server = http://archlinux.kushwanthreddy.com/$repo/os/$arch
#Server = https://archlinux.kushwanthreddy.com/$repo/os/$arch
#Server = https://in.arch.niranjan.co/$repo/os/$arch
#Server = http://mirrors.nxtgen.com/archlinux-mirror/$repo/os/$arch
#Server = https://mirrors.nxtgen.com/archlinux-mirror/$repo/os/$arch
#Server = http://mirror.sahil.world/archlinux/$repo/os/$arch
#Server = https://mirror.sahil.world/archlinux/$repo/os/$arch
#Server = http://mirrors.saswata.cc/archlinux/$repo/os/$arch
#Server = https://mirrors.saswata.cc/archlinux/$repo/os/$arch

## Indonesia
#Server = http://mirror.citrahost.com/archlinux/$repo/os/$arch
#Server = https://mirror.citrahost.com/archlinux/$repo/os/$arch
#Server = http://mirror.gi.co.id/archlinux/$repo/os/$arch
#Server = https://mirror.gi.co.id/archlinux/$repo/os/$arch
#Server = http://kebo.pens.ac.id/archlinux/$repo/os/$arch
#Server = http://mirror.ditatompel.com/archlinux/$repo/os/$arch
#Server = https://mirror.ditatompel.com/archlinux/$repo/os/$arch
#Server = http://mirror.papua.go.id/archlinux/$repo/os/$arch
#Server = https://mirror.papua.go.id/archlinux/$repo/os/$arch
#Server = http://mirror.repository.id/archlinux/$repo/os/$arch
#Server = https://mirror.repository.id/archlinux/$repo/os/$arch
#Server = https://kacabenggala.uny.ac.id/archlinux/$repo/os/$arch

## Iran
#Server = http://mirror.arvancloud.ir/archlinux/$repo/os/$arch
#Server = https://mirror.arvancloud.ir/archlinux/$repo/os/$arch
#Server = http://mirror.famaserver.com/archlinux/$repo/os/$arch
#Server = https://mirror.famaserver.com/archlinux/$repo/os/$arch
#Server = http://repo.iut.ac.ir/repo/archlinux/$repo/os/$arch
#Server = http://mirror.mobinhost.com/archlinux/$repo/os/$arch
#Server = https://mirror.mobinhost.com/archlinux/$repo/os/$arch

## Israel
#Server = http://archlinux.interhost.co.il/$repo/os/$arch
#Server = https://archlinux.interhost.co.il/$repo/os/$arch
#Server = http://mirror.isoc.org.il/pub/archlinux/$repo/os/$arch
#Server = https://mirror.isoc.org.il/pub/archlinux/$repo/os/$arch

## Italy
#Server = http://it.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://it.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.garr.it/archlinux/$repo/os/$arch
#Server = https://arch.mirror.hyperbit.it/$repo/os/$arch
#Server = http://mala-arch-server.eu/$repo/os/$arch
#Server = https://mala-arch-server.eu/$repo/os/$arch
#Server = http://archlinux.mirror.server24.net/$repo/os/$arch
#Server = https://archlinux.mirror.server24.net/$repo/os/$arch

## Japan
#Server = http://mirror.aria-on-the-planet.es/archlinux/$repo/os/$arch
#Server = https://mirror.aria-on-the-planet.es/archlinux/$repo/os/$arch
#Server = http://mirrors.cat.net/archlinux/$repo/os/$arch
#Server = https://mirrors.cat.net/archlinux/$repo/os/$arch
#Server = http://jp.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://jp.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://ftp.tsukuba.wide.ad.jp/Linux/archlinux/$repo/os/$arch
#Server = http://mirror.hashy0917.net/archlinux/$repo/os/$arch
#Server = https://mirror.hashy0917.net/archlinux/$repo/os/$arch
#Server = http://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch
#Server = https://ftp.jaist.ac.jp/pub/Linux/ArchLinux/$repo/os/$arch
#Server = http://www.miraa.jp/archlinux/$repo/os/$arch
#Server = https://www.miraa.jp/archlinux/$repo/os/$arch
#Server = http://mirror.rain.ne.jp/archlinux/$repo/os/$arch
#Server = https://mirror.rain.ne.jp/archlinux/$repo/os/$arch
#Server = http://ftp.yz.yamagata-u.ac.jp/pub/linux/archlinux/$repo/os/$arch
#Server = https://ftp.yz.yamagata-u.ac.jp/pub/linux/archlinux/$repo/os/$arch

## Kazakhstan
#Server = http://mirror.linxhost.ru/$repo/os/$arch
#Server = http://mirror.ps.kz/archlinux/$repo/os/$arch
#Server = https://mirror.ps.kz/archlinux/$repo/os/$arch

## Kenya
#Server = http://archlinux.mirror.liquidtelecom.com/$repo/os/$arch
#Server = https://archlinux.mirror.liquidtelecom.com/$repo/os/$arch

## Latvia
#Server = http://ftp.linux.edu.lv/archlinux/$repo/os/$arch
#Server = https://ftp.linux.edu.lv/archlinux/$repo/os/$arch
#Server = http://archlinux.koyanet.lv/archlinux/$repo/os/$arch
#Server = https://archlinux.koyanet.lv/archlinux/$repo/os/$arch

## Lithuania
#Server = http://mirrors.atviras.lt/archlinux/$repo/os/$arch
#Server = https://mirrors.atviras.lt/archlinux/$repo/os/$arch
#Server = http://mirror.sinirlan.net/archlinux/$repo/os/$arch
#Server = https://mirror.sinirlan.net/archlinux/$repo/os/$arch

## Luxembourg
#Server = http://arch-lux.spirex.me/$repo/os/$arch
#Server = https://arch-lux.spirex.me/$repo/os/$arch
#Server = http://mirror.lu.stratonexus.net/archlinux/$repo/os/$arch
#Server = https://mirror.lu.stratonexus.net/archlinux/$repo/os/$arch

## Malaysia
#Server = https://mirror.mrleong.net/archlinux/$repo/os/$arch

## Mauritius
#Server = http://archlinux-mirror.cloud.mu/$repo/os/$arch
#Server = https://archlinux-mirror.cloud.mu/$repo/os/$arch

## Mexico
#Server = http://lidsol.fi-b.unam.mx/archlinux/$repo/os/$arch
#Server = https://lidsol.fi-b.unam.mx/archlinux/$repo/os/$arch
#Server = https://arch.jsc.mx/$repo/os/$arch

## Moldova
#Server = http://md.mirrors.hacktegic.com/archlinux/$repo/os/$arch
#Server = https://md.mirrors.hacktegic.com/archlinux/$repo/os/$arch
#Server = http://mirror.hosthink.net/arch/$repo/os/$arch
#Server = https://mirror.hosthink.net/arch/$repo/os/$arch
#Server = http://mirror.ihost.md/archlinux/$repo/os/$arch
#Server = https://mirror.ihost.md/archlinux/$repo/os/$arch
#Server = http://mirror.mangohost.net/archlinux/$repo/os/$arch
#Server = https://mirror.mangohost.net/archlinux/$repo/os/$arch
#Server = https://md.arch.niranjan.co/$repo/os/$arch

## Morocco
#Server = http://mirror.abderraziq.com/archlinux/$repo/os/$arch
#Server = https://mirror.abderraziq.com/archlinux/$repo/os/$arch

## Nepal
#Server = http://mirrors.nepalicloud.com/archlinux/$repo/os/$arch
#Server = https://mirrors.nepalicloud.com/archlinux/$repo/os/$arch

## Netherlands
#Server = http://ams.nl.mirrors.bjg.at/arch/$repo/os/$arch
#Server = https://ams.nl.mirrors.bjg.at/arch/$repo/os/$arch
#Server = http://mirror.bouwhuis.network/archlinux/$repo/os/$arch
#Server = https://mirror.bouwhuis.network/archlinux/$repo/os/$arch
#Server = http://mirror.nl.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = https://mirror.nl.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = http://nl.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://nl.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.cj2.nl/archlinux/$repo/os/$arch
#Server = https://mirror.cj2.nl/archlinux/$repo/os/$arch
#Server = http://mirrors.evoluso.com/archlinux/$repo/os/$arch
#Server = http://nl.mirror.flokinet.net/archlinux/$repo/os/$arch
#Server = https://nl.mirror.flokinet.net/archlinux/$repo/os/$arch
#Server = https://mirror.iusearchbtw.nl/$repo/os/$arch
#Server = http://mirror.koddos.net/archlinux/$repo/os/$arch
#Server = https://mirror.koddos.net/archlinux/$repo/os/$arch
#Server = http://arch.mirrors.lavatech.top/$repo/os/$arch
#Server = https://arch.mirrors.lavatech.top/$repo/os/$arch
#Server = http://mirror.ams1.nl.leaseweb.net/archlinux/$repo/os/$arch
#Server = https://mirror.ams1.nl.leaseweb.net/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.liteserver.nl/$repo/os/$arch
#Server = https://archlinux.mirror.liteserver.nl/$repo/os/$arch
#Server = http://mirror.lyrahosting.com/archlinux/$repo/os/$arch
#Server = https://mirror.lyrahosting.com/archlinux/$repo/os/$arch
#Server = http://mirror.mijn.host/archlinux/$repo/os/$arch
#Server = https://mirror.mijn.host/archlinux/$repo/os/$arch
#Server = http://nl.mirror.cx/archlinux/$repo/os/$arch
#Server = https://nl.mirror.cx/archlinux/$repo/os/$arch
#Server = https://nl.mirrors.mk/archlinux/$repo/os/$arch
#Server = https://nl.arch.niranjan.co/$repo/os/$arch
#Server = http://ftp.nluug.nl/os/Linux/distr/archlinux/$repo/os/$arch
#Server = http://mirror.nyaa.vc/archlinux/$repo/os/$arch
#Server = https://mirror.nyaa.vc/archlinux/$repo/os/$arch
#Server = http://mirror.serverion.com/archlinux/$repo/os/$arch
#Server = https://mirror.serverion.com/archlinux/$repo/os/$arch
#Server = http://ftp.snt.utwente.nl/pub/os/linux/archlinux/$repo/os/$arch
#Server = http://archlinux.mirror.wearetriple.com/$repo/os/$arch
#Server = https://archlinux.mirror.wearetriple.com/$repo/os/$arch
#Server = http://mirrors.xtom.nl/archlinux/$repo/os/$arch
#Server = https://mirrors.xtom.nl/archlinux/$repo/os/$arch

## New Caledonia
#Server = http://mirror.lagoon.nc/pub/archlinux/$repo/os/$arch
#Server = http://archlinux.nautile.nc/archlinux/$repo/os/$arch
#Server = https://archlinux.nautile.nc/archlinux/$repo/os/$arch

## New Zealand
#Server = http://mirror.2degrees.nz/archlinux/$repo/os/$arch
#Server = https://mirror.2degrees.nz/archlinux/$repo/os/$arch
#Server = http://mirror.fsmg.org.nz/archlinux/$repo/os/$arch
#Server = https://mirror.fsmg.org.nz/archlinux/$repo/os/$arch
#Server = https://nz.arch.niranjan.co/$repo/os/$arch
#Server = https://archlinux.ourhome.kiwi/$repo/os/$arch

## North Macedonia
#Server = http://arch.softver.org.mk/archlinux/$repo/os/$arch
#Server = https://mk.mirrors.mk/archlinux/$repo/os/$arch
#Server = http://mirror.onevip.mk/archlinux/$repo/os/$arch
#Server = http://mirror.t-home.mk/archlinux/$repo/os/$arch
#Server = https://mirror.t-home.mk/archlinux/$repo/os/$arch

## Norway
#Server = http://mirror.archlinux.no/$repo/os/$arch
#Server = https://mirror.archlinux.no/$repo/os/$arch
#Server = http://archlinux.uib.no/$repo/os/$arch
#Server = https://archlinux.lysakermoen.com/$repo/os/$arch
#Server = http://no.mirror.cx/archlinux/$repo/os/$arch
#Server = https://no.mirror.cx/archlinux/$repo/os/$arch
#Server = http://mirror.neuf.no/archlinux/$repo/os/$arch
#Server = https://mirror.neuf.no/archlinux/$repo/os/$arch
#Server = http://mirror.terrahost.no/linux/archlinux/$repo/os/$arch

## Paraguay
#Server = http://archlinux.mirror.py/archlinux/$repo/os/$arch

## Philippines
#Server = http://mirrors.ostentiaz.net/arch/$repo/os/$arch
#Server = https://mirrors.ostentiaz.net/arch/$repo/os/$arch

## Poland
#Server = http://mirror.alldaydev.com/archlinux/$repo/os/$arch
#Server = https://mirror.alldaydev.com/archlinux/$repo/os/$arch
#Server = http://ftp.icm.edu.pl/pub/Linux/dist/archlinux/$repo/os/$arch
#Server = https://ftp.icm.edu.pl/pub/Linux/dist/archlinux/$repo/os/$arch
#Server = http://mirror.juniorjpdj.pl/archlinux/$repo/os/$arch
#Server = https://mirror.juniorjpdj.pl/archlinux/$repo/os/$arch
#Server = http://arch.midov.pl/arch/$repo/os/$arch
#Server = https://arch.midov.pl/arch/$repo/os/$arch
#Server = http://ftp.psnc.pl/linux/archlinux/$repo/os/$arch
#Server = https://ftp.psnc.pl/linux/archlinux/$repo/os/$arch
#Server = http://arch.sakamoto.pl/$repo/os/$arch
#Server = https://arch.sakamoto.pl/$repo/os/$arch

## Portugal
#Server = http://mirror.barata.pt/archlinux/$repo/os/$arch
#Server = https://mirror.barata.pt/archlinux/$repo/os/$arch
#Server = http://glua.ua.pt/pub/archlinux/$repo/os/$arch
#Server = https://glua.ua.pt/pub/archlinux/$repo/os/$arch
#Server = http://mirror.leitecastro.com/archlinux/$repo/os/$arch
#Server = https://mirror.leitecastro.com/archlinux/$repo/os/$arch
#Server = http://mirrors.up.pt/pub/archlinux/$repo/os/$arch
#Server = https://mirrors.up.pt/pub/archlinux/$repo/os/$arch
#Server = http://ftp.rnl.tecnico.ulisboa.pt/pub/archlinux/$repo/os/$arch
#Server = https://ftp.rnl.tecnico.ulisboa.pt/pub/archlinux/$repo/os/$arch

## Romania
#Server = http://mirrors.chroot.ro/archlinux/$repo/os/$arch
#Server = https://mirrors.chroot.ro/archlinux/$repo/os/$arch
#Server = http://mirror.efect.ro/archlinux/$repo/os/$arch
#Server = https://mirror.efect.ro/archlinux/$repo/os/$arch
#Server = http://ro.mirror.flokinet.net/archlinux/$repo/os/$arch
#Server = https://ro.mirror.flokinet.net/archlinux/$repo/os/$arch
#Server = http://mirrors.hosterion.ro/archlinux/$repo/os/$arch
#Server = https://mirrors.hosterion.ro/archlinux/$repo/os/$arch
#Server = http://mirrors.hostico.ro/archlinux/$repo/os/$arch
#Server = https://mirrors.hostico.ro/archlinux/$repo/os/$arch
#Server = http://archlinux.mirrors.linux.ro/$repo/os/$arch
#Server = http://mirrors.nav.ro/archlinux/$repo/os/$arch
#Server = https://ro.arch.niranjan.co/$repo/os/$arch
#Server = http://mirrors.nxthost.com/archlinux/$repo/os/$arch
#Server = https://mirrors.nxthost.com/archlinux/$repo/os/$arch
#Server = http://mirrors.pidginhost.com/arch/$repo/os/$arch
#Server = https://mirrors.pidginhost.com/arch/$repo/os/$arch

## Russia
#Server = http://archlinux.gay/archlinux/$repo/os/$arch
#Server = https://archlinux.gay/archlinux/$repo/os/$arch
#Server = http://mirror.cachy-arch.ru/archlinux/$repo/os/$arch
#Server = https://mirror.cachy-arch.ru/archlinux/$repo/os/$arch
#Server = http://ru.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://ru.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.kamtv.ru/archlinux/$repo/os/$arch
#Server = https://mirror.kamtv.ru/archlinux/$repo/os/$arch
#Server = http://mirror.kpfu.ru/archlinux/$repo/os/$arch
#Server = https://mirror.kpfu.ru/archlinux/$repo/os/$arch
#Server = http://wan.metrosg.ru/archlinux/$repo/os/$arch
#Server = https://wan.metrosg.ru/archlinux/$repo/os/$arch
#Server = http://mirror.murmellow.lol/archlinux/$repo/os/$arch
#Server = https://mirror.murmellow.lol/archlinux/$repo/os/$arch
#Server = http://mirror.nw-sys.ru/archlinux/$repo/os/$arch
#Server = https://mirror.nw-sys.ru/archlinux/$repo/os/$arch
#Server = http://mirrors.powernet.com.ru/archlinux/$repo/os/$arch
#Server = http://repository.su/archlinux/$repo/os/$arch
#Server = https://repository.su/archlinux/$repo/os/$arch
#Server = http://web.sketserv.ru/archlinux/$repo/os/$arch
#Server = https://web.sketserv.ru/archlinux/$repo/os/$arch
#Server = http://mirror.truenetwork.ru/archlinux/$repo/os/$arch
#Server = https://mirror.truenetwork.ru/archlinux/$repo/os/$arch
#Server = http://vlst.su/archlinux/$repo/os/$arch
#Server = https://vlst.su/archlinux/$repo/os/$arch
#Server = http://mirror.yandex.ru/archlinux/$repo/os/$arch
#Server = https://mirror.yandex.ru/archlinux/$repo/os/$arch

## Réunion
#Server = http://arch.mithril.re/$repo/os/$arch

## Saudi Arabia
#Server = http://sa.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://sa.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.maeen.sa/arch-mirror/$repo/os/$arch
#Server = https://mirror.maeen.sa/arch-mirror/$repo/os/$arch

## Serbia
#Server = http://mirror.pmf.kg.ac.rs/archlinux/$repo/os/$arch
#Server = http://mirror1.sox.rs/archlinux/$repo/os/$arch
#Server = https://mirror1.sox.rs/archlinux/$repo/os/$arch

## Singapore
#Server = http://mirror.aktkn.sg/archlinux/$repo/os/$arch
#Server = https://mirror.aktkn.sg/archlinux/$repo/os/$arch
#Server = http://mirror.sg.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = https://mirror.sg.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = http://sg.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://sg.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://download.nus.edu.sg/mirror/archlinux/$repo/os/$arch
#Server = http://mirror.freedif.org/archlinux/$repo/os/$arch
#Server = https://mirror.freedif.org/archlinux/$repo/os/$arch
#Server = https://singapore.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://mirror.guillaumea.fr/archlinux/$repo/os/$arch
#Server = https://mirror.guillaumea.fr/archlinux/$repo/os/$arch
#Server = http://mirror.jingk.ai/archlinux/$repo/os/$arch
#Server = https://mirror.jingk.ai/archlinux/$repo/os/$arch
#Server = https://sg.arch.niranjan.co/$repo/os/$arch
#Server = http://ossmirror.mycloud.services/os/linux/archlinux/$repo/os/$arch
#Server = http://mirror.sg.gs/archlinux/$repo/os/$arch
#Server = https://mirror.sg.gs/archlinux/$repo/os/$arch

## Slovakia
#Server = http://ftp.energotel.sk/pub/linux/arch/$repo/os/$arch
#Server = https://ftp.energotel.sk/pub/linux/arch/$repo/os/$arch
#Server = http://mirror.lnx.sk/pub/linux/archlinux/$repo/os/$arch
#Server = https://mirror.lnx.sk/pub/linux/archlinux/$repo/os/$arch
#Server = http://tux.rainside.sk/archlinux/$repo/os/$arch

## Slovenia
#Server = https://mirror.archlinux.si/$repo/os/$arch
#Server = https://www.sooftware.com/mirrors/Arch-Linux/$repo/os/$arch
#Server = http://mirror.tux.si/arch/$repo/os/$arch
#Server = https://mirror.tux.si/arch/$repo/os/$arch

## South Africa
#Server = http://archlinux.za.mirror.allworldit.com/archlinux/$repo/os/$arch
#Server = https://archlinux.za.mirror.allworldit.com/archlinux/$repo/os/$arch
#Server = http://za.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://za.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://johannesburg.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://mirror.is.co.za/mirror/archlinux.org/$repo/os/$arch
#Server = http://archlinux.mirror.net.za/$repo/os/$arch
#Server = https://archlinux.mirror.net.za/$repo/os/$arch
#Server = http://mirrors.urbanwave.co.za/archlinux/$repo/os/$arch
#Server = https://mirrors.urbanwave.co.za/archlinux/$repo/os/$arch

## South Korea
#Server = http://kr.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://kr.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.distly.kr/archlinux/$repo/os/$arch
#Server = https://mirror.distly.kr/archlinux/$repo/os/$arch
#Server = http://ftp.kaist.ac.kr/ArchLinux/$repo/os/$arch
#Server = http://mirror.funami.tech/arch/$repo/os/$arch
#Server = https://mirror.funami.tech/arch/$repo/os/$arch
#Server = https://mirror.hemino.net/archlinux/$repo/os/$arch
#Server = http://ftp.hrts.kr/archlinux/$repo/os/$arch
#Server = https://ftp.hrts.kr/archlinux/$repo/os/$arch
#Server = http://ftp.io.kr/$repo/os/$arch
#Server = https://ftp.io.kr/$repo/os/$arch
#Server = http://mirror.keiminem.com/archlinux/$repo/os/$arch
#Server = http://mirror2.keiminem.com/archlinux/$repo/os/$arch
#Server = https://mirror.keiminem.com/archlinux/$repo/os/$arch
#Server = https://mirror2.keiminem.com/archlinux/$repo/os/$arch
#Server = https://mirror.krfoss.org/archlinux/$repo/os/$arch
#Server = http://ftp.lanet.kr/pub/archlinux/$repo/os/$arch
#Server = https://ftp.lanet.kr/pub/archlinux/$repo/os/$arch
#Server = http://mirror.pileus.kr/archlinux/$repo/os/$arch
#Server = https://mirror.pileus.kr/archlinux/$repo/os/$arch
#Server = http://mirror.siwoo.org/archlinux/$repo/os/$arch
#Server = https://mirror.siwoo.org/archlinux/$repo/os/$arch
#Server = http://mirror.techlabs.co.kr/archlinux/$repo/os/$arch
#Server = https://mirror.techlabs.co.kr/archlinux/$repo/os/$arch
#Server = http://mirror.wane.kr/archlinux/$repo/os/$arch
#Server = https://mirror.wane.kr/archlinux/$repo/os/$arch
#Server = http://mirror.yuki.net.uk/archlinux/$repo/os/$arch
#Server = https://mirror.yuki.net.uk/archlinux/$repo/os/$arch

## Spain
#Server = http://mirror.es.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = https://mirror.es.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = http://es.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://es.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.raiolanetworks.com/archlinux/$repo/os/$arch
#Server = https://mirror.raiolanetworks.com/archlinux/$repo/os/$arch
#Server = https://ftp.rediris.es/mirror/archlinux/$repo/os/$arch

## Sweden
#Server = http://mirror.accum.se/mirror/archlinux/$repo/os/$arch
#Server = https://mirror.accum.se/mirror/archlinux/$repo/os/$arch
#Server = https://mirror.braindrainlan.nu/archlinux/$repo/os/$arch
#Server = https://umea.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://ftpmirror.infania.net/mirror/archlinux/$repo/os/$arch
#Server = http://ftp.ludd.ltu.se/mirrors/archlinux/$repo/os/$arch
#Server = https://ftp.ludd.ltu.se/mirrors/archlinux/$repo/os/$arch
#Server = http://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch
#Server = https://ftp.lysator.liu.se/pub/archlinux/$repo/os/$arch
#Server = http://mirror.bahnhof.net/pub/archlinux/$repo/os/$arch
#Server = https://mirror.bahnhof.net/pub/archlinux/$repo/os/$arch
#Server = http://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch
#Server = https://ftp.myrveln.se/pub/linux/archlinux/$repo/os/$arch
#Server = https://mirror.osbeck.com/archlinux/$repo/os/$arch
#Server = http://mirror.retropc.se/archlinux/$repo/os/$arch
#Server = https://mirror.retropc.se/archlinux/$repo/os/$arch
#Server = http://mirror.tedwall.se/archlinux/$repo/os/$arch
#Server = https://mirror.tedwall.se/archlinux/$repo/os/$arch
#Server = https://mirror.zyner.org/mirror/archlinux/$repo/os/$arch

## Switzerland
#Server = http://pkg.adfinis-on-exoscale.ch/archlinux-pkgbuild/$repo/os/$arch
#Server = http://pkg.adfinis-on-exoscale.ch/archlinux/$repo/os/$arch
#Server = https://pkg.adfinis-on-exoscale.ch/archlinux-pkgbuild/$repo/os/$arch
#Server = https://pkg.adfinis-on-exoscale.ch/archlinux/$repo/os/$arch
#Server = http://mirror.arch-linux.ch/archlinux/$repo/os/$arch
#Server = https://mirror.arch-linux.ch/archlinux/$repo/os/$arch
#Server = https://archlinux.lan.brgn.ch/archlinux/$repo/os/$arch
#Server = http://ch.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://ch.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.hb9hil.org/archlinux/$repo/os/$arch
#Server = https://mirror.hb9hil.org/archlinux/$repo/os/$arch
#Server = http://mirror.init7.net/archlinux/$repo/os/$arch
#Server = https://mirror.init7.net/archlinux/$repo/os/$arch
#Server = http://mirror.metanet.ch/archlinux/$repo/os/$arch
#Server = https://mirror.metanet.ch/archlinux/$repo/os/$arch
#Server = http://mirror.puzzle.ch/archlinux/$repo/os/$arch
#Server = https://mirror.puzzle.ch/archlinux/$repo/os/$arch
#Server = https://theswissbay.ch/archlinux/$repo/os/$arch
#Server = https://mirror.ungleich.ch/mirror/packages/archlinux/$repo/os/$arch

## Taiwan
#Server = http://mirror.archlinux.tw/ArchLinux/$repo/os/$arch
#Server = https://mirror.archlinux.tw/ArchLinux/$repo/os/$arch
#Server = http://archlinux.ccns.ncku.edu.tw/archlinux/$repo/os/$arch
#Server = https://archlinux.ccns.ncku.edu.tw/archlinux/$repo/os/$arch
#Server = http://tw.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://tw.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://free.nchc.org.tw/arch/$repo/os/$arch
#Server = https://taipei.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://archlinux.cs.nycu.edu.tw/$repo/os/$arch
#Server = https://archlinux.cs.nycu.edu.tw/$repo/os/$arch
#Server = http://ftp.tku.edu.tw/Linux/ArchLinux/$repo/os/$arch
#Server = http://mirror.twds.com.tw/archlinux/$repo/os/$arch
#Server = https://mirror.twds.com.tw/archlinux/$repo/os/$arch

## Thailand
#Server = https://mirror.cyberbits.asia/archlinux/$repo/os/$arch
#Server = http://mirror.kku.ac.th/archlinux/$repo/os/$arch
#Server = https://mirror.kku.ac.th/archlinux/$repo/os/$arch

## Tunisia
#Server = https://mirror.safiabidi.com/$repo/os/$arch

## Türkiye
#Server = http://ftp.linux.org.tr/archlinux/$repo/os/$arch
#Server = https://tr.arch.niranjan.co/$repo/os/$arch
#Server = http://mirror.timtal.com.tr/archlinux/$repo/os/$arch
#Server = https://mirror.timtal.com.tr/archlinux/$repo/os/$arch

## Ukraine
#Server = http://distrohub.kyiv.ua/archlinux/$repo/os/$arch
#Server = https://distrohub.kyiv.ua/archlinux/$repo/os/$arch
#Server = http://repo.hyron.dev/archlinux/$repo/os/$arch
#Server = https://repo.hyron.dev/archlinux/$repo/os/$arch
#Server = http://mirror.hostiko.network/archlinux/$repo/os/$arch
#Server = https://mirror.hostiko.network/archlinux/$repo/os/$arch
#Server = http://archlinux.ip-connect.vn.ua/$repo/os/$arch
#Server = https://archlinux.ip-connect.vn.ua/$repo/os/$arch
#Server = http://mirror.mirohost.net/archlinux/$repo/os/$arch
#Server = https://mirror.mirohost.net/archlinux/$repo/os/$arch
#Server = http://mirrors.reitarovskyi.com.ua/archlinux/$repo/os/$arch
#Server = https://mirrors.reitarovskyi.com.ua/archlinux/$repo/os/$arch
#Server = http://mirror.trapmaid.org/archlinux/$repo/os/$arch
#Server = https://mirror.trapmaid.org/archlinux/$repo/os/$arch

## United Arab Emirates
#Server = https://mirror.hafeezh.com/archlinux/$repo/os/$arch

## United Kingdom
#Server = http://archlinux.uk.mirror.allworldit.com/archlinux/$repo/os/$arch
#Server = https://archlinux.uk.mirror.allworldit.com/archlinux/$repo/os/$arch
#Server = https://repo.c48.uk/arch/$repo/os/$arch
#Server = http://gb.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://gb.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://london.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://mirror.marcusn.net/archlinux/$repo/os/$arch
#Server = https://mirror.marcusn.net/archlinux/$repo/os/$arch
#Server = http://mirrors.melbourne.co.uk/archlinux/$repo/os/$arch
#Server = https://mirrors.melbourne.co.uk/archlinux/$repo/os/$arch
#Server = http://www.mirrorservice.org/sites/ftp.archlinux.org/$repo/os/$arch
#Server = https://www.mirrorservice.org/sites/ftp.archlinux.org/$repo/os/$arch
#Server = http://mirror.netweaver.uk/archlinux/$repo/os/$arch
#Server = https://mirror.netweaver.uk/archlinux/$repo/os/$arch
#Server = https://uk.arch.niranjan.co/$repo/os/$arch
#Server = http://lon.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://lon.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = http://mirror.server.net/archlinux/$repo/os/$arch
#Server = https://mirror.server.net/archlinux/$repo/os/$arch
#Server = https://repo.slithery.uk/$repo/os/$arch
#Server = https://mirror.st2projects.com/archlinux/$repo/os/$arch
#Server = http://mirrors.ukfast.co.uk/sites/archlinux.org/$repo/os/$arch
#Server = https://mirrors.ukfast.co.uk/sites/archlinux.org/$repo/os/$arch
#Server = http://mirror.cov.ukservers.com/archlinux/$repo/os/$arch
#Server = https://mirror.cov.ukservers.com/archlinux/$repo/os/$arch

## United States
#Server = http://mirrors.acm.wpi.edu/archlinux/$repo/os/$arch
#Server = http://mirror.adectra.com/archlinux/$repo/os/$arch
#Server = https://mirror.adectra.com/archlinux/$repo/os/$arch
#Server = https://mirror.akane.network/archmirror/$repo/os/$arch
#Server = http://mirror.arizona.edu/archlinux/$repo/os/$arch
#Server = https://mirror.arizona.edu/archlinux/$repo/os/$arch
#Server = http://arlm.tyzoid.com/$repo/os/$arch
#Server = https://arlm.tyzoid.com/$repo/os/$arch
#Server = http://mirrors.bloomu.edu/archlinux/$repo/os/$arch
#Server = https://mirrors.bloomu.edu/archlinux/$repo/os/$arch
#Server = https://arch-mirror.brightlight.today/$repo/os/$arch
#Server = http://mirrors.cat.pdx.edu/archlinux/$repo/os/$arch
#Server = http://mirror.us.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = https://mirror.us.cdn-perfprod.com/archlinux/$repo/os/$arch
#Server = http://us.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = https://us.mirrors.cicku.me/archlinux/$repo/os/$arch
#Server = http://mirror.clarkson.edu/archlinux/$repo/os/$arch
#Server = https://mirror.clarkson.edu/archlinux/$repo/os/$arch
#Server = http://mirror.colonelhosting.com/archlinux/$repo/os/$arch
#Server = https://mirror.colonelhosting.com/archlinux/$repo/os/$arch
#Server = http://arch.mirror.constant.com/$repo/os/$arch
#Server = https://arch.mirror.constant.com/$repo/os/$arch
#Server = http://mirror.cs.odu.edu/archlinux/$repo/os/$arch
#Server = https://mirror.cs.odu.edu/archlinux/$repo/os/$arch
#Server = http://mirror.cs.vt.edu/pub/ArchLinux/$repo/os/$arch
#Server = http://repo.customcomputercare.com/archlinux/$repo/os/$arch
#Server = https://repo.customcomputercare.com/archlinux/$repo/os/$arch
#Server = http://distro.ibiblio.org/archlinux/$repo/os/$arch
#Server = http://codingflyboy.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://coresite.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://forksystems.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://irltoolkit.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://mirror.fcix.net/archlinux/$repo/os/$arch
#Server = http://mnvoip.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://nnenix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://nocix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://ohioix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://opencolo.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://southfront.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://volico.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://ziply.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://codingflyboy.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://coresite.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://forksystems.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://irltoolkit.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://mirror.fcix.net/archlinux/$repo/os/$arch
#Server = https://mnvoip.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://nnenix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://nocix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://ohioix.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://opencolo.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://southfront.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://volico.mm.fcix.net/archlinux/$repo/os/$arch
#Server = https://ziply.mm.fcix.net/archlinux/$repo/os/$arch
#Server = http://mirror.fossable.org/archlinux/$repo/os/$arch
#Server = https://losangeles.mirror.pkgbuild.com/$repo/os/$arch
#Server = http://mirrors.gigenet.com/archlinux/$repo/os/$arch
#Server = https://mirror.givebytes.net/archlinux/$repo/os/$arch
#Server = https://mirror2.givebytes.net/archlinux/$repo/os/$arch
#Server = https://arch.goober.cloud/$repo/os/$arch
#Server = http://mirror.hasphetica.win/archlinux/$repo/os/$arch
#Server = https://mirror.hasphetica.win/archlinux/$repo/os/$arch
#Server = http://arch.hu.fo/archlinux/$repo/os/$arch
#Server = https://arch.hu.fo/archlinux/$repo/os/$arch
#Server = http://arch.hugeblank.dev/$repo/os/$arch
#Server = https://arch.hugeblank.dev/$repo/os/$arch
#Server = http://repo.ialab.dsu.edu/archlinux/$repo/os/$arch
#Server = https://repo.ialab.dsu.edu/archlinux/$repo/os/$arch
#Server = http://mirrors.iu13.net/archlinux/$repo/os/$arch
#Server = https://mirrors.iu13.net/archlinux/$repo/os/$arch
#Server = https://arch.mirror.k0.ae/$repo/os/$arch
#Server = http://mirror.kalem.dev/archlinux/$repo/os/$arch
#Server = https://mirror.kalem.dev/archlinux/$repo/os/$arch
#Server = http://mirrors.kernel.org/archlinux/$repo/os/$arch
#Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch
#Server = https://mirrors.lahansons.com/archlinux/$repo/os/$arch
#Server = http://mirror.sfo12.us.leaseweb.net/archlinux/$repo/os/$arch
#Server = http://mirror.wdc1.us.leaseweb.net/archlinux/$repo/os/$arch
#Server = https://mirror.sfo12.us.leaseweb.net/archlinux/$repo/os/$arch
#Server = https://mirror.wdc1.us.leaseweb.net/archlinux/$repo/os/$arch
#Server = http://mirrors.liquidweb.com/archlinux/$repo/os/$arch
#Server = https://mirrors.logal.dev/archlinux/$repo/os/$arch
#Server = http://mirrors.lug.mtu.edu/archlinux/$repo/os/$arch
#Server = https://mirrors.lug.mtu.edu/archlinux/$repo/os/$arch
#Server = http://mirror.lug.umbc.edu/archlinux/$repo/os/$arch
#Server = https://mirror.lug.umbc.edu/archlinux/$repo/os/$arch
#Server = https://m.lqy.me/arch/$repo/os/$arch
#Server = https://arch.mirror.marcusspencer.us:4443/archlinux/$repo/os/$arch
#Server = http://mirror.math.princeton.edu/pub/archlinux/$repo/os/$arch
#Server = http://mirror.metrocast.net/archlinux/$repo/os/$arch
#Server = http://arch.miningtcup.me/$repo/os/$arch
#Server = https://arch.miningtcup.me/$repo/os/$arch
#Server = https://us.mirrors.mk/archlinux/$repo/os/$arch
#Server = https://mirrors.shr.cx/arch/$repo/os/$arch
#Server = http://iad.mirrors.misaka.one/archlinux/$repo/os/$arch
#Server = https://iad.mirrors.misaka.one/archlinux/$repo/os/$arch
#Server = http://repo.miserver.it.umich.edu/archlinux/$repo/os/$arch
#Server = http://mirrors.mit.edu/archlinux/$repo/os/$arch
#Server = https://mirrors.mit.edu/archlinux/$repo/os/$arch
#Server = http://mirror.mra.sh/archlinux/$repo/os/$arch
#Server = https://mirror.mra.sh/archlinux/$repo/os/$arch
#Server = https://us.arch.niranjan.co/$repo/os/$arch
#Server = http://mirrors.ocf.berkeley.edu/archlinux/$repo/os/$arch
#Server = https://mirrors.ocf.berkeley.edu/archlinux/$repo/os/$arch
#Server = http://archmirror1.octyl.net/$repo/os/$arch
#Server = https://archmirror1.octyl.net/$repo/os/$arch
#Server = http://ftp.osuosl.org/pub/archlinux/$repo/os/$arch
#Server = https://ftp.osuosl.org/pub/archlinux/$repo/os/$arch
#Server = https://mirror.pilotfiber.com/archlinux/$repo/os/$arch
#Server = http://dfw.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = http://iad.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = http://ord.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://dfw.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://iad.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = https://ord.mirror.rackspace.com/archlinux/$repo/os/$arch
#Server = http://plug-mirror.rcac.purdue.edu/archlinux/$repo/os/$arch
#Server = https://plug-mirror.rcac.purdue.edu/archlinux/$repo/os/$arch
#Server = http://mirrors.rit.edu/archlinux/$repo/os/$arch
#Server = https://mirrors.rit.edu/archlinux/$repo/os/$arch
#Server = http://mirror.siena.edu/archlinux/$repo/os/$arch
#Server = http://mirrors.smeal.xyz/arch-linux/$repo/os/$arch
#Server = https://mirrors.smeal.xyz/arch-linux/$repo/os/$arch
#Server = http://mirrors.sonic.net/archlinux/$repo/os/$arch
#Server = https://mirrors.sonic.net/archlinux/$repo/os/$arch
#Server = https://us-mnz.soulharsh007.dev/archlinux/$repo/os/$arch
#Server = http://mirror.pit.teraswitch.com/archlinux/$repo/os/$arch
#Server = https://mirror.pit.teraswitch.com/archlinux/$repo/os/$arch
#Server = https://mirror.theash.xyz/arch/$repo/os/$arch
#Server = http://mirror.tzulo.com/archlinux/$repo/os/$arch
#Server = https://mirror.tzulo.com/archlinux/$repo/os/$arch
#Server = http://mirror.umd.edu/archlinux/$repo/os/$arch
#Server = https://mirror.umd.edu/archlinux/$repo/os/$arch
#Server = http://mirrors.vectair.net/archlinux/$repo/os/$arch
#Server = https://mirrors.vectair.net/archlinux/$repo/os/$arch
#Server = http://mirror.vtti.vt.edu/archlinux/$repo/os/$arch
#Server = http://wcbmedia.io:8000/$repo/os/$arch
#Server = http://mirrors.xmission.com/archlinux/$repo/os/$arch
#Server = http://mirrors.xtom.com/archlinux/$repo/os/$arch
#Server = https://mirrors.xtom.com/archlinux/$repo/os/$arch
#Server = https://yonderly.org/mirrors/archlinux/$repo/os/$arch
#Server = https://mirror.zackmyers.io/archlinux/$repo/os/$arch
#Server = https://zxcvfdsa.com/arch/$repo/os/$arch

## Uzbekistan
#Server = http://mirror.dc.uz/arch/$repo/os/$arch
#Server = https://mirror.dc.uz/arch/$repo/os/$arch

## Vietnam
#Server = http://mirror.bizflycloud.vn/archlinux/$repo/os/$arch
#Server = https://mirrors.huongnguyen.dev/arch/$repo/os/$arch
#Server = https://mirror.khoinet.dpdns.org/Arch/$repo/os/$arch
#Server = https://mirror.meowsmp.net/arch/$repo/os/$arch
#Server = https://mirrors.nguyenhoang.cloud/archlinux/$repo/os/$arch


## Iran (Intranet Fallbacks & Community)
#Server = https://mirror.0-1.ir/archlinux/$repo/os/$arch
#Server = https://mirror.0-1.cloud/archlinux/$repo/os/$arch
#Server = https://linux-mirror.liara.ir/archlinux/$repo/os/$arch
#Server = https://mirror.famaserver.com/archlinux/$repo/os/$arch
# === END EMBEDDED MIRRORLIST DATA ===
