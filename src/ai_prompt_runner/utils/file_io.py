"""File system helpers for persisting outputs."""

import json
from pathlib import Path


def ensure_parent_dir(path: Path) -> None:
    """Create parent directory when missing."""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    """Write JSON file with stable formatting."""
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict) -> None:
    """Write markdown output from normalized payload."""
    ensure_parent_dir(path)
    content = (
        "# AI Prompt Response\n\n"
        f"## Prompt\n\n{payload['prompt']}\n\n"
        f"## Response\n\n{payload['response']}\n\n"
        "## Metadata\n\n"
        f"- Provider: {payload['metadata']['provider']}\n"
        f"- Timestamp (UTC): {payload['metadata']['timestamp_utc']}\n"
    )
    path.write_text(content, encoding="utf-8")