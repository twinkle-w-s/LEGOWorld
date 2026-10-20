# Working on LEGOWorld

For LEGO design requests, connect the LEGOWorld MCP server and read
`skills/lego-builder/SKILL.md`. Use its native image feedback for visual review.
The server supplies tools; the connected multimodal agent handles language,
planning and appearance decisions. `legoworld demo` is an offline smoke test.

For implementation work, use the local `.venv` interpreter. Run
`python -m pytest -q` with that interpreter after changes to the workflow.
Keep modeling, checks, rendering and export on the same upstream engine state.
Studio export converts bottom-face engine positions to top-face LDraw origins;
mixed brick/plate and rotated-part round trips must keep passing.

Keep generated work in `outputs/`. V2 has a frozen 60-part upright catalog;
`catalog.json` records measured LDraw origins and BrickNet stud/receiver labels.
Never synthesize a full stud grid for slopes, arches, corners or jumpers.
The default collision backend is BrickNet; missing colliders must block export.
Actual LDraw meshes supply preview geometry. `aabb`/`boxes` are explicit fallback
environment settings, not precision validation. See docs/V2.md for asset setup.
Run precision tests with real assets installed; report skips separately from passes.
Do not claim full physical simulation or tested Studio GUI compatibility.
