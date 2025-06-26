# fzur - fzf AUR

fzur (**fz**f A**UR**) is an [AUR helper](https://wiki.archlinux.org/title/AUR_helper) with an [fzf](https://github.com/junegunn/fzf) interface that does not rely on other AUR tools. It currently only handles AUR packages and dependencies, but it may become a [Pacman](https://wiki.archlinux.org/title/Pacman) wrapper in the future.

## Design choices

### Shell scripts

I didn't realize the majority of the functionality could be done with a single line using Yay. I did notice a couple more complicated wrappers, but they still relied on [Yay](https://github.com/Jguer/yay) or [Paru](https://github.com/Morganamilo/paru) which are both compiled programs over 8MB. They are good tools and definitely worth using for the extra functionality, and I know shell scripts are inefficient in other ways but I had already stared this project before I knew and now that it is here why add another software layer?

### Package sorting

When opening the package selection menu it is sorted alphabetically but fzf does its own sorting when filtering. The reason it is not sorted by popularity is so only a 450KB compressed package list needs to be initially downloaded instead of 8MB+ of compressed JSON. Afterwards the information for each individual package can be fetched and cached as needed. It also generally makes things feel snappier as parsing 40MB+ of (uncompressed) JSON can be slow and splitting things up into different files would use even more disk space.

## Requirements

Assuming sudo is already installed the dependencies can be installed with:

```sh
sudo pacman -S --needed base-devel curl fzf git jq
```

After that `fzur` and `aur-info.sh` can simply be copied to `/usr/local/bin` or somewhere else in the $PATH until this is submitted as an AUR package.

## Usage

By default fzur will open the installation menu and download the list of all AUR packages if it does not already exist.

```
-i, --install   Select and install AUR packages with fzf
-u, --update    Select and update AUR packages with fzf
-s, --sync      Re-download the AUR package list and clear the info cache
-c, --clean     Clear the cache including all PKGBUILD repositories
```

When using `--install` or `--update` additional flags may be passed to [makepkg](https://wiki.archlinux.org/title/Makepkg).

The preview can also be run separately with `aur-info.sh pkg-name`.

## Future plans

- Proper split package support
- Use an fzf for reviewing PKGBUILDs
- Turn this into a full Pacman wrapper
  - Show repository and AUR packages together by default
  - Package removal
  - Easy orphaned package cleaning
- Better error handling, for example when a package does not come from the AUR or official repositories
- Don't exit entirely when a single PKGBUILD is rejected

## Resources

- [FreeCodeCamp Bash Scripting Tutorial](https://youtu.be/tK9Oc6AEnR4)
- [play.jqlang.org](https://play.jqlang.org/)
- [Regex101](https://regex101.com/)
- https://wiki.archlinux.org/title/AUR_helper
- https://wiki.archlinux.org/title/Aurweb_RPC_interface
- https://wiki.archlinux.org/title/.SRCINFO
