"""Provider factory for runtime provider creation."""

import os
from dataclasses import dataclass
from typing import Callable

from ai_prompt_runner.core.errors import PromptRunnerError
from ai_prompt_runner.services.base import BaseProvider
from ai_prompt_runner.services.http_provider import HTTPProvider, HTTPProviderConfig


class ConfigurationError(PromptRunnerError):
    """Raised when provider runtime configuration is invalid."""


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    """Normalized provider runtime configuration after precedence resolution."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class ProviderSpec:
    """Factory metadata for a supported provider."""

    # Canonical provider key used by the registry.
    provider_id: str
    # Callable that builds a concrete provider instance from normalized config.
    builder: Callable[[ProviderRuntimeConfig], BaseProvider]


def _build_http_provider(config: ProviderRuntimeConfig) -> BaseProvider:
    """Build the existing HTTP provider from normalized runtime configuration."""
    return HTTPProvider(
        HTTPProviderConfig(
            endpoint=config.endpoint,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    )


# Central provider registry.
# In v1.1 step 1 we keep only the current behavior: "http" provider support.
PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "http": ProviderSpec(provider_id="http", builder=_build_http_provider),
}


def _resolve_runtime_config(
    api_endpoint: str | None,
    api_key: str | None,
    api_model: str | None,
    timeout_seconds: int | None,
    max_retries: int | None,
) -> ProviderRuntimeConfig:
    """
    Resolve runtime config with deterministic precedence:
    CLI args > environment variables > internal defaults.
    """
    endpoint = (api_endpoint or os.getenv("AI_API_ENDPOINT", "")).strip()
    key = (api_key or os.getenv("AI_API_KEY", "")).strip()
    model = (api_model or os.getenv("AI_API_MODEL", "default")).strip() or "default"

    # Keep old timeout behavior exactly as before.
    resolved_timeout = timeout_seconds if timeout_seconds is not None else 30
    if resolved_timeout <= 0:
        raise ConfigurationError("timeout_seconds must be greater than 0.")

    # Keep old retries behavior exactly as before.
    resolved_max_retries = max_retries if max_retries is not None else 0
    if resolved_max_retries < 0:
        raise ConfigurationError("max_retries must be greater than or equal to 0.")

    # Required fields for authenticated HTTP calls.
    if not endpoint:
        raise ConfigurationError("AI_API_ENDPOINT is required.")
    if not key:
        raise ConfigurationError("AI_API_KEY is required.")

    return ProviderRuntimeConfig(
        endpoint=endpoint,
        api_key=key,
        model=model,
        timeout_seconds=resolved_timeout,
        max_retries=resolved_max_retries,
    )


def create_provider(
    provider_name: str,
    api_endpoint: str | None = None,
    api_key: str | None = None,
    api_model: str | None = None,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
) -> BaseProvider:
    """
    Create a provider from a registry entry.

    This keeps factory logic thin:
    - lookup provider by key
    - resolve normalized config once
    - delegate construction to the provider spec
    """
    provider_spec = PROVIDER_REGISTRY.get(provider_name)
    if provider_spec is None:
        raise ConfigurationError(f"Unsupported provider '{provider_name}'.")

    runtime_config = _resolve_runtime_config(
        api_endpoint=api_endpoint,
        api_key=api_key,
        api_model=api_model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

    return provider_spec.builder(runtime_config)