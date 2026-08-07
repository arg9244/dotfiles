source /usr/share/cachyos-fish-config/cachyos-config.fish
set -gx PATH $HOME/.local/bin $HOME/.npm-global/bin $HOME/.bun/bin $PATH
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
