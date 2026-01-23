#!/usr/bin/env python3
import re
import requests
import sys
from graphlib import TopologicalSorter, CycleError
from os import environ
from pathlib import Path
from subprocess import run, DEVNULL
from time import time

DEP_PATTERN = re.compile(r"^\s*(?:check|make)?depends = ([\w\-.]+)")
CACHE_DIR = Path(environ["ARF_CACHE"])
PKGS_DIR = CACHE_DIR / "pkgbuild"
PKGS_DIR.mkdir(parents=True, exist_ok=True)
MAX_AGE = 3600  # 1 hour
pacman_cache = {}


def pacman_has(pkg, scope):
    key = (pkg, scope)
    if key not in pacman_cache:
        pacman_cache[key] = (
            run(["pacman", f"-{scope}sq", f"^{pkg}$"], stdout=DEVNULL).returncode == 0
        )
    return pacman_cache[key]


def repo_is_fresh(repo):
    try:
        head = repo / ".git" / "FETCH_HEAD"
        return time() - head.stat().st_mtime < MAX_AGE
    except FileNotFoundError:
        return False


def fetch_dependencies(pkg):
    repo = PKGS_DIR / pkg

    if repo.is_dir():
        if not repo_is_fresh(repo):
            print(f"Pulling {pkg}...", file=sys.stderr)
            run(["git", "pull", "-q", "--ff-only"], cwd=repo, check=True)
    else:
        with open(f"{CACHE_DIR}/packages.txt", "r") as f:
            if not any(pkg == line.rstrip("\n") for line in f):
                raise RuntimeError(f"{pkg} is not an AUR package.")

        print(f"Cloning {pkg}...", file=sys.stderr)
        run(
            ["git", "clone", "-q", f"https://aur.archlinux.org/{pkg}.git"],
            cwd=PKGS_DIR,
            check=True,
        )

    with open(repo / ".SRCINFO", "r") as f:
        return [m.group(1) for line in f if (m := DEP_PATTERN.match(line))]


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


def build_graph(targets):
    graph = {}
    seen = set()

    def add_pkg(pkg):
        if pkg in seen:
            return

        seen.add(pkg)
        if pacman_has(pkg, "S"):
            graph.setdefault(pkg, set())
            return

        deps = []
        for dep in fetch_dependencies(pkg):
            if pacman_has(dep, "Q") or pacman_has(dep, "S"):
                continue
            provider = find_provider(dep)
            if not provider:
                raise RuntimeError(f"Unsatisfied dependency: {dep}")
            deps.append(provider)

        graph[pkg] = set(deps)
        for d in deps:
            add_pkg(d)

    for t in targets:
        add_pkg(t)
    return graph


def resolve(targets):
    graph = build_graph(targets)
    ts = TopologicalSorter(graph)

    try:
        order = list(ts.static_order())
    except CycleError as e:
        print(f"WARNING: dependency cycle detected, {e}", file=sys.stderr)
        for node, deps in graph.copy().items():
             graph[node] = {d for d in deps if node not in graph.get(d, ())}

        ts = TopologicalSorter(graph)
        order = list(ts.static_order())

    pacman_pkgs = [p for p in order if pacman_has(p, "S")]
    aur_pkgs = [p for p in order if not pacman_has(p, "S")]
    for pkg in pacman_pkgs:
        print(f"PACMAN {pkg}")
    for pkg in aur_pkgs:
        print(f"AUR {pkg}")


def main():
    resolve(sys.argv[1:])


if __name__ == "__main__":
    main()
