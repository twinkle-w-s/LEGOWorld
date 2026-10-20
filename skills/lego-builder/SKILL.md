---
name: lego-builder
description: Design and revise common-brick LEGO models with LEGOWorld MCP tools, visual feedback, collision checks and Studio IO/MPD export.
---

# LEGO builder MVP

Use the connected `legoworld` tools. The server contains no LLM: you are the
planning and visual-review agent. If the tools are not connected, follow the
project README to generate the local MCP client configuration first.

1. Read the user's subject, approximate size and color preferences. For a first
   build, choose roughly 100–300 common upright parts. Give a short design brief.
2. Call `create_model` with a descriptive name. Search the catalog and inspect
   unfamiliar dimensions before placing parts. Coordinates are LDU, negative Y
   is up, and placements refer to the bottom face. Use 20 LDU per stud, 8 per
   plate and 24 per brick. Only the exposed upright common-part catalog is in scope.
3. Build a base and recognizable silhouette in small batches. Prefer the wall,
   room, roof and connection helpers over guessing dozens of absolute positions.
4. Call `review_model` with a description of what changed. Read its JSON and
   **look at its native image content**, showing four azimuths of the current model.
   A saved filename or base64 in a text string does not establish visual feedback.
5. Fix collisions, floating/unanchored parts, unknown parts and off-grid positions
   first. Use `describe_errors`, then move/remove/rebuild the affected parts.
6. Inspect proportions, silhouette, color balance and requested details in the
   images. Make one or two specific visual improvements, then review again.
   Save a checkpoint before a large revision. Do not claim that the deterministic
   offline demo proves autonomous visual reasoning.
7. Stop when the brief is met or after five visual revisions. If basic-check
   errors remain, explain them and retain the draft rather than claiming success.
8. Call `export_model`. Return its IO, MPD, PNG and validation paths. The IO file
   is a basic new Studio model; instruction pages and live Studio control are
   outside this MVP. A passing simplified stud/AABB check is not a physical
   stability certification. Aesthetics is a visual judgment, not a measured score.
