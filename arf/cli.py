import sys
from argparse import ArgumentParser
from arf.exceptions import ArfException, SrcinfoParseError
from arf.format import print_error, print_srcinfo_errors
from arf.main import (
    cmd_install,
    cmd_update,
    cmd_remove,
    cmd_clean,
    cmd_sync,
    cmd_reason,
)


def add_aur_flags(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-a", "--aur-only", dest="aur_only", action="store_true")
    group.add_argument("-A", "--no-aur", dest="no_aur", action="store_true")
    parser.add_argument("--mflags", help="A string of flags to pass to makepkg")


def parse_args():
    parser = ArgumentParser(prog="arf", description="Arf: an fzf Pacman wrapper and AUR helper")
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser(
        "install",
        aliases=["i"],
        help="Install packages (default, interactive if none specified)",
    )
    install.add_argument("packages", nargs="*", help="Packages to install (opens fzf if omitted)")
    add_aur_flags(install)
    install.set_defaults(func=cmd_install)

    update = subparsers.add_parser("update", aliases=["u"], help="Update system and AUR packages")
    add_aur_flags(update)
    update.add_argument(
        "-d",
        "--devel",
        action="store_true",
        help="Update all development (-git) packages",
    )
    update.set_defaults(func=cmd_update)

    remove = subparsers.add_parser(
        "remove", aliases=["r"], help="Remove packages (interactive if none specified)"
    )
    remove.add_argument("-c", "--cascade", action="store_true", help="Remove all dependent packages")
    remove.add_argument("packages", nargs="*", help="Packages to remove (opens fzf if omitted)")
    remove.set_defaults(func=cmd_remove)

    reason = subparsers.add_parser(
        "reason", help="Change the installation reason of packages (interactive if none specified)"
    )
    reason.set_defaults(func=cmd_reason)
    reason.add_argument(
        "packages", nargs="*", help="Packages to set install reason on (opens fzf if omitted)"
    )
    group = reason.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-d", "--asdeps", action="store_true", help="Mark as dependencies of another package"
    )
    group.add_argument(
        "-e", "--asexplicit", action="store_true", help="Mark as explicitly installed by the user"
    )

    clean = subparsers.add_parser("clean", aliases=["c"], help="Remove orphans and clean cache")
    clean.set_defaults(func=cmd_clean)

    sync = subparsers.add_parser("sync", aliases=["s"], help="Refresh AUR metadata")
    sync.set_defaults(func=cmd_sync)

    return parser.parse_args(["install"] if len(sys.argv) == 1 else None)


def main():
    args = parse_args()
    try:
        args.func(args)

    except SrcinfoParseError as e:
        print_error(str(e))
        print_srcinfo_errors(e.errors)
        sys.exit(1)

    except ArfException as e:
        print_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
