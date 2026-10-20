"""CLI for serving tools, generating client config, and a deterministic smoke demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="legoworld")
    parser.add_argument("command", choices=("serve", "demo", "mcp-config", "doctor", "fetch-assets", "demo-v2"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if args.command == "mcp-config":
        print(json.dumps({"mcpServers": {"legoworld": {
            "command": sys.executable,
            "args": ["-X", "utf8", "-m", "legoworld", "serve", "--workspace", str(workspace)],
        }}}, indent=2))
        return
    if args.command == "fetch-assets":
        from legoworld.assets import fetch_assets
        fetch_assets()
        return
    from legoworld import server
    server.configure(workspace)
    if args.command == "serve":
        # Initialize native libraries before starting the stdio event loop.
        from legoworld.precision import collision_report
        collision_report([])
        server.mcp.run(transport="stdio")
    elif args.command == "doctor":
        from importlib.metadata import version
        from legoworld.precision import collision_report
        from legoworld.assets import ldraw_root, collider_root
        from legoworld.catalog import RECORDS
        print(json.dumps({
            "python": sys.version.split()[0], "mcp": version("mcp"),
            "lego-mcp": version("lego-mcp"), "pillow": version("Pillow"),
            "workspace": str(workspace), "catalog_parts": len(server.engine.PART_INDEX),
            "collision": collision_report([]),
            "ldraw_library": str(ldraw_root()), "geometry_installed": (ldraw_root()/"parts/3001.dat").is_file(),
            "collider_library": str(collider_root()),
            "missing_geometry": [pid for pid in RECORDS if not (ldraw_root()/"parts"/(pid+".dat")).is_file()],
            "missing_colliders": [pid for pid, r in RECORDS.items()
                                  if not (collider_root()/"cvx"/(r["collider"]+".cvx.obj")).is_file()],
            "agent": "Connect a multimodal MCP host; no model API is called by this server.",
        }, indent=2))
    else:
        if args.command == "demo-v2":
            from legoworld.demo_v2 import run_demo
        else:
            from legoworld.demo import run_demo
        result = run_demo()
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
