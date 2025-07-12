#!/usr/bin/env bash
set -euo pipefail

pkg=$1

cd "$FZUR_CACHE/pkgbuild/$pkg"

if [ "$(pacman -Qqs "^${pkg}$")" ]; then
    date=$(pacman -Qi "$pkg" | grep 'Build Date' | cut -d ':' -f 2-)
    commit=$(git log --before "$(date -d "$date" +%s)" --pretty="%h" -1)
    git diff --color=always "$commit" -- . ':!.SRCINFO'
else
    git diff --color=always "$(git hash-object -t tree /dev/null)" ':!.SRCINFO'
fi
