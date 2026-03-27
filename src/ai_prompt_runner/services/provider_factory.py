"""Provider factory for runtime provider creation."""

import os
from dataclasses import dataclass
from typing import Callable, Literal

from ai_prompt_runner.core.errors import PromptRunnerError
from ai_prompt_runner.services.anthropic_provider import AnthropicProvider, AnthropicProviderConfig
from ai_prompt_runner.services.base import BaseProvider
from ai_prompt_runner.services.google_provider import GoogleProvider, GoogleProviderConfig
from ai_prompt_runner.services.http_provider import HTTPProvider, HTTPProviderConfig
from ai_prompt_runner.services.openai_compatible_provider import OpenAICompatibleProvider, OpenAICompatibleProviderConfig

class ConfigurationError(PromptRunnerError):
    """Raised when provider runtime configuration is invalid."""


# Tri-state capability status:
# - supported: guaranteed by this provider adapter
# - unsupported: explicitly not implemented in this adapter
# - unknown: depends on upstream backend/model, adapter cannot guarantee it
ProviderCapabilityState = Literal["supported", "unsupported", "unknown"]


@dataclass(frozen=True)
class ProviderCapabilities:
    """Capability matrix for features exposed by the CLI."""

    stream: ProviderCapabilityState
    system: ProviderCapabilityState
    usage: ProviderCapabilityState
    temperature: ProviderCapabilityState
    top_p: ProviderCapabilityState
    max_tokens: ProviderCapabilityState


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
    # Optional provider defaults used during config resolution.
    # They can also be reused in CLI/help or documentation.
    default_endpoint: str
    default_model: str
    # Provider capability contract used by safety validation layers.
    capabilities: ProviderCapabilities


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

def _build_openai_compatible_provider(config: ProviderRuntimeConfig) -> BaseProvider:
    """Build an OpenAI-compatible provider from normalized runtime configuration."""
    return OpenAICompatibleProvider(
        OpenAICompatibleProviderConfig(
            endpoint=config.endpoint,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    )

def _build_anthropic_provider(config: ProviderRuntimeConfig) -> BaseProvider:
    """Build an Anthropic Messages API provider from normalized runtime configuration."""
    return AnthropicProvider(
        AnthropicProviderConfig(
            endpoint=config.endpoint,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    )


def _build_google_provider(config: ProviderRuntimeConfig) -> BaseProvider:
    """Build a Google Gemini generateContent provider from normalized runtime configuration."""
    return GoogleProvider(
        GoogleProviderConfig(
            endpoint=config.endpoint,
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    )


# Central provider registry with protocol-level provider classes and brand aliases.
PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "http": ProviderSpec(
        provider_id="http",
        builder=_build_http_provider,
        default_endpoint="",
        default_model="default",
        capabilities=ProviderCapabilities(
            stream="unsupported",
            system="supported",
            usage="unsupported",
            temperature="unsupported",
            top_p="unsupported",
            max_tokens="unsupported",
        ),
    ),
    "openai_compatible": ProviderSpec(
        provider_id="openai_compatible",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "openai": ProviderSpec(
        provider_id="openai",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="supported",
            temperature="supported",
            top_p="supported",
            max_tokens="supported",
        ),
    ),
    "openrouter": ProviderSpec(
        provider_id="openrouter",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://openrouter.ai/api/v1",
        default_model="openrouter/auto",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "groq": ProviderSpec(
        provider_id="groq",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.groq.com/openai/v1",
        default_model="llama-3.1-70b-versatile",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "together": ProviderSpec(
        provider_id="together",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.together.xyz/v1",
        default_model="mistralai/Mixtral-8x7B-Instruct-v0.1",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "fireworks": ProviderSpec(
        provider_id="fireworks",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p1-70b-instruct",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "perplexity": ProviderSpec(
        provider_id="perplexity",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.perplexity.ai",
        default_model="llama-3.1-sonar-small-128k-online",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "inception": ProviderSpec(
        provider_id="inception",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.inceptionlabs.ai/v1",
        default_model="inception/mercury-2",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "x": ProviderSpec(
        provider_id="x",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.x.ai/v1",
        default_model="grok-3-latest",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "xai": ProviderSpec(
        provider_id="xai",
        builder=_build_openai_compatible_provider,
        default_endpoint="https://api.x.ai/v1",
        default_model="grok-3-latest",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "lmstudio": ProviderSpec(
        provider_id="lmstudio",
        builder=_build_openai_compatible_provider,
        default_endpoint="http://localhost:1234/v1",
        default_model="local-model",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "ollama": ProviderSpec(
        provider_id="ollama",
        builder=_build_openai_compatible_provider,
        default_endpoint="http://localhost:11434/v1",
        default_model="llama3.2",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="unknown",
            temperature="unknown",
            top_p="unknown",
            max_tokens="unknown",
        ),
    ),
    "anthropic": ProviderSpec(
        provider_id="anthropic",
        builder=_build_anthropic_provider,
        default_endpoint="https://api.anthropic.com/v1/messages",
        default_model="claude-3-7-sonnet-latest",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="supported",
            temperature="supported",
            top_p="supported",
            max_tokens="supported",
        ),
    ),
    "google": ProviderSpec(
        provider_id="google",
        builder=_build_google_provider,
        default_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        default_model="gemini-2.5-flash",
        capabilities=ProviderCapabilities(
            stream="supported",
            system="supported",
            usage="supported",
            temperature="supported",
            top_p="supported",
            max_tokens="supported",
        ),
    ),
}


def get_provider_spec(provider_name: str) -> ProviderSpec:
    """Return provider spec from registry or raise a configuration error."""
    provider_spec = PROVIDER_REGISTRY.get(provider_name)
    if provider_spec is None:
        raise ConfigurationError(f"Unsupported provider '{provider_name}'.")
    return provider_spec

def _resolve_runtime_config(
    provider_spec: ProviderSpec,
    api_endpoint: str | None,
    api_key: str | None,
    api_model: str | None,
    timeout_seconds: int | None,
    max_retries: int | None,
) -> ProviderRuntimeConfig:
    """
    Resolve runtime config with deterministic precedence:
    CLI args > environment variables > provider defaults.
    """

    # Endpoint can come from CLI, env, or provider-specific default in registry.
    endpoint = (
        api_endpoint
        or os.getenv("AI_API_ENDPOINT")
        or provider_spec.default_endpoint
        or ""
    ).strip()

    # API key remains required for all current network providers.
    key = (api_key or os.getenv("AI_API_KEY", "")).strip()

    # Model can come from CLI, env, or provider-specific default in registry.
    model = (
        api_model
        or os.getenv("AI_API_MODEL")
        or provider_spec.default_model
        or "default"
    ).strip() or "default"

    # Keep existing timeout behavior unchanged.
    resolved_timeout = timeout_seconds if timeout_seconds is not None else 30
    if resolved_timeout <= 0:
        raise ConfigurationError("timeout_seconds must be greater than 0.")

    # Keep existing retry behavior unchanged.
    resolved_max_retries = max_retries if max_retries is not None else 0
    if resolved_max_retries < 0:
        raise ConfigurationError("max_retries must be greater than or equal to 0.")

    # Fail fast on missing required runtime credentials/config.
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

    Factory remains thin:
    - lookup provider by key
    - resolve normalized config once
    - delegate provider construction to the spec builder
    """
    provider_spec = get_provider_spec(provider_name)

    runtime_config = _resolve_runtime_config(
        provider_spec=provider_spec,
        api_endpoint=api_endpoint,
        api_key=api_key,
        api_model=api_model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

    return provider_spec.builder(runtime_config)
