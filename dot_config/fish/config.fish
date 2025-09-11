# source /usr/share/cachyos-fish-config/cachyos-config.fish
starship init fish | source

# Add ~/bin to the PATH
set -gx PATH $HOME/bin $PATH

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end
