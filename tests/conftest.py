import pytest

from legoworld import server


@pytest.fixture(autouse=True)
def fresh_model(tmp_path, monkeypatch):
    # The original workflow suite stays runnable without the large asset pack.
    # Dedicated precision tests explicitly select and exercise the real backend.
    monkeypatch.setenv("LEGOWORLD_COLLISION", "aabb")
    monkeypatch.setenv("LEGOWORLD_RENDERER", "boxes")
    server.configure(tmp_path)
    server.engine.create_model("test_model")
    yield
    server.engine.create_model("empty")
