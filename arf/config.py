from os import environ
import re
from importlib.resources import files
from pathlib import Path

ARF_CACHE = Path(environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "arf"
PKGS_DIR = ARF_CACHE / "pkgbuild"
EDITOR = environ.get("EDITOR", "nano")
PACMAN_AUTH = environ.get("PACMAN_AUTH", "sudo")
DEFAULT_FZF_CMD = ["fzf", "--ansi", "--reverse", "--header-first", "--preview-window=75%"]
PREVIEW_SCRIPTS = files("arf").joinpath("previews")
EXCLUDE_PACKAGE_PATTERN = re.compile(r".*-(bin-debug.*|debug-.+-any)\.pkg\.tar\.zst")
VCS_SUFFIXES = ("-git", "-svn", "-hg", "-bzr", "-cvs")
