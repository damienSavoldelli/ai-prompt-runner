"""Validation helpers for normalized response payload."""

from ai_prompt_runner.core.errors import PromptRunnerError


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

    # Optional execution timing metadata.
    execution_ms = payload["metadata"].get("execution_ms")
    if execution_ms is not None:
        if not isinstance(execution_ms, int):
            raise ValidationError("'metadata.execution_ms' must be an integer.")
        if execution_ms < 0:
            raise ValidationError("'metadata.execution_ms' must be greater than or equal to 0.")

    # Optional normalized provider usage metadata.
    usage = payload["metadata"].get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValidationError("'metadata.usage' must be an object.")

        allowed_usage_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
        unknown_usage_keys = set(usage.keys()) - allowed_usage_keys
        if unknown_usage_keys:
            raise ValidationError(f"Unsupported usage keys: {sorted(unknown_usage_keys)}")

        for usage_key in allowed_usage_keys:
            usage_value = usage.get(usage_key)
            if usage_value is None:
                continue
            if not isinstance(usage_value, int):
                raise ValidationError(f"'metadata.usage.{usage_key}' must be an integer.")
            if usage_value < 0:
                raise ValidationError(
                    f"'metadata.usage.{usage_key}' must be greater than or equal to 0."
                )
