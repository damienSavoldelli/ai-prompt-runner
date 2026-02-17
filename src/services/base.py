"""Provider interface for future multi-provider support."""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract provider contract."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        raise NotImplementedError