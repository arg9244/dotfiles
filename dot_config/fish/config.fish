# source /usr/share/cachyos-fish-config/cachyos-config.fish
starship init fish | source

# Add ~/bin to the PATH
set -gx PATH $HOME/bin $PATH

#alias
alias yt-opus="yt-dlp -f ba -x --audio-format opus"
