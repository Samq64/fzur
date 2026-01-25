#!/usr/bin/env python3
import re
import requests
import sys
from os import environ
from pathlib import Path
from pyalpm import Handle, SIG_DATABASE
from pycman.config import PacmanConfig
from subprocess import run
from time import time

DEP_PATTERN = re.compile(r"^\s*(?:check|make)?depends = ([\w\-.]+)")
CACHE_DIR = Path(environ["ARF_CACHE"])
PKGS_DIR = CACHE_DIR / "pkgbuild"
PKGS_DIR.mkdir(parents=True, exist_ok=True)
MAX_AGE = 3600  # 1 hour

alpm_handle = PacmanConfig('/etc/pacman.conf').initialize_alpm()
localdb = alpm_handle.get_localdb()


def syncdb_has(pkg):
    return any(db.get_pkg(pkg) for db in alpm_handle.get_syncdbs())


def aur_has(pkg):
    with open(f"{CACHE_DIR}/packages.txt", "r") as f:
        return any(pkg == line.rstrip("\n") for line in f)


def repo_is_fresh(repo):
    f = repo / ".git" / "FETCH_HEAD"
    if not f.exists():
        file = repo / ".git" / "HEAD"
    return time() - f.stat().st_mtime < MAX_AGE


def fetch_dependencies(pkg):
    repo = PKGS_DIR / pkg

    if repo.is_dir():
        if not repo_is_fresh(repo):
            print(f"Pulling {pkg}...", file=sys.stderr)
            run(["git", "pull", "-q", "--ff-only"], cwd=repo, check=True)
    else:
        if not aur_has(pkg):
            raise RuntimeError(f"{pkg} is not an AUR package.")

        print(f"Cloning {pkg}...", file=sys.stderr)
        run(
            ["git", "clone", "-q", f"https://aur.archlinux.org/{pkg}.git"],
            cwd=PKGS_DIR,
            check=True,
        )

    with open(repo / ".SRCINFO", "r") as f:
        return [m.group(1) for line in f if (m := DEP_PATTERN.match(line))]


def aur_provider(pkg_name):
    if aur_has(pkg_name):
        return pkg_name

    r = requests.get(
        "https://aur.archlinux.org/rpc/v5/search",
        params={"by": "provides", "arg": pkg_name},
        timeout=10,
    )
    r.raise_for_status()

    providers = [p["Name"] for p in r.json().get("results", [])]
    if not providers:
        return None
    if len(providers) == 1:
        return providers[0]

    result = run(
        ["fzf", "--header", f"Select a package to provide {pkg_name}"],
        input="\n".join(providers),
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() or None


def resolve(targets):
    resolved = set()
    resolving = set()
    pacman_pkgs = set()
    order = []

    def visit(pkg):
        if pkg in resolved:
            return

        if pkg in resolving:
            print(f"WARNING: Dependency cycle detected for {pkg}", file=sys.stderr)
            return

        if syncdb_has(pkg):
            pacman_pkgs.add(pkg)
            resolved.add(pkg)
            return

        resolving.add(pkg)

        for dep in fetch_dependencies(pkg):
            if localdb.get_pkg(dep) or dep in resolved:
                continue

            if syncdb_has(dep):
                pacman_pkgs.add(dep)
                continue

            provider = aur_provider(dep)
            if not provider:
                raise RuntimeError(f"Unsatisfied dependency: {dep}")
            visit(provider)

        resolving.remove(pkg)
        resolved.add(pkg)
        order.append(pkg)

    for pkg in targets:
        visit(pkg)

    for pkg in pacman_pkgs:
        print(f"PACMAN {pkg}")
    for pkg in order:
        print(f"AUR {pkg}")


def main():
    resolve(sys.argv[1:])


if __name__ == "__main__":
    main()
