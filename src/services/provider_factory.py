
"""Provider factory for runtime provider creation."""

import os

from src.core.errors import PromptRunnerError
from src.services.base import BaseProvider
from src.services.http_provider import HTTPProvider, HTTPProviderConfig


class ConfigurationError(PromptRunnerError):
    """Raised when provider runtime configuration is invalid."""


def create_provider(
    provider_name: str,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    api_model: str | None = None,
) -> BaseProvider:
    """Create a provider instance from CLI args and environment fallback."""
    # Restrict to supported providers for now (future: add more branches).
    if provider_name != "http":
        raise ConfigurationError(f"Unsupported provider '{provider_name}'.")

    # CLI flags have priority; environment variables provide defaults.
    endpoint = (api_endpoint or os.getenv("AI_API_ENDPOINT", "")).strip()
    key = (api_key or os.getenv("AI_API_KEY", "")).strip()
    model = (api_model or os.getenv("AI_API_MODEL", "default")).strip() or "default"

    # Fail fast with explicit configuration errors.
    if not endpoint:
        raise ConfigurationError("AI_API_ENDPOINT is required.")
    if not key:
        raise ConfigurationError("AI_API_KEY is required.")

    # Return a provider instance matching the BaseProvider contract.
    return HTTPProvider(
        HTTPProviderConfig(
            endpoint=endpoint,
            api_key=key,
            model=model,
        )
    )