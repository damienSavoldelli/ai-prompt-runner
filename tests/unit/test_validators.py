import pytest

from src.core.validators import ValidationError, validate_response_payload

def test_validate_response_payload_accepts_valid_payload() -> None:
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
    """Test that if the payload is missing required metadata keys, we raise a ValidationError with a clear message."""
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
    """Test that if the 'prompt' field in the payload is not a string, we raise a ValidationError with a clear message."""
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
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": "not-a-dict",
    }

    with pytest.raises(ValidationError, match="'metadata' must be an object."):
        validate_response_payload(payload)


def test_validate_response_payload_rejects_non_string_metadata_provider() -> None:
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