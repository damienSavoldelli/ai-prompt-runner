import pytest

from src.core.errors import ProviderError
from src.services.base import BaseProvider
from src.services.http_provider import HTTPProvider, HTTPProviderConfig
from src.services.mock_provider import MockProvider


def _make_provider(provider_name: str, failure_message: str | None = None) -> BaseProvider:
    """Build a provider instance for shared contract tests."""
    if provider_name == "http":
        return HTTPProvider(
            HTTPProviderConfig(
                endpoint="http://localhost:11434/api/generate",
                api_key="dummy",
                model="llama3.2",
                timeout_seconds=5,
                max_retries=0,
            )
        )

    if provider_name == "mock":
        return MockProvider(failure_message=failure_message)

    raise AssertionError(f"Unknown provider fixture '{provider_name}'.")


@pytest.mark.parametrize("provider_name", ["http", "mock"])
def test_provider_contract_generate_returns_string_for_valid_prompt(
    provider_name: str,
    monkeypatch,
) -> None:
    """A provider must return response text for a valid prompt."""
    provider = _make_provider(provider_name)

    if provider_name == "http":
        class FakeResponse:
            status_code = 200

            def json(self) -> dict:
                return {"response": "Echo: hello"}

        monkeypatch.setattr(
            "src.services.http_provider.requests.post",
            lambda *args, **kwargs: FakeResponse(),
        )

    result = provider.generate("hello")

    assert isinstance(result, str)
    assert result == "Echo: hello"


@pytest.mark.parametrize("provider_name", ["http", "mock"])
def test_provider_contract_generate_raises_provider_error_on_failure(
    provider_name: str,
    monkeypatch,
) -> None:
    """A provider must raise a provider-domain error on generation failure."""
    provider = _make_provider(provider_name, failure_message="mock failure")

    if provider_name == "http":
        from src.services.http_provider import requests

        def fake_post(*args, **kwargs):
            raise requests.ConnectionError("network down")

        monkeypatch.setattr(
            "src.services.http_provider.requests.post",
            fake_post,
        )

    with pytest.raises(ProviderError):
        provider.generate("hello")