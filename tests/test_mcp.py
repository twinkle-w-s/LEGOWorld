import asyncio
import base64
import io
import json
import os
import sys
import importlib.util

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image


@pytest.mark.parametrize("backend", ("aabb", "bricknet"))
def test_real_stdio_client_receives_images_and_exports(tmp_path, monkeypatch, backend):
    if backend == "bricknet":
        from legoworld.assets import collider_root, ldraw_root
        if (importlib.util.find_spec("pybullet") is None or
                not (collider_root()/"cvx/3039.cvx.obj").is_file() or
                not (ldraw_root()/"parts/3039.dat").is_file()):
            pytest.skip("Install precision dependencies and assets")
    monkeypatch.setenv("LEGOWORLD_COLLISION", backend)
    monkeypatch.setenv("LEGOWORLD_RENDERER", "ldraw" if backend == "bricknet" else "boxes")
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "legoworld", "serve", "--workspace", str(tmp_path)],
            env=dict(os.environ),
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                handshake = await client.initialize()
                assert handshake.serverInfo.name == "LEGOWorld"
                tools = {tool.name for tool in (await client.list_tools()).tools}
                assert {"create_model", "search_parts", "review_model", "export_model"} <= tools
                assert {"get_connectors", "attach_part", "preview_placement", "replace_part",
                        "transform_group", "render_view", "measure_model", "inspect_part"} <= tools
                for name, arguments in [
                    ("create_model", {"name": "wire_test"}),
                    ("add_part", {"part_id": "3039" if backend == "bricknet" else "3001",
                                  "color": "red", "x": 0, "y": 0, "z": 0}),
                ]:
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                if backend == "bricknet":
                    attached = await client.call_tool("attach_part", {
                        "base_instance_id": "1", "base_connector": 0, "part_id": "3005",
                        "part_connector": 1, "color": "yellow"})
                    assert not attached.isError, attached
                    assert json.loads(attached.content[0].text)["ok"]
                review = await client.call_tool("review_model", {"note": "Protocol image check"})
                assert not review.isError, review
                images = [block for block in review.content if block.type == "image"]
                assert images, "Images must be native image blocks, not base64 hidden in text."
                with Image.open(io.BytesIO(base64.b64decode(images[0].data))) as picture:
                    assert picture.size == (1200, 940)
                final = await client.call_tool("export_model", {})
                assert not final.isError, final
                data = json.loads(next(block.text for block in final.content if block.type == "text"))
                assert data["ok"] is True
                assert data["checks"]["backend"] == backend
                assert data["checks"]["verified"] == (backend == "bricknet")
                assert (tmp_path / "outputs" / "wire_test" / "model.io").is_file()
    asyncio.run(asyncio.wait_for(exercise(), timeout=60))
