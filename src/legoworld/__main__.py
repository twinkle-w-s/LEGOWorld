"""CLI for serving tools, generating client config, and a deterministic smoke demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="legoworld")
    parser.add_argument("command", choices=("serve", "demo", "mcp-config", "doctor"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if args.command == "mcp-config":
        print(json.dumps({"mcpServers": {"legoworld": {
            "command": sys.executable,
            "args": ["-m", "legoworld", "serve", "--workspace", str(workspace)],
        }}}, indent=2))
        return
    from legoworld import server
    server.configure(workspace)
    if args.command == "serve":
        server.mcp.run(transport="stdio")
    elif args.command == "doctor":
        from importlib.metadata import version
        print(json.dumps({
            "python": sys.version.split()[0], "mcp": version("mcp"),
            "lego-mcp": version("lego-mcp"), "pillow": version("Pillow"),
            "workspace": str(workspace), "catalog_parts": len(server.engine.PART_INDEX),
            "agent": "Connect a multimodal MCP host; no model API is called by this server.",
        }, indent=2))
    else:
        from legoworld.demo import run_demo
        result = run_demo()
        print(json.dumps(result, indent=2))
        if not result["ok"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
