#!/usr/bin/env bash
# fzur: A standalone fzf AUR helper
# Dependencies: base-devel, curl, fzf, git, jq, pacman, sudo (default privilege elevation)

set -euo pipefail

export FZF_DEFAULT_OPTS='--reverse --header-first --preview-window 75%'
export PACMAN_AUTH=${PACMAN_AUTH:-sudo}
export FZUR_CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/fzur
readonly PKGS_DIR="$FZUR_CACHE/pkgbuild"
readonly BOLD=$(tput bold || echo '')
readonly YELLOW=$(tput setaf 3 || echo '')
readonly RESET=$(tput sgr0 || echo '')

declare -ag pulled_repos pacman_pkgs aur_pkgs review_pkgs
declare -Ag seen_deps

if [[ $0 == *.sh ]]; then
    SCRIPT_DIR=$(realpath "$(dirname "$0")")
else
    SCRIPT_DIR=/usr/lib/fzur
fi

is_installed() {
    pacman -Qqs "^$1$" &>/dev/null
}

is_repo_pkg() {
    pacman -Ssq "^$1$" &>/dev/null
}

download_aur_list() {
    mkdir -p "$FZUR_CACHE"
    cd "$FZUR_CACHE"
    echo 'Downloading AUR package list...'
    curl -fsSL https://aur.archlinux.org/packages.gz | gzip -d >packages.txt
}

update_repo() {
    local pkg=$1

    for repo in "${pulled_repos[@]}"; do
        if [[ $repo = "$pkg" ]]; then
            cd "$PKGS_DIR/$pkg"
            return
        fi
    done

    mkdir -p "$PKGS_DIR"
    cd "$PKGS_DIR"
    if [[ -d $pkg ]]; then
        echo "Pulling $pkg..."
        cd "$pkg"
        git pull --quiet --ff-only
    else
        echo "Cloning $pkg from the AUR..."
        git clone --quiet "https://aur.archlinux.org/$pkg"
        cd "$pkg"
    fi
    pulled_repos+=("$pkg")
}

get_dependencies() {
    [[ ${seen_deps[$1]+x} ]] && return
    seen_deps[$1]=1

    update_repo "$1"
    local dep deps
    deps=$(grep -Po '^\s*(check|make)?depends = \K[\w\-\.]+' .SRCINFO) || true

    for dep in $deps; do
        is_installed "$dep" && continue

        if is_repo_pkg "$dep"; then
            pacman_pkgs+=("$dep")
            continue
        fi

        if grep -Fxq "$dep" "$FZUR_CACHE/packages.txt"; then
            # In the AUR directly
            provider=$dep
        else
            # Provided by another AUR package
            mapfile -t providers < <(
                curl -fsSL "https://aur.archlinux.org/rpc/v5/search?by=provides&arg=$dep" |
                    jq -r '.results[].Name'
            )
            if [[ ${#providers[@]} -eq 1 ]]; then
                provider="${providers[0]}"
            else
                provider=$(printf "%s\n" "${providers[@]}" |
                    fzf --header "Select a package to provide \"$dep\"")
            fi
        fi
        review_pkgs+=("$dep")
        aur_pkgs+=("$provider")
        get_dependencies "$provider"
    done
}

install_pkgs() {
    aur_pkgs=()
    pacman_pkgs=()
    review_pkgs=()
    local pkg
    local skip_review=false
    if [[ $1 = --skip-review ]]; then
        skip_review=true
        shift
    fi

    for pkg in "$@"; do
        if is_repo_pkg "$pkg"; then
            pacman_pkgs+=("$pkg")
        elif grep -Fxq "$pkg" "$FZUR_CACHE/packages.txt"; then
            [[ $skip_review = false ]] && review_pkgs+=("$pkg")
            aur_pkgs+=("$pkg")
            get_dependencies "$pkg"
        else
            echo "Unknown package: $pkg"
            exit 1
        fi
    done

    if [[ ${#pacman_pkgs[@]} -gt 0 ]]; then
        $PACMAN_AUTH pacman -S --asdeps --needed "${pacman_pkgs[@]}"
    fi

    if [[ ${#aur_pkgs[@]} -gt 0 ]]; then
        reversed_aur_pkgs=()
        for ((i = ${#aur_pkgs[@]} - 1; i >= 0; i--)); do
            reversed_aur_pkgs+=("${aur_pkgs[i]}")
        done

        if [[ ${#review_pkgs[@]} -gt 0 ]]; then
            printf "%s\n" "${review_pkgs[@]}" | fzf --preview "$SCRIPT_DIR/diff-preview.sh {1}" \
                --header 'Review PKGBUILDs' --footer 'Enter: Accept all | Esc: Cancel' >/dev/null
        fi

        for pkg in "${reversed_aur_pkgs[@]}"; do
            cd "$PKGS_DIR/$pkg"
            echo -e "\n${BOLD}Installing ${pkg}...\n${RESET}"
            if grep -Fwq "$pkg" <<<"$@"; then
                makepkg -i $makepkg_opts
            else
                makepkg -i --asdeps $makepkg_opts
            fi
        done
    fi
}

select_pkgs() {
    local list pkgs
    [[ -s $FZUR_CACHE/packages.txt ]] || download_aur_list

    if [[ $aur_only = false ]]; then
        list=$(pacman -Ssq | awk '!seen[$0]++') # Remove duplicates from other repos
    fi

    [[ $repos_only = false ]] && list+=$(<"$FZUR_CACHE/packages.txt")

    mapfile -t pkgs < <(
        echo "$list" |
            fzf --multi --header 'Select packages to install' \
                --preview "$SCRIPT_DIR/pkg-preview.sh {1}"
    )

    [[ ${#pkgs[@]} -eq 0 ]] && return
    echo "${BOLD}Selected:${RESET} ${pkgs[*]}"
    install_pkgs "${pkgs[@]}"
}

update_pkgs() {
    [[ $aur_only = false ]] && $PACMAN_AUTH pacman -Syu
    [[ $repos_only = true ]] && return
    local updates=()
    local pkg
    echo "${BOLD}Checking for AUR updates...${RESET}"
    [[ -s $FZUR_CACHE/packages.txt ]] || download_aur_list

    for pkg in $(pacman -Qqm | grep -v '\-debug$'); do
        if ! grep -Fxq "$pkg" "$FZUR_CACHE/packages.txt"; then
            echo "${YELLOW}Skipping unknown package: ${pkg}${RESET}"
            continue
        fi
        update_repo "$pkg"
        local installed new
        installed=$(pacman -Qi "$pkg" | awk '/^Version/{print $3}')
        new=$(awk '/^\s*pkgver/{ver=$3} /^\s*pkgrel/{print ver "-" $3}' .SRCINFO)
        if grep -q epoch .SRCINFO; then
            new="$(awk '/^\s*epoch/{print $3}' .SRCINFO):$new"
        fi
        if [[ $(vercmp "$installed" "$new") -lt 0 || ($update_devel = true && $pkg =~ -git$) ]]; then
            updates+=("$pkg")
        fi
    done

    if [[ ${#updates[@]} -eq 0 ]]; then
        echo "All AUR packages are up to date."
        return
    fi

    local selected
    mapfile -t selected < <(printf "%s\n" "${updates[@]}" | fzf --multi \
        --preview "$SCRIPT_DIR/diff-preview.sh {1}" \
        --header 'Select AUR packages to update' --bind 'load:select-all')
    install_pkgs --skip-review "${selected[@]}"
}

remove() {
    local pkgs=()
    if [[ $# -gt 0 ]]; then
        pkgs=("$@")
    else
        local filter=''
        [[ $aur_only = true ]] && filter='--foreign'
        [[ $repos_only = true ]] && filter='--native'

        mapfile -t pkgs < <(
            pacman -Qqe $filter |
                fzf --multi --header 'Select packages to remove' --preview 'pacman -Qi {1}'
        )
        [[ ${#pkgs[@]} -eq 0 ]] && return
        echo Selected for removal: "${pkgs[@]}"
    fi
    $PACMAN_AUTH pacman -Rns "${pkgs[@]}"
}

clean() {
    local orphans
    orphans=$(pacman -Qdtq || echo '')
    [[ -n $orphans ]] && $PACMAN_AUTH pacman -Rns $orphans

    rm -f "$FZUR_CACHE/packages.txt"
    rm -rf "$FZUR_CACHE/info"

    local pkgs
    pkgs=$(pacman -Qqm)
    [[ -d $PKGS_DIR ]] || return
    for dir in "$PKGS_DIR"/*; do
        local name
        name=$(basename "$dir")
        if ! grep -qx "$name" <<<"$pkgs"; then
            echo "Removing PKGBUILD directory for $name"
            rm -rf "$dir"
        fi
    done
}

show_help() {
    cat <<EOF
Usage: fzur [options] [packages]

-c, --clean     Remove orphaned packages and clear the fzur cache (except used repositories)
-i, --install   Install packages with fzf (default)
-r, --remove    Remove packages and their dependencies with fzf (pacman -Rns)
-s, --sync      Re-download the AUR package list and clear the info cache
-u, --update    Run pacman -Syu and select AUR updates with fzf

-d, --devel     Rebuild all -git packages when passed with --update
-a, --aur       Only list or update AUR packages
--no-aur        Do not list or update AUR packages
--makepkg-flags makepkg flags to be passed when using --install or --update

Packages may be passed to --install or --remove to skip the fzf menu
EOF
}

action=install
aur_only=false
repos_only=false
update_devel=false
makepkg_opts=''
args=$(getopt -n fzur -o acdhirsu \
    --long aur,no-aur,clean,devel,install,help,makepkg-flags:,remove,sync,update \
    -- "$@")

eval set -- "$args"

while true; do
    case $1 in
    -a | --aur)
        aur_only=true
        shift
        ;;
    -c | --clean)
        clean
        exit
        ;;
    -d | --devel)
        update_devel=true
        shift
        ;;
    -h | --help)
        show_help
        exit
        ;;
    -i | --install)
        action=install
        shift
        ;;
    --makepkg-flags)
        makepkg_opts=$2
        shift 2
        ;;
    --no-aur)
        repos_only=true
        shift
        ;;
    -r | --remove)
        action=remove
        shift
        ;;
    -s | --sync)
        rm -rf "$FZUR_CACHE/info"
        download_aur_list
        exit
        ;;
    -u | --update)
        action=update_pkgs
        shift
        ;;
    --)
        shift
        break
        ;;
    *) break ;;
    esac
done

if [[ $action = install ]]; then
    if [[ $# -eq 0 ]]; then
        select_pkgs
    else
        [[ -s $FZUR_CACHE/packages.txt ]] || download_aur_list
        install_pkgs "$@"
    fi
    exit
fi

$action "$@"
