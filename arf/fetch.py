import gzip
import json
import subprocess
from arf.config import ARF_CACHE, PKGS_DIR
from arf.exceptions import RepoFetchError, RPCError
from functools import cache
from io import BytesIO
from pathlib import Path
from urllib import request, parse, error

_seen_repos = set()


def http_get(url: str, params: dict | None = None, as_json: bool = False):
    if params:
        query_string = parse.urlencode(params)
        url = f"{url}?{query_string}"

    try:
        with request.urlopen(url, timeout=10) as response:
            if as_json:
                try:
                    return json.load(response)
                except json.JSONDecodeError as e:
                    raise RPCError(f"{url} returned non-JSON response.") from e
            return response.read()
    except error.HTTPError as e:
        raise RPCError(f"{url} returned HTTP code {e.code}.") from e
    except error.URLError as e:
        raise RPCError(f"Failed to fetch {url}: {e.reason}") from e


def search_rpc(query: str, by: str = "name", type: str = "search") -> list[dict]:
    url = f"https://aur.archlinux.org/rpc/v5/{type}"
    data = http_get(url, params={"by": by, "arg": query}, as_json=True)
    return data.get("results", [])


def download_package_list(force: bool = False) -> Path:
    file_path = Path(ARF_CACHE / "packages.txt")
    if not file_path.exists() or force:
        ARF_CACHE.mkdir(parents=True, exist_ok=True)
        print("Downloading AUR package list...")

        compressed_data = http_get("https://aur.archlinux.org/packages.gz")
        with gzip.open(BytesIO(compressed_data), "rt") as gz, file_path.open("w") as f:
            for line in gz:
                f.write(line)

    return file_path


@cache
def package_list() -> set[str]:
    file_path = download_package_list()
    if not file_path or not file_path.exists():
        return set()
    with open(file_path, "r") as f:
        return {line.strip() for line in f}


def get_repo(pkg_name: str) -> Path:
    repo = PKGS_DIR / pkg_name

    if pkg_name in _seen_repos:
        return repo

    if repo.is_dir():
        print(f"Pulling {pkg_name}...")
        try:
            subprocess.run(["git", "pull", "-q", "--ff-only"], cwd=repo, check=True)
        except subprocess.CalledProcessError as e:
            raise RepoFetchError(f"Could not pull {pkg_name} from the AUR.") from e
    else:
        PKGS_DIR.mkdir(parents=True, exist_ok=True)
        if pkg_name not in package_list():
            raise RepoFetchError(f"{pkg_name} is not an AUR package.")

        print(f"Cloning {pkg_name}...")
        try:
            subprocess.run(
                ["git", "clone", "-q", f"https://aur.archlinux.org/{pkg_name}.git"],
                cwd=PKGS_DIR,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RepoFetchError(f"Could not clone {pkg_name} from the AUR.") from e

    _seen_repos.add(pkg_name)
    return repo
