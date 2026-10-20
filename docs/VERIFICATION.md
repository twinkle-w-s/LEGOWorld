# First release verification — 2026-10-20

Environment: Windows, Python 3.12.14 in the project `.venv`, MCP 1.30.0,
Pillow 12.3.0. The MCP catalog contains 32 common parts. Upstream part 3857
is excluded: its built-in 16x16 footprint disagrees with the official LDraw
16x32 baseplate, so it cannot be exported faithfully using that definition.

The tests exercise a real stdio client/server handshake, tool discovery,
placement, native MCP image content, export, collision/repair, rejection of
empty/floating/disconnected models, mixed brick/plate origins, and four upright
rotation round trips. Run `.venv/Scripts/python.exe -m pytest -q` to reproduce.

The offline `demo` built a 61-part house, detected a deliberately duplicated
part, removed it, returned four views and exported IO/MPD. This is a deterministic
tool-chain check, not an autonomous LLM evaluation.

The assistant then inspected the four-view PNG in this conversation and noticed
open gable ends. Through a real MCP client, it loaded the model, saved a checkpoint,
added 12 gable parts with blue accent panels, reviewed the native image response
and exported the resulting 73-part house. The checked-in example is this reviewed
version. Final basic-check results: 0 collisions, 0 floating, 0 unanchored,
0 off-grid parts, 1 connected rigid body, 126 connection edges.

IO verification covers ZIP integrity, its model.ldr payload, transformation
consistency and re-import. Actual opening/editing/re-saving in the user's Studio
installation is still a manual acceptance step. An independent general-agent
client has not been configured globally or benchmarked for autonomous aesthetics.
