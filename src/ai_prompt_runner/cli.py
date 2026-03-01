"""Command-line entrypoint for ai-prompt-runner."""

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from importlib.metadata import PackageNotFoundError, version
from dotenv import load_dotenv

from ai_prompt_runner.core.errors import PromptRunnerError
from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.provider_factory import ConfigurationError, create_provider
from ai_prompt_runner.utils.file_io import write_json, write_markdown

# Define exit codes
EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

def _get_app_version() -> str:
    """Return installed package version, with a safe fallback for local runs."""
    try:
        return version("ai-prompt-runner")
    except PackageNotFoundError:
        return "0.1.0-dev"

def _non_negative_int(value: str) -> int:
    """Argparse validator: retries must be >= 0."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("retries must be an integer.") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError("retries must be greater than or equal to 0.")
    return parsed

def _non_blank_text(value: str) -> str:
    """Argparse validator: text input must not be empty or whitespace only."""
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("prompt must not be empty.")
    return normalized


def _http_url(value: str) -> str:
    """Argparse validator: endpoint must be an http/https URL."""
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("api-endpoint must not be empty.")
    if not (normalized.startswith("http://") or normalized.startswith("https://")):
        raise argparse.ArgumentTypeError("api-endpoint must start with http:// or https://.")
    return normalized
    
def _positive_int(value: str) -> int:
    """Argparse validator: timeout must be a strictly positive integer."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be an integer.") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive integer.")
    return parsed

def _prompt_file_text(value: str) -> str:
    """Argparse validator: read prompt text from a file and reject empty content."""
    try:
        content = Path(value).read_text(encoding="utf-8")
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"prompt-file could not be read: {exc}") from exc
    return _non_blank_text(content)

def _resolve_prompt_text(args: argparse.Namespace) -> str:
    """Resolve prompt from CLI args first, then piped stdin."""
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file
    if not sys.stdin.isatty():
        return _non_blank_text(sys.stdin.read())
    raise argparse.ArgumentTypeError("prompt is required (use --prompt, --prompt-file, or stdin).")

def _load_config_file(path_value: str) -> dict:
    """Load and validate an optional TOML config file."""
    try:
        with open(path_value, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"config could not be read: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise argparse.ArgumentTypeError(f"config is not valid TOML: {exc}") from exc

    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError("config root must be a TOML table.")

    section = data.get("ai_prompt_runner", {})
    if not isinstance(section, dict):
        raise argparse.ArgumentTypeError("config section [ai_prompt_runner] must be a table.")
    
    return section


def _merge_runtime_config(args: argparse.Namespace) -> argparse.Namespace:
    """Merge CLI, env, and TOML config with precedence CLI > env > config."""
    config = args.config or {}

    if "api_key" in config:
        raise argparse.ArgumentTypeError("config key 'api_key' is not supported; use AI_API_KEY or --api-key.")

    if not isinstance(config, dict):
        raise argparse.ArgumentTypeError("config must resolve to a mapping.")

    allowed_keys = {
        "provider",
        "api_endpoint",
        "api_model",
        "timeout",
        "retries",
        "out_json",
        "out_md",
    }
    unknown_keys = sorted(set(config.keys()) - allowed_keys)
    if unknown_keys:
        raise argparse.ArgumentTypeError(f"unsupported config keys: {unknown_keys}")

    def _pick_no_env(cli_value, config_key: str, default):
        if cli_value is not None:
            return cli_value
        if config_key in config:
            return config[config_key]
        return default

    def _pick_with_env(cli_value, env_name: str, config_key: str, default=None):
        if cli_value is not None:
            return cli_value
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value
        if config_key in config:
            return config[config_key]
        return default

    args.provider = _pick_no_env(args.provider, "provider", "http")
    args.api_endpoint = _pick_with_env(args.api_endpoint, "AI_API_ENDPOINT", "api_endpoint", None)
    args.api_model = _pick_with_env(args.api_model, "AI_API_MODEL", "api_model", None)
    args.timeout = _pick_no_env(args.timeout, "timeout", 30)
    args.retries = _pick_no_env(args.retries, "retries", 0)
    args.out_json = _pick_no_env(args.out_json, "out_json", "outputs/response.json")
    args.out_md = _pick_no_env(args.out_md, "out_md", "outputs/response.md")

    # Validate TOML-provided values with the same CLI validators where applicable.
    if "api_endpoint" in config and args.api_endpoint is not None:
        args.api_endpoint = _http_url(str(args.api_endpoint))
    if "api_model" in config and args.api_model is not None:
        args.api_model = str(args.api_model).strip() or None
    if "timeout" in config:
        args.timeout = _positive_int(str(args.timeout))
    if "retries" in config:
        args.retries = _non_negative_int(str(args.retries))
    if "provider" in config:
        args.provider = str(args.provider).strip() or "http"
    if "out_json" in config:
        args.out_json = str(args.out_json)
    if "out_md" in config:
        args.out_md = str(args.out_md)

    return args


# Build safe preview values for --help without leaking secrets.
def _env_preview() -> tuple[str, str, str]:
    """Return safe preview of environment configuration for help text."""
    endpoint = os.getenv("AI_API_ENDPOINT", "").strip() or "not set"
    model = os.getenv("AI_API_MODEL", "").strip() or "not set"
    key = "***set***" if os.getenv("AI_API_KEY", "").strip() else "not set"
    return endpoint, model, key

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""

    endpoint_preview, model_preview, key_preview = _env_preview()

    parser = argparse.ArgumentParser(
        description=(
            "Send a prompt to an AI API and print normalized JSON output.\n"
            "Prompt input sources (priority): --prompt, --prompt-file, then piped stdin.\n"
            "Configuration can be passed via CLI args or AI_API_* env vars."
        ),
        epilog=(
            "Examples:\n"
            "  ai-prompt-runner --prompt \"Hello\" --provider http\n"
            "  ai-prompt-runner --prompt-file prompts/hello.txt --provider http\n"
            "  echo \"Hello\" | ai-prompt-runner --provider http\n"
            "\n"
            "Exit codes:\n"
            f"  {EXIT_OK}  Success\n"
            f"  {EXIT_RUNTIME_ERROR}  Runtime error (configuration/provider/output)\n"
            f"  {EXIT_USAGE_ERROR}  Usage/validation error\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    prompt_group = parser.add_mutually_exclusive_group(required=False)
    prompt_group.add_argument( "--prompt", type=_non_blank_text, help="Prompt text to send (mutually exclusive with --prompt-file).")
    prompt_group.add_argument( "--prompt-file", type=_prompt_file_text, help="Path to a UTF-8 text file containing the prompt (mutually exclusive with --prompt).")
    parser.add_argument("--provider", default=None, help="Provider name (currently: http).")
    parser.add_argument( "--config", type=_load_config_file, help="Path to a TOML config file (optional; CLI overrides env and config).")
    parser.add_argument( "--api-endpoint", type=_http_url, help=f"AI API endpoint URL (env AI_API_ENDPOINT: {endpoint_preview}).")
    parser.add_argument("--api-key", help=f"AI API key (env AI_API_KEY: {key_preview}). Prefer env var in production.")
    parser.add_argument("--api-model", help=f"AI model name (env AI_API_MODEL: {model_preview}).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_app_version()}")
    parser.add_argument("--out-json", default=None, help="JSON output path.")
    parser.add_argument("--out-md", default=None, help="Markdown output path.")
    parser.add_argument("--timeout",type=_positive_int,default=None,help="HTTP timeout in seconds (must be > 0).")
    parser.add_argument( "--retries", type=_non_negative_int, default=None, help="Maximum retry attempts on network errors (must be >= 0).")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint returning process exit code."""

    load_dotenv()  # Load .env before building the parser so dynamic help reflects env values.
    parser = build_parser()  # Build CLI definition (arguments, help text, version flag).
    args = parser.parse_args(argv)  # Parse runtime arguments into a namespace.
    try:
        args = _merge_runtime_config(args)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    # Resolve prompt from CLI args first, then fallback to piped stdin.
    try:
        prompt_text = _resolve_prompt_text(args)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    
    # Wire infrastructure (provider) to application logic (runner).
    try:
        provider = create_provider(
            provider_name=args.provider,
            api_endpoint=args.api_endpoint,
            api_key=args.api_key,
            api_model=args.api_model,
            timeout_seconds=args.timeout,
            max_retries=args.retries,
        )
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    runner = PromptRunner(provider=provider)

    try:
        payload = runner.run(
            PromptRequest(
                prompt_text=prompt_text,
                provider=args.provider,
            )
        )

        write_json(Path(args.out_json), payload)
        write_markdown(Path(args.out_md), payload)
    except PromptRunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
