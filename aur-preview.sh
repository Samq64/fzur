#!/usr/bin/env bash
set -euo pipefail

bold=$(tput bold)
red=$(tput setaf 1)
reset=$(tput sgr0)

if [ $# -ne 1 ]; then
    echo "Usage: $0 package-name" && exit 1
fi

mkdir -p "$HOME/.cache/fzur/pkginfo"
cd "$HOME/.cache/fzur/pkginfo"

if [ -s "$1.json" ]; then
    # TODO: Invalidate cache after some time
    info=$(cat "$1.json")
else
    # Download the package info and flatten the arrays into comma separeated strings
    info=$(curl -s "https://aur.archlinux.org/rpc/v5/info?arg[]=$1" | jq -c '.["results"][0] | (.. | arrays) |= join(", ")')
    if [ "$info" = null ]; then
        echo "${red}AUR package not found: $1${reset}"
        exit 1
    fi
    echo "$info" > "$1.json"
fi

get() {
    jq --arg key "$1" -r '.[$key]' <<< "$info"
}

maintainer=$(get Maintainer)
[ "$maintainer" = null ] && maintainer=${red}orphan${reset}

version_label=$(get Version)
outdated_timestamp=$(get OutOfDate)
if [ "$outdated_timestamp" != null ]; then
    version_label+=" ${red}out-of-date ($(date -d @"${outdated_timestamp}" +%F))${reset}"
fi

cat << EOF
${bold}Package Base${reset}    $(get PackageBase)
${bold}Description${reset}     $(get Description)
${bold}Version${reset}         $version_label
${bold}Upstream URL${reset}    $(get URL)
${bold}Licenses${reset}        $(get License)
${bold}Conflicts${reset}       $(get Conflicts)
${bold}Provides${reset}        $(get Provides)
${bold}Submitter${reset}       $(get Submitter)
${bold}Maintainer${reset}      $maintainer
${bold}Votes${reset}           $(get NumVotes)
${bold}Popularity${reset}      $(get Popularity)
${bold}Depends On${reset}      $(get Depends)
${bold}Optional Deps${reset}   $(get OptDepends)
${bold}Make Deps${reset}       $(get MakeDepends)
${bold}First Submitted${reset} $(date -d @"$(get FirstSubmitted)")
${bold}Last Modified${reset}   $(date -d @"$(get LastModified)")
EOF

