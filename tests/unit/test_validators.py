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