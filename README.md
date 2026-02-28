# ai-prompt-runner

[![CI](https://github.com/damienSavoldelli/ai-prompt-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/damienSavoldelli/ai-prompt-runner/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/tag/damienSavoldelli/ai-prompt-runner?sort=semver)](https://github.com/damienSavoldelli/ai-prompt-runner/tags)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)

Modular Python CLI that sends prompts to an AI API and saves outputs as JSON and Markdown.

## Design Philosophy

ai-prompt-runner is intentionally designed as a stateless execution layer:

**1 input → 1 API call → 1 structured output**

It does not manage conversational state, orchestration, agents, or multi-step workflows.

The project focuses on:

- deterministic execution
- explicit configuration precedence
- contract-driven provider abstraction
- strict failure-path handling
- reproducible CI validation

Provider implementations must conform to a shared contract validated through reusable contract tests.

An official `MockProvider` is included to guarantee deterministic behavior and network-independent validation.

## Public Roadmap & Engineering Approach

This project includes a detailed public roadmap and documentation of its structured AI-assisted development approach.

Explore the full project overview, roadmap and methodology here:

[🔗 AI Prompt Runner – Project Page](https://nutritious-ringer-9ec.notion.site/AI-Prompt-Runner-30ca11bd93a28009bde3fb280d7179fd)

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [Requirements](#requirements)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Configuration File (Optional)](#configuration-file-optional)
- [CLI Usage](#cli-usage)
- [Project Structure](#project-structure)
- [Architecture Principles](#architecture-principles)
- [Output Contract](#output-contract)
- [Output Examples](#output-examples)
- [Testing](#testing)
- [Lint](#lint)
- [CI](#ci)
- [Versioning](#versioning)
- [Release Notes](#release-notes)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## Requirements

- Python 3.11+
- Virtual environment recommended

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

## Environment Variables

Create a local `.env` file (or use CLI flags directly):

```env
AI_API_ENDPOINT=
AI_API_KEY=
AI_API_MODEL=default
```

You can start from `.env.example`.

## Configuration File (Optional)

You can provide a TOML config file with `--config` for non-sensitive runtime defaults.

Example (`config.toml`):

```toml
[ai_prompt_runner]
provider = "http"
api_endpoint = "http://localhost:11434/api/generate"
api_model = "llama3.2"
timeout = 30
retries = 0
out_json = "outputs/response.json"
out_md = "outputs/response.md"
```

You can start from [`config.example.toml`](config.example.toml) and copy it to a local `config.toml` (do not store secrets in this file)

Configuration precedence is:

`CLI > environment variables (.env / shell env) > TOML config > built-in defaults`

Security note:
- `api_key` is intentionally not supported in the TOML config file.
- Use `AI_API_KEY` (recommended) or `--api-key` for secrets.

## CLI Usage

Use either command style:
- Installed console script: `ai-prompt-runner ...`
- Module fallback: `python3 -m src.cli ...`

Show help:

```bash
ai-prompt-runner --help
python3 -m src.cli --help
```

Run with `.env` values:

```bash
ai-prompt-runner --prompt "Hello world"
python3 -m src.cli --prompt "Hello world"
```

Run with an optional TOML config file:

```bash
ai-prompt-runner --config config.toml --prompt "Hello world"
python3 -m src.cli --config config.toml --prompt "Hello world"
```

CLI flags and environment variables override values from the config file.

Run with explicit API values:

```bash
ai-prompt-runner \
  --prompt "Hello world" \
  --api-endpoint "http://localhost:11434/api/generate" \
  --api-key "dummy" \
  --api-model "llama3.2"

python3 -m src.cli \
  --prompt "Hello world" \
  --api-endpoint "http://localhost:11434/api/generate" \
  --api-key "dummy" \
  --api-model "llama3.2"
```

Custom output paths:

```bash
ai-prompt-runner \
  --prompt "Hello world" \
  --out-json outputs/my_response.json \
  --out-md outputs/my_response.md

python3 -m src.cli \
  --prompt "Hello world" \
  --out-json outputs/my_response.json \
  --out-md outputs/my_response.md
```

## Project Structure

```text
Root/
│
├── src/
│   ├── cli.py
│   ├── core/
│   │   ├── errors.py
│   │   ├── models.py
│   │   ├── runner.py
│   │   └── validators.py
│   ├── services/
│   │   ├── base.py
│   │   ├── http_provider.py
│   │   └── provider_factory.py
│   └── utils/
│       └── file_io.py
│
├── prompts/
│
├── tests/
│   ├── unit/
│   └── e2e/
│
├── .github/workflows/ci.yml
├── requirements.txt
├── pyproject.toml
├── README.md
└── AGENT.md
```

## Architecture Principles

- `src/cli.py`: argument parsing and process-level I/O only.
- `src/core/`: business rules and payload validation.
- `src/services/`: external integrations (AI provider implementations).
- Provider layer follows an explicit contract enforced by reusable contract tests.
- `MockProvider` ensures deterministic behavior and decouples validation from network dependencies.
- `src/utils/`: file persistence helpers.

## Output Contract

The normalized JSON response is treated as a stable contract and is formally defined by [`schemas/response.schema.json`](schemas/response.schema.json).

Detailed contract documentation is available in [`docs/output-contract.md`](docs/output-contract.md).

## Output Examples

Generated JSON (`outputs/response.json`):

```json
{
  "prompt": "Hello world",
  "response": "Echo: Hello world",
  "metadata": {
    "provider": "http",
    "timestamp_utc": "2026-02-18T13:43:51.236575+00:00"
  }
}
```

Generated Markdown (`outputs/response.md`):

```md
# AI Prompt Response

## Prompt

Hello world

## Response

Echo: Hello world

## Metadata

- Provider: http
- Timestamp (UTC): 2026-02-18T13:43:51.236575+00:00
```

## Testing

Run all tests:

```bash
python3 -m pytest
```

Run unit tests only:

```bash
python3 -m pytest tests/unit
```

Run E2E tests only:

```bash
python3 -m pytest tests/e2e
```

Coverage (requires `pytest-cov`):

```bash
python3 -m pytest --cov=src --cov-report=term-missing -q
```

Generate an HTML coverage report:

```bash
python3 -m pytest --cov=src --cov-report=term-missing --cov-report=html -q
```

Open `htmlcov/index.html` in a browser to inspect file-by-file coverage.

## Lint

```bash
ruff check .
```

## CI

GitHub Actions workflow runs on:
- `push`
- `pull_request`

Pipeline includes:
- dependency installation
- lint
- tests

## Versioning

This project follows semantic versioning.

Create release tags such as:
- `v0.1.0`
- `v1.0.0`

Release history and notes should be published through GitHub Releases.

## Release Notes

See `CHANGELOG.md` for version history.

## Troubleshooting

- `ModuleNotFoundError: No module named 'src'`:
  run commands from repository root and use `python3 -m ...` syntax.
- `Connection refused` on API call:
  verify `AI_API_ENDPOINT`, provider availability, and local network access.
- `requests`/`pytest` not found:
  activate `.venv` and reinstall dependencies with `python3 -m pip install -r requirements.txt`.

## Security

- Never commit `.env` files containing secrets.
- Never hardcode API keys in source code.
- Prefer environment variables over CLI flags for sensitive values like `AI_API_KEY`.
