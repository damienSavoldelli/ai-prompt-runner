"""Domain models for prompt execution."""


from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class PromptRequest:
    """Input payload for a prompt execution."""

    prompt_text: str
    provider: str
    
@dataclass(frozen=True)
class PromptResponse:
    """Normalized output payload from a provider."""

    prompt: str
    response: str
    provider: str
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Return a JSON-serializable dictionary."""
        return {
            "prompt": self.prompt,
            "response": self.response,
            "metadata": {
                "provider": self.provider,
                "timestamp_utc": self.timestamp_utc,
            },
        }