source /usr/share/cachyos-fish-config/cachyos-config.fish
set -gx PATH $HOME/.local/bin $HOME/.npm-global/bin $HOME/.bun/bin $HOME/Games/bin $PATH
set -gx HSA_OVERRIDE_GFX_VERSION 10.3.0
set -gx EDITOR micro
set -gx VISUAL micro
set -gx GIT_EDITOR micro

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end
alias purge="sudo paru -Rnscu"

alias stop-docker 'docker stop (docker ps -q) 2>/dev/null; sudo systemctl stop docker docker.socket containerd'
alias start-docker 'sudo systemctl start docker docker.socket containerd'

# hyprwhspr: stt daemon, started/stopped manually (systemd service disabled)
alias hyprwhspr-start 'systemctl --user start hyprwhspr.service'
alias hyprwhspr-stop 'systemctl --user stop hyprwhspr.service'

# chezmoi: sync live dotfiles → chezmoi source dir (add new, update changed, forget deleted)
function chezsync
    chezmoi re-add
    for f in (chezmoi managed --include files)
        test -e "$HOME/$f"; or chezmoi forget "$f"
    end
    echo "chezmoi synced (re-add + forget deletions)"
end

# chezmoi: commit all changes in the source dir and push to the configured remote (GitHub)
alias chezpush="chezmoi git -- add -A . && chezmoi git -- commit -m 'Update dotfiles' && chezmoi git -- push"

# List packages by their INITIAL install date, pulled from the pacman log
# ([ALPM] installed lines only — ignores upgrades/reinstalls).
# Newest entries at the bottom (ascending date order).
# Caveat: only sees installs recorded in /var/log/pacman.log; append
# rotated logs (zcat ...1.gz ...2.gz) if history predates this archive.
function pkgs
    grep '\[ALPM\] installed ' /var/log/pacman.log |
        sed -E 's/^\[([^]]+)\] \[ALPM\] installed ([^ ]+) \(.*\)$/\1 \2/' |
        sort -k2,2 -k1,1 |
        awk '!seen[$2]++' |
        sort -k1,1 |
        while read -l ts pkg
            printf '%s  %s\n' (date -d "$ts" '+%Y-%m-%d %H:%M:%S') "$pkg"
        end
end
