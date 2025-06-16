# fzur - fzf AUR

A work in progress AUR helper with an fzf interface.

### Requirements

- base-devel
- curl
- fzf
- git
- jq

### Usage

```
--install   -i  Select an AUR package for installation using fzf
--update    -u  Update all installed AUR packages
--clean     -c  Clears the cache including all PKGBUILD repositories
```

The list of AUR packages will be downloaded on first run.
