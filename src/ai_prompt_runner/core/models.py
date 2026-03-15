"""Domain models for prompt execution."""


from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class GenerationConfig:
    """
    Optional runtime controls forwarded to provider implementations.

    `None` values mean "use provider default behavior".
    """

    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None

    def is_empty(self) -> bool:
        """Return True when no explicit runtime control is set."""
        return (
            self.temperature is None
            and self.max_tokens is None
            and self.top_p is None
        )


@dataclass(frozen=True)
class UsageMetadata:
    """Normalized token usage metadata returned by providers when available."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict:
        """Serialize only known token counters to keep payload additive."""
        payload: dict[str, int] = {}
        if self.prompt_tokens is not None:
            payload["prompt_tokens"] = self.prompt_tokens
        if self.completion_tokens is not None:
            payload["completion_tokens"] = self.completion_tokens
        if self.total_tokens is not None:
            payload["total_tokens"] = self.total_tokens
        return payload


@dataclass(frozen=True)
class PromptRequest:
    """Input payload for a prompt execution."""

    prompt_text: str
    provider: str
    # Optional one-shot instruction layer applied before the user prompt.
    # This keeps execution stateless while allowing stricter prompt control.
    system_prompt: str | None = None
    # Optional runtime controls. `None` means provider default behavior.
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False

    def generation_config(self) -> GenerationConfig | None:
        """Return provider runtime controls, or None when unset."""
        config = GenerationConfig(
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
        )
        if config.is_empty():
            return None
        return config


@dataclass(frozen=True)
class PromptResponse:
    """Normalized output payload from a provider."""

    prompt: str
    response: str
    provider: str
    execution_ms: int | None = None
    usage: UsageMetadata | None = None
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary."""
        metadata: dict[str, object] = {
            "provider": self.provider,
            "timestamp_utc": self.timestamp_utc,
        }
        if self.execution_ms is not None:
            metadata["execution_ms"] = self.execution_ms
        if self.usage is not None:
            usage = self.usage.to_dict()
            if usage:
                metadata["usage"] = usage

        return {
            "prompt": self.prompt,
            "response": self.response,
            "metadata": metadata,
        }
