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

Keep generated work in `outputs/`. The first release supports common upright
bricks and plates, not arbitrary part geometry or complete physical simulation.
