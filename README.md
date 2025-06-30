# Fzur

This is Fzur, which stands for **fz**f A**UR**. It is a couple of bash scripts made to simplify the process of searching for, installing and updating packages from the [Arch User Repository](https://aur.archlinux.org), which is a large collection of build scripts often referred to as [PKGBUILDs](https://wiki.archlinux.org/title/PKGBUILD) for Arch Linux. It uses the [fzf](https://github.com/junegunn/fzf) fuzzy finder tool for interactively selecting packages and previewing information about them. It is not dependant on other AUR tools.

## Requirements

Assuming `sudo` is already installed, the dependencies can be installed on Arch Linux with:

```sh
sudo pacman -S --needed base-devel curl fzf git jq
```

After that, `fzur` and `fzf-info` can simply be copied to `/usr/local/bin` or somewhere else in the `$PATH` environment variable until this tool is itself submitted as an AUR package.

## Usage of Fzur

Fzur can be run run on its own which will open the installation menu or with one of the following options as the first argument: clean, install, remove, sync, update. Multiple packages may be selected with the tab key. Additionally [makepkg flags](https://man.archlinux.org/man/makepkg.8) may be passed as arguments after the install or update options.

The --clean option removes all installed orphaned packages and PKGBUILD repositories for packages that are not installed.

The --install option is the default which downloads the list of all AUR packages, if it does not already exist, and presents an fzf menu listing them all along with the official packages to filter through. Information about each package is displayed in the right pane using the `fzur-info` script which will be explained below.

After the package selection, all of their dependencies will be determined and installed at once. Afterwards another fzf menu will appear, this time to review the AUR PKGBUILDs (build scripts) which can accepted as a group with enter, or the installation can be cancelled with escape. Finally all the AUR packages are installed without further user interaction until the final installation prompt for the built packages.

The --remove option opens an fzf menu and runs `pacman -Rns` on the selected packages. 

The --sync option deletes the AUR package information cache and re-downloads the list of packages on the AUR.

The --update option prompts to run `pacman -Syu` and then checks all installed AUR packages including ones installed with another tool for updates and presents an fzf menu to choose which ones to accept. The rest of the process is similar to the installation of those packages.

## Usage of fzur-info

This script displays information about the provided package such as its version, license and dependencies. For AUR packages the information is downloaded from the AUR's remote procedure call (RPC) interface and then cached for 1 day.

`fzur-info` may be run separately from the rest of Fzur and accepts a package name as its only argument, for example: `fzur-info firefox-nightly`.

## Design choices

### Package sorting

When opening the package selection menu, it is sorted alphabetically but fzf does its own sorting when filtering. The reason AUR packages are not sorted by popularity is so only a 450KB compressed package list needs to be initially downloaded instead of 8MB+ of compressed JSON. Afterwards the information for each individual package can be fetched and cached as needed. It also generally makes things feel snappier as parsing 40MB+ of (uncompressed) JSON can be slow and splitting things up into different files would use a little more disk space on top of that.

### Fewer interactions

Fzur tries to reduce the number of interactions needed when installing or updating packages. This is done by determining the dependencies beforehand and installing all necessary packages form the official repositories first, including build dependencies. Afterwards a prompt is shown to review all PKGBUILDs at once, and finally a confirmation to install the built AUR packages.

### Stand-alone scripts

There are other tools and even fairly simple command chains that can achieve the majority of Fzur's functionality, however the ones I found all depend on [Paru](https://github.com/Morganamilo/paru) or [Yay](https://github.com/Jguer/yay) which are both 8MB+ programs that need to be compiled from the AUR.

Fzur, on the other hand only has a few dependencies, none of which are from the AUR and since it is just a couple of shell scripts it does not need to be compiled. It was also a great opportunity for me to expand my shell scripting knowledge.

## Main resources used

- [FreeCodeCamp Bash Scripting Tutorial](https://youtu.be/tK9Oc6AEnR4)
- [play.jqlang.org](https://play.jqlang.org/)
- [Regex101](https://regex101.com/)
- https://wiki.archlinux.org/title/AUR_helper
- https://wiki.archlinux.org/title/Aurweb_RPC_interface
- https://wiki.archlinux.org/title/Pacman/Tips_and_tricks
- https://wiki.archlinux.org/title/.SRCINFO
