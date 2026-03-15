"""Command-line entrypoint for ai-prompt-runner."""

import argparse
import json
import os
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

from importlib.metadata import PackageNotFoundError, version
from dotenv import load_dotenv

from ai_prompt_runner.core.errors import PromptRunnerError
from ai_prompt_runner.core.models import PromptRequest
from ai_prompt_runner.core.runner import PromptRunner
from ai_prompt_runner.services.provider_factory import (
    ConfigurationError,
    ProviderSpec,
    create_provider,
    get_provider_spec,
)
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


def _non_negative_float(value: str) -> float:
    """Argparse validator: temperature must be a float >= 0."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("temperature must be a float.") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError("temperature must be greater than or equal to 0.")
    return parsed


def _top_p_float(value: str) -> float:
    """Argparse validator: top-p must be a float in (0, 1]."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("top-p must be a float.") from exc

    if parsed <= 0 or parsed > 1:
        raise argparse.ArgumentTypeError("top-p must be greater than 0 and less than or equal to 1.")
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


def _resolve_optional_prompt_text_for_dry_run(args: argparse.Namespace) -> str | None:
    """
    Resolve prompt text for dry-run diagnostics without consuming stdin.

    Dry-run is config/capability validation only, so prompt input is optional.
    """
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file
    return None

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
        "temperature",
        "max_tokens",
        "top_p",
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
    args.temperature = _pick_no_env(args.temperature, "temperature", None)
    args.max_tokens = _pick_no_env(args.max_tokens, "max_tokens", None)
    args.top_p = _pick_no_env(args.top_p, "top_p", None)
    args.timeout = _pick_no_env(args.timeout, "timeout", 30)
    args.retries = _pick_no_env(args.retries, "retries", 0)
    args.out_json = _pick_no_env(args.out_json, "out_json", "outputs/response.json")
    args.out_md = _pick_no_env(args.out_md, "out_md", "outputs/response.md")

    # Validate TOML-provided values with the same CLI validators where applicable.
    if "api_endpoint" in config and args.api_endpoint is not None:
        args.api_endpoint = _http_url(str(args.api_endpoint))
    if "api_model" in config and args.api_model is not None:
        args.api_model = str(args.api_model).strip() or None
    if "temperature" in config and args.temperature is not None:
        args.temperature = _non_negative_float(str(args.temperature))
    if "max_tokens" in config and args.max_tokens is not None:
        args.max_tokens = _positive_int(str(args.max_tokens))
    if "top_p" in config and args.top_p is not None:
        args.top_p = _top_p_float(str(args.top_p))
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


def _requested_capabilities(args: argparse.Namespace) -> dict[str, bool]:
    """Return capability requests implied by current CLI arguments."""
    return {
        "stream": bool(args.stream),
        "system": args.system is not None,
        "temperature": args.temperature is not None,
        "top_p": args.top_p is not None,
        "max_tokens": args.max_tokens is not None,
    }


def _evaluate_provider_capabilities(
    provider_spec: ProviderSpec,
    args: argparse.Namespace,
) -> tuple[list[str], list[str]]:
    """
    Evaluate requested CLI options against provider capabilities.

    Returns:
    - warnings (permissive mode informational messages)
    - errors (strict mode blocking messages)
    """
    warnings: list[str] = []
    errors: list[str] = []

    requested = _requested_capabilities(args)

    for capability_name, is_requested in requested.items():
        if not is_requested:
            continue

        capability_state = getattr(provider_spec.capabilities, capability_name)
        if capability_state == "supported":
            continue

        message = (
            f"provider '{provider_spec.provider_id}' reports capability "
            f"'{capability_name}' as {capability_state}."
        )

        if args.strict_capabilities:
            errors.append(message)
            continue

        warnings.append(
            f"{message} Continuing in permissive mode; behavior may fallback or "
            "provider may ignore this option."
        )

    return warnings, errors


def _provider_runtime_snapshot(provider, args: argparse.Namespace) -> dict[str, object]:
    """
    Build a sanitized runtime snapshot from provider config when available.

    API key is always masked in this diagnostic payload.
    """
    config = getattr(provider, "config", None)
    endpoint = getattr(config, "endpoint", args.api_endpoint)
    model = getattr(config, "model", args.api_model)
    timeout_seconds = getattr(config, "timeout_seconds", args.timeout)
    max_retries = getattr(config, "max_retries", args.retries)
    raw_api_key = getattr(config, "api_key", None)

    return {
        "endpoint": endpoint,
        "api_key": "***set***" if bool(raw_api_key) else "not set",
        "model": model,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
    }


def _build_effective_config_payload(
    provider_spec: ProviderSpec,
    provider,
    args: argparse.Namespace,
    warnings: list[str],
    errors: list[str],
    prompt_text: str | None,
) -> dict[str, object]:
    """Return JSON-serializable effective configuration diagnostics."""
    return {
        "provider": {
            "name": provider_spec.provider_id,
            **_provider_runtime_snapshot(provider, args),
        },
        "request": {
            "prompt_provided": prompt_text is not None,
            "system_provided": args.system is not None,
            "stream": args.stream,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "top_p": args.top_p,
        },
        "capabilities": asdict(provider_spec.capabilities),
        "capability_validation": {
            "strict_mode": args.strict_capabilities,
            "warnings": warnings,
            "errors": errors,
        },
    }


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
    parser.add_argument(
        "--system",
        type=_non_blank_text,
        help="Optional one-shot system instruction applied before the prompt.",
    )
    parser.add_argument("--provider", default=None, help="Provider name (currently: http).")
    parser.add_argument( "--config", type=_load_config_file, help="Path to a TOML config file (optional; CLI overrides env and config).")
    parser.add_argument( "--api-endpoint", type=_http_url, help=f"AI API endpoint URL (env AI_API_ENDPOINT: {endpoint_preview}).")
    parser.add_argument("--api-key", help=f"AI API key (env AI_API_KEY: {key_preview}). Prefer env var in production.")
    parser.add_argument("--api-model", help=f"AI model name (env AI_API_MODEL: {model_preview}).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_app_version()}")
    parser.add_argument("--out-json", default=None, help="JSON output path.")
    parser.add_argument("--out-md", default=None, help="Markdown output path.")
    parser.add_argument("--stream",action="store_true",help="Stream response chunks to stdout when supported by the provider; final JSON/Markdown outputs are still written after completion.")
    parser.add_argument(
        "--strict-capabilities",
        action="store_true",
        help="Fail when requested options are unsupported or unknown for the selected provider.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration/capabilities and exit without provider execution.",
    )
    parser.add_argument(
        "--print-effective-config",
        action="store_true",
        help="Print resolved runtime configuration (with masked secrets).",
    )
    parser.add_argument(
        "--temperature",
        type=_non_negative_float,
        default=None,
        help="Optional generation temperature (float >= 0).",
    )
    parser.add_argument(
        "--max-tokens",
        type=_positive_int,
        default=None,
        help="Optional max token budget for completion (integer > 0).",
    )
    parser.add_argument(
        "--top-p",
        type=_top_p_float,
        default=None,
        help="Optional nucleus sampling value (0 < top-p <= 1).",
    )
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

    # Resolve prompt text unless dry-run mode is requested.
    if args.dry_run:
        prompt_text = _resolve_optional_prompt_text_for_dry_run(args)
    else:
        try:
            prompt_text = _resolve_prompt_text(args)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))

    # Validate requested capabilities before provider instantiation.
    try:
        provider_spec = get_provider_spec(args.provider)
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    warnings, errors = _evaluate_provider_capabilities(provider_spec, args)
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"Error: capability check failed: {error}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    
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

    effective_config = _build_effective_config_payload(
        provider_spec=provider_spec,
        provider=provider,
        args=args,
        warnings=warnings,
        errors=errors,
        prompt_text=prompt_text,
    )

    if args.print_effective_config:
        print(json.dumps(effective_config, indent=2, ensure_ascii=False), file=sys.stderr)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "status": "ok",
                    "effective_config": effective_config,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return EXIT_OK

    runner = PromptRunner(provider=provider)

    def _print_stream_chunk(chunk: str) -> None:
        """Render stream chunks progressively without buffering delays."""
        print(chunk, end="", flush=True)

    try:
        payload = runner.run(
            PromptRequest(
                prompt_text=prompt_text or "",
                provider=args.provider,
                system_prompt=args.system,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                top_p=args.top_p,
                stream=args.stream,
            )
            ,
            on_stream_chunk=_print_stream_chunk if args.stream else None,
        )

        # Keep streamed token output readable and separate from final JSON payload.
        if args.stream:
            print()

        write_json(Path(args.out_json), payload)
        write_markdown(Path(args.out_md), payload)
    except PromptRunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
