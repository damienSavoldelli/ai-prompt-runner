import pytest

from src.services.http_provider import HTTPProvider
from src.services.provider_factory import ConfigurationError, create_provider


def test_create_provider_returns_http_provider_with_cli_values() -> None:
    # Arrange + Act: build provider from explicit CLI-like values.
    provider = create_provider(
        provider_name="http",
        api_endpoint="http://localhost:11434/api/generate",
        api_key="dummy",
        api_model="llama3.2",
    )

    # Assert: returned provider type and normalized config are correct.
    assert isinstance(provider, HTTPProvider)
    assert provider.config.endpoint == "http://localhost:11434/api/generate"
    assert provider.config.api_key == "dummy"
    assert provider.config.model == "llama3.2"


def test_create_provider_rejects_unknown_provider() -> None:
    # Unsupported provider names must fail fast with a clear error.
    with pytest.raises(ConfigurationError, match="Unsupported provider"):
        create_provider(provider_name="unknown")


def test_create_provider_requires_endpoint() -> None:
    # Endpoint is mandatory for HTTP provider creation.
    with pytest.raises(ConfigurationError, match="AI_API_ENDPOINT is required"):
        create_provider(
            provider_name="http",
            api_endpoint="",
            api_key="dummy",
            api_model="llama3.2",
        )


def test_create_provider_requires_api_key() -> None:
    # API key is mandatory for authenticated provider calls.
    with pytest.raises(ConfigurationError, match="AI_API_KEY is required"):
        create_provider(
            provider_name="http",
            api_endpoint="http://localhost:11434/api/generate",
            api_key="",
            api_model="llama3.2",
        )