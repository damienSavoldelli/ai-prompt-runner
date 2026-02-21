import pytest
import requests

from src.core.errors import ProviderError
from src.services.http_provider import HTTPProvider, HTTPProviderConfig


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_generate_retries_then_succeeds(monkeypatch) -> None:
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
