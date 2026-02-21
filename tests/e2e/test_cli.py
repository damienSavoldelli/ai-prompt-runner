import json
from pathlib import Path

from src import cli


class FakeProvider:
    """E2E test double returning deterministic output."""

    def generate(self, prompt: str) -> str:
        return f"Echo: {prompt}"


def test_cli_main_generates_json_and_markdown_files(monkeypatch, tmp_path: Path) -> None:
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