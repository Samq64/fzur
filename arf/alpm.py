import pyalpm
from arf.format import print_warning
from pycman.config import PacmanConfig
from re import escape


class Alpm:
    def __init__(self, conf="/etc/pacman.conf"):
        self.handle = PacmanConfig(conf).initialize_alpm()
        self.localdb = self.handle.get_localdb()
        self.syncdbs = self.handle.get_syncdbs()

    def is_installed(self, package: str) -> bool:
        # Unlike get_pkg(), search() with an exact match includes providers
        # e.g. ttf-font -> noto-fonts
        pattern = f"^{escape(package)}$"
        return bool(self.localdb.search(pattern))

    def all_local_packages(self) -> set[str]:
        return {pkg.name for pkg in self.localdb.pkgcache}

    def all_sync_packages(self) -> set[str]:
        return {pkg.name for db in self.syncdbs for pkg in db.pkgcache}

    def explicit_not_required(self) -> set[str]:
        return {
            pkg.name
            for pkg in self.localdb.pkgcache
            if pkg.reason == pyalpm.PKG_REASON_EXPLICIT and not pkg.compute_requiredby()
        }

    def explicit(self) -> set[str]:
        return {
            pkg.name for pkg in self.localdb.pkgcache if pkg.reason == pyalpm.PKG_REASON_EXPLICIT
        }

    def dependencies(self) -> set[str]:
        return self.all_local_packages() - self.explicit()

    def foreign_packages(self) -> set[str]:
        return self.all_local_packages() - self.all_sync_packages()

    def orphans(self) -> set[str]:
        return {
            pkg.name
            for pkg in self.localdb.pkgcache
            if pkg.reason == pyalpm.PKG_REASON_DEPEND
            and not pkg.compute_requiredby()
            and not pkg.compute_optionalfor()
        }

    def get_providers(self, name: str) -> set[str]:
        return {
            pkg.name
            for db in self.syncdbs
            for pkg in db.search(name)
            if any(p.split("=")[0] == name for p in pkg.provides)
        }

    def get_group(self, name: str) -> set[str] | None:
        for db in self.syncdbs:
            if group := db.read_grp(name):
                _, packages = group
                return {pkg.name for pkg in packages}
        print_warning(f"Group {name} not found.")
        return None

    def get_sync_package(self, name: str):
        for db in self.syncdbs:
            if pkg := db.get_pkg(name):
                return pkg
        return None

    def get_local_package(self, name: str):
        return self.localdb.get_pkg(name)
