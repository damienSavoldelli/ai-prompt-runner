import pytest
import json
from pathlib import Path

from src import cli


class FakeProvider:
    """E2E test double returning deterministic output."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"


def test_cli_main_generates_json_and_markdown_files(monkeypatch, tmp_path: Path) -> None:
    """Test that the CLI generates expected JSON and Markdown files from a prompt, using a fake provider to avoid real API calls."""
    # Replace runtime provider creation to avoid real network calls.
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    # Run the CLI entrypoint with explicit output paths.
    exit_code = cli.main(
        [
            "--prompt",
            "Hello E2E",
            "--provider",
            "http",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    assert out_json.exists()
    assert out_md.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["prompt"] == "Hello E2E"
    assert payload["response"] == "Echo: Hello E2E"
    assert payload["metadata"]["provider"] == "http"

    md_content = out_md.read_text(encoding="utf-8")
    assert "# AI Prompt Response" in md_content
    assert "## Prompt" in md_content
    assert "## Response" in md_content
    
def test_cli_main_forwards_timeout_and_retries_to_provider_factory(monkeypatch, tmp_path: Path) -> None:
    """Test that CLI arguments for timeout and retries are correctly forwarded to the provider factory."""
    # Capture arguments forwarded by the CLI to the provider factory.
    captured: dict = {}

    class FakeProvider:
        # Return deterministic output to keep this test network-free.
        def generate(self, prompt: str) -> str:
            return f"Echo: {prompt}"

    def fake_create_provider(**kwargs):
        captured.update(kwargs)
        return FakeProvider()

    # Replace runtime provider creation with a local test double.
    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    # Run CLI with explicit timeout/retries and output destinations.
    exit_code = cli.main(
        [
            "--prompt",
            "Hello Forwarding",
            "--provider",
            "http",
            "--timeout",
            "7",
            "--retries",
            "2",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    # Ensure CLI succeeded and forwarded the expected factory parameters.
    assert exit_code == 0
    assert captured["provider_name"] == "http"
    assert captured["timeout_seconds"] == 7
    assert captured["max_retries"] == 2
    
def test_cli_rejects_blank_prompt() -> None:
    """Test that the CLI rejects a blank prompt with an appropriate error message and exit code."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--prompt", "   "])

    assert exc_info.value.code == 2


def test_cli_rejects_invalid_api_endpoint_scheme() -> None:
    """Test that the CLI rejects an API endpoint with an unsupported URL scheme, providing a clear error message and exit code."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--prompt", "Hello", "--api-endpoint", "ftp://example.test"])

    assert exc_info.value.code == 2
