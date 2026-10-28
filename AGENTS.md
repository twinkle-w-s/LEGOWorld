# Working on LEGOWorld V3

For LEGO design requests, read skills/lego-builder/SKILL.md. The external multimodal
agent writes Python and interprets native MCP images; this service calls no LLM API.

Use the project .venv interpreter. Run python -m pytest -q after workflow changes.
Keep Python builds, MCP edits, validation, rendering and export on the same V3 project
document. Materialize it through the pinned BrickAgent bridge; never reintroduce a
separate BrickBuilderMCP state or synthesized stud grid.

Coordinates are native LDraw, -Y up, with per-part native origins and general proper
rigid rotations. Export needs no bottom-origin correction. Tests must retain hierarchy,
color inheritance, alias transforms, authored contacts and non-upright MPD round trips.

Backend private-member access belongs in backend.py. Keep scene edits copy-on-write,
revision-guarded and atomic. Rebuilding a component invalidates its descendants;
external authored joins must rebind through named ports or fail. Do not silently
drop authored joins. Native collisions/checks run in disposable processes.

Missing recursive geometry or colliders must block verification. No AABB fallback.
Batch checks skip stability; export runs complete native checks. Do not mark an
unfinished draft exportable. Report real-asset test skips separately.

Keep generated work in outputs/. Preserve user .claude/ and credentials. The V2
catalog.json is now only the common-part selection/history, not the runtime engine.
Do not claim full force/deformation simulation or tested Studio GUI compatibility.
