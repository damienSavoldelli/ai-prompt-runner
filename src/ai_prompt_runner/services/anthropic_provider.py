"""Anthropic Messages API provider implementation using requests."""

from dataclasses import dataclass

import requests

from ai_prompt_runner.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)
from ai_prompt_runner.services.base import BaseProvider


@dataclass
class AnthropicProviderConfig:
    """Configuration for Anthropic Messages API requests."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0
    max_tokens: int = 1024


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic's Messages API contract."""

    def __init__(self, config: AnthropicProviderConfig) -> None:
        self.config = config

    def _raise_for_mapped_status(self, response: requests.Response) -> None:
        """Map provider HTTP status codes to domain-specific exceptions."""
        status_code = response.status_code

        explicit_status_errors = {
            401: AuthenticationError("Provider authentication failed (HTTP 401)."),
            403: AuthorizationError("Provider authorization failed (HTTP 403)."),
            429: RateLimitError("Provider rate limit exceeded (HTTP 429)."),
        }

        mapped_error = explicit_status_errors.get(status_code)
        if mapped_error is not None:
            raise mapped_error

        if 500 <= status_code <= 599:
            raise UpstreamServerError(f"Provider server error (HTTP {status_code}).")
        if status_code >= 400:
            raise ProviderError(f"Provider returned HTTP {status_code}.")

    def _extract_text(self, body: dict) -> str:
        """
        Extract text from Anthropic Messages API response payload.

        Expected shape:
        {
            "content": [
                {"type": "text", "text": "..."},
                ...
            ]
        }
        """
        content_blocks = body.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise ProviderError("Provider response must contain a non-empty 'content' list.")

        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue

            text = block.get("text")
            if isinstance(text, str):
                return text
            raise ProviderError("Provider text content block must contain string 'text'.")

        raise ProviderError("Provider response must contain at least one text content block.")

    def generate(self, prompt: str) -> str:
        """Send one prompt to Anthropic and return generated text."""
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Retry only transient transport failures.
        for attempt in range(self.config.max_retries + 1):
            try:
                response = requests.post(
                    self.config.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt == self.config.max_retries:
                    raise ProviderError(f"Provider request failed: {exc}") from exc
                continue

            self._raise_for_mapped_status(response)

            try:
                body = response.json()
            except ValueError as exc:
                raise ProviderError("Provider returned invalid JSON.") from exc

            return self._extract_text(body)

        # Defensive fallback: loop always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")
