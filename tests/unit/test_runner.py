from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.base import BaseProvider


class FakeProvider(BaseProvider):
    """Test double implementing the provider contract without network I/O."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"


def test_runner_returns_normalized_payload() -> None:
    """Return a normalized payload containing prompt, response, and metadata."""
    
    # Arrange: inject a fake provider to isolate business logic.
    runner = PromptRunner(provider=FakeProvider())

    # Act: run the use case with normalized input.
    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )

    # Assert: output follows the expected domain contract.
    assert payload["prompt"] == "Hello"
    assert payload["response"] == "Echo: Hello"
    assert payload["metadata"]["provider"] == "fake"
    assert "timestamp_utc" in payload["metadata"]
