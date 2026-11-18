"""Operator-hosted demo relay: a bearer-token HTTP front for the phone lifecycle.

The relay holds the real Twilio/Deepgram credentials so a jury machine needs only
a scoped demo token. It re-applies the same policy, idempotency and confirmation
checks as the local MCP by delegating to ``PhoneTaskService``.
"""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from fredo.settings import Settings

from .lifecycle import PhoneTaskService, ProviderFailed, error_code
from .policy import Policy, PolicyError, build_task
from .providers import PhoneProvider, provider_from_settings
from .runtime import create_runtime_app
from .store import ActiveCall, IdempotencyConflict, TaskStore


@dataclass(slots=True)
class RelayRateLimiter:
    max_requests: int = 30
    window_seconds: int = 60
    _requests: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._requests[key]
        while bucket and now - bucket[0] >= self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True


@dataclass(slots=True)
class DemoRelay:
    settings: Settings
    store: TaskStore
    provider: PhoneProvider
    limiter: RelayRateLimiter = field(default_factory=RelayRateLimiter)
    service: PhoneTaskService = field(init=False)

    def __post_init__(self) -> None:
        self.service = PhoneTaskService(
            policy=Policy(self.settings.allowed_numbers),
            store=self.store,
            provider=self.provider,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> DemoRelay:
        if settings.telephony_provider not in {"real", "mock"}:
            raise ValueError("The relay must use FREDO_TELEPHONY_PROVIDER=real")
        if not settings.demo_access_token:
            raise ValueError("FREDO_DEMO_ACCESS_TOKEN is required on the relay")
        return cls(
            settings=settings,
            store=TaskStore(settings.state_dir / "bond_tasks.sqlite3"),
            provider=provider_from_settings(settings),
        )

    def app(self) -> Starlette:
        # The same public process handles Twilio callbacks and the demo API.
        app = create_runtime_app(self.settings, self.store)
        app.routes.extend(
            [
                Route("/v1/calls", self.create_call, methods=["POST"]),
                Route("/v1/calls/{call_id}", self.get_call, methods=["GET"]),
                Route("/v1/calls/{call_id}/cancel", self.cancel_call, methods=["POST"]),
            ]
        )
        return app

    def _authorized(self, request: Request) -> bool:
        supplied = request.headers.get("authorization", "")
        expected = f"Bearer {self.settings.demo_access_token}"
        return hmac.compare_digest(supplied, expected)

    def _rate_limited(self, request: Request) -> bool:
        token_id = request.headers.get("authorization", "")[-16:]
        client_host = request.client.host if request.client else "unknown"
        return not self.limiter.allow(f"{client_host}:{token_id}")

    async def create_call(self, request: Request) -> JSONResponse:
        auth_error = self._guard(request)
        if auth_error:
            return auth_error
        try:
            body = await request.json()
            if not isinstance(body, dict):
                return JSONResponse({"error": "invalid_request"}, status_code=400)
            task = build_task(body.get("task"), self.service.policy)
            # dial() rejects unconfirmed tasks: the relay never serves previews.
            result, replayed = await self.service.dial(task)
        except ProviderFailed:
            return JSONResponse({"error": "provider_unavailable"}, status_code=502)
        except (PolicyError, IdempotencyConflict, ActiveCall) as exc:
            return JSONResponse({"error": error_code(exc), "message": str(exc)}, status_code=409)
        except (TypeError, ValueError):
            return JSONResponse({"error": "invalid_request"}, status_code=400)
        payload = result.as_dict()
        payload["replayed"] = replayed
        return JSONResponse(payload, status_code=200)

    async def get_call(self, request: Request) -> JSONResponse:
        auth_error = self._guard(request)
        if auth_error:
            return auth_error
        result = await self.service.status(request.path_params["call_id"])
        if result is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse(result.as_dict())

    async def cancel_call(self, request: Request) -> JSONResponse:
        auth_error = self._guard(request)
        if auth_error:
            return auth_error
        result = await self.service.cancel(request.path_params["call_id"])
        if result is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse(result.as_dict())

    def _guard(self, request: Request) -> JSONResponse | None:
        if not self._authorized(request):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        if self._rate_limited(request):
            return JSONResponse({"error": "rate_limited"}, status_code=429)
        return None


def create_demo_relay_app(settings: Settings | None = None) -> Starlette:
    relay = DemoRelay.from_settings(settings or Settings.from_env())
    return relay.app()
