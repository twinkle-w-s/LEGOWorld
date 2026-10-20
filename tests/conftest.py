import pytest

from legoworld import server


@pytest.fixture(autouse=True)
def fresh_model(tmp_path):
    server.configure(tmp_path)
    server.engine.create_model("test_model")
    yield
    server.engine.create_model("empty")
