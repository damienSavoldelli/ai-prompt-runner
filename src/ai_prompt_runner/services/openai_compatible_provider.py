"""OpenAI-compatible provider porvider implementation using requests."""

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
class OpenAICompatibleProviderConfig:
    """Configuration for OpenAI-compatible chat completion providers."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0


class OpenAICompatibleProvider(BaseProvider):
    """
    Provider for APIs that expose an OpenAI-compatible chat-completions contract.

    Request shape sent:
    {
        "model": "...",
        "messages": [{"role": "user", "content": "..."}]
    }

    Response shape expected:
    {
        "choices": [{"message": {"content": "..."}}]
    }
    """

    def __init__(self, config: OpenAICompatibleProviderConfig) -> None:
        self.config = config

    def _normalized_endpoint(self) -> str:
        """
        Normalize endpoint to the chat-completions route.

        We allow callers to provide either:
        - base URL (e.g. https://api.openai.com/v1)
        - full route (.../chat/completions)

        This keeps factory defaults and user overrides flexible.
        """
        base = self.config.endpoint.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _raise_for_mapped_status(self, response: requests.Response) -> None:
        """Map provider HTTP status codes to domain-specific exceptions."""
        status_code = response.status_code

        # Explicit mappings for statuses we want to classify precisely.
        explicit_status_errors = {
            401: AuthenticationError("Provider authentication failed (HTTP 401)."),
            403: AuthorizationError("Provider authorization failed (HTTP 403)."),
            429: RateLimitError("Provider rate limit exceeded (HTTP 429)."),
        }

        mapped_error = explicit_status_errors.get(status_code)
        if mapped_error is not None:
            raise mapped_error

        # Fallback classification keeps behavior deterministic for unknown error statuses.
        if 500 <= status_code <= 599:
            raise UpstreamServerError(f"Provider server error (HTTP {status_code}).")
        if status_code >= 400:
            raise ProviderError(f"Provider returned HTTP {status_code}.")

    def _extract_text(self, body: dict) -> str:
        """
        Extract text from an OpenAI-compatible response payload.

        We validate each layer explicitly to fail fast with clear domain errors
        if an upstream service returns an unexpected shape.
        """
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("Provider response must contain a non-empty 'choices' list.")

        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderError("Provider response choice must be an object.")

        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderError("Provider response choice must contain a 'message' object.")

        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderError("Provider response message must contain string 'content'.")

        return content

    def generate(self, prompt: str) -> str:
        """
        Send a single prompt and return generated text.

        Contract: one prompt in, one response string out.
        """
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Retry only transient transport errors. Deterministic HTTP responses are handled directly.
        for attempt in range(self.config.max_retries + 1):
            try:
                response = requests.post(
                    self._normalized_endpoint(),
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

        # Defensive fallback: the loop above always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")