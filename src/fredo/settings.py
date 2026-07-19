from __future__ import annotations

import os
import json
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


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _demo_profile() -> dict[str, str]:
    """Read the public, non-secret demo relay profile shipped with the repo."""
    profile_paths = (
        Path.cwd() / "demo" / "profile.json",
        Path(__file__).resolve().parents[2] / "demo" / "profile.json",
    )
    for profile_path in profile_paths:
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


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
    # Flux end-of-turn tuning. Higher threshold + longer timeout make the agent
    # wait for the caller to actually finish instead of cutting on brief pauses
    # or background noise on an 8 kHz PSTN line.
    eot_threshold: float = 0.7
    eot_timeout_ms: int = 7000
    eager_eot_threshold: float | None = None
    # Keep the mandatory synthetic-voice/no-recording disclosure un-interruptible
    # so noise cannot truncate the legal opening.
    protect_disclosure: bool = True
    # Graceful silence handling instead of the model guessing an answer from noise.
    silence_reprompt_seconds: int = 12
    silence_goodbye_seconds: int = 10
    telephony_provider: str = "real"
    demo_endpoint: str | None = None
    demo_access_token: str | None = field(default=None, repr=False)
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

        profile = _demo_profile()
        demo_endpoint = (
            env.get("FREDO_DEMO_ENDPOINT")
            or profile.get("endpoint")
            or ""
        ).rstrip("/") or None
        demo_access_token = env.get("FREDO_DEMO_ACCESS_TOKEN") or profile.get("access_token") or None
        provider = env.get("FREDO_TELEPHONY_PROVIDER", "").strip().lower()
        if not provider:
            # A configured demo relay is the zero-credential default. Local
            # real mode remains available when explicitly selected.
            provider = "demo" if demo_endpoint else "real"
        if provider not in {"real", "mock", "demo"}:
            raise ValueError("FREDO_TELEPHONY_PROVIDER must be 'real', 'mock' or 'demo'")

        state_dir = Path(env.get("FREDO_STATE_DIR", ".local-state")).expanduser()

        eot_threshold = _float(env, "FREDO_EOT_THRESHOLD", 0.7)
        if not 0.5 <= eot_threshold <= 0.9:
            raise ValueError("FREDO_EOT_THRESHOLD must be between 0.5 and 0.9")
        eot_timeout_ms = _integer(env, "FREDO_EOT_TIMEOUT_MS", 7000)
        if not 500 <= eot_timeout_ms <= 10000:
            raise ValueError("FREDO_EOT_TIMEOUT_MS must be between 500 and 10000")
        eager_raw = env.get("FREDO_EAGER_EOT_THRESHOLD")
        eager_eot_threshold: float | None = None
        if eager_raw:
            eager_eot_threshold = _float(env, "FREDO_EAGER_EOT_THRESHOLD", 0.5)
            if not 0.3 <= eager_eot_threshold <= 0.9:
                raise ValueError("FREDO_EAGER_EOT_THRESHOLD must be between 0.3 and 0.9")
            if eager_eot_threshold > eot_threshold:
                raise ValueError("FREDO_EAGER_EOT_THRESHOLD must be <= FREDO_EOT_THRESHOLD")

        silence_reprompt = _integer(env, "FREDO_SILENCE_REPROMPT_SECONDS", 12)
        if not 5 <= silence_reprompt <= 60:
            raise ValueError("FREDO_SILENCE_REPROMPT_SECONDS must be between 5 and 60")
        silence_goodbye = _integer(env, "FREDO_SILENCE_GOODBYE_SECONDS", 10)
        if not 5 <= silence_goodbye <= 60:
            raise ValueError("FREDO_SILENCE_GOODBYE_SECONDS must be between 5 and 60")

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
            eot_threshold=eot_threshold,
            eot_timeout_ms=eot_timeout_ms,
            eager_eot_threshold=eager_eot_threshold,
            protect_disclosure=env.get("FREDO_PROTECT_DISCLOSURE", "1").strip().lower()
            not in {"0", "false", "no"},
            silence_reprompt_seconds=silence_reprompt,
            silence_goodbye_seconds=silence_goodbye,
            telephony_provider=provider,
            demo_endpoint=demo_endpoint,
            demo_access_token=demo_access_token,
            state_dir=state_dir,
        )

    def with_public_url(self, public_url: str) -> "Settings":
        return replace(self, public_url=public_url.rstrip("/"))

    def missing_for_real_call(self) -> list[str]:
        if self.telephony_provider == "demo":
            missing: list[str] = []
            if not self.demo_endpoint:
                missing.append("FREDO_DEMO_ENDPOINT")
            if not self.demo_access_token:
                missing.append("FREDO_DEMO_ACCESS_TOKEN")
            return missing
        if self.telephony_provider == "mock":
            return []
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
            "demo_configured": bool(self.demo_endpoint and self.demo_access_token),
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
