---
name: lego-builder
description: Design and refine LEGO models through LEGOWorld V3 using BrickAgent Python components, transactional MCP edits, visual feedback and Studio export.
---

# LEGO builder V3

Use the connected LEGOWorld MCP tools. You provide design decisions and visual
judgment; the server handles deterministic geometry. Read [V3 API and examples](../../docs/V3.md)
when writing a build script or using ports, batch edits and component replacement.

Prefer Python for repeated structure and MCP for inspection and local refinement.
Write a workspace-local script implementing build(**parameters) -> brickagent.Assembly.
Use native Assembly.attach rather than guessed origins. Loop over real connectors;
ordinary, hollow and side studs have distinct native types. at() uses studs/plates/studs,
while move() and JSON poses use LDU. -Y is up. Arbitrary proper rigid rotations are allowed.

Read get_model_tree to obtain current revision and node IDs. Pass expected_revision
on every write. Build in useful component batches with run_build_script. Expose named
ports for connections that must survive component replacement; require_contact records
a second support or loop closure. Definitions may be shared; local tool edits affect
only the selected occurrence. Replacing a component discards its internal tool edits
and invalidates descendant IDs, so refresh the tree afterward. Do not automatically
re-run a whole-model script to preserve unrelated local edits.

Use apply_edits to group additions, attachment, recolor and transforms. Existing
authored joins must be detached explicitly before moving their endpoints apart.
A replacement part needs connector mappings for referenced connectors. Failed batches
preserve the active model; inspect the report and render its candidate_id if available.

Call review_model after a meaningful construction or refinement. Actually inspect
the native image for silhouette, proportions, colors and requested details. Use
render_view with component node_ids for close-ups. Save a checkpoint before large
revisions. Continue useful revisions until the request is met; expose remaining
problems if the checks or visual requirements cannot be satisfied.

batch_valid only establishes native geometry/contact checks. Export requires full
native stability; multiple independent stable objects are allowed. Missing assets
are a setup problem, never verified geometry. Do not substitute a bounding-box checker.
Stability treats connected parts as rigid and does not certify real clutch forces.

Finish through export_model. Return IO, MPD, preview and validation links, plus the
V3 project JSON when continued editing matters. Prefer JSON/checkpoints for resuming:
MPD stores geometry/hierarchy but loses named ports and authored-contact intent.
Do not claim autonomous quality from the deterministic demo or verified Studio GUI use.
