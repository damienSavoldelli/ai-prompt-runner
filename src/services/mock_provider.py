"""Mock provider implementation for contract validation and local tests."""

from src.services.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic provider implementation without network access."""

    def generate(self, prompt: str) -> str:
        """Return a deterministic response for the provided prompt."""
        return f"Echo: {prompt}"