#!/usr/bin/env bash
set -uo pipefail

# Global JS tools — run manually post-install (or anytime).
# All packages go through bun (bins in ~/.bun/bin, on PATH).
# Add or remove packages here; each is installed/updated to latest.
packages=(
  omniroute
  @oh-my-pi/pi-coding-agent
)

echo "Installing ${packages[*]} via bun..."
bun install -g "${packages[@]}"
echo "Done. Verify: bun pm ls -g"
