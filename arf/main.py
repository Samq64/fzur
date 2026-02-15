import itertools
import shlex
import shutil
import subprocess
import sys
from arf import ui
from arf.alpm import Alpm
from arf.config import ARF_CACHE, EXCLUDE_PACKAGE_PATTERN, PACMAN_AUTH, PKGS_DIR
from arf.exceptions import SrcinfoParseError
from arf.fetch import download_package_list, get_repo, package_list
from arf.format import Colors, print_step, print_error, print_warning
from arf.resolve import Resolver
from pyalpm import vercmp
from srcinfo.parse import parse_srcinfo

alpm = Alpm()


def run_command(cmd, cwd=None):
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except KeyboardInterrupt:
        sys.exit(130)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


def run_pacman(args):
    run_command([PACMAN_AUTH, "pacman", *args])


def get_pkg_archives(repo):
    proc = subprocess.run(
        ["makepkg", "--packagelist"], text=True, capture_output=True, cwd=str(repo)
    )
    packages = proc.stdout.strip().splitlines()
    return [pkg for pkg in packages if not EXCLUDE_PACKAGE_PATTERN.match(pkg)]


def aur_batch_install(aur_pkgs, asdeps=True, flags=None):
    built = []

    makepkg_cmd = ["makepkg"]
    if asdeps:
        makepkg_cmd.append("--asdeps")
    if flags:
        makepkg_cmd += [*flags]

    for pkg in aur_pkgs:
        print_step(f"Installing AUR package: {pkg}", pad=True)
        repo = get_repo(pkg)
        run_command(makepkg_cmd, cwd=repo)
        built += get_pkg_archives(repo)

    run_pacman(["-U", *built])


def install_packages(packages, makepkg_flags=None, skip=None):
    skip = skip or []

    print_step("Resolving dependencies...")
    resolver = Resolver(alpm, ui.provider_prompt, ui.group_prompt)
    pacman, aur = resolver.resolve(packages)

    pacman_names = [p["name"] for p in pacman]
    pacman_deps = [p["name"] for p in pacman if p.get("dependency")]
    all_aur = list(itertools.chain(*aur))
    needs_review = [pkg for pkg in all_aur if pkg not in skip]

    if needs_review and not ui.review_prompt(needs_review):
        return

    if pacman:
        print_step("Installing Pacman packages...")
        run_pacman(["-S", "--needed", *pacman_names])
        if pacman_deps:
            run_pacman(["-Dq", "--asdeps", *pacman_deps])
    if aur:
        flags = shlex.split(makepkg_flags) if makepkg_flags else []
        for group in aur:
            asdeps = group == aur[-1]
            aur_batch_install(group, asdeps=asdeps, flags=flags)


def cmd_install(args):
    packages = args.packages
    if not packages:
        items = []
        if not args.aur_only:
            items += sorted(alpm.all_sync_packages())
        if not args.no_aur:
            aur_packages = sorted(package_list())
            if items:
                items += [Colors.DIM + pkg + Colors.RESET for pkg in aur_packages]
            else:
                items += aur_packages
        packages = ui.select(
            items,
            "Select packages to install",
            preview="package.sh",
        )

    if packages:
        install_packages(packages, makepkg_flags=args.mflags)


def cmd_update(args):
    if not args.aur_only:
        run_pacman(["-Syu"])
    if not args.no_aur:
        updates = []
        print_step("Checking for AUR updates...")
        aur_pkgs = package_list()

        for pkg in alpm.foreign_packages():
            if pkg.endswith("-debug"):
                continue
            if pkg not in aur_pkgs:
                print_warning(f"Skipping unknown package: {pkg}")
                continue
            path = get_repo(pkg)
            with open(path / ".SRCINFO", "r") as f:
                srcinfo, errors = parse_srcinfo(f.read())
                if errors:
                    raise SrcinfoParseError(pkg, errors)

            installed_version = alpm.get_local_package(pkg).version
            new_version = srcinfo["pkgver"] + "-" + srcinfo["pkgrel"]
            if vercmp(installed_version, new_version) < 0 or (args.devel and pkg.endswith("-git")):
                updates.append(pkg)

        if not updates:
            print("All AUR packages are up to date.")
            return

        selected = ui.select(updates, "Select AUR packages to update", preview="diff.sh", all=True)
        if selected:
            install_packages(selected, skip=selected, makepkg_flags=args.mflags)


def cmd_remove(args):
    if args.packages:
        packages = args.packages
    else:
        items = sorted(alpm.explicit_not_required())
        packages = ui.select(
            items,
            "Select packages to remove",
            preview="COLUMNS=$FZF_PREVIEW_COLUMNS pacman -Qi",
        )
    if packages:
        run_pacman(["-Rns", *packages])


def cmd_clean(args):
    orphans = alpm.orphans()
    if orphans:
        print_step("Removing orphaned packages...")
        run_pacman(["-Rns", *orphans])

    if not PKGS_DIR.is_dir():
        return

    print_step("Cleaning Arf's cache...")

    foreign = alpm.foreign_packages()
    for subdir in PKGS_DIR.iterdir():
        name = subdir.name
        if name not in foreign:
            try:
                shutil.rmtree(subdir)
                print(f" Removed PKGBUILD directory for {name}")
            except PermissionError as e:
                print_error(str(e))


def cmd_sync(args):
    shutil.rmtree(ARF_CACHE / "info", ignore_errors=True)
    download_package_list(force=True)
