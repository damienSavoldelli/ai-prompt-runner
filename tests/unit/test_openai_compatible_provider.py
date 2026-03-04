import pytest
import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.services.openai_compatible_provider import (
    OpenAICompatibleProvider,
    OpenAICompatibleProviderConfig,
)


class DummyResponse:
    """Small test double for requests.Response-like JSON behavior."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def _make_provider(
    *,
    endpoint: str = "https://api.openai.com/v1",
    max_retries: int = 0,
) -> OpenAICompatibleProvider:
    """Build provider instances with deterministic test defaults."""
    return OpenAICompatibleProvider(
        OpenAICompatibleProviderConfig(
            endpoint=endpoint,
            api_key="dummy",
            model="gpt-4o-mini",
            timeout_seconds=5,
            max_retries=max_retries,
        )
    )


def test_generate_returns_text_and_normalizes_endpoint(monkeypatch) -> None:
    """
    Validate nominal behavior:
    - the endpoint is normalized to /chat/completions
    - the provider extracts text from choices[0].message.content
    """
    provider = _make_provider(endpoint="https://api.openai.com/v1")
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Echo: hello"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    result = provider.generate("hello")

    assert result == "Echo: hello"
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["json"]["model"] == "gpt-4o-mini"
    assert observed["json"]["messages"][0]["role"] == "user"
    assert observed["json"]["messages"][0]["content"] == "hello"
    assert observed["timeout"] == 5


def test_generate_preserves_full_chat_completions_endpoint(monkeypatch) -> None:
    """
    If caller already provides /chat/completions, provider must not duplicate
    the suffix.
    """
    provider = _make_provider(
        endpoint="https://api.openai.com/v1/chat/completions",
    )
    called = {"url": ""}

    def fake_post(url, headers, json, timeout):
        called["url"] = url
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello") == "ok"
    assert called["url"] == "https://api.openai.com/v1/chat/completions"


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Transient transport errors should be retried up to max_retries."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse(
            {"choices": [{"message": {"content": "ok"}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    assert provider.generate("hello") == "ok"
    assert calls["count"] == 3


def test_generate_fails_after_retry_exhausted(monkeypatch) -> None:
    """Exhausted retries should raise a ProviderError with clear context."""
    provider = _make_provider(max_retries=1)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.Timeout("timed out")

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider request failed"):
        provider.generate("hello")

    assert calls["count"] == 2


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (429, RateLimitError),
        (503, UpstreamServerError),
    ],
)
def test_generate_maps_http_status_to_domain_errors(
    monkeypatch,
    status_code: int,
    expected_error: type[Exception],
) -> None:
    """Known HTTP statuses must map to stable domain exceptions."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyResponse({"error": "x"}, status_code=status_code)

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    with pytest.raises(expected_error):
        provider.generate("hello")

    # Deterministic status responses should fail immediately (no retries).
    assert calls["count"] == 1


def test_generate_maps_unknown_4xx_to_provider_error(monkeypatch) -> None:
    """Unexpected 4xx statuses should map to the generic ProviderError."""
    provider = _make_provider()

    def fake_post(*args, **kwargs):
        return DummyResponse({"error": "unused"}, status_code=418)

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        fake_post,
    )

    with pytest.raises(ProviderError, match="Provider returned HTTP 418."):
        provider.generate("hello")


def test_generate_rejects_invalid_json_response(monkeypatch) -> None:
    """A 200 response with invalid JSON must raise a ProviderError."""
    provider = _make_provider()

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("invalid json")

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("hello")


def test_generate_rejects_missing_choices(monkeypatch) -> None:
    """Response payload must include a non-empty choices list."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "unused"}, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain a non-empty 'choices' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_string_message_content(monkeypatch) -> None:
    """content must be a plain string to satisfy provider contract."""
    provider = _make_provider()

    payload = {"choices": [{"message": {"content": 123}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.openai_compatible_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response message must contain string 'content'.",
    ):
        provider.generate("hello")
