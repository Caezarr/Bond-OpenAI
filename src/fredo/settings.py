from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


def _csv(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    deepgram_api_key: str | None = field(default=None, repr=False)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = field(default=None, repr=False)
    twilio_phone_number: str | None = None
    endpoint_secret: str | None = field(default=None, repr=False)
    allowed_numbers: frozenset[str] = frozenset()
    public_url: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    max_duration_seconds: int = 180
    max_concurrent_calls: int = 1
    listen_model: str = "flux-general-multi"
    listen_language: str = "en"
    llm_provider: str = "open_ai"
    llm_model: str = "gpt-4o-mini"
    voice_model: str = "aura-2-thalia-en"
    telephony_provider: str = "real"
    state_dir: Path = Path(".local-state")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        if environ is None:
            load_dotenv()
            env: Mapping[str, str] = os.environ
        else:
            env = environ

        max_duration = _integer(env, "FREDO_MAX_DURATION_SECONDS", 180)
        if not 10 <= max_duration <= 180:
            raise ValueError("FREDO_MAX_DURATION_SECONDS must be between 10 and 180")

        max_concurrent = _integer(env, "FREDO_MAX_CONCURRENT_CALLS", 1)
        if max_concurrent != 1:
            raise ValueError("The hackathon profile requires FREDO_MAX_CONCURRENT_CALLS=1")

        provider = env.get("FREDO_TELEPHONY_PROVIDER", "real").strip().lower()
        if provider not in {"real", "mock"}:
            raise ValueError("FREDO_TELEPHONY_PROVIDER must be 'real' or 'mock'")

        state_dir = Path(env.get("FREDO_STATE_DIR", ".local-state")).expanduser()
        return cls(
            deepgram_api_key=env.get("DEEPGRAM_API_KEY") or None,
            twilio_account_sid=env.get("TWILIO_ACCOUNT_SID") or None,
            twilio_auth_token=env.get("TWILIO_AUTH_TOKEN") or None,
            twilio_phone_number=env.get("TWILIO_PHONE_NUMBER") or None,
            endpoint_secret=env.get("FREDO_ENDPOINT_SECRET") or None,
            allowed_numbers=_csv(env.get("FREDO_ALLOWED_NUMBERS")),
            public_url=(env.get("FREDO_PUBLIC_URL") or "").rstrip("/") or None,
            host=env.get("FREDO_HOST", "127.0.0.1"),
            port=_integer(env, "FREDO_PORT", 8080),
            max_duration_seconds=max_duration,
            max_concurrent_calls=max_concurrent,
            listen_model=env.get("FREDO_LISTEN_MODEL", "flux-general-multi"),
            listen_language=env.get("FREDO_LISTEN_LANGUAGE", "en"),
            llm_provider=env.get("FREDO_LLM_PROVIDER", "open_ai"),
            llm_model=env.get("FREDO_LLM_MODEL", "gpt-4o-mini"),
            voice_model=env.get("FREDO_VOICE_MODEL", "aura-2-thalia-en"),
            telephony_provider=provider,
            state_dir=state_dir,
        )

    def with_public_url(self, public_url: str) -> "Settings":
        return replace(self, public_url=public_url.rstrip("/"))

    def missing_for_real_call(self) -> list[str]:
        required = {
            "DEEPGRAM_API_KEY": self.deepgram_api_key,
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_PHONE_NUMBER": self.twilio_phone_number,
            "FREDO_ENDPOINT_SECRET": self.endpoint_secret,
            "FREDO_ALLOWED_NUMBERS": next(iter(self.allowed_numbers), None),
            "FREDO_PUBLIC_URL": self.public_url,
        }
        return [name for name, value in required.items() if not value]

    def public_summary(self) -> dict[str, object]:
        """Return diagnostics without ever serializing credentials."""
        return {
            "telephony_provider": self.telephony_provider,
            "deepgram_configured": bool(self.deepgram_api_key),
            "twilio_configured": bool(
                self.twilio_account_sid
                and self.twilio_auth_token
                and self.twilio_phone_number
            ),
            "endpoint_auth_configured": bool(self.endpoint_secret),
            "allowed_destination_count": len(self.allowed_numbers),
            "public_url_configured": bool(self.public_url),
            "max_duration_seconds": self.max_duration_seconds,
            "max_concurrent_calls": self.max_concurrent_calls,
            "listen_model": self.listen_model,
            "voice_model": self.voice_model,
        }
