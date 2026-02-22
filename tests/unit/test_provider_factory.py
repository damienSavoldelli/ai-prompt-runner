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
        timeout_seconds=12,
        max_retries=3,
    )

    # Assert: returned provider type and normalized config are correct.
    assert isinstance(provider, HTTPProvider)
    assert provider.config.endpoint == "http://localhost:11434/api/generate"
    assert provider.config.api_key == "dummy"
    assert provider.config.model == "llama3.2"
    assert provider.config.timeout_seconds == 12
    assert provider.config.max_retries == 3


def test_create_provider_rejects_unknown_provider() -> None:
    # Unsupported provider names must fail fast with a clear error.
    with pytest.raises(ConfigurationError, match="Unsupported provider"):
        create_provider(provider_name="unknown")


def test_create_provider_requires_endpoint(monkeypatch) -> None:
    # Endpoint is mandatory for HTTP provider creation.    
    monkeypatch.delenv("AI_API_ENDPOINT", raising=False) # Remove env fallback to validate explicit missing endpoint behavior.
    with pytest.raises(ConfigurationError, match="AI_API_ENDPOINT is required"):
        create_provider(
            provider_name="http",
            api_endpoint="",
            api_key="dummy",
            api_model="llama3.2",
        )


def test_create_provider_requires_api_key(monkeypatch) -> None:
    # API key is mandatory for authenticated provider calls.   
    monkeypatch.delenv("AI_API_KEY", raising=False) # Remove env fallback to validate explicit missing API key behavior.
    with pytest.raises(ConfigurationError, match="AI_API_KEY is required"):
        create_provider(
            provider_name="http",
            api_endpoint="http://localhost:11434/api/generate",
            api_key="",
            api_model="llama3.2",
        )
        
@pytest.mark.parametrize("bad_timeout", [0, -5])
def test_create_provider_rejects_invalid_timeout(bad_timeout: int) -> None:
    # Timeout must be a positive integer if provided.
    with pytest.raises(ConfigurationError, match="timeout_seconds must be greater than 0"):
        create_provider(
            provider_name="http",
            api_endpoint="http://localhost:11434/api/generate",
            api_key="dummy",
            api_model="llama3.2",
            timeout_seconds=bad_timeout,
        )

def test_create_provider_rejects_negative_retries() -> None:
    with pytest.raises(ConfigurationError, match="max_retries must be greater than or equal to 0"):
        create_provider(
            provider_name="http",
            api_endpoint="http://localhost:11434/api/generate",
            api_key="dummy",
            api_model="llama3.2",
            max_retries=-1,
        )