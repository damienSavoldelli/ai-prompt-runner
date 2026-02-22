import pytest
import requests

from src.services.http_provider import HTTPProvider, HTTPProviderConfig

from src.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)

class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    # Kept for compatibility with earlier tests / provider implementations.
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_generate_retries_then_succeeds(monkeypatch) -> None:
    """Test that if the provider call fails with a transient error, we retry the expected number of times and eventually succeed if the error resolves."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://example.test/api",
            api_key="dummy",
            model="m1",
            timeout_seconds=5,
            max_retries=2,
        )
    )

    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network error")
        return DummyResponse({"response": "ok"})

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

    result = provider.generate("hello")
    assert result == "ok"
    assert calls["count"] == 3


def test_generate_fails_after_retry_exhausted(monkeypatch) -> None:
    """Test that if the provider call fails with a transient error and we exhaust all retries, we raise a ProviderError."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://example.test/api",
            api_key="dummy",
            model="m1",
            timeout_seconds=5,
            max_retries=1,
        )
    )

    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise requests.Timeout("timed out")

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

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
def test_generate_maps_http_status_to_specific_errors(monkeypatch, status_code: int, expected_error: type[Exception]) -> None:
    """Test that specific HTTP error statuses from the provider are mapped to our domain-specific exceptions."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://example.test/api",
            api_key="dummy",
            model="m1",
            timeout_seconds=5,
            max_retries=2,
        )
    )

    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return DummyResponse({"error": "x"}, status_code=status_code)

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

    with pytest.raises(expected_error):
        provider.generate("hello")

    # HTTP status errors are deterministic responses, so they should fail immediately.
    assert calls["count"] == 1
    
def test_generate_maps_unknown_4xx_to_generic_provider_error(monkeypatch) -> None:
    """Test that an unexpected 4xx status code from the provider results in a generic ProviderError rather than an uncaught exception or incorrect mapping."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://localhost:11434/api/generate",
            api_key="dummy",
            model="llama3.2",
            timeout_seconds=5,
            max_retries=0,
        )
    )

    class FakeResponse:
        status_code = 418

        def json(self):
            return {"response": "unused"}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

    with pytest.raises(ProviderError, match="Provider returned HTTP 418."):
        provider.generate("Hello")
        
def test_generate_rejects_invalid_json_response(monkeypatch) -> None:
    """Test that if the provider returns a 200 OK but the body is not valid JSON, we raise a ProviderError with a clear message."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://localhost:11434/api/generate",
            api_key="dummy",
            model="llama3.2",
            timeout_seconds=5,
            max_retries=0,
        )
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("invalid json")

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

    with pytest.raises(ProviderError, match="Provider returned invalid JSON."):
        provider.generate("Hello")
    
    
def test_generate_rejects_non_string_response_field(monkeypatch) -> None:
    """Test that if the provider returns a JSON response without the expected 'response' field or if it's not a string, we raise a ProviderError."""
    provider = HTTPProvider(
        HTTPProviderConfig(
            endpoint="http://localhost:11434/api/generate",
            api_key="dummy",
            model="llama3.2",
            timeout_seconds=5,
            max_retries=0,
        )
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"response": 123}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("src.services.http_provider.requests.post", fake_post)

    with pytest.raises(ProviderError, match="Provider response must contain a string field 'response'."):
          provider.generate("Hello")