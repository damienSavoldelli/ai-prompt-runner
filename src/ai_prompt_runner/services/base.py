"""Provider interface for stable multi-provider support."""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class BaseProvider(ABC):
    """Abstract provider contract.

    Implementations must accept a full prompt string and return a response
    string on success.

    Implementations must raise a provider-domain exception when generation
    fails.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate response text from the provided prompt."""
        raise NotImplementedError

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """
        Stream response chunks from the provided prompt.
        Providers that do not support streaming should keep this default behavior so callers can explicitly fallback to non-stream execution.
        """
        raise NotImplementedError("Streaming is not supported by this provider.")
