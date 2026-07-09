source /usr/share/cachyos-fish-config/cachyos-config.fish
starship init fish | source

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end
alias purge="sudo paru -Rnscu"
alias clean="sudo crunchycleaner -a"

# chezmoi: re-add changes to already-tracked files from their original locations
# (e.g. changes made directly to ~/.config/somefile get synced to the chezmoi source dir)
alias chezreadd="chezmoi re-add"

# chezmoi: commit all changes in the source dir and push to the configured remote (GitHub)
alias chezpush="chezmoi git -- add -A . && chezmoi git -- commit -m 'Update dotfiles' && chezmoi git -- push"
starship init fish | source
