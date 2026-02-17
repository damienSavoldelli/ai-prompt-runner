"""Command-line entrypoint for ai-prompt-runner."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Send a prompt to an AI API and save outputs."
    )
    parser.add_argument("--prompt", help="Prompt text to send.")
    parser.add_argument("--provider", default="http", help="Provider name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint returning process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"prompt={args.prompt!r}, provider={args.provider!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
