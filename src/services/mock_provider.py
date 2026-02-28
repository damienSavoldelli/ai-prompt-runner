"""Mock provider implementation for contract validation and local tests."""

from src.core.errors import ProviderError
from src.services.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic provider implementation without network access."""

    def __init__(self, failure_message: str | None = None) -> None:
        self.failure_message = failure_message

    def generate(self, prompt: str) -> str:
        """Return deterministic text or raise a provider-domain error."""
        if self.failure_message is not None:
            raise ProviderError(self.failure_message)
        return f"Echo: {prompt}"