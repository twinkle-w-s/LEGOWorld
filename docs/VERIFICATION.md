# V2 verification — 2026-10-20

Windows, project Python 3.12.14, LEGOWorld 0.2.0, MCP 1.30.0,
BrickNet 0.1.1 and locally compiled PyBullet 3.2.7. Official LDraw geometry and
BrickNet convex assets are installed in `.cache/assets/`; all 60 curated parts
have geometry and canonical colliders. The native source build succeeded on
this machine; another Windows machine may need C++ Build Tools.

`.venv/Scripts/python.exe -X utf8 -m pytest -q`: **25 passed**, zero skipped,
12.33 seconds. Original workflow tests explicitly use fast AABB/boxes fallback.
Dedicated precision tests use real downloaded assets and PyBullet. MCP tests
start real subprocesses for **both** backends; the precision path attaches a
brick to an actual slope stud, returns native images and exports successfully.

Additional coverage: round parts whose AABBs overlap but convex bodies do not;
rejection of true overlap; missing-collider export refusal; exact stud layouts;
all 28 added parts attaching to a real base stud; read-only placement previews;
full-state rollback after invalid replacement/group transforms; actual slope
mesh/camera rendering; all added parts through four rotated MPD round trips;
coincident compound-baseplate detection; unsupported import-pose rejection.
The precision checks skip explicitly if dependencies/assets are absent, so a
fresh machine's basic-test passes must not be represented as precision passes.

`legoworld demo-v2` produced the checked-in 39-part castle gateway using **9 new
part types**, actual mesh previews and Studio IO/MPD. Final report: 0 collisions,
0 floating, 0 unanchored, 0 grid errors, 1 rigid body, 40 connection edges;
BrickNet `verified=true`, tolerance 1 LDU. Overlap preflight rejected a deliberate
conflict, and a flower recolor via validated replacement succeeded. The assistant
visually inspected the four-view image and the isolated close-up. This is a
deterministic demonstration, not a new autonomous LLM benchmark.

Run `legoworld doctor` to inspect missing assets; run `legoworld fetch-assets`
to install them. Actual Studio GUI opening/editing/re-saving remains unverified.
Convex penetration and the upright connection graph do not certify load-bearing
or clutch-force stability. The renderer uses opaque flat shading, no ray tracing.

## First release verification (historical)

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
