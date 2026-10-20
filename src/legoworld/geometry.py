"""Read actual LDraw triangle geometry; no Blender or GPU required."""

from functools import lru_cache
import io
import math

import numpy as np
from PIL import Image, ImageDraw
from lego_mcp import parts
from lego_mcp import server as engine

from legoworld.assets import ldraw_root


@lru_cache(maxsize=2048)
def mesh(filename: str) -> tuple[np.ndarray, np.ndarray]:
    """Flatten type 1 references and type 3/4 faces, preserving explicit colors.

    Type 2/5 edge lines are intentionally omitted. Winding varies across old
    LDraw primitives, so the software preview draws both sides.
    """
    filename = filename.lower().replace("\\", "/")
    if ".." in filename.split("/") or filename.startswith("/"):
        raise ValueError("Invalid LDraw reference")
    root = ldraw_root()
    path = next((p for p in (root / "parts" / filename, root / "p" / filename) if p.is_file()), None)
    if path is None:
        raise FileNotFoundError(f"Missing LDraw geometry {filename}; run legoworld fetch-assets.")
    triangles, colors = [], []
    for line in path.read_text(encoding="latin-1").splitlines():
        tokens = line.split()
        if not tokens or tokens[0] not in ("1", "3", "4"):
            continue
        kind, color = int(tokens[0]), int(tokens[1], 0) if tokens[1].startswith("0x") else int(tokens[1])
        if kind == 1:
            values = np.array(tokens[2:14], dtype=float)
            child, child_colors = mesh(" ".join(tokens[14:]))
            triangles.extend(child @ values[3:].reshape(3, 3).T + values[:3])
            colors.extend(np.where(child_colors == 16, color, child_colors))
        else:
            vertices = np.array(tokens[2:], dtype=float).reshape(-1, 3)
            triangles.append(vertices[[0, 1, 2]])
            colors.append(color)
            if kind == 4:
                triangles.append(vertices[[0, 2, 3]])
                colors.append(color)
    return np.array(triangles, dtype=float).reshape(-1, 3, 3), np.array(colors, dtype=int)


def world_mesh(instances=None):
    from legoworld.catalog import bottom_origin
    instances = engine.STATE.parts.values() if instances is None else instances
    triangles, colors = [], []
    for instance in instances:
        local, local_colors = mesh(instance.part_id + ".dat")
        matrix = np.array(engine.effective_matrix(instance)).reshape(3, 3)
        triangles.append((local - bottom_origin(instance.part_id)) @ matrix.T
                         + (instance.x, instance.y, instance.z))
        colors.extend(np.where(local_colors == 16, instance.color, local_colors))
    if not triangles:
        return np.empty((0, 3, 3)), np.empty((0,), dtype=int)
    return np.concatenate(triangles), np.array(colors)


def render_png(azimuth=35.0, elevation=28.0, width=600, height=440, instance_ids=None) -> bytes:
    """Orthographic shaded real-mesh preview with a per-pixel depth buffer."""
    selected = None if instance_ids is None else [engine.STATE.parts[i] for i in instance_ids]
    triangles, color_ids = world_mesh(selected)
    canvas = np.full((height, width, 3), (245, 245, 248), dtype=np.uint8)
    if len(triangles):
        a, e = math.radians(azimuth), math.radians(elevation)
        right = np.array([math.cos(a), 0, -math.sin(a)])
        up = np.array([math.sin(a)*math.sin(e), -math.cos(e), math.cos(a)*math.sin(e)])
        toward = np.cross(right, up)
        camera = triangles @ np.array([right, -up, toward]).T
        low, high = camera[:, :, :2].min((0, 1)), camera[:, :, :2].max((0, 1))
        scale = min((width - 36) / max(high[0]-low[0], 1), (height - 36) / max(high[1]-low[1], 1))
        camera[:, :, :2] = (camera[:, :, :2] - (low+high)/2) * scale + (width/2, height/2)
        normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        # Two-sided lighting accommodates legacy primitives without BFC winding.
        light = np.array([-0.35, -0.85, -0.4]); light /= np.linalg.norm(light)
        brightness = .56 + .44 * np.abs(normals @ light / np.maximum(lengths, 1e-10))
        rgb = np.array([parts.color_rgb(int(c)) if c < 0x2000000 else
                        ((int(c)>>16)&255, (int(c)>>8)&255, int(c)&255) for c in color_ids])
        shades = np.clip(rgb * brightness[:, None], 0, 255).astype(np.uint8)
        depth = np.full((height, width), -np.inf)
        for triangle, shade in zip(camera, shades):
            x0, y0 = np.maximum(np.floor(triangle[:, :2].min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(triangle[:, :2].max(0)).astype(int), (width-1, height-1))
            if x1 < x0 or y1 < y0:
                continue
            p, q, r = triangle
            determinant = (q[1]-r[1])*(p[0]-r[0]) + (r[0]-q[0])*(p[1]-r[1])
            if abs(determinant) < 1e-8:
                continue
            yy, xx = np.mgrid[y0:y1+1, x0:x1+1]
            u = ((q[1]-r[1])*(xx+.5-r[0])+(r[0]-q[0])*(yy+.5-r[1]))/determinant
            v = ((r[1]-p[1])*(xx+.5-r[0])+(p[0]-r[0])*(yy+.5-r[1]))/determinant
            w = 1-u-v
            z = u*p[2]+v*q[2]+w*r[2]
            region = depth[y0:y1+1, x0:x1+1]
            mask = (u >= -1e-7) & (v >= -1e-7) & (w >= -1e-7) & (z > region)
            region[mask] = z[mask]
            canvas[y0:y1+1, x0:x1+1][mask] = shade
    picture = Image.fromarray(canvas)
    ImageDraw.Draw(picture).text((12, 10), "LDraw mesh / CPU depth buffer", fill=(60, 65, 75))
    stream = io.BytesIO()
    picture.save(stream, format="PNG")
    return stream.getvalue()
