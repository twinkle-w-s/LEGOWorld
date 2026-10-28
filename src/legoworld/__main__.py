"""Local CLI for the hybrid BrickAgent/MCP workflow."""

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(prog="legoworld")
    parser.add_argument("command", choices=("serve", "doctor", "fetch-assets", "mcp-config", "run", "demo", "demo-v3"))
    parser.add_argument("path", nargs="?")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--parameters", default="{}")
    parser.add_argument("--full", action="store_true", help="doctor: scan all supported parts and recursive assets")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if args.command == "mcp-config":
        print(json.dumps({"mcpServers": {"legoworld": {"command": sys.executable,
            "args": ["-X", "utf8", "-m", "legoworld", "serve", "--workspace", str(workspace)]}}}, indent=2))
        return
    if args.command == "fetch-assets":
        from legoworld.assets import fetch_assets
        fetch_assets()
        return
    if args.command == "doctor":
        from importlib.metadata import version
        from legoworld.catalog import doctor
        print(json.dumps({"python": sys.version.split()[0], "brickagent": version("brickagent"),
            "bricknet": version("bricknet"), **doctor(args.full)}, indent=2))
        return
    from legoworld import server
    server.configure(workspace)
    if args.command == "serve":
        server.mcp.run(transport="stdio")
        return
    if args.command in ("demo", "demo-v3"):
        from legoworld.demo import run_demo
        result = run_demo(server.PROJECT)
    else:
        if not args.path:
            parser.error("run requires a Python build script path")
        project = server.PROJECT
        result = project.mutate("build", project.revision, path=args.path,
            parameters=json.loads(args.parameters), mode="replace_model", target_id="root")
        result.pop("document", None)
    from legoworld.design_tools import present
    print(json.dumps(present(result), indent=2, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
