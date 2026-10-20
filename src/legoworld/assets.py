"""Explicit, project-local installation of public geometry assets."""

import os
import tarfile
import zipfile
from pathlib import Path

import httpx


def asset_root() -> Path:
    return Path(os.environ.get("LEGOWORLD_ASSETS", Path(__file__).resolve().parents[2] / ".cache/assets"))


def ldraw_root() -> Path:
    return Path(os.environ.get("LDRAW_LIBRARY_PATH", asset_root() / "ldraw"))


def collider_root() -> Path:
    return Path(os.environ.get("BRICKNET_DATA", asset_root() / "bricknet"))


def fetch_assets() -> None:
    root = asset_root()
    root.mkdir(parents=True, exist_ok=True)
    downloads = (
        ("colliders.tar.gz", "https://keeper.mpdl.mpg.de/seafhttp/f/24c17eb2d4d14c7ebd41/?op=view"),
        ("ldraw.zip", "https://library.ldraw.org/library/updates/complete.zip"),
    )
    for name, url in downloads:
        path = root / name
        if not path.is_file():
            partial = path.with_suffix(path.suffix + ".partial")
            print(f"Downloading {name} ...", flush=True)
            with httpx.stream("GET", url, follow_redirects=True, timeout=120,
                              headers={"User-Agent": "LEGOWorld/0.2"}) as response:
                response.raise_for_status()
                with partial.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
            partial.replace(path)
        if name.endswith(".gz"):
            destination = collider_root() / "cvx"
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(path) as archive:
                archive.extractall(destination, filter="data")
        else:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(root)
        print(f"Installed {name}", flush=True)
