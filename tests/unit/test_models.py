"""Unit tests for domain model helpers."""

from ai_prompt_runner.core.models import (
    ExecutionContextMetadata,
    ExecutionRuntimeConfig,
    PromptRequest,
    PromptResponse,
    UsageMetadata,
)


def test_prompt_request_generation_config_returns_none_when_unset() -> None:
    """No runtime control values should produce no generation config."""
    request = PromptRequest(prompt_text="hello", provider="mock")
    assert request.generation_config() is None


def test_prompt_request_generation_config_returns_values_when_set() -> None:
    """Runtime controls should be forwarded exactly as provided."""
    request = PromptRequest(
        prompt_text="hello",
        provider="mock",
        temperature=0.2,
        max_tokens=256,
        top_p=0.9,
    )

    config = request.generation_config()
    assert config is not None
    assert config.temperature == 0.2
    assert config.max_tokens == 256
    assert config.top_p == 0.9


def test_usage_metadata_to_dict_omits_none_fields() -> None:
    """Usage serialization must stay additive and omit unset counters."""
    usage = UsageMetadata(prompt_tokens=12, completion_tokens=None, total_tokens=34)
    assert usage.to_dict() == {"prompt_tokens": 12, "total_tokens": 34}


def test_prompt_response_to_dict_omits_optional_metadata_by_default() -> None:
    """Legacy payload shape must stay valid when optional fields are unset."""
    response = PromptResponse(
        prompt="hello",
        response="world",
        provider="mock",
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )

    assert response.to_dict() == {
        "prompt": "hello",
        "response": "world",
        "metadata": {
            "provider": "mock",
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
        },
    }


def test_prompt_response_to_dict_includes_execution_and_usage_when_present() -> None:
    """Optional metadata must be included when providers expose it."""
    response = PromptResponse(
        prompt="hello",
        response="world",
        provider="openai_compatible",
        execution_ms=123,
        usage=UsageMetadata(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )

    assert response.to_dict() == {
        "prompt": "hello",
        "response": "world",
        "metadata": {
            "provider": "openai_compatible",
            "timestamp_utc": "2026-01-01T00:00:00+00:00",
            "execution_ms": 123,
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        },
    }


def test_prompt_response_to_dict_omits_empty_usage_payload() -> None:
    """
    If a UsageMetadata object exists but all fields are unset, do not emit a
    partial/empty usage object in output metadata.
    """
    response = PromptResponse(
        prompt="hello",
        response="world",
        provider="mock",
        usage=UsageMetadata(),
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )

    assert response.to_dict()["metadata"] == {
        "provider": "mock",
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
    }


def test_prompt_response_to_dict_includes_execution_context_and_model() -> None:
    """Execution provenance metadata should serialize in a deterministic shape."""
    execution_context = ExecutionContextMetadata(
        provider_protocol="openai-compatible",
        api_endpoint="https://api.openai.com/v1",
        model_requested="gpt-4o-mini",
        model_resolved="gpt-4o-mini-2026-02-15",
        runner_version="1.6.0",
        prompt_hash="sha256:" + ("a" * 64),
        runtime=ExecutionRuntimeConfig(
            stream=True,
            system_prompt_provided=True,
            temperature=0.2,
            max_tokens=128,
            top_p=0.9,
            timeout_seconds=30,
            max_retries=1,
        ),
    )

    response = PromptResponse(
        prompt="hello",
        response="world",
        provider="openai",
        model="gpt-4o-mini-2026-02-15",
        execution_context=execution_context,
        timestamp_utc="2026-01-01T00:00:00+00:00",
    )

    assert response.to_dict()["metadata"]["model"] == "gpt-4o-mini-2026-02-15"
    assert response.to_dict()["metadata"]["execution_context"] == {
        "provider_protocol": "openai-compatible",
        "api_endpoint": "https://api.openai.com/v1",
        "model_requested": "gpt-4o-mini",
        "model_resolved": "gpt-4o-mini-2026-02-15",
        "runner_version": "1.6.0",
        "prompt_hash": "sha256:" + ("a" * 64),
        "runtime": {
            "stream": True,
            "system_prompt_provided": True,
            "temperature": 0.2,
            "max_tokens": 128,
            "top_p": 0.9,
            "timeout_seconds": 30,
            "max_retries": 1,
        },
    }
