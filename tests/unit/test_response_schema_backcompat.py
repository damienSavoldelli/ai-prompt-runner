import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def _load_response_schema() -> dict:
    """Load the official response JSON schema from disk."""
    return json.loads(
        Path("schemas/response.schema.json").read_text(encoding="utf-8")
    )


def test_historical_response_payload_fixtures_remain_schema_compatible() -> None:
    """Historical response payload fixtures must remain compatible with the schema."""
    validator = Draft202012Validator(
        _load_response_schema(),
        format_checker=FormatChecker(),
    )

    fixture_paths = sorted(Path("tests/fixtures").glob("response_payload_v*.json"))

    assert fixture_paths != []

    for fixture_path in fixture_paths:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda err: list(err.path),
        )
        assert errors == [], f"{fixture_path} failed schema validation: {errors}"