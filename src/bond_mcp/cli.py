from __future__ import annotations

import argparse
import json
from pathlib import Path

from fredo.settings import Settings

from .server import McpServer, run_stdio


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bond-mcp", description="Local Bond-OpenAI phone MCP")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the MCP over stdio")
    doctor = sub.add_parser("doctor", help="Check local readiness")
    doctor.add_argument("--json", action="store_true")
    install = sub.add_parser("install", help="Generate an MCP client configuration")
    install.add_argument("--client", choices=("codex", "bond", "generic"), required=True)
    install.add_argument("--print", action="store_true", dest="print_only")
    return parser


def _config() -> dict[str, object]:
    return {"command": "uv", "args": ["run", "bond-mcp", "serve"], "cwd": str(Path.cwd())}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        import asyncio

        asyncio.run(run_stdio(McpServer()))
        return 0
    if args.command == "install":
        config = _config()
        if args.client == "generic" or args.print_only:
            print(json.dumps(config, indent=2))
            return 0
        print(f"MCP config for {args.client} (copy into the client's local settings):")
        print(json.dumps({"bond-openai": config}, indent=2))
        return 0
    settings = Settings.from_env()
    summary = settings.public_summary()
    summary["mcp"] = "ready"
    summary["missing"] = settings.missing_for_real_call()
    print(json.dumps(summary, indent=2) if args.json else "bond-mcp: " + ("ready" if not summary["missing"] else "configuration incomplete"))
    return 0 if not summary["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
