from os import environ
from pathlib import Path

ARF_CACHE = Path(environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "arf"
PKGS_DIR = ARF_CACHE / "pkgbuild"

FZF_OPTS = ["fzf", "--reverse", "--header-first", "--preview-window=75%"]
EDITOR = environ.get("EDITOR", "nano")
PACMAN_AUTH = environ.get("PACMAN_AUTH", "sudo")
