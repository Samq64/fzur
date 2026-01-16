#!/usr/bin/env python3
import re
import requests
import sys
from os import environ
from pathlib import Path
from subprocess import run, DEVNULL

DEP_PATTERN = re.compile(r"^\s*(?:check|make)?depends = ([\w\-.]+)")
PKGS_DIR = Path(environ["FZUR_CACHE"]) / "pkgbuild"
PKGS_DIR.mkdir(parents=True, exist_ok=True)


def pacman_has(pkg, type):
    return run(["pacman", f"-{type}sq", f"^{pkg}$"], stdout=DEVNULL).returncode == 0


def fetch_dependencies(pkg):
    repo = PKGS_DIR / pkg

    if repo.is_dir():
        print(f"Pulling {pkg}...", file=sys.stderr)
        run(["git", "pull", "-q", "--ff-only"], cwd=repo, check=True)
    else:
        print(f"Cloning {pkg}...", file=sys.stderr)
        run(
            ["git", "clone", "-q", f"https://aur.archlinux.org/{pkg}.git"],
            cwd=PKGS_DIR,
            check=True,
        )

    with open(repo / ".SRCINFO", "r") as f:
        return [
            m.group(1)
            for line in f
            if (m :=DEP_PATTERN.match(line))
        ]


def find_provider(pkg_name):
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

        if pacman_has(pkg, "Q"):
            resolved.add(pkg)
            return

        if pacman_has(pkg, "S"):
            pacman_pkgs.add(pkg)
            resolved.add(pkg)
            return

        resolving.add(pkg)

        for dep in fetch_dependencies(pkg):
            if pacman_has(dep, "Q") or dep in resolved:
                continue

            if pacman_has(dep, "S"):
                pacman_pkgs.add(dep)
                continue

            provider = find_provider(dep)
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
