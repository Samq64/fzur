#!/usr/bin/env bash
set -euo pipefail

pkg=$1
exclude=(':!.SRCINFO' ':!.gitignore')
cd "$FZUR_CACHE/pkgbuild/$pkg"

if pacman -Qqs "^$pkg$" >/dev/null; then
    date=$(pacman -Qi "$pkg" | sed -n 's/^Build Date *: //p')
    commit=$(git log --before "$(date -d "$date" +%s)" -1 --pretty="%h")
else
    commit=$(git hash-object -t tree /dev/null)
fi

git diff --color=always "$commit" -- . "${exclude[@]}"
