"""Unit tests for the public Python API facade."""

import pytest

from ai_prompt_runner.api import run_prompt
from ai_prompt_runner.services.provider_factory import ConfigurationError


class DummyResponse:
    """Minimal fake HTTP response object for provider monkeypatching."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def test_run_prompt_returns_normalized_payload_with_http_provider(monkeypatch) -> None:
    """Public API should return the same normalized payload shape as CLI execution."""
    monkeypatch.setattr(
        "ai_prompt_runner.services.http_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "Echo: Hello from API"}),
    )

    payload = run_prompt(
        prompt="Hello from API",
        provider="http",
        api_endpoint="http://example.test/api",
        api_key="dummy",
        api_model="m1",
        timeout_seconds=5,
        max_retries=0,
    )

    assert payload["prompt"] == "Hello from API"
    assert payload["response"] == "Echo: Hello from API"
    assert payload["metadata"]["provider"] == "http"
    assert "timestamp_utc" in payload["metadata"]


def test_run_prompt_forwards_system_prompt_to_http_provider(monkeypatch) -> None:
    """System prompt should be forwarded through the same runner/provider pipeline."""

    def fake_post(*args, **kwargs):
        payload = kwargs["json"]
        assert "SYSTEM:\nYou are strict.\n\nUSER:\nHello" == payload["prompt"]
        return DummyResponse({"response": "Echo: ok"})

    monkeypatch.setattr(
        "ai_prompt_runner.services.http_provider.requests.post",
        fake_post,
    )

    payload = run_prompt(
        prompt="Hello",
        system_prompt="You are strict.",
        provider="http",
        api_endpoint="http://example.test/api",
        api_key="dummy",
        api_model="m1",
    )

    assert payload["response"] == "Echo: ok"


def test_run_prompt_raises_configuration_error_for_unknown_provider() -> None:
    """Unknown providers should raise the same configuration error as CLI path."""
    with pytest.raises(ConfigurationError, match="Unsupported provider"):
        run_prompt(prompt="Hello", provider="unknown-provider", api_key="dummy")


def test_run_prompt_raises_configuration_error_when_endpoint_missing() -> None:
    """Factory-level config validation must be preserved in public API mode."""
    with pytest.raises(ConfigurationError, match="AI_API_ENDPOINT is required"):
        run_prompt(
            prompt="Hello",
            provider="http",
            api_key="dummy",
            api_endpoint="",
        )
