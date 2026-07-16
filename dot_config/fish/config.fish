source /usr/share/cachyos-fish-config/cachyos-config.fish

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end
alias purge="sudo paru -Rnscu"

alias stop-docker 'docker stop (docker ps -q) 2>/dev/null; sudo systemctl stop docker docker.socket containerd'
alias start-docker 'sudo systemctl start docker docker.socket containerd'

# chezmoi: re-add changes to already-tracked files from their original locations
# (e.g. changes made directly to ~/.config/somefile get synced to the chezmoi source dir)
alias chezreadd="chezmoi re-add"

# chezmoi: commit all changes in the source dir and push to the configured remote (GitHub)
alias chezpush="chezmoi git -- add -A . && chezmoi git -- commit -m 'Update dotfiles' && chezmoi git -- push"
starship init fish | source

# Headroom: compress every OpenCode Zen request via local proxy :8786
if not ss -ltn 2>/dev/null | grep -q 8786
  setsid env ANTHROPIC_TARGET_API_URL=https://opencode.ai/zen/v1 OPENAI_TARGET_API_URL=https://opencode.ai/zen/v1 /home/reza/.local/bin/headroom proxy --port 8786 --mode token >/tmp/headroom_zen.log 2>&1 < /dev/null
end
set -gx OPENCODE_ZEN_BASE_URL http://127.0.0.1:8786

