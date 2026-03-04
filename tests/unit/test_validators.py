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
