import pytest

from legoworld.assets import collider_root, ldraw_root
from legoworld.project import Project


@pytest.fixture(autouse=True)
def asset_environment(monkeypatch):
    monkeypatch.setenv("BRICKNET_DATA", str(collider_root().resolve()))
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", str(ldraw_root().resolve()))


@pytest.fixture
def real_assets():
    if not (collider_root() / "cvx/3001.cvx.obj").is_file() or not (ldraw_root() / "parts/3001.dat").is_file():
        pytest.skip("Install real assets with legoworld fetch-assets")


@pytest.fixture
def project(tmp_path, real_assets):
    return Project(tmp_path)


@pytest.fixture
def script(tmp_path):
    def write(source, name="build.py"):
        path = tmp_path / name
        path.write_text(source, encoding="utf-8")
        return str(path)
    return write
