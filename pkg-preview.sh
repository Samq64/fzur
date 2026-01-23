#!/usr/bin/env bash
# Prints information about an AUR or official Arch package.
# Requirements: curl, jq

set -euo pipefail
COLUMNS=$FZF_PREVIEW_COLUMNS
readonly PKG=$1
readonly FILE="$ARF_CACHE/info/$PKG.json"

if [[ -f "$FILE" && $(find "$FILE" -mtime -1) ]]; then
    cat "$FILE"
    exit
fi

if pacman -Si --color=always "$PKG" 2>/dev/null | sed '/^$/q'; then
    exit
fi

if [[ ! -s $ARF_CACHE/packages.txt ]]; then
    echo 'AUR package list not found.' >&2
    exit 1
fi

if ! grep -qx "$PKG" "$ARF_CACHE/packages.txt"; then
    echo "Unknown package: $PKG" >&2
    exit 1
fi

readonly INDENT_WIDTH=18
readonly BOLD=$(tput bold || echo '')
readonly RED=$(tput setaf 1 || echo '')
readonly RESET=$(tput sgr0 || echo '')

tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT
curl -fsSL "https://aur.archlinux.org/rpc/v5/info?arg=$PKG" |
    jq -re --arg red "$RED" --arg bold "$BOLD" --arg reset "$RESET" '
    .results[0]
    | (.. | arrays) |= join("  ")
    | (.FirstSubmitted, .LastModified) |=
        if . != null then (tonumber | strftime("%c")) else "None" end
    | if .OutOfDate? then
        .Version += " " + $red + "Out-of-date (" +
        (.OutOfDate | tonumber | strftime("%Y-%m-%d")) + ")" + $reset
      else . end
    | .Maintainer //= ($red + "Orphan" + $reset) as $p |
    [
        "\($bold)Repository\($reset)      : AUR",
        "\($bold)Package Base\($reset)    : \($p.PackageBase // "None")",
        "\($bold)Version\($reset)         : \($p.Version // "None")",
        "\($bold)Description\($reset)     : \($p.Description // "None")",
        "\($bold)Upstream URL\($reset)    : \($p.URL // "None")",
        "\($bold)Licenses\($reset)        : \($p.License // "None")",
        "\($bold)Provides\($reset)        : \($p.Provides // "None")",
        "\($bold)Conflicts With\($reset)  : \($p.Conflicts // "None")",
        "\($bold)Depends On\($reset)      : \($p.Depends // "None")",
        "\($bold)Optional Deps\($reset)   : \($p.OptDepends // "None")",
        "\($bold)Make Deps\($reset)       : \($p.MakeDepends // "None")",
        "\($bold)Submitter\($reset)       : \($p.Submitter // "None")",
        "\($bold)Maintainer\($reset)      : \($p.Maintainer // "None")",
        "\($bold)Votes\($reset)           : \($p.NumVotes // "None")",
        "\($bold)Popularity\($reset)      : \($p.Popularity // "None")",
        "\($bold)First Submitted\($reset) : \($p.FirstSubmitted // "None")",
        "\($bold)Last Modified\($reset)   : \($p.LastModified // "None")"
    ]
    | .[]
' >"$tmp_file"

mkdir -p "$ARF_CACHE/info"
mv "$tmp_file" "$FILE"

while read line; do
     printf "%s\n" "$line" |
        fold -s -w $((COLUMNS - INDENT_WIDTH)) |
        sed -e '2,$s/^ //' -e "1!s/^/$(printf '%*s' $INDENT_WIDTH "")/"
done <"$FILE"
