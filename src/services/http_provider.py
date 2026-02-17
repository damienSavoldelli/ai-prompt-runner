"""HTTP provider implementation using requests."""

from dataclasses import dataclass

import requests

from src.services.base import BaseProvider


@dataclass
class HTTPProviderConfig:
    """Configuration for the generic HTTP AI provider."""

    endpoint: str
    api_key: str
    timeout_seconds: int = 30
    model: str = "default"


class HTTPProvider(BaseProvider):
    """Simple JSON-over-HTTP provider.

    Expected API contract:
    Request JSON: {"model": "...", "prompt": "..."}
    Response JSON: {"response": "..."}
    """

    def __init__(self, config: HTTPProviderConfig) -> None:
        self.config = config

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.config.model, "prompt": prompt}

        response = requests.post(
            self.config.endpoint,
            headers=headers,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()

        result = body.get("response")
        if not isinstance(result, str):
            raise ValueError("Provider response must contain a string field 'response'.")
        return result