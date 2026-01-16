#!/usr/bin/env python3
import os
import re
import requests
import sys
from pathlib import Path
from subprocess import run


def fetch_dependencies(pkg):
    PKGS_DIR = Path.home() / ".cache/fzur/pkgbuild"
    pattern = re.compile(r'^\s*(?:check|make)?depends = ([\w\-.]+)')
    deps = []

    if Path(PKGS_DIR / pkg).is_dir():
        print(f"Pulling {pkg}...", file=sys.stderr)
        run(
            ["git", "pull", "-q", "--ff-only"],
            cwd=PKGS_DIR / pkg,
            check=True
        )
    else:
        print(f"Cloning {pkg}...", file=sys.stderr)
        run(
            ["git", "clone", "-q", f"https://aur.archlinux.org/{pkg}.git"],
            cwd=PKGS_DIR,
            check=True
        )

    with open(PKGS_DIR / pkg / ".SRCINFO", "r") as f:
        for line in f:
            match = pattern.match(line)
            if match:
                deps.append(match.group(1))
    return deps


def find_provider(pkg_name):
    r = requests.get(
        "https://aur.archlinux.org/rpc/v5/search",
        params={"by": "provides", "arg": pkg_name},
        timeout=10
    )

    r.raise_for_status()
    results = r.json().get("results", [])
    providers = [pkg["Name"] for pkg in results]

    if not providers:
        return None

    if len(providers) == 1:
        return providers[0]

    cmd = run(
        ["fzf"],
        input="\n".join(providers),
        text=True,
        capture_output=True
    )
    selection = cmd.stdout.strip()
    return selection if selection else None


def resolve(targets):
    resolved = set()
    resolving = set()
    pacman_pkgs = set()
    order = []

    def is_resolved(pkg):
        if pkg in pacman_pkgs or pkg in resolved:
            return True
        result = run(["pacman", "-Qqs", f"^{pkg}$"], stdout=subprocess.DEVNULL)
        if result.returncode == 0:
            return True
        return False

    def visit(pkg):
        if is_resolved(pkg):
            return
        if pkg in resolving:
            raise RuntimeError(f"Dependency cycle detected: {pkg}")

        resolving.add(pkg)
        deps = fetch_dependencies(pkg)

        for dep in deps:
            if is_resolved(dep):
                continue

            result = run(["pacman", "-Ssq", f"^{dep}$"], stdout=subprocess.DEVNULL)
            if result.returncode == 0:
                pacman_pkgs.add(dep)
            else:
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
