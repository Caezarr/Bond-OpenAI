from __future__ import annotations

from pathlib import Path

import pytest
from fakes import ALLOWED, OTHER_ALLOWED, FakeProvider

from bond_mcp.lifecycle import PhoneTaskService
from bond_mcp.policy import Policy
from bond_mcp.server import McpServer
from bond_mcp.store import TaskStore
from fredo.settings import Settings


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def policy() -> Policy:
    return Policy(frozenset({ALLOWED, OTHER_ALLOWED}))


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    return TaskStore(tmp_path / "tasks.sqlite3")


@pytest.fixture
def service(policy: Policy, store: TaskStore, provider: FakeProvider) -> PhoneTaskService:
    return PhoneTaskService(policy=policy, store=store, provider=provider)


@pytest.fixture
def server(tmp_path: Path, provider: FakeProvider) -> McpServer:
    settings = Settings(allowed_numbers=frozenset({ALLOWED, OTHER_ALLOWED}))
    return McpServer(settings, store_path=tmp_path / "tasks.sqlite3", provider=provider)
