import re
from arf import fetch
from arf.exceptions import SrcinfoParseError, PackageResolutionError
from arf.format import print_warning
from graphlib import TopologicalSorter
from srcinfo.parse import parse_srcinfo
from typing import NamedTuple


class ResolvedPackages(NamedTuple):
    pacman: list[dict]
    aur: list[list[str]]


class Resolver:
    def __init__(self, alpm, select_provider, select_group):
        self.alpm = alpm
        self.sorter = TopologicalSorter()
        self.select_provider = select_provider
        self.select_group = select_group

        self.resolved = set()
        self.resolving = set()
        self.cycles = set()
        self.provider_cache = {}
        self.dependency_cache = {}
        self.pacman = []

    def strip_version(self, pkg_name: str) -> str:
        return re.split(r"[<>=]", pkg_name, maxsplit=1)[0]

    def fetch_dependencies(self, provider: str) -> set[str]:
        if provider in self.dependency_cache:
            return self.dependency_cache[provider]

        if repo_pkg := self.alpm.get_sync_package(provider):
            deps = set(repo_pkg.depends)
        else:
            repo = fetch.get_repo(provider)
            with open(repo / ".SRCINFO", "r") as f:
                parsed, errors = parse_srcinfo(f.read())
                if errors:
                    raise SrcinfoParseError(provider, errors)
                deps = set(parsed.get("depends", []) + parsed.get("makedepends", []))
                for subpkg in parsed.get("packages", {}).values():
                    deps.update(subpkg.get("depends", []))

        self.dependency_cache[provider] = deps
        return deps

    def resolve_pkg_name(self, pkg: str) -> str | None:
        pkg = self.strip_version(pkg)
        if pkg in self.provider_cache:
            return self.provider_cache[pkg]

        if self.alpm.get_sync_package(pkg):
            return pkg

        repo_providers = self.alpm.get_providers(pkg)
        if repo_providers:
            providers = sorted(repo_providers)
        elif pkg in fetch.package_list():
            return pkg
        else:
            response = fetch.search_rpc(pkg, by="provides")
            providers = sorted({p["Name"] for p in response})

        if not providers:
            return None
        if len(providers) == 1:
            return providers[0]

        selected = self.select_provider(pkg, providers)
        return selected

    def handle_group(self, name: str, members: list) -> None:
        selected = self.select_group(name, members)
        for pkg in selected:
            self.visit(pkg)
        self.resolving.remove(name)
        self.resolved.add(name)

    def visit(self, pkg: str, parent=None) -> None:
        pkg = self.strip_version(pkg)
        if (parent and self.alpm.is_installed(pkg)) or pkg in self.resolved:
            return

        if pkg in self.resolving:
            print_warning(f"Dependency cycle detected for {pkg}")
            self.cycles.add(pkg)
            return

        self.resolving.add(pkg)

        provider = self.resolve_pkg_name(pkg)
        if provider:
            self.provider_cache[pkg] = provider
        elif group_pkgs := self.alpm.get_group(pkg):
            self.handle_group(pkg, group_pkgs)
            return
        else:
            raise PackageResolutionError(pkg, parent)

        deps = self.fetch_dependencies(provider)

        for dep in deps:
            self.visit(dep, parent=pkg)

        self.resolving.remove(pkg)
        self.resolved.add(pkg)

        if self.alpm.get_sync_package(provider):
            self.pacman.append({"name": provider, "dependency": parent is not None})
        else:
            aur_deps = []
            for dep in deps:
                name = self.resolve_pkg_name(dep)
                if not name:
                    continue
                if provider in self.cycles:
                    continue
                if self.alpm.is_installed(name) or self.alpm.get_sync_package(name):
                    continue
                aur_deps.append(name)

            self.sorter.add(provider, *aur_deps)

    def resolve(self, targets: list[str]) -> ResolvedPackages:
        for pkg in targets:
            self.visit(pkg)

        layers = []
        self.sorter.prepare()
        while self.sorter.is_active():
            ready = self.sorter.get_ready()
            layers.append(list(ready))
            self.sorter.done(*ready)

        return ResolvedPackages(pacman=self.pacman, aur=layers)
