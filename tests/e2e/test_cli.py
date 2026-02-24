import pytest
import json
import argparse

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


def test_cli_returns_error_on_provider_configuration_error(monkeypatch, capsys) -> None:
    """Test that if the provider factory raises a ConfigurationError due to invalid config, the CLI catches it and exits with an error message."""
    def fake_create_provider(**kwargs):
        raise cli.ConfigurationError("invalid provider config")

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    exit_code = cli.main(["--prompt", "Hello"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: invalid provider config" in captured.err   
    
def test_cli_returns_error_on_runner_failure(monkeypatch, capsys) -> None:
    """Test that if the PromptRunner raises a PromptRunnerError during execution, the CLI catches it and exits with an appropriate error message."""
    class FakeProvider:
        pass

    class FakeRunner:
        def __init__(self, provider) -> None:
            self.provider = provider

        def run(self, request):
            raise cli.PromptRunnerError("runner failed")

    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())
    monkeypatch.setattr(cli, "PromptRunner", FakeRunner)

    exit_code = cli.main(["--prompt", "Hello"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: runner failed" in captured.err


def test_get_app_version_falls_back_when_metadata_is_missing(monkeypatch) -> None:
    """Test that if the package metadata is missing (e.g. during development), _get_app_version falls back to a default version string without raising an exception."""
    def fake_version(_: str) -> str:
        raise cli.PackageNotFoundError

    monkeypatch.setattr(cli, "version", fake_version)

    assert cli._get_app_version() == "0.1.0-dev"


def test_non_negative_int_rejects_non_integer() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="retries must be an integer"):
        cli._non_negative_int("abc")


def test_non_negative_int_rejects_negative_value() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="greater than or equal to 0"):
        cli._non_negative_int("-1")


def test_positive_int_rejects_non_integer() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="timeout must be an integer"):
        cli._positive_int("abc")


def test_positive_int_rejects_zero() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="timeout must be a positive integer"):
        cli._positive_int("0")


def test_http_url_rejects_blank_value() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="api-endpoint must not be empty"):
        cli._http_url("   ")


def test_http_url_returns_normalized_http_url() -> None:
    assert cli._http_url("  https://example.test/api  ") == "https://example.test/api"
    
def test_cli_main_reads_prompt_from_file(monkeypatch, tmp_path: Path) -> None:
    """Test that the CLI can read prompt text from a file when --prompt-file is used."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Hello from file\n", encoding="utf-8")

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt-file",
            str(prompt_file),
            "--provider",
            "http",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["prompt"] == "Hello from file"
    assert payload["response"] == "Echo: Hello from file"

def test_cli_rejects_prompt_and_prompt_file_used_together(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Hello from file\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--prompt",
                "Hello",
                "--prompt-file",
                str(prompt_file),
            ]
        )

    assert exc_info.value.code == 2
    
def test_cli_rejects_missing_prompt_file() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--prompt-file",
                "does-not-exist.txt",
            ]
        )

    assert exc_info.value.code == 2
    
def test_cli_rejects_blank_prompt_file_content(tmp_path: Path) -> None:
    prompt_file = tmp_path / "blank.txt"
    prompt_file.write_text("   \n\t", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--prompt-file",
                str(prompt_file),
            ]
        )

    assert exc_info.value.code == 2
    
def test_cli_main_reads_prompt_from_stdin_when_no_prompt_args(monkeypatch, tmp_path: Path) -> None:
    """Test that the CLI can read prompt text from piped stdin when no prompt-related CLI args are provided."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "Hello from stdin\n"

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--provider",
            "http",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["prompt"] == "Hello from stdin"
    assert payload["response"] == "Echo: Hello from stdin"

def test_cli_rejects_blank_stdin_prompt(monkeypatch) -> None:
    """Test that if the CLI receives blank input from stdin when no prompt args are provided, it rejects it with an appropriate error message and exit code."""
    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "   \n\t"

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
    
def test_cli_prefers_prompt_argument_over_stdin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "Hello from stdin\n"

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt",
            "Hello from arg",
            "--provider",
            "http",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["prompt"] == "Hello from arg"
    assert payload["response"] == "Echo: Hello from arg"
    
def test_cli_prefers_prompt_file_over_stdin(monkeypatch, tmp_path: Path) -> None:
    """Test that if both --prompt-file and piped stdin are provided, the CLI prefers the prompt file content."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return "Hello from stdin\n"

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Hello from file\n", encoding="utf-8")

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt-file",
            str(prompt_file),
            "--provider",
            "http",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["prompt"] == "Hello from file"
    assert payload["response"] == "Echo: Hello from file"


def test_cli_rejects_missing_prompt_source_when_stdin_is_tty(monkeypatch) -> None:
    """Test that if no prompt-related CLI args are provided and stdin is a TTY (i.e. not piped), the CLI rejects the missing prompt with an appropriate error message and exit code."""
    class FakeStdin:
        def isatty(self) -> bool:
            return True

        def read(self) -> str:
            return ""

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2


def test_cli_help_documents_prompt_sources_and_exit_codes(capsys) -> None:
    """Test that the CLI help text includes documentation of prompt input sources and exit codes for user clarity."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "--prompt-file" in captured.out
    assert "piped stdin" in captured.out
    assert "Exit codes:" in captured.out
    assert "0  Success" in captured.out
    assert "1  Runtime error" in captured.out
    assert "2  Usage/validation error" in captured.out