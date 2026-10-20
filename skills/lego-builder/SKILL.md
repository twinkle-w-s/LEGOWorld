---
name: lego-builder
description: Design and revise common-brick LEGO models with LEGOWorld MCP tools, visual feedback, collision checks and Studio IO/MPD export.
---

# LEGO builder v2

Use the connected `legoworld` tools. The server contains no LLM: you are the
planning and visual-review agent. If the tools are not connected, follow the
project README to generate the local MCP client configuration first.

1. Read the user's subject, approximate size and color preferences. For a first
   build, choose roughly 100–300 common upright parts. Give a short design brief.
2. Call `create_model` with a descriptive name. Search the catalog and inspect
   unfamiliar dimensions before placing parts. Coordinates are LDU, negative Y
   is up, and placements refer to the bottom face. Use 20 LDU per stud, 8 per
   plate and 24 per brick. The curated 60-part upright catalog is in scope.
   Inspect get_part_info/get_connectors for slopes, curves, arches and jumpers;
   their origins and stud positions can differ from ordinary rectangular bricks.
3. Build a base and recognizable silhouette in small batches. Prefer the wall,
   room, roof and connection helpers over guessing dozens of absolute positions.
   Use attach_part to align selected stud/receiver indices, preview_placement to
   check a proposed pose without changing the model, and find_valid_placements
   to get checked proposals. Search is bounded to 500 poses; it is not exhaustive.
   Only upright stud/receiver connections are supported, even if a part has
   additional physical features. Do not assume side/hinge/axle connections work.
4. Call `review_model` with a description of what changed. Read its JSON and
   **look at its native image content**, showing four azimuths of the current model.
   A saved filename or base64 in a text string does not establish visual feedback.
5. Fix collisions, floating/unanchored parts, unknown parts and off-grid positions
   first. Use `describe_errors`, then move/remove/rebuild the affected parts.
6. Inspect proportions, silhouette, color balance and requested details in the
   images. Make one or two specific visual improvements, then review again.
   Save a checkpoint before a large revision. Do not claim that the deterministic
   offline demo proves autonomous visual reasoning.
   Use render_view with selected instance_ids for close-ups and alternate angles.
   replace_part and transform_group validate the whole result and automatically
   roll back invalid edits. The group pivot is explicit in world X/Z coordinates.
7. Stop when the brief is met or after five visual revisions. If basic-check
   errors remain, explain them and retain the draft rather than claiming success.
8. Call `export_model`. Return its IO, MPD, PNG and validation paths. The IO file
   is a basic new Studio model; instruction pages and live Studio control are
   outside this MVP. Default collision checking uses BrickNet convex bodies and
   a 1 LDU penetration tolerance. Missing colliders are unverified; fix setup
   instead of silently switching backends. Explicit AABB fallback reports
   verified=false and is conservative. Connection checks do not certify clutch
   forces or load stability. Aesthetics is a visual judgment, not a measured score.
