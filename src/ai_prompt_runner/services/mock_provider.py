"""Mock provider implementation for contract validation and local tests."""

from collections.abc import Iterator

from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.services.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic provider implementation without network access."""

    def __init__(self, failure_message: str | None = None) -> None:
        self.failure_message = failure_message

    def generate(self, prompt: str) -> str:
        """Return deterministic text or raise a provider-domain error."""
        if self.failure_message is not None:
            raise ProviderError(self.failure_message)
        return f"Echo: {prompt}"

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """
        Yield deterministic chunks for stream-path tests without network I/O.

        The stream shape is intentionally simple and stable: one character
        at a time, which makes reconstruction assertions deterministic.
        """
        if self.failure_message is not None:
            raise ProviderError(self.failure_message)
        for char in f"Echo: {prompt}":
            yield char
