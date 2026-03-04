import pytest

from ai_prompt_runner.services.http_provider import HTTPProvider
from ai_prompt_runner.services.openai_compatible_provider import OpenAICompatibleProvider
from ai_prompt_runner.services.provider_factory import ConfigurationError, create_provider


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


def test_create_provider_supports_inception_alias_with_registry_defaults(monkeypatch) -> None:
    """
    Brand alias `inception` must resolve to the protocol-level OpenAI-compatible
    provider and use registry defaults when CLI endpoint/model are omitted.
    """
    # Isolate provider-default resolution from caller shell environment.
    monkeypatch.delenv("AI_API_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_API_MODEL", raising=False)

    provider = create_provider(
        provider_name="inception",
        api_key="dummy",
        timeout_seconds=10,
        max_retries=1,
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.endpoint == "https://api.inceptionlabs.ai/v1"
    assert provider.config.model == "inception/mercury-2"
    assert provider.config.api_key == "dummy"
    assert provider.config.timeout_seconds == 10
    assert provider.config.max_retries == 1


def test_create_provider_supports_openai_alias_with_registry_defaults(monkeypatch) -> None:
    """
    Canonical OpenAI alias should resolve to the OpenAI-compatible provider
    with default endpoint/model when CLI values are omitted.
    """
    # Isolate provider-default resolution from caller shell environment.
    monkeypatch.delenv("AI_API_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_API_MODEL", raising=False)

    provider = create_provider(
        provider_name="openai",
        api_key="dummy",
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.endpoint == "https://api.openai.com/v1"
    assert provider.config.model == "gpt-4o-mini"
    assert provider.config.api_key == "dummy"


def test_create_provider_supports_openrouter_alias_with_registry_defaults(monkeypatch) -> None:
    """
    Brand aliases backed by the same OpenAI-compatible protocol should still
    resolve to provider-specific defaults from the registry.
    """
    # Isolate provider-default resolution from caller shell environment.
    monkeypatch.delenv("AI_API_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_API_MODEL", raising=False)

    provider = create_provider(
        provider_name="openrouter",
        api_key="dummy",
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.endpoint == "https://openrouter.ai/api/v1"
    assert provider.config.model == "openrouter/auto"


def test_create_provider_allows_cli_overrides_on_openai_compatible_alias() -> None:
    """
    CLI arguments must keep highest precedence over provider defaults for
    endpoint and model selection.
    """
    provider = create_provider(
        provider_name="groq",
        api_endpoint="https://override.example/v1",
        api_key="dummy",
        api_model="override-model",
        timeout_seconds=7,
        max_retries=2,
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.endpoint == "https://override.example/v1"
    assert provider.config.model == "override-model"
    assert provider.config.timeout_seconds == 7
    assert provider.config.max_retries == 2
