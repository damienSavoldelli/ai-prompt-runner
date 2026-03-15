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

    # Optional normalized model metadata.
    model = payload["metadata"].get("model")
    if model is not None and not isinstance(model, str):
        raise ValidationError("'metadata.model' must be a string.")

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

    # Optional additive execution provenance context.
    execution_context = payload["metadata"].get("execution_context")
    if execution_context is not None:
        if not isinstance(execution_context, dict):
            raise ValidationError("'metadata.execution_context' must be an object.")

        required_context_keys = {
            "provider_protocol",
            "api_endpoint",
            "model_requested",
            "model_resolved",
            "runner_version",
            "prompt_hash",
            "runtime",
        }
        missing_context = required_context_keys - set(execution_context.keys())
        if missing_context:
            raise ValidationError(
                f"Missing execution context keys: {sorted(missing_context)}"
            )

        for key_name in {"provider_protocol", "api_endpoint", "model_requested", "model_resolved"}:
            value = execution_context.get(key_name)
            if value is not None and not isinstance(value, str):
                raise ValidationError(
                    f"'metadata.execution_context.{key_name}' must be a string or null."
                )

        runner_version = execution_context.get("runner_version")
        if not isinstance(runner_version, str):
            raise ValidationError("'metadata.execution_context.runner_version' must be a string.")

        prompt_hash = execution_context.get("prompt_hash")
        if not isinstance(prompt_hash, str):
            raise ValidationError("'metadata.execution_context.prompt_hash' must be a string.")
        if not prompt_hash.startswith("sha256:"):
            raise ValidationError(
                "'metadata.execution_context.prompt_hash' must start with 'sha256:'."
            )

        runtime = execution_context.get("runtime")
        if not isinstance(runtime, dict):
            raise ValidationError("'metadata.execution_context.runtime' must be an object.")

        required_runtime_keys = {
            "stream",
            "system_prompt_provided",
            "temperature",
            "max_tokens",
            "top_p",
            "timeout_seconds",
            "max_retries",
        }
        missing_runtime = required_runtime_keys - set(runtime.keys())
        if missing_runtime:
            raise ValidationError(
                f"Missing execution runtime keys: {sorted(missing_runtime)}"
            )

        if not isinstance(runtime.get("stream"), bool):
            raise ValidationError(
                "'metadata.execution_context.runtime.stream' must be a boolean."
            )
        if not isinstance(runtime.get("system_prompt_provided"), bool):
            raise ValidationError(
                "'metadata.execution_context.runtime.system_prompt_provided' must be a boolean."
            )

        temperature = runtime.get("temperature")
        if temperature is not None and not isinstance(temperature, (int, float)):
            raise ValidationError(
                "'metadata.execution_context.runtime.temperature' must be a number or null."
            )
        max_tokens = runtime.get("max_tokens")
        if max_tokens is not None and not isinstance(max_tokens, int):
            raise ValidationError(
                "'metadata.execution_context.runtime.max_tokens' must be an integer or null."
            )
        top_p = runtime.get("top_p")
        if top_p is not None and not isinstance(top_p, (int, float)):
            raise ValidationError(
                "'metadata.execution_context.runtime.top_p' must be a number or null."
            )
        timeout_seconds = runtime.get("timeout_seconds")
        if timeout_seconds is not None and not isinstance(timeout_seconds, int):
            raise ValidationError(
                "'metadata.execution_context.runtime.timeout_seconds' must be an integer or null."
            )
        max_retries = runtime.get("max_retries")
        if max_retries is not None and not isinstance(max_retries, int):
            raise ValidationError(
                "'metadata.execution_context.runtime.max_retries' must be an integer or null."
            )
