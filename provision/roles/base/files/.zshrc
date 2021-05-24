source /usr/share/zsh/share/antigen.zsh

antigen use oh-my-zsh

antigen bundle autojump
antigen bundle extract

antigen bundle mafredri/zsh-async # required for pure
antigen bundle sindresorhus/pure

antigen apply

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

alias v='nvim'
alias vi='nvim'
alias vim='nvim'

export EDITOR='nvim'

export GOPATH="$HOME/.go"
export GOBIN="$GOPATH/bin"

export PATH="$PATH:$HOME/.cargo/bin:$HOME/.yarn/bin:$GOBIN"