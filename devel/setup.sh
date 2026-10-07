#Source this file (from bash or zsh) to add the ncnotebookdevtool command to
#your PATH, and (in bash 4 or later) enable completion of its modes.

if [ "x${BASH_VERSION:-}" != "x" ]; then
    export PATH="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/bin:${PATH}"
    if ((BASH_VERSINFO >= 4)); then
        type complete compgen 1>/dev/null 2>/dev/null
        if [ $? == 0 ]; then
            _ncnotebookdevtool_completions ()
            {
                if [ $COMP_CWORD -eq 1 ]; then
                    COMPREPLY=($(compgen -W "$(ncnotebookdevtool --show-completion-list)" "${COMP_WORDS[1]}"))
                else
                    COMPREPLY=()
                fi
            }
            complete -o bashdefault -o default -F _ncnotebookdevtool_completions ncnotebookdevtool
        fi
    fi
elif [ "x${ZSH_VERSION:-}" != "x" ]; then
    export PATH="${0:a:h}/bin:${PATH}"
else
    echo "ERROR: This script only supports bash or zsh for now. You will"
    echo "       have to manually add <reporoot>/devel/bin to your PATH"
fi
