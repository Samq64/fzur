#!/usr/bin/env bash
# Requirements: curl, jq

set -euo pipefail
dir=${XDG_CACHE_HOME:-$HOME/.cache}/fzur/info
cols=${FZF_PREVIEW_COLUMNS:-$(tput cols)}
bold=$(tput bold)
red=$(tput setaf 1)
reset=$(tput sgr0)

if [ $# -ne 1 ]; then
    echo "Usage: $0 package-name" && exit 1
fi

mkdir -p "$dir"
cd "$dir"

if [ "$(find "$1.json" -mtime -1 2>/dev/null)" ]; then
    info=$(cat "$1.json")
else
    # Download the package info and flatten the arrays into comma separeated strings
    info=$(curl -s "https://aur.archlinux.org/rpc/v5/info?arg=$1" \
        | jq -c '.["results"][0] | (.. | arrays) |= join(", ")')

    if [ "$info" = null ]; then
        echo "${red}Failed to fetch package information for $1.$reset"
        exit 1
    fi
    echo "$info" > "$1.json"
fi

get() {
    local val
    val=$(jq --arg key "$1" -r '.[$key]' <<< "$info")
    [ "$val" = null ] && val=None
    echo "$val"
}

maintainer=$(get Maintainer)
[ "$maintainer" = None ] && maintainer=${red}Orphan${reset}

version_label=$(get Version)
outdated_timestamp=$(get OutOfDate)
if [ "$outdated_timestamp" != None ]; then
    version_label+=" ${red}Out-of-date ($(date -d @"${outdated_timestamp}" +%F))$reset"
fi

# https://stackoverflow.com/a/58893261
# TODO: Wrap words instead of characters
cat <<EOF | column -t -s '|' -c "$cols" \
    --table-columns C1,C2 --table-noheadings --table-wrap C2
${bold}Repository${reset}|: AUR
${bold}Package Base${reset}|: $(get PackageBase)
${bold}Version${reset}|: $version_label
${bold}Description${reset}|: $(get Description)
${bold}Upstream URL${reset}|: $(get URL)
${bold}Licenses${reset}|: $(get License)
${bold}Provides${reset}|: $(get Provides)
${bold}Conflicts With${reset}|: $(get Conflicts)
${bold}Depends On${reset}|: $(get Depends)
${bold}Optional Deps${reset}|: $(get OptDepends)
${bold}Make Deps${reset}|: $(get MakeDepends)
${bold}Submitter${reset}|: $(get Submitter)
${bold}Maintainer${reset}|: $maintainer
${bold}Votes${reset}|: $(get NumVotes)
${bold}Popularity${reset}|: $(get Popularity)
${bold}First Submitted${reset}|: $(date -d @"$(get FirstSubmitted)")
${bold}Last Modified${reset}|: $(date -d @"$(get LastModified)")
EOF
