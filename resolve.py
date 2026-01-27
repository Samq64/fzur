#!/usr/bin/env python3
import re
import requests
import sys
from pycman.config import PacmanConfig
from subprocess import run
from time import time

from config import ARF_CACHE, PKGS_DIR
import ui

DEP_PATTERN = re.compile(r"^\s*(?:check|make)?depends = ([\w\-.]+)")
PKGS_DIR.mkdir(parents=True, exist_ok=True)
MAX_AGE = 3600  # 1 hour

alpm_handle = PacmanConfig('/etc/pacman.conf').initialize_alpm()
localdb = alpm_handle.get_localdb()


with open(f"{ARF_CACHE}/packages.txt", "r") as f:
    AUR_PKGS = {line.strip() for line in f}


def syncdb_has(pkg):
    return any(db.search(f"^{pkg}$") for db in alpm_handle.get_syncdbs())


def repo_is_fresh(repo):
    f = repo / ".git" / "FETCH_HEAD"
    if not f.exists():
        f = repo / ".git" / "HEAD"
    return time() - f.stat().st_mtime < MAX_AGE


def fetch_dependencies(pkg):
    repo = PKGS_DIR / pkg

    if repo.is_dir():
        if not repo_is_fresh(repo):
            print(f"Pulling {pkg}...", file=sys.stderr)
            run(["git", "pull", "-q", "--ff-only"], cwd=repo, check=True)
    else:
        if pkg not in AUR_PKGS:
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
    if pkg_name in AUR_PKGS:
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

    return ui.select_one(providers, f"Select a package to provide {pkg_name}")


def resolve(targets):
    resolved = set()
    resolving = set()
    pacman_pkgs = set()
    aur_order = []

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
            if localdb.search(f"^{dep}$") or dep in resolved:
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
        aur_order.append(pkg)

    for pkg in targets:
        visit(pkg)

    return {
        "PACMAN": pacman_pkgs,
        "AUR": aur_order
    }


def main():
    pkgs = resolve(sys.argv[1:])
    for label, group in pkgs.items():
        for pkg in group:
            print(f"{label} {pkg}")


if __name__ == "__main__":
    main()
