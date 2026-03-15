import pytest
import json
import argparse
import runpy
import sys

from pathlib import Path

from ai_prompt_runner import cli


class FakeProvider:
    """E2E test double returning deterministic output."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config=None,
    ) -> str:
        if system_prompt is not None:
            return f"Echo: SYSTEM={system_prompt} | USER={prompt}"
        return f"Echo: {prompt}"

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        generation_config=None,
    ):
        """Stream deterministic chunks to exercise CLI streaming behavior."""
        if system_prompt is not None:
            for char in f"Echo: SYSTEM={system_prompt} | USER={prompt}":
                yield char
            return
        for char in f"Echo: {prompt}":
            yield char


def test_cli_main_generates_json_and_markdown_files(monkeypatch, tmp_path: Path) -> None:
    """Generate JSON/Markdown outputs from a prompt using a fake provider."""
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
    """Forward timeout/retries CLI values to the provider factory."""
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


def test_cli_main_forwards_system_and_runtime_controls_to_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Forward --system and runtime controls into PromptRequest before runner execution."""
    captured: dict = {}

    class FakeRunner:
        def __init__(self, provider) -> None:
            self.provider = provider

        def run(self, request, on_stream_chunk=None):
            captured["system_prompt"] = request.system_prompt
            captured["temperature"] = request.temperature
            captured["max_tokens"] = request.max_tokens
            captured["top_p"] = request.top_p
            return {
                "prompt": request.prompt_text,
                "response": f"Echo: {request.prompt_text}",
                "metadata": {
                    "provider": request.provider,
                    "timestamp_utc": "2026-01-01T00:00:00+00:00",
                    "execution_ms": 1,
                },
            }

    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())
    monkeypatch.setattr(cli, "PromptRunner", FakeRunner)

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt",
            "Hello",
            "--provider",
            "http",
            "--system",
            "You are strict.",
            "--temperature",
            "0.2",
            "--max-tokens",
            "120",
            "--top-p",
            "0.95",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    assert captured["system_prompt"] == "You are strict."
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 120
    assert captured["top_p"] == 0.95


def test_cli_rejects_blank_prompt() -> None:
    """Reject a blank prompt argument as a usage error."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--prompt", "   "])

    assert exc_info.value.code == 2


def test_cli_rejects_blank_system_prompt() -> None:
    """Reject a blank system instruction argument as a usage error."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--prompt", "Hello", "--system", "   "])

    assert exc_info.value.code == 2


def test_cli_rejects_invalid_api_endpoint_scheme() -> None:
    """Reject an API endpoint that does not use http/https."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--prompt", "Hello", "--api-endpoint", "ftp://example.test"])

    assert exc_info.value.code == 2


def test_cli_returns_error_on_provider_configuration_error(monkeypatch, capsys) -> None:
    """Return a runtime error when provider creation fails with configuration error."""
    
    def fake_create_provider(**kwargs):
        raise cli.ConfigurationError("invalid provider config")

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    exit_code = cli.main(["--prompt", "Hello"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: invalid provider config" in captured.err


def test_cli_returns_error_on_runner_failure(monkeypatch, capsys) -> None:
    """Return a runtime error when the runner raises a domain error."""
    class FakeProvider:
        pass

    class FakeRunner:
        def __init__(self, provider) -> None:
            self.provider = provider

        def run(self, request, on_stream_chunk=None):
            raise cli.PromptRunnerError("runner failed")

    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())
    monkeypatch.setattr(cli, "PromptRunner", FakeRunner)

    exit_code = cli.main(["--prompt", "Hello"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: runner failed" in captured.err


def test_get_app_version_falls_back_when_metadata_is_missing(monkeypatch) -> None:
    """Fallback to a dev version when package metadata is unavailable."""
    def fake_version(_: str) -> str:
        raise cli.PackageNotFoundError

    monkeypatch.setattr(cli, "version", fake_version)

    assert cli._get_app_version() == "0.1.0-dev"


def test_non_negative_int_rejects_non_integer() -> None:
    """Reject non-integer retry values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="retries must be an integer"):
        cli._non_negative_int("abc")


def test_non_negative_int_rejects_negative_value() -> None:
    """Reject negative retry values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="greater than or equal to 0"):
        cli._non_negative_int("-1")


def test_positive_int_rejects_non_integer() -> None:
    """Reject non-integer timeout values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="timeout must be an integer"):
        cli._positive_int("abc")


def test_positive_int_rejects_zero() -> None:
    """Reject zero timeout values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="timeout must be a positive integer"):
        cli._positive_int("0")


def test_non_negative_float_rejects_non_float() -> None:
    """Reject non-float temperature values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="temperature must be a float"):
        cli._non_negative_float("abc")


def test_non_negative_float_rejects_negative_value() -> None:
    """Reject negative temperature values in the CLI validator."""
    with pytest.raises(
        argparse.ArgumentTypeError,
        match="temperature must be greater than or equal to 0",
    ):
        cli._non_negative_float("-0.1")


def test_top_p_float_rejects_invalid_range() -> None:
    """Reject out-of-range top-p values in the CLI validator."""
    with pytest.raises(
        argparse.ArgumentTypeError,
        match="top-p must be greater than 0 and less than or equal to 1",
    ):
        cli._top_p_float("1.2")


def test_top_p_float_rejects_non_float() -> None:
    """Reject non-float top-p values in the CLI validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="top-p must be a float"):
        cli._top_p_float("abc")


def test_http_url_rejects_blank_value() -> None:
    """Reject blank endpoint values in the URL validator."""
    with pytest.raises(argparse.ArgumentTypeError, match="api-endpoint must not be empty"):
        cli._http_url("   ")


def test_http_url_returns_normalized_http_url() -> None:
    """Normalize surrounding whitespace for valid HTTP(S) endpoint values."""
    assert cli._http_url("  https://example.test/api  ") == "https://example.test/api"


def test_cli_main_reads_prompt_from_file(monkeypatch, tmp_path: Path) -> None:
    """Read prompt content from --prompt-file and run the CLI successfully."""
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
    """Reject mutually exclusive prompt sources when both flags are provided."""
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
    """Reject --prompt-file when the target file does not exist."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "--prompt-file",
                "does-not-exist.txt",
            ]
        )

    assert exc_info.value.code == 2


def test_cli_rejects_blank_prompt_file_content(tmp_path: Path) -> None:
    """Reject --prompt-file when the file content is blank/whitespace-only."""
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
    """Read prompt content from piped stdin when no prompt flags are provided."""
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
    """Reject blank piped stdin content when used as the prompt source."""
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
    """Prefer --prompt over piped stdin when both sources are available."""
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
    """Prefer --prompt-file over piped stdin when both sources are available."""
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
    """Reject missing prompt input when no flags are provided and stdin is a TTY."""
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
    """Document prompt sources and exit codes in the CLI help output."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0

    # argparse writes --help output to stdout and exits with code 0.
    captured = capsys.readouterr()
    assert "--prompt-file" in captured.out
    assert "--system" in captured.out
    assert "--stream" in captured.out
    assert "--strict-capabilities" in captured.out
    assert "--temperature" in captured.out
    assert "--max-tokens" in captured.out
    assert "--top-p" in captured.out
    assert "--config" in captured.out
    assert "piped stdin" in captured.out
    assert "Exit codes:" in captured.out
    assert "0  Success" in captured.out
    assert "1  Runtime error" in captured.out
    assert "2  Usage/validation error" in captured.out


def test_cli_warns_on_unsupported_capability_in_permissive_mode(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """Warn and continue when an unsupported capability is requested without strict mode."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt",
            "Hello",
            "--provider",
            "http",
            "--temperature",
            "0.2",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Warning: provider 'http' reports capability 'temperature' as unsupported." in captured.err


def test_cli_strict_capabilities_rejects_unsupported_option(monkeypatch, capsys) -> None:
    """Fail before provider execution when strict mode rejects unsupported capabilities."""
    called = {"create_provider": False}

    def fake_create_provider(**kwargs):
        called["create_provider"] = True
        return FakeProvider()

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    exit_code = cli.main(
        [
            "--prompt",
            "Hello",
            "--provider",
            "http",
            "--temperature",
            "0.2",
            "--strict-capabilities",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert called["create_provider"] is False
    assert (
        "Error: capability check failed: provider 'http' reports capability "
        "'temperature' as unsupported."
    ) in captured.err


def test_cli_warns_on_unknown_capability_in_permissive_mode(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """Warn and continue when requested capability support is unknown."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt",
            "Hello",
            "--provider",
            "openai",
            "--top-p",
            "0.95",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Warning: provider 'openai' reports capability 'top_p' as unknown." in captured.err


def test_cli_strict_capabilities_rejects_unknown_option(monkeypatch, capsys) -> None:
    """Fail before provider execution when strict mode rejects unknown capabilities."""
    called = {"create_provider": False}

    def fake_create_provider(**kwargs):
        called["create_provider"] = True
        return FakeProvider()

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    exit_code = cli.main(
        [
            "--prompt",
            "Hello",
            "--provider",
            "openai",
            "--top-p",
            "0.95",
            "--strict-capabilities",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert called["create_provider"] is False
    assert (
        "Error: capability check failed: provider 'openai' reports capability "
        "'top_p' as unknown."
    ) in captured.err


def test_cli_rejects_missing_config_file() -> None:
    """Reject --config when the referenced TOML file does not exist."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", "does-not-exist.toml", "--prompt", "Hello"])

    assert exc_info.value.code == 2


def test_cli_rejects_invalid_toml_config_file(tmp_path: Path) -> None:
    """Reject --config when the file content is not valid TOML."""
    config_file = tmp_path / "bad.toml"
    config_file.write_text("not = [valid", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", str(config_file), "--prompt", "Hello"])

    assert exc_info.value.code == 2


def test_cli_uses_config_file_values_for_runtime_options(monkeypatch, tmp_path: Path) -> None:
    """Use TOML config values for runtime options when CLI/env do not override them."""

    # Isolate this test from local env/.env so TOML values are actually exercised.
    monkeypatch.setattr(cli, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("AI_API_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_API_MODEL", raising=False)

    captured: dict = {}

    class FakeProvider:
        def generate(self, prompt: str) -> str:
            return f"Echo: {prompt}"

    def fake_create_provider(**kwargs):
        # Capture resolved runtime configuration without performing real I/O.
        captured.update(kwargs)
        return FakeProvider()

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)

    # Build a valid TOML config file for runtime configuration resolution.
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        (
            "[ai_prompt_runner]\n"
            "provider = \"http\"\n"
            "api_endpoint = \"http://localhost:11434/api/generate\"\n"
            "api_model = \"llama3.2\"\n"
            "timeout = 7\n"
            "retries = 2\n"
            "out_json = \"outputs/from-config.json\"\n"
            "out_md = \"outputs/from-config.md\"\n"
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "--config",
            str(config_file),
            "--prompt",
            "Hello from config",
            "--api-key",
            "dummy",
        ]
    )

    assert exit_code == 0
    assert captured["provider_name"] == "http"
    assert captured["api_endpoint"] == "http://localhost:11434/api/generate"
    assert captured["api_model"] == "llama3.2"
    assert captured["timeout_seconds"] == 7
    assert captured["max_retries"] == 2


def test_cli_rejects_api_key_in_config_file(tmp_path: Path) -> None:
    """Reject secrets in TOML config and require --api-key/AI_API_KEY instead."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        (
            "[ai_prompt_runner]\n"
            "api_key = \"secret\"\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", str(config_file), "--prompt", "Hello"])

    assert exc_info.value.code == 2


def test_cli_rejects_unknown_config_key(tmp_path: Path) -> None:
    """Reject unknown keys in the [ai_prompt_runner] config section."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        (
            "[ai_prompt_runner]\n"
            "unknown_key = \"value\"\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", str(config_file), "--prompt", "Hello"])

    assert exc_info.value.code == 2
    
def test_cli_rejects_non_table_ai_prompt_runner_config_section(tmp_path: Path) -> None:
    """Reject a non-table [ai_prompt_runner] config section."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        'ai_prompt_runner = "not-a-table"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--config", str(config_file), "--prompt", "Hello"])

    assert exc_info.value.code == 2
    

def test_cli_prefers_cli_over_env_and_config_for_api_model(monkeypatch, tmp_path: Path) -> None:
    """CLI values must override both environment variables and TOML config values."""
    captured: dict = {}

    class FakeProvider:
        def generate(self, prompt: str) -> str:
            return f"Echo: {prompt}"

    def fake_create_provider(**kwargs):
        captured.update(kwargs)
        return FakeProvider()

    monkeypatch.setattr(cli, "create_provider", fake_create_provider)
    monkeypatch.setenv("AI_API_MODEL", "env-model")

    config_file = tmp_path / "config.toml"
    config_file.write_text(
        (
            "[ai_prompt_runner]\n"
            "api_endpoint = \"http://localhost:11434/api/generate\"\n"
            "api_model = \"config-model\"\n"
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "--config",
            str(config_file),
            "--prompt",
            "Hello",
            "--api-key",
            "dummy",
            "--api-model",
            "cli-model",
        ]
    )

    assert exit_code == 0
    assert captured["api_model"] == "cli-model"


def test_merge_runtime_config_rejects_non_mapping_config() -> None:
    """Reject a parsed config payload that does not resolve to a mapping."""
    args = argparse.Namespace(config=["not-a-mapping"])

    with pytest.raises(argparse.ArgumentTypeError, match="config must resolve to a mapping"):
        cli._merge_runtime_config(args)


def test_merge_runtime_config_validates_generation_controls_from_config() -> None:
    """
    Validate generation controls loaded from TOML with the same validators as CLI.
    """
    args = argparse.Namespace(
        prompt=None,
        prompt_file=None,
        system=None,
        provider=None,
        config={
            "temperature": "0.2",
            "max_tokens": "120",
            "top_p": "0.95",
        },
        api_endpoint=None,
        api_key=None,
        api_model=None,
        out_json=None,
        out_md=None,
        stream=False,
        timeout=None,
        retries=None,
        temperature=None,
        max_tokens=None,
        top_p=None,
    )

    merged = cli._merge_runtime_config(args)
    assert merged.temperature == 0.2
    assert merged.max_tokens == 120
    assert merged.top_p == 0.95


def test_load_config_file_rejects_non_mapping_root(monkeypatch, tmp_path: Path) -> None:
    """Reject a TOML payload whose parsed root is not a mapping."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("ignored = true\n", encoding="utf-8")

    monkeypatch.setattr(cli.tomllib, "load", lambda fh: ["not-a-mapping"])

    with pytest.raises(argparse.ArgumentTypeError, match="config root must be a TOML table"):
        cli._load_config_file(str(config_file))


def test_cli_stream_prints_chunks_and_persists_final_payload(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """Stream chunks to stdout and still persist the same final response payload."""
    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeProvider())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"

    exit_code = cli.main(
        [
            "--prompt",
            "Hello Stream",
            "--provider",
            "openai",
            "--stream",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["response"] == "Echo: Hello Stream"

    captured = capsys.readouterr()
    assert "Echo: Hello Stream" in captured.out


def test_cli_stream_falls_back_to_generate_when_provider_has_no_stream(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Fallback to non-stream execution when provider does not implement streaming."""

    class FakeNoStreamProvider:
        def generate(self, prompt: str) -> str:
            return f"Echo: {prompt}"

    monkeypatch.setattr(cli, "create_provider", lambda **_: FakeNoStreamProvider())

    out_json = tmp_path / "outputs" / "response.json"
    out_md = tmp_path / "outputs" / "response.md"
    exit_code = cli.main(
        [
            "--prompt",
            "Hello Fallback",
            "--provider",
            "http",
            "--stream",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert exit_code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["response"] == "Echo: Hello Fallback"


def test_cli_module_entrypoint_executes_main_guard(monkeypatch) -> None:
    """Execute module as __main__ to cover the script entrypoint guard."""
    # Ensure module execution does not inherit pytest arguments.
    monkeypatch.setattr(sys, "argv", ["ai-prompt-runner"])
    sys.modules.pop("ai_prompt_runner.cli", None)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("ai_prompt_runner.cli", run_name="__main__")

    assert exc_info.value.code == 2
