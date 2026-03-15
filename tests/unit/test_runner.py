import pytest

from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.services.base import BaseProvider


class FakeProvider(BaseProvider):
    """Test double implementing the provider contract without network I/O."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"

    def generate_stream(self, prompt: str):
        """Yield deterministic chunks for stream-path runner tests."""
        yield "Echo: "
        yield prompt


class FakeNoStreamProvider(BaseProvider):
    """Provider stub that explicitly does not support streaming."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"


class FakeInvalidStreamChunkProvider(BaseProvider):
    """Provider stub emitting a non-string stream chunk for guard-rail coverage."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"

    def generate_stream(self, prompt: str):
        # Intentionally invalid chunk type to validate runner-level guard.
        yield 123


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


def test_runner_stream_reconstructs_response_and_emits_chunks() -> None:
    """Rebuild the final response from stream chunks while forwarding chunk callbacks."""
    streamed_chunks: list[str] = []
    runner = PromptRunner(provider=FakeProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=True,
        ),
        on_stream_chunk=streamed_chunks.append,
    )

    assert streamed_chunks == ["Echo: ", "Hello"]
    assert payload["response"] == "Echo: Hello"


def test_runner_stream_falls_back_when_provider_does_not_support_stream() -> None:
    """Use non-stream generation when provider stream support is unavailable."""
    runner = PromptRunner(provider=FakeNoStreamProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=True,
        )
    )

    assert payload["response"] == "Echo: Hello"


def test_runner_stream_rejects_non_string_chunks() -> None:
    """Stream chunks must be strings; invalid chunk types should fail fast."""
    runner = PromptRunner(provider=FakeInvalidStreamChunkProvider())

    with pytest.raises(ProviderError, match="Provider stream chunks must be strings."):
        runner.run(
            PromptRequest(
                prompt_text="Hello",
                provider="fake",
                stream=True,
            )
        )
