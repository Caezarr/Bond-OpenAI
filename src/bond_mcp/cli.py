from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fredo.audio import audio_encoding_available
from fredo.settings import Settings

from .server import McpServer, run_stdio


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bond-mcp", description="Local Bond-OpenAI phone MCP")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the MCP over stdio")
    sub.add_parser("relay", help="Run the operator-hosted zero-credential demo relay")
    demo = sub.add_parser("demo", help="Manage the public zero-credential demo profile")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    configure = demo_sub.add_parser("configure", help="Publish a relay URL and scoped demo token")
    configure.add_argument("--endpoint", required=True, help="Public HTTPS relay URL")
    configure.add_argument("--token", help="Scoped public demo token")
    configure.add_argument(
        "--public",
        action="store_true",
        help="Use the operator's explicit public allowlist-only demo mode",
    )
    configure.add_argument("--force", action="store_true", help="Replace the existing profile")
    doctor = sub.add_parser("doctor", help="Check local readiness")
    doctor.add_argument("--json", action="store_true")
    install = sub.add_parser("install", help="Generate an MCP client configuration")
    install.add_argument("--client", choices=("codex", "bond", "generic"), required=True)
    install.add_argument("--print", action="store_true", dest="print_only")
    install.add_argument("--write", type=Path, help="Write a config file at this explicit path")
    install.add_argument("--force", action="store_true", help="Allow replacing the explicit --write path")
    return parser


def _config() -> dict[str, object]:
    return {"command": "uv", "args": ["run", "bond-mcp", "serve"], "cwd": str(Path.cwd())}


def _doctor_summary(settings: Settings) -> dict[str, object]:
    """Return safe deployment diagnostics without exposing configuration values."""
    summary = settings.public_summary()
    audio_enabled = bool(
        settings.audio_stream_origin
        or (settings.telephony_provider == "demo" and settings.demo_endpoint)
    )
    encoder_available = audio_encoding_available()
    # In demo mode, the remote relay owns the hub and MP3 encoder. The local
    # stdio MCP only requests a short-lived stream descriptor, so it does not
    # need lameenc installed.
    encoder_required = audio_enabled and settings.telephony_provider != "demo"
    missing = settings.missing_for_real_call()
    if encoder_required and not encoder_available:
        missing.append("lameenc (run: uv sync --frozen --extra audio)")
    summary.update(
        {
            "mcp": "ready",
            "audio_stream_configured": audio_enabled,
            "audio_encoder_available": encoder_available,
            "audio_encoder_required": encoder_required,
            "audio_ready": not encoder_required or encoder_available,
            "missing": missing,
        }
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        import asyncio

        server = McpServer()
        server.start_runtime()
        asyncio.run(run_stdio(server))
        return 0
    if args.command == "relay":
        import uvicorn

        from .demo_relay import create_demo_relay_app

        settings = Settings.from_env()
        uvicorn.run(create_demo_relay_app(settings), host=settings.host, port=settings.port)
        return 0
    if args.command == "demo":
        if args.demo_command != "configure":
            return 2
        parsed = urlsplit(args.endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            print("Demo relay endpoint must be a public HTTPS URL", file=sys.stderr)
            return 2
        if not args.public and (not args.token or len(args.token) < 16):
            print("Demo token must be at least 16 characters", file=sys.stderr)
            return 2
        profile_path = Path.cwd() / "demo" / "profile.json"
        if profile_path.exists() and not args.force:
            current = json.loads(profile_path.read_text(encoding="utf-8"))
            if current.get("endpoint") or current.get("access_token"):
                print(f"Refusing to overwrite existing demo profile: {profile_path}", file=sys.stderr)
                return 2
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(
                {
                    "endpoint": args.endpoint.rstrip("/"),
                    **({"public": True} if args.public else {"access_token": args.token}),
                    "profile": "public-demo",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Published demo profile at {profile_path}")
        return 0
    if args.command == "install":
        config = _config()
        rendered = json.dumps({"bond-openai": config}, indent=2) + "\n"
        if args.write:
            if args.write.exists() and not args.force:
                print(f"Refusing to overwrite existing file: {args.write}", file=sys.stderr)
                return 2
            args.write.parent.mkdir(parents=True, exist_ok=True)
            args.write.write_text(rendered, encoding="utf-8")
            print(f"Wrote {args.write}")
            return 0
        if args.client == "generic" or args.print_only:
            print(json.dumps(config, indent=2))
            return 0
        print(f"MCP config for {args.client} (copy into the client's local settings):")
        print(rendered, end="")
        return 0
    settings = Settings.from_env()
    summary = _doctor_summary(settings)
    print(json.dumps(summary, indent=2) if args.json else "bond-mcp: " + ("ready" if not summary["missing"] else "configuration incomplete"))
    return 0 if not summary["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
