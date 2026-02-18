"""Command-line entrypoint for ai-prompt-runner."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.core.errors import PromptRunnerError
from src.core.models import PromptRequest
from src.core.runner import PromptRunner
from src.services.provider_factory import ConfigurationError, create_provider
from src.utils.file_io import write_json, write_markdown

APP_VERSION = "0.1.0"


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
            "Send a prompt to an AI API and print normalized JSON output. "
            "Configuration can be passed via CLI args or AI_API_* env vars."
        )
    )
    parser.add_argument("--prompt", required=True, help="Prompt text to send.")
    parser.add_argument("--provider", default="http", help="Provider name (currently: http).")
    parser.add_argument("--api-endpoint", help=f"AI API endpoint URL (env AI_API_ENDPOINT: {endpoint_preview}).")
    parser.add_argument("--api-key", help=f"AI API key (env AI_API_KEY: {key_preview}). Prefer env var in production.")
    parser.add_argument("--api-model", help=f"AI model name (env AI_API_MODEL: {model_preview}).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--out-json", default="outputs/response.json", help="JSON output path.")
    parser.add_argument("--out-md", default="outputs/response.md", help="Markdown output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint returning process exit code."""

    load_dotenv()  # Load .env before building the parser so dynamic help reflects env values.
    parser = build_parser()  # Build CLI definition (arguments, help text, version flag).
    args = parser.parse_args(argv)  # Parse runtime arguments into a namespace.

    # Wire infrastructure (provider) to application logic (runner).
    try:
        provider = create_provider(
            provider_name=args.provider,
            api_endpoint=args.api_endpoint,
            api_key=args.api_key,
            api_model=args.api_model,
        )
    except ConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    runner = PromptRunner(provider=provider)

    try:
        payload = runner.run(
            PromptRequest(
                prompt_text=args.prompt,
                provider=args.provider,
            )
        )

        write_json(Path(args.out_json), payload)
        write_markdown(Path(args.out_md), payload)
    except PromptRunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
