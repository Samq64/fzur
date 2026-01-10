#!/usr/bin/env bash
# Prints information about an AUR or official Arch package.
# Requirements: curl, jq

set -euo pipefail
COLUMNS=$FZF_PREVIEW_COLUMNS
readonly INDENT_WIDTH=18
readonly PKG=$1
readonly JSON_FILE="$CACHE_DIR/info/$PKG.json"
readonly BOLD=$(tput bold || echo '')
readonly RED=$(tput setaf 1 || echo '')
readonly RESET=$(tput sgr0 || echo '')

declare -ra KEY_ORDER=(
    PackageBase Version Description URL License Provides Conflicts
    Depends OptDepends MakeDepends Submitter Maintainer NumVotes
    Popularity FirstSubmitted LastModified
)

declare -rA LABELS=(
    [PackageBase]='Package Base'
    [Version]='Version'
    [Description]='Description'
    [URL]='Upstream URL'
    [License]='Licenses'
    [Provides]='Provides'
    [Conflicts]='Conflicts With'
    [Depends]='Depends On'
    [OptDepends]='Optional Deps'
    [MakeDepends]='Make Deps'
    [Submitter]='Submitter'
    [Maintainer]='Maintainer'
    [NumVotes]='Votes'
    [Popularity]='Popularity'
    [FirstSubmitted]='First Submitted'
    [LastModified]='Last Modified'
)

cache_is_fresh() {
    [[ -f "$1" && $(find "$1" -mtime -1) ]]
}

print_key_value() {
    local label=$1 value=$2
    printf "%b%-*s%b : " "$BOLD" $((INDENT_WIDTH - 3)) "$label" "$RESET"
    printf "%s\n" "$value" |
        fold -s -w $((COLUMNS - INDENT_WIDTH)) |
        sed -e '2,$s/^ //' \
            -e "1!s/^/$(printf '%*s' $INDENT_WIDTH "")/"
}

if [[ ! -s $CACHE_DIR/packages.txt ]]; then
    echo 'AUR package list not found.' >&2
    exit 1
fi

if ! grep -qx "$PKG" "$CACHE_DIR/packages.txt"; then
    pacman -Si --color=always "$PKG"
    exit
fi

jq_keys=$(printf '%s\n' "${KEY_ORDER[@]}" | jq -R . | jq -s .)

if ! cache_is_fresh "$JSON_FILE"; then
    tmp_json=$(mktemp)
    trap 'rm -f "$tmp_json"' EXIT
    curl -fsSL "https://aur.archlinux.org/rpc/v5/info?arg=$PKG" |
        jq -ce --arg red "$RED" --arg reset "$RESET" --argjson keys "$jq_keys" '
        .results[0]
        | (.. | arrays) |= join("  ")
        | (.FirstSubmitted, .LastModified) |=
            if . != null then (tonumber | strftime("%c")) else . end
        | if .OutOfDate? then
            .Version += " " + $red + "Out-of-date (" +
            (.OutOfDate | tonumber | strftime("%Y-%m-%d")) + ")" + $reset
          else . end
        | .Maintainer //= ($red + "Orphan" + $reset)
        | with_entries(select((.key as $k | $keys | index($k)) and (.value != null)))
    ' >"$tmp_json"
    mkdir -p "$CACHE_DIR/info"
    mv "$tmp_json" "$JSON_FILE"
fi

print_key_value "Repository" "AUR"

mapfile -t values < <(
    jq -r --argjson keys "$jq_keys" '
    $keys[] as $k | (.[$k] // "None")' <"$JSON_FILE"
)

for i in "${!KEY_ORDER[@]}"; do
    key="${KEY_ORDER[i]}"
    print_key_value "${LABELS[$key]}" "${values[i]}"
done
