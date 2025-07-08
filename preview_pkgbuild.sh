#!/usr/bin/env bash
set -euo pipefail

pkg=$1
cd "$CACHE_DIR/pkgbuild/$pkg"

if pacman -Qqs "^${pkg}$"; then
    date=$(pacman -Qi "$pkg" | grep 'Build Date' | cut -d ':' -f 2-)
    commit=$(git log --reverse --since "$(date -d "$date" +%s)" --pretty=format:"%h" | head -1)
    git diff --color=always "$commit" PKGBUILD
elif [ -x /usr/bin/bat ]; then
    bat --color=always PKGBUILD
else
    cat -n PKGBUILD
fi
