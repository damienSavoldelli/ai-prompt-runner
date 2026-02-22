"""HTTP provider implementation using requests."""

from dataclasses import dataclass

import requests

from src.services.base import BaseProvider

from src.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ProviderError,
    RateLimitError,
    UpstreamServerError,
)

@dataclass
class HTTPProviderConfig:
    """Configuration for the generic HTTP AI provider."""

    endpoint: str
    api_key: str
    timeout_seconds: int = 30
    model: str = "default"
    max_retries: int = 0


class HTTPProvider(BaseProvider):
    """Simple JSON-over-HTTP provider.

    Expected API contract:
    Request JSON: {"model": "...", "prompt": "..."}
    Response JSON: {"response": "..."}
    """

    def __init__(self, config: HTTPProviderConfig) -> None:
        self.config = config
        
    def _raise_for_mapped_status(self, response: requests.Response) -> None:
        """Raise domain-specific exceptions for known HTTP error statuses."""
        status_code = response.status_code

        if status_code == 401:
            raise AuthenticationError("Provider authentication failed (HTTP 401).")
        if status_code == 403:
            raise AuthorizationError("Provider authorization failed (HTTP 403).")
        if status_code == 429:
            raise RateLimitError("Provider rate limit exceeded (HTTP 429).")
        if 500 <= status_code <= 599:
            raise UpstreamServerError(f"Provider server error (HTTP {status_code}).")
        if status_code >= 400:
            raise ProviderError(f"Provider returned HTTP {status_code}.")
        

    def generate(self, prompt: str) -> str:
        """Send the prompt to the provider and return the response string."""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.config.model, "prompt": prompt}

        # Implement simple retry logic for transient network errors.
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

            # Check for HTTP errors and raise appropriate exceptions.
            self._raise_for_mapped_status(response)

            try:
                body = response.json()
                break
            except ValueError as exc:
                raise ProviderError("Provider returned invalid JSON.") from exc

        result = body.get("response")
        if not isinstance(result, str):
            raise ProviderError("Provider response must contain a string field 'response'.")
        return result