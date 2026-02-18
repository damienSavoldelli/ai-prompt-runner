from pathlib import Path

from src.utils.file_io import write_json, write_markdown


def test_write_json_creates_file_with_expected_content(tmp_path: Path) -> None:
    # Representative normalized payload produced by the runner.
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }
    # tmp_path is a pytest-provided temporary directory for isolated file I/O.
    out = tmp_path / "out" / "response.json"

    write_json(out, payload)

    # File should exist and include key JSON fields.
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert '"prompt": "Hello"' in content
    assert '"provider": "http"' in content


def test_write_markdown_creates_file_with_expected_sections(tmp_path: Path) -> None:
    # Same payload, written to a human-readable markdown report.
    payload = {
        "prompt": "Hello",
        "response": "Hi there",
        "metadata": {
            "provider": "http",
            "timestamp_utc": "2026-02-18T10:00:00+00:00",
        },
    }
    out = tmp_path / "out" / "response.md"

    write_markdown(out, payload)

    # Validate markdown structure rather than exact full text.
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# AI Prompt Response" in content
    assert "## Prompt" in content
    assert "## Response" in content
    assert "## Metadata" in content
