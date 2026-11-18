"""Settings: fail-closed validation of safety bounds and provider selection."""

from __future__ import annotations

import pytest

from fredo.settings import Settings

BASE = {"FREDO_TELEPHONY_PROVIDER": "real"}


@pytest.mark.parametrize("value", ["9", "181", "600"])
def test_duration_cap_cannot_exceed_180_seconds(value: str) -> None:
    with pytest.raises(ValueError, match="FREDO_MAX_DURATION_SECONDS"):
        Settings.from_env({**BASE, "FREDO_MAX_DURATION_SECONDS": value})


def test_duration_cap_defaults_to_180() -> None:
    assert Settings.from_env(BASE).max_duration_seconds == 180


def test_concurrency_is_pinned_to_one_call() -> None:
    with pytest.raises(ValueError, match="FREDO_MAX_CONCURRENT_CALLS"):
        Settings.from_env({**BASE, "FREDO_MAX_CONCURRENT_CALLS": "2"})


def test_allowlist_is_parsed_from_csv() -> None:
    settings = Settings.from_env({**BASE, "FREDO_ALLOWED_NUMBERS": " +33600000000, ,+33600000001"})
    assert settings.allowed_numbers == frozenset({"+33600000000", "+33600000001"})


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="FREDO_TELEPHONY_PROVIDER"):
        Settings.from_env({"FREDO_TELEPHONY_PROVIDER": "pstn"})


def test_settings_reject_out_of_range_endpointing() -> None:
    with pytest.raises(ValueError, match="FREDO_EOT_THRESHOLD"):
        Settings.from_env({**BASE, "FREDO_EOT_THRESHOLD": "0.2"})


def test_settings_reject_eager_above_eot() -> None:
    with pytest.raises(ValueError, match="FREDO_EAGER_EOT_THRESHOLD"):
        Settings.from_env(
            {**BASE, "FREDO_EOT_THRESHOLD": "0.6", "FREDO_EAGER_EOT_THRESHOLD": "0.8"}
        )


def test_settings_auto_select_demo_without_provider_keys() -> None:
    settings = Settings.from_env(
        {"FREDO_DEMO_ENDPOINT": "https://relay.example", "FREDO_DEMO_ACCESS_TOKEN": "public-demo"}
    )
    assert settings.telephony_provider == "demo"
    assert settings.missing_for_real_call() == []
    assert settings.public_summary()["demo_configured"] is True


def test_real_mode_reports_missing_configuration_without_values() -> None:
    settings = Settings(telephony_provider="real", deepgram_api_key="dg-secret")
    missing = settings.missing_for_real_call()
    assert "TWILIO_AUTH_TOKEN" in missing and "DEEPGRAM_API_KEY" not in missing
    assert "dg-secret" not in repr(settings)
    assert "dg-secret" not in str(settings.public_summary())
