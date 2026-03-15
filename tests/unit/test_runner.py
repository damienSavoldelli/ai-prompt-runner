from ai_prompt_runner.core.errors import ProviderError
from ai_prompt_runner.core.models import GenerationConfig, PromptRequest, UsageMetadata
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.base import BaseProvider
import pytest


class FakeProvider(BaseProvider):
    """Test double implementing the provider contract without network I/O."""
    provider_protocol = "fake-protocol"

    def __init__(self) -> None:
        # Mimic provider runtime config attributes expected by provenance capture.
        self.config = type(
            "FakeConfig",
            (),
            {
                "endpoint": "https://api.fake.test/v1",
                "model": "fake-model",
                "timeout_seconds": 30,
                "max_retries": 0,
            },
        )()

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
    provider_protocol = "fake-protocol"

    def __init__(self) -> None:
        self.config = type(
            "FakeConfig",
            (),
            {
                "endpoint": "https://api.fake.test/v1",
                "model": "fake-model",
                "timeout_seconds": 30,
                "max_retries": 0,
            },
        )()

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


class FakeResolvedModelProvider(FakeProvider):
    """Provider stub exposing resolved model metadata after generation."""

    def get_last_model_resolved(self) -> str | None:
        return "fake-model-2026-03-15"


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
    assert payload["metadata"]["model"] == "fake-model"
    assert payload["metadata"]["execution_context"]["provider_protocol"] == "fake-protocol"
    assert payload["metadata"]["execution_context"]["api_endpoint"] == "https://api.fake.test/v1"
    assert payload["metadata"]["execution_context"]["model_requested"] == "fake-model"
    assert payload["metadata"]["execution_context"]["runner_version"]
    assert payload["metadata"]["execution_context"]["prompt_hash"].startswith("sha256:")


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
    non_stream_payload["metadata"]["execution_context"]["runtime"]["stream"] = "<normalized>"
    stream_payload["metadata"]["execution_context"]["runtime"]["stream"] = "<normalized>"

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


def test_runner_prompt_hash_changes_when_system_prompt_is_present() -> None:
    """Prompt provenance hash must include system prompt context when provided."""
    runner = PromptRunner(provider=FakeProvider())

    payload_without_system = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )
    payload_with_system = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
            system_prompt="You are strict.",
        )
    )

    hash_without_system = payload_without_system["metadata"]["execution_context"]["prompt_hash"]
    hash_with_system = payload_with_system["metadata"]["execution_context"]["prompt_hash"]

    assert hash_without_system != hash_with_system


def test_runner_prefers_provider_resolved_model_in_metadata() -> None:
    """When provider exposes resolved model metadata, metadata.model should use it."""
    runner = PromptRunner(provider=FakeResolvedModelProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )

    assert payload["metadata"]["model"] == "fake-model-2026-03-15"
    assert (
        payload["metadata"]["execution_context"]["model_resolved"]
        == "fake-model-2026-03-15"
    )


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


def test_runner_version_falls_back_when_package_metadata_missing(monkeypatch) -> None:
    """Runner provenance should use fallback version when package metadata is unavailable."""
    runner = PromptRunner(provider=FakeProvider())

    def _raise_not_found(_name: str) -> str:
        raise runner_module.PackageNotFoundError

    import ai_prompt_runner.core.runner as runner_module

    monkeypatch.setattr(runner_module, "version", _raise_not_found)

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )

    assert payload["metadata"]["execution_context"]["runner_version"] == "0.1.0-dev"


@pytest.mark.parametrize(
    ("provider_protocol", "endpoint", "model", "timeout_seconds", "max_retries", "expected_message"),
    [
        (123, "https://api.fake.test/v1", "fake-model", 30, 0, "Provider protocol metadata must be a string."),
        ("fake-protocol", 123, "fake-model", 30, 0, "Provider endpoint metadata must be a string."),
        ("fake-protocol", "https://api.fake.test/v1", 123, 30, 0, "Provider requested model metadata must be a string."),
        ("fake-protocol", "https://api.fake.test/v1", "fake-model", "30", 0, "Provider timeout metadata must be an integer."),
        ("fake-protocol", "https://api.fake.test/v1", "fake-model", 30, "0", "Provider retry metadata must be an integer."),
    ],
)
def test_runner_rejects_invalid_provider_context_metadata(
    provider_protocol,
    endpoint,
    model,
    timeout_seconds,
    max_retries,
    expected_message: str,
) -> None:
    """Runner should fail fast on invalid provider context metadata types."""

    class _BadContextProvider(BaseProvider):
        def __init__(self) -> None:
            self.provider_protocol = provider_protocol
            self.config = type(
                "BadConfig",
                (),
                {
                    "endpoint": endpoint,
                    "model": model,
                    "timeout_seconds": timeout_seconds,
                    "max_retries": max_retries,
                },
            )()

        def generate(
            self,
            prompt: str,
            system_prompt: str | None = None,
            generation_config: GenerationConfig | None = None,
        ) -> str:
            return f"Echo: {prompt}"

    runner = PromptRunner(provider=_BadContextProvider())

    with pytest.raises(ProviderError, match=expected_message):
        runner.run(
            PromptRequest(
                prompt_text="Hello",
                provider="fake",
            )
        )


def test_runner_rejects_invalid_resolved_model_metadata_type() -> None:
    """Runner should reject non-string resolved model metadata from providers."""

    class _BadResolvedModelProvider(FakeProvider):
        def get_last_model_resolved(self):  # type: ignore[override]
            return 123

    runner = PromptRunner(provider=_BadResolvedModelProvider())

    with pytest.raises(
        ProviderError,
        match="Provider resolved model metadata must be a string.",
    ):
        runner.run(
            PromptRequest(
                prompt_text="Hello",
                provider="fake",
            )
        )
