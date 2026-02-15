# Arf

Arf is an fzf Pacman wrapper and AUR helper.

## Features

- Review all build scripts at once with fzf previews
- Edit PKGBUILD with Ctrl+E
- fzf driven package provider and group prompts
- Option to update all development (`-git`) packages
- Minimal installation confirmations
- No AUR dependencies

## Installation
```sh
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/arf-git.git
cd arf-git
makepkg -si
```

## Usage

The default behaviour is to install packages interactively. Run `arf --help` for a list of subcommands. Each subcommand also has a `--help` flag.
