import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.base import BaseProvider


class FakeProvider(BaseProvider):
    """Test double implementing the provider contract without network I/O."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"


def _load_response_schema() -> dict:
    """Load the official response JSON schema from disk."""
    return json.loads(
        Path("schemas/response.schema.json").read_text(encoding="utf-8")
    )


def _build_validator() -> Draft202012Validator:
    """Build a validator for the official response schema."""
    return Draft202012Validator(
        _load_response_schema(),
        format_checker=FormatChecker(),
    )


def test_runner_payload_matches_official_response_schema() -> None:
    """Runner output must validate against the official JSON schema."""
    runner = PromptRunner(provider=FakeProvider())

    payload = runner.run(
        PromptRequest(
            prompt_text="Hello",
            provider="fake",
        )
    )

    errors = sorted(
        _build_validator().iter_errors(payload),
        key=lambda err: list(err.path),
    )

    assert errors == []


def test_response_schema_rejects_invalid_timestamp_format() -> None:
    """Official schema must reject non-date-time timestamp values."""
    payload = {
        "prompt": "Hello",
        "response": "Echo: Hello",
        "metadata": {
            "provider": "fake",
            "timestamp_utc": "not-a-timestamp",
        },
    }

    errors = sorted(
        _build_validator().iter_errors(payload),
        key=lambda err: list(err.path),
    )

    assert len(errors) == 1
    assert list(errors[0].path) == ["metadata", "timestamp_utc"]


def test_response_schema_rejects_missing_required_field() -> None:
    """Official schema must reject payloads missing required top-level fields."""
    payload = {
        "prompt": "Hello",
        "metadata": {
            "provider": "fake",
            "timestamp_utc": "2026-02-28T12:00:00+00:00",
        },
    }

    errors = sorted(
        _build_validator().iter_errors(payload),
        key=lambda err: list(err.path),
    )

    assert len(errors) == 1
    assert errors[0].validator == "required"


def test_response_schema_rejects_unexpected_metadata_field() -> None:
    """Official schema must reject unexpected metadata fields."""
    payload = {
        "prompt": "Hello",
        "response": "Echo: Hello",
        "metadata": {
            "provider": "fake",
            "timestamp_utc": "2026-02-28T12:00:00+00:00",
            "source": "unexpected",
        },
    }

    errors = sorted(
        _build_validator().iter_errors(payload),
        key=lambda err: list(err.path),
    )

    assert len(errors) == 1
    assert errors[0].validator == "additionalProperties"