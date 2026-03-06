"""Google Gemini generateContent provider implementation using requests."""

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
class GoogleProviderConfig:
    """Configuration for Google Gemini generateContent requests."""

    endpoint: str
    api_key: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 0


class GoogleProvider(BaseProvider):
    """Provider for Gemini generateContent protocol."""

    def __init__(self, config: GoogleProviderConfig) -> None:
        self.config = config

    def _normalized_endpoint(self) -> str:
        """
        Build full generateContent URL from a base models endpoint.

        Example:
        https://generativelanguage.googleapis.com/v1beta/models
        -> .../models/{model}:generateContent
        """
        base = self.config.endpoint.rstrip("/")
        return f"{base}/{self.config.model}:generateContent"

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
        Extract text from Gemini generateContent response payload.

        Expected shape:
        {
            "candidates": [
                {"content": {"parts": [{"text": "..."}]}}
            ]
        }
        """
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError("Provider response must contain a non-empty 'candidates' list.")

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ProviderError("Provider response candidate must be an object.")

        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise ProviderError("Provider response candidate must contain a 'content' object.")

        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ProviderError("Provider response content must contain a non-empty 'parts' list.")

        first_part = parts[0]
        if not isinstance(first_part, dict):
            raise ProviderError("Provider response part must be an object.")

        text = first_part.get("text")
        if not isinstance(text, str):
            raise ProviderError("Provider response part must contain string 'text'.")

        return text

    def generate(self, prompt: str) -> str:
        """Send one prompt to Gemini and return generated text."""
        headers = {
            "x-goog-api-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        }

        # Retry only transient transport failures.
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

        # Defensive fallback: loop always returns or raises.
        raise ProviderError("Provider request failed unexpectedly.")
