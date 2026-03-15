import pytest

from ai_prompt_runner.core.validators import ValidationError, validate_response_payload


def test_validate_response_payload_accepts_valid_payload() -> None:
    """Accept payloads that match the response contract."""
    # Arrange: payload matching the expected domain contract.
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "execution_ms": 42,
        },
    }

    # Act + Assert: no exception should be raised.
    validate_response_payload(payload)


def test_validate_response_payload_rejects_missing_top_level_key() -> None:
    """Reject payloads missing required top-level keys."""
    # Arrange: missing required 'response' key.
    payload = {
        "prompt": "Hello",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }

    # Assert: contract violation is reported.
    with pytest.raises(ValidationError):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_missing_metadata_key() -> None:
    """Reject payloads missing required metadata keys."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
        },
    }

    with pytest.raises(ValidationError, match="Missing metadata keys"):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_prompt() -> None:
    """Reject payloads where prompt is not a string."""
    payload = {
        "prompt": 123,
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }

    with pytest.raises(ValidationError, match="'prompt' must be a string."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_response() -> None:
    """Reject payloads where response is not a string."""
    payload = {
        "prompt": "Hello",
        "response": 123,
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }

    with pytest.raises(ValidationError, match="'response' must be a string."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_object_metadata() -> None:
    """Reject payloads where metadata is not an object."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": "not-a-dict",
    }

    with pytest.raises(ValidationError, match="'metadata' must be an object."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_metadata_provider() -> None:
    """Reject payloads where metadata.provider is not a string."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": 123,
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }

    with pytest.raises(ValidationError, match="'metadata.provider' must be a string."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_metadata_timestamp() -> None:
    """Reject payloads where metadata.timestamp_utc is not a string."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": 123,
        },
    }

    with pytest.raises(ValidationError, match="'metadata.timestamp_utc' must be a string."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_integer_execution_ms() -> None:
    """Reject payloads where metadata.execution_ms is not an integer."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "execution_ms": "42",
        },
    }

    with pytest.raises(ValidationError, match="'metadata.execution_ms' must be an integer."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_negative_execution_ms() -> None:
    """Reject payloads where metadata.execution_ms is negative."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "execution_ms": -1,
        },
    }

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_ms' must be greater than or equal to 0.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_accepts_optional_usage_object() -> None:
    """Accept normalized usage metadata when token counts are valid integers."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        },
    }

    validate_response_payload(payload)


def test_validate_response_payload_rejects_non_object_usage() -> None:
    """Reject payloads where metadata.usage is not an object."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "usage": "invalid",
        },
    }

    with pytest.raises(ValidationError, match="'metadata.usage' must be an object."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_unknown_usage_key() -> None:
    """Reject payloads where metadata.usage includes unsupported keys."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "usage": {
                "cached_tokens": 1,
            },
        },
    }

    with pytest.raises(ValidationError, match="Unsupported usage keys"):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_integer_usage_value() -> None:
    """Reject payloads where a usage counter is not an integer."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "usage": {
                "prompt_tokens": "10",
            },
        },
    }

    with pytest.raises(
        ValidationError,
        match="'metadata.usage.prompt_tokens' must be an integer.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_negative_usage_value() -> None:
    """Reject payloads where a usage counter is negative."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "usage": {
                "total_tokens": -1,
            },
        },
    }

    with pytest.raises(
        ValidationError,
        match="'metadata.usage.total_tokens' must be greater than or equal to 0.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_accepts_execution_context_metadata() -> None:
    """Accept additive execution context metadata when shape is valid."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "openai",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "model": "gpt-4o-mini",
            "execution_context": {
                "provider_protocol": "openai-compatible",
                "api_endpoint": "https://api.openai.com/v1",
                "model_requested": "gpt-4o-mini",
                "model_resolved": "gpt-4o-mini-2026-02-15",
                "runner_version": "1.6.0",
                "prompt_hash": "sha256:" + ("a" * 64),
                "runtime": {
                    "stream": False,
                    "system_prompt_provided": False,
                    "temperature": None,
                    "max_tokens": None,
                    "top_p": None,
                    "timeout_seconds": 30,
                    "max_retries": 0,
                },
            },
        },
    }

    validate_response_payload(payload)


def test_validate_response_payload_rejects_execution_context_without_sha256_prefix() -> None:
    """Reject execution context prompt hashes that are not SHA256-prefixed."""
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "openai",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "execution_context": {
                "provider_protocol": "openai-compatible",
                "api_endpoint": "https://api.openai.com/v1",
                "model_requested": "gpt-4o-mini",
                "model_resolved": None,
                "runner_version": "1.6.0",
                "prompt_hash": "md5:abc",
                "runtime": {
                    "stream": False,
                    "system_prompt_provided": False,
                    "temperature": None,
                    "max_tokens": None,
                    "top_p": None,
                    "timeout_seconds": 30,
                    "max_retries": 0,
                },
            },
        },
    }

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_context.prompt_hash' must start with 'sha256:'.",
    ):
        validate_response_payload(payload)


def _base_execution_context_payload() -> dict:
    """Build a valid payload scaffold with execution context metadata."""
    return {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "openai",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
            "model": "gpt-4o-mini",
            "execution_context": {
                "provider_protocol": "openai-compatible",
                "api_endpoint": "https://api.openai.com/v1",
                "model_requested": "gpt-4o-mini",
                "model_resolved": None,
                "runner_version": "1.6.0",
                "prompt_hash": "sha256:" + ("a" * 64),
                "runtime": {
                    "stream": False,
                    "system_prompt_provided": False,
                    "temperature": None,
                    "max_tokens": None,
                    "top_p": None,
                    "timeout_seconds": 30,
                    "max_retries": 0,
                },
            },
        },
    }


def test_validate_response_payload_rejects_non_string_model() -> None:
    """Reject payloads where metadata.model is present but not a string."""
    payload = _base_execution_context_payload()
    payload["metadata"]["model"] = 123

    with pytest.raises(ValidationError, match="'metadata.model' must be a string."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_object_execution_context() -> None:
    """Reject payloads where metadata.execution_context is not an object."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"] = "invalid"

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_context' must be an object.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_missing_execution_context_keys() -> None:
    """Reject execution_context objects missing required provenance keys."""
    payload = _base_execution_context_payload()
    del payload["metadata"]["execution_context"]["runtime"]

    with pytest.raises(ValidationError, match="Missing execution context keys"):
        validate_response_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("provider_protocol", 123),
        ("api_endpoint", 123),
        ("model_requested", 123),
        ("model_resolved", 123),
    ],
)
def test_validate_response_payload_rejects_non_string_execution_context_nullable_fields(
    field_name: str,
    field_value,
) -> None:
    """Reject non-string values for nullable string execution_context fields."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"][field_name] = field_value

    with pytest.raises(
        ValidationError,
        match=(
            f"'metadata.execution_context.{field_name}' must be a string or null."
        ),
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_runner_version() -> None:
    """Reject execution_context runner_version values that are not strings."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["runner_version"] = 1

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_context.runner_version' must be a string.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_prompt_hash() -> None:
    """Reject execution_context prompt_hash values that are not strings."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["prompt_hash"] = 1

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_context.prompt_hash' must be a string.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_object_runtime_context() -> None:
    """Reject execution_context runtime values that are not objects."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["runtime"] = "invalid"

    with pytest.raises(
        ValidationError,
        match="'metadata.execution_context.runtime' must be an object.",
    ):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_missing_runtime_keys() -> None:
    """Reject runtime context when required keys are missing."""
    payload = _base_execution_context_payload()
    del payload["metadata"]["execution_context"]["runtime"]["max_tokens"]

    with pytest.raises(ValidationError, match="Missing execution runtime keys"):
        validate_response_payload(payload)


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_message"),
    [
        ("stream", "no", "'metadata.execution_context.runtime.stream' must be a boolean."),
        (
            "system_prompt_provided",
            "no",
            "'metadata.execution_context.runtime.system_prompt_provided' must be a boolean.",
        ),
        (
            "temperature",
            "0.2",
            "'metadata.execution_context.runtime.temperature' must be a number or null.",
        ),
        (
            "max_tokens",
            "10",
            "'metadata.execution_context.runtime.max_tokens' must be an integer or null.",
        ),
        (
            "top_p",
            "0.9",
            "'metadata.execution_context.runtime.top_p' must be a number or null.",
        ),
        (
            "timeout_seconds",
            "30",
            "'metadata.execution_context.runtime.timeout_seconds' must be an integer or null.",
        ),
        (
            "max_retries",
            "1",
            "'metadata.execution_context.runtime.max_retries' must be an integer or null.",
        ),
    ],
)
def test_validate_response_payload_rejects_invalid_runtime_context_types(
    field_name: str,
    field_value,
    expected_message: str,
) -> None:
    """Reject runtime context fields with invalid primitive types."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["runtime"][field_name] = field_value

    with pytest.raises(ValidationError, match=expected_message):
        validate_response_payload(payload)


def test_validate_response_payload_accepts_zero_execution_ms() -> None:
    """Accept execution_ms equal to zero (non-negative boundary)."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_ms"] = 0

    validate_response_payload(payload)


def test_validate_response_payload_accepts_zero_usage_values() -> None:
    """Accept usage counters equal to zero (non-negative boundary)."""
    payload = _base_execution_context_payload()
    payload["metadata"]["usage"] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    validate_response_payload(payload)


def test_validate_response_payload_allows_additional_top_level_keys() -> None:
    """Allow additive top-level keys without failing missing-key checks."""
    payload = _base_execution_context_payload()
    payload["extra_top_level"] = "kept for forward compatibility"

    validate_response_payload(payload)


def test_validate_response_payload_allows_additional_execution_context_keys() -> None:
    """Allow additive execution_context keys without failing required-key checks."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["extra_context_key"] = "allowed"

    validate_response_payload(payload)


def test_validate_response_payload_allows_additional_runtime_keys() -> None:
    """Allow additive runtime keys without failing required-key checks."""
    payload = _base_execution_context_payload()
    payload["metadata"]["execution_context"]["runtime"]["extra_runtime_key"] = "allowed"

    validate_response_payload(payload)
