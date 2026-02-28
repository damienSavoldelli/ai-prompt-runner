"""Provider interface for stable multi-provider support."""

from abc import ABC, abstractmethod


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