import pytest
import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.services.google_provider import (
    GoogleProvider,
    GoogleProviderConfig,
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
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models",
    max_retries: int = 0,
) -> GoogleProvider:
    """Build provider instances with deterministic test defaults."""
    return GoogleProvider(
        GoogleProviderConfig(
            endpoint=endpoint,
            api_key="dummy",
            model="gemini-2.5-flash",
            timeout_seconds=5,
            max_retries=max_retries,
        )
    )


def test_generate_returns_text_and_normalizes_endpoint(monkeypatch) -> None:
    """Extract generated text and build expected generateContent endpoint."""
    provider = _make_provider()
    observed = {}

    def fake_post(url, headers, json, timeout):
        observed["url"] = url
        observed["headers"] = headers
        observed["json"] = json
        observed["timeout"] = timeout
        return DummyResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Echo: hello"}]}}
                ]
            },
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        fake_post,
    )

    result = provider.generate("hello")

    assert result == "Echo: hello"
    assert (
        observed["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    )
    assert observed["json"]["contents"][0]["parts"][0]["text"] == "hello"
    assert observed["timeout"] == 5


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Transient transport errors should be retried up to max_retries."""
    provider = _make_provider(max_retries=2)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse(
            {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
            status_code=200,
        )

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
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
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("hello")


def test_generate_rejects_missing_candidates_list(monkeypatch) -> None:
    """Response payload must include a non-empty candidates list."""
    provider = _make_provider()

    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse({"response": "unused"}, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response must contain a non-empty 'candidates' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_object_candidate(monkeypatch) -> None:
    """Each candidate entry must be an object."""
    provider = _make_provider()

    payload = {"candidates": [123]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response candidate must be an object.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_content_object(monkeypatch) -> None:
    """Each candidate must include a content object."""
    provider = _make_provider()

    payload = {"candidates": [{}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response candidate must contain a 'content' object.",
    ):
        provider.generate("hello")


def test_generate_rejects_missing_parts_list(monkeypatch) -> None:
    """Candidate content must include a non-empty parts list."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response content must contain a non-empty 'parts' list.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_object_part(monkeypatch) -> None:
    """Each part entry must be an object."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {"parts": [123]}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response part must be an object.",
    ):
        provider.generate("hello")


def test_generate_rejects_non_string_part_text(monkeypatch) -> None:
    """Part text must be a string to satisfy provider contract."""
    provider = _make_provider()

    payload = {"candidates": [{"content": {"parts": [{"text": 123}]}}]}
    monkeypatch.setattr(
        "ai_prompt_runner.services.google_provider.requests.post",
        lambda *args, **kwargs: DummyResponse(payload, status_code=200),
    )

    with pytest.raises(
        ProviderError,
        match="Provider response part must contain string 'text'.",
    ):
        provider.generate("hello")


def test_generate_defensive_fallback_on_invalid_retry_config() -> None:
    """
    Defensive path coverage: if a caller constructs an invalid config
    (negative max_retries), the loop is skipped and fallback error is raised.
    """
    provider = _make_provider(max_retries=-1)

    with pytest.raises(ProviderError, match="Provider request failed unexpectedly."):
        provider.generate("hello")
