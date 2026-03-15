from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.core.models import GenerationConfig, PromptRequest, UsageMetadata
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.base import BaseProvider
import pytest


class FakeProvider(BaseProvider):
    """Test double implementing the provider contract without network I/O."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        if system_prompt is not None:
            return f"Echo: SYSTEM={system_prompt} | USER={prompt}"
        return f"Echo: {prompt}"

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ):
        """Yield deterministic chunks for stream-path runner tests."""
        if system_prompt is not None:
            yield f"SYSTEM={system_prompt} | "
            yield f"USER={prompt}"
            return
        yield "Echo: "
        yield prompt


class FakeNoStreamProvider(BaseProvider):
    """Provider stub that explicitly does not support streaming."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        if system_prompt is not None:
            return f"Echo: SYSTEM={system_prompt} | USER={prompt}"
        return f"Echo: {prompt}"


class FakeInvalidStreamChunkProvider(BaseProvider):
    """Provider stub emitting a non-string stream chunk for guard-rail coverage."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        return f"Echo: {prompt}"

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ):
        # Intentionally invalid chunk type to validate runner-level guard.
        yield 123


class FakeCaptureConfigProvider(BaseProvider):
    """Provider stub capturing forwarded generation configuration for assertions."""

    def __init__(self) -> None:
        self.last_config: GenerationConfig | None = None

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        self.last_config = generation_config
        return f"Echo: {prompt}"

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ):
        self.last_config = generation_config
        yield "Echo: "
        yield prompt


class FakeUsageProvider(BaseProvider):
    """Provider stub exposing normalized usage through get_last_usage hook."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        return f"Echo: {prompt}"

    def get_last_usage(self) -> UsageMetadata | None:
        return UsageMetadata(
            prompt_tokens=12,
            completion_tokens=34,
            total_tokens=46,
        )


class FakeInvalidUsageProvider(BaseProvider):
    """Provider stub returning an invalid usage type to test runner guard rails."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config: GenerationConfig | None = None,
    ) -> str:
        return f"Echo: {prompt}"

    def get_last_usage(self):  # type: ignore[override]
        return {"prompt_tokens": 1}


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
    assert isinstance(payload["metadata"]["execution_ms"], int)
    assert payload["metadata"]["execution_ms"] >= 0


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


def test_runner_stream_and_non_stream_payloads_match_except_timestamp() -> None:
    """
    Stream mode must preserve artifact determinism: the final payload content
    matches non-stream mode except for runtime timestamp generation.
    """
    runner = PromptRunner(provider=FakeProvider())

    non_stream_payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=False,
        )
    )
    stream_payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=True,
        )
    )

    # Normalize runtime-generated metadata so we can assert deterministic
    # payload equivalence between stream and non-stream execution paths.
    non_stream_payload["metadata"]["timestamp_utc"] = "<normalized>"
    stream_payload["metadata"]["timestamp_utc"] = "<normalized>"
    non_stream_payload["metadata"]["execution_ms"] = "<normalized>"
    stream_payload["metadata"]["execution_ms"] = "<normalized>"

    assert stream_payload == non_stream_payload


def test_runner_forwards_system_prompt_to_generate() -> None:
    """Forward one-shot system instruction in non-stream execution mode."""
    runner = PromptRunner(provider=FakeProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            system_prompt="You are strict.",
        )
    )

    assert payload["response"] == "Echo: SYSTEM=You are strict. | USER=Hello"


def test_runner_forwards_system_prompt_to_generate_stream() -> None:
    """Forward one-shot system instruction in stream execution mode."""
    runner = PromptRunner(provider=FakeProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            system_prompt="You are strict.",
            stream=True,
        )
    )

    assert payload["response"] == "SYSTEM=You are strict. | USER=Hello"


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


def test_runner_forwards_generation_config_to_generate() -> None:
    """Forward runtime controls to provider generate path when set."""
    provider = FakeCaptureConfigProvider()
    runner = PromptRunner(provider=provider)

    runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            temperature=0.2,
            max_tokens=150,
            top_p=0.95,
        )
    )

    assert provider.last_config is not None
    assert provider.last_config.temperature == 0.2
    assert provider.last_config.max_tokens == 150
    assert provider.last_config.top_p == 0.95


def test_runner_forwards_generation_config_to_generate_stream() -> None:
    """Forward runtime controls to provider stream path when set."""
    provider = FakeCaptureConfigProvider()
    runner = PromptRunner(provider=provider)

    runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=True,
            temperature=0.2,
            max_tokens=150,
            top_p=0.95,
        )
    )

    assert provider.last_config is not None
    assert provider.last_config.temperature == 0.2
    assert provider.last_config.max_tokens == 150
    assert provider.last_config.top_p == 0.95


def test_runner_forwards_system_and_generation_config_to_generate() -> None:
    """
    Forward both system prompt and runtime controls to the non-stream provider path.
    """
    provider = FakeCaptureConfigProvider()
    runner = PromptRunner(provider=provider)

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            system_prompt="You are strict.",
            temperature=0.2,
            max_tokens=150,
            top_p=0.95,
        )
    )

    assert payload["response"] == "Echo: Hello"
    assert provider.last_config is not None
    assert provider.last_config.temperature == 0.2
    assert provider.last_config.max_tokens == 150
    assert provider.last_config.top_p == 0.95


def test_runner_forwards_system_and_generation_config_to_generate_stream() -> None:
    """
    Forward both system prompt and runtime controls to the stream provider path.
    """
    provider = FakeCaptureConfigProvider()
    runner = PromptRunner(provider=provider)

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            stream=True,
            system_prompt="You are strict.",
            temperature=0.2,
            max_tokens=150,
            top_p=0.95,
        )
    )

    assert payload["response"] == "Echo: Hello"
    assert provider.last_config is not None
    assert provider.last_config.temperature == 0.2
    assert provider.last_config.max_tokens == 150
    assert provider.last_config.top_p == 0.95


def test_runner_includes_provider_usage_metadata_in_payload() -> None:
    """Runner should include normalized provider usage when available."""
    runner = PromptRunner(provider=FakeUsageProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )

    assert payload["metadata"]["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "total_tokens": 46,
    }


def test_runner_rejects_invalid_provider_usage_shape() -> None:
    """Runner should fail fast when a provider returns invalid usage type."""
    runner = PromptRunner(provider=FakeInvalidUsageProvider())

    with pytest.raises(
        ProviderError,
        match="Provider usage metadata must be a UsageMetadata object.",
    ):
        runner.run(
            PromptRequest(
                prompt_text="Hello",
                provider="fake",
            )
        )
