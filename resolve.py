#!/usr/bin/env python3
import re
import requests
import sys
from graphlib import TopologicalSorter, CycleError
from os import environ
from pathlib import Path
from pyalpm import Handle, SIG_DATABASE
from pycman.config import PacmanConfig
from subprocess import run, DEVNULL
from time import time

DEP_PATTERN = re.compile(r"^\s*(?:check|make)?depends = ([\w\-.]+)")
CACHE_DIR = Path(environ["ARF_CACHE"])
PKGS_DIR = CACHE_DIR / "pkgbuild"
PKGS_DIR.mkdir(parents=True, exist_ok=True)
MAX_AGE = 3600  # 1 hour

config = PacmanConfig('/etc/pacman.conf')
handle = config.initialize_alpm()
localdb = handle.get_localdb()


def repos_have(pkg):
    return any(db.get_pkg(pkg) for db in handle.get_syncdbs())


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


def build_graph(targets):
    graph = {}
    seen = set()

    def add_pkg(pkg):
        if pkg in seen:
            return

        seen.add(pkg)
        if repos_have(pkg):
            graph.setdefault(pkg, set())
            return

        deps = []
        for dep in fetch_dependencies(pkg):
            if localdb.get_pkg(pkg):
                continue
            if repos_have(dep):
                graph.setdefault(dep, set())
                continue
            provider = aur_provider(dep)
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

    pacman_pkgs = [p for p in order if repos_have(p)]
    aur_pkgs = [p for p in order if not repos_have(p)]
    for pkg in pacman_pkgs:
        print(f"PACMAN {pkg}")
    for pkg in aur_pkgs:
        print(f"AUR {pkg}")


def main():
    resolve(sys.argv[1:])


if __name__ == "__main__":
    main()
