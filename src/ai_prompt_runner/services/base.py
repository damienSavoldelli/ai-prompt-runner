"""Provider interface for stable multi-provider support."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from ai_prompt_runner.core.models import GenerationConfig, UsageMetadata


class BaseProvider(ABC):
    """Abstract provider contract.

    Implementations must accept a full prompt string and return a response
    string on success.

    Implementations must raise a provider-domain exception when generation
    fails.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        """Generate response text from the provided prompt."""
        raise NotImplementedError

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """
        Stream response chunks from the provided prompt.

        `system_prompt` is optional and represents one-shot instruction context
        for providers that support role-aware prompting.

        `generation_config` carries optional runtime controls such as
        temperature, max token budget, and top-p sampling.

        Providers that do not support streaming should keep this default
        behavior so callers can explicitly fallback to non-stream execution.
        """
        raise NotImplementedError("Streaming is not supported by this provider.")

    def get_last_usage(self) -> UsageMetadata | None:
        """
        Return normalized usage metadata captured during the last provider call.

        Providers can override this hook when upstream APIs expose token usage.
        The default returns None to keep compatibility with providers that do
        not expose usage metrics.
        """
        return None
