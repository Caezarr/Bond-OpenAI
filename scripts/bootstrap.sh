#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
LOCAL_BIN="$PROJECT_DIR/.bond-tools/bin"

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    brew install uv
    return
  fi
  if command -v curl >/dev/null 2>&1; then
    mkdir -p "$LOCAL_BIN"
    curl -LsSf https://astral.sh/uv/0.10.9/install.sh \
      | UV_INSTALL_DIR="$LOCAL_BIN" sh
    PATH="$LOCAL_BIN:$PATH"
    export PATH
    return
  fi
  echo "Bond-OpenAI cannot install uv automatically: install uv or Homebrew first." >&2
  exit 1
}

ensure_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    brew install cloudflared
    return
  fi
  echo "cloudflared is optional until a live Twilio callback test; continuing." >&2
  return
}

ensure_uv
if ! command -v uv >/dev/null 2>&1; then
  echo "Bond-OpenAI could not put uv on PATH after installation." >&2
  exit 1
fi

uv sync --frozen --extra dev
if ! uv run bond-mcp doctor --json; then
  echo "Dependencies are installed. Add provider variables, then rerun 'uv run bond-mcp doctor --json'." >&2
fi
