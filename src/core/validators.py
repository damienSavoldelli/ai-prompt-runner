"""Validation helpers for normalized response payload."""

from src.core.errors import PromptRunnerError


class ValidationError(PromptRunnerError):
    """Raised when normalized payload validation fails."""


def validate_response_payload(payload: dict) -> None:
    """Validate the expected payload shape for output serialization."""

    # Validate top-level contract first.
    required_top_keys = {"prompt", "response", "metadata"}
    missing_top = required_top_keys - set(payload.keys())
    if missing_top:
        raise ValidationError(f"Missing top-level keys: {sorted(missing_top)}")

    # Enforce basic field types for predictable serialization.
    if not isinstance(payload["prompt"], str):
        raise ValidationError("'prompt' must be a string.")
    if not isinstance(payload["response"], str):
        raise ValidationError("'response' must be a string.")
    if not isinstance(payload["metadata"], dict):
        raise ValidationError("'metadata' must be an object.")

    # Validate metadata sub-contract.
    required_meta_keys = {"provider", "timestamp_utc"}
    missing_meta = required_meta_keys - set(payload["metadata"].keys())
    if missing_meta:
        raise ValidationError(f"Missing metadata keys: {sorted(missing_meta)}")

    if not isinstance(payload["metadata"]["provider"], str):
        raise ValidationError("'metadata.provider' must be a string.")
    if not isinstance(payload["metadata"]["timestamp_utc"], str):
        raise ValidationError("'metadata.timestamp_utc' must be a string.")