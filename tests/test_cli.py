"""CLI: never overwrites files it did not create."""

from __future__ import annotations

from pathlib import Path

import pytest

from bond_mcp.cli import main


def test_install_writes_only_an_explicit_new_path(tmp_path: Path) -> None:
    target = tmp_path / "codex-mcp.json"
    assert main(["install", "--client", "codex", "--write", str(target)]) == 0
    assert '"bond-openai"' in target.read_text(encoding="utf-8")
    assert main(["install", "--client", "codex", "--write", str(target)]) == 2


def _configure(endpoint: str, token: str = "public-demo-token-1234") -> int:
    return main(["demo", "configure", "--endpoint", endpoint, "--token", token])


def test_demo_configure_writes_public_profile_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _configure("https://relay.example") == 0
    profile = (tmp_path / "demo" / "profile.json").read_text(encoding="utf-8")
    assert "relay.example" in profile
    assert _configure("https://other.example") == 2


def test_demo_configure_rejects_http_and_short_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert _configure("http://relay.example") == 2
    assert _configure("https://relay.example", token="short") == 2
    assert not (tmp_path / "demo" / "profile.json").exists()
