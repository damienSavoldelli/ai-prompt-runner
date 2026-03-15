# ai-prompt-runner

[![CI](https://github.com/damienSavoldelli/ai-prompt-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/damienSavoldelli/ai-prompt-runner/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/ai-prompt-runner.svg)](https://pypi.org/project/ai-prompt-runner/)
[![Python](https://img.shields.io/pypi/pyversions/ai-prompt-runner)](https://pypi.org/project/ai-prompt-runner/)
[![License](https://img.shields.io/pypi/l/ai-prompt-runner)](https://pypi.org/project/ai-prompt-runner/)

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
- [uv Workflow](#uv-workflow)
- [Environment Variables](#environment-variables)
- [Configuration File (Optional)](#configuration-file-optional)
- [CLI Usage](#cli-usage)
- [Supported Providers](#supported-providers)
- [System Prompt (--system)](#system-prompt---system)
- [Streaming (--stream)](#streaming---stream)
- [Runtime Controls](#runtime-controls)
- [Safety Modes](#safety-modes)
- [Execution Logs (--log-run-dir)](#execution-logs---log-run-dir)
- [Structured Runtime Errors](#structured-runtime-errors)
- [Execution Metadata](#execution-metadata)
- [Project Structure](#project-structure)
- [Architecture Principles](#architecture-principles)
- [Technical Docs](#technical-docs)
- [Output Contract](#output-contract)
- [Output Examples](#output-examples)
- [Testing](#testing)
- [Lint](#lint)
- [CI](#ci)
- [Versioning](#versioning)
- [Release Notes](#release-notes)
- [Release Checklist](#release-checklist)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## Requirements

- Python 3.11+
- Virtual environment recommended

## Installation

Recommended for CLI usage with `pipx`:

```bash
pipx install ai-prompt-runner
```

Verify the installed command:

```bash
ai-prompt-runner --version
```

Install from PyPI with `pip` (fallback):

```bash
python3 -m pip install ai-prompt-runner
```

If the installed command is not found, your Python script directory may not be on `PATH`.
In that case, prefer `pipx` for CLI usage or run the module directly:

```bash
python3 -m ai_prompt_runner.cli --version
```

Install from source for development:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## uv Workflow

`uv` is supported as the modern dependency and task runner workflow for local development.

Sync the project with development dependencies:

```bash
uv sync --extra dev
```

Run the test suite:

```bash
uv run pytest
```

Run tests with the CI coverage gate:

```bash
uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=95
```

Run lint checks:

```bash
uv run ruff check .
```

Build package distributions:

```bash
uv run python3 -m build
```

`pip`-based commands remain supported, but `uv` is the recommended workflow for local development.

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
temperature = 0.2
max_tokens = 512
top_p = 0.9
timeout = 30
retries = 0
out_json = "outputs/response.json"
out_md = "outputs/response.md"
log_run_dir = "logs"
```

You can start from [`config.example.toml`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/config.example.toml) and copy it to a local `config.toml` (do not store secrets in this file)

Configuration precedence is:

`CLI > environment variables (.env / shell env) > TOML config > built-in defaults`

Security note:
- `api_key` is intentionally not supported in the TOML config file.
- Use `AI_API_KEY` (recommended) or `--api-key` for secrets.

Runtime controls:
- `temperature`, `max_tokens`, and `top_p` are optional and provider-forwarded.
- If omitted, provider defaults are used.

## CLI Usage

Use either command style:
- Installed console script: `ai-prompt-runner ...`
- Module fallback: `python3 -m ai_prompt_runner.cli ...`

Show help:

```bash
ai-prompt-runner --help
python3 -m ai_prompt_runner.cli --help
```

Run with `.env` values:

```bash
ai-prompt-runner --prompt "Hello world"
python3 -m ai_prompt_runner.cli --prompt "Hello world"
```

Run with an optional TOML config file:

```bash
ai-prompt-runner --config config.toml --prompt "Hello world"
python3 -m ai_prompt_runner.cli --config config.toml --prompt "Hello world"
```

CLI flags and environment variables override values from the config file.

## Supported Providers

The provider factory is protocol-first and registry-driven.

OpenAI-compatible protocol providers (same runtime class, different defaults/aliases):

- `openai_compatible`
- `openai`
- `openrouter`
- `groq`
- `together`
- `fireworks`
- `perplexity`
- `inception`
- `x`
- `xai`
- `lmstudio`
- `ollama`

Other protocol providers:

- `anthropic`
- `google`
- `http` (legacy generic JSON-over-HTTP provider)

Run with explicit API values:

```bash
ai-prompt-runner \
  --prompt "Hello world" \
  --api-endpoint "http://localhost:11434/api/generate" \
  --api-key "dummy" \
  --api-model "llama3.2"

python3 -m ai_prompt_runner.cli \
  --prompt "Hello world" \
  --api-endpoint "http://localhost:11434/api/generate" \
  --api-key "dummy" \
  --api-model "llama3.2"
```

Run with Anthropic defaults:

```bash
ai-prompt-runner \
  --provider anthropic \
  --api-key "$AI_API_KEY" \
  --prompt "Explain retry logic"
```

Run with OpenAI defaults:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --prompt "Explain configuration precedence"
```

Run with Google defaults:

```bash
ai-prompt-runner \
  --provider google \
  --api-key "$AI_API_KEY" \
  --prompt "Summarize this architecture"
```

Run with xAI defaults:

```bash
ai-prompt-runner \
  --provider xai \
  --api-key "$AI_API_KEY" \
  --prompt "Generate a concise changelog entry"
```

Run locally with Ollama defaults:

```bash
ai-prompt-runner \
  --provider ollama \
  --api-key "dummy" \
  --prompt "Hello from local Ollama"
```

## System Prompt (--system)

Use `--system` to pass optional one-shot instruction context together with `--prompt`.

Example:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --system "You are a strict API architect." \
  --prompt "Explain retry logic in 5 bullets"
```

Behavior by provider type:

- role-aware protocol providers (`openai_compatible` aliases, `anthropic`, `google`) map `--system` to native system fields
- non role-aware providers (`http`, `mock`) use deterministic prompt composition:
  - `SYSTEM: ...`
  - `USER: ...`

`--system` does not introduce conversation state; execution remains stateless and single-shot.

## Streaming (--stream)

Use `--stream` to print response chunks progressively when the selected provider supports streaming.

Streaming-capable providers:

- `openai_compatible` and all OpenAI-compatible aliases (`openai`, `openrouter`, `groq`, `together`, `fireworks`, `perplexity`, `inception`, `x`, `xai`, `lmstudio`, `ollama`)
- `anthropic`
- `google`
- `mock` (test-only deterministic stream)

Non-stream provider behavior:

- `http` falls back to non-stream execution even if `--stream` is set.

Example:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --stream \
  --prompt "Explain retry strategy"
```

`--stream` changes console UX only. Final JSON and Markdown outputs still contain the complete final response payload.

## Runtime Controls

Use optional runtime controls to tune generation behavior per execution.

Available flags:

- `--temperature` (float `>= 0`)
- `--max-tokens` (integer `> 0`)
- `--top-p` (float `> 0` and `<= 1`)

Example:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --temperature 0.2 \
  --max-tokens 512 \
  --top-p 0.9 \
  --prompt "Explain exponential backoff in one paragraph"
```

These controls are passed to protocol providers and mapped to provider-native request fields.

## Safety Modes

Use safety/diagnostic flags to validate execution intent before runtime:

- `--strict-capabilities`: fail when requested options are `unsupported` or `unknown` for the selected provider.
- `--dry-run`: validate resolved config and capability checks, then exit without generation.
- `--print-effective-config`: print resolved runtime configuration (with masked API key).

Capability states are registry-driven per provider:

- `supported`
- `unsupported`
- `unknown`

Default mode is permissive:

- capability mismatches produce warnings
- execution continues (provider fallback or provider-side ignore may happen)

With `--strict-capabilities`, capability mismatches are treated as hard runtime errors.

Current capability matrix fields:

- `stream`
- `system`
- `usage`
- `temperature`
- `top_p`
- `max_tokens`

Example strict capability check:

```bash
ai-prompt-runner \
  --provider http \
  --temperature 0.2 \
  --strict-capabilities \
  --prompt "Hello"
```

Example dry-run preflight:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --dry-run \
  --print-effective-config
```

`--dry-run` does not call provider generation and does not write JSON/Markdown artifacts.
In dry-run mode, prompt input is optional because execution is preflight-only.

## Execution Logs (--log-run-dir)

Use `--log-run-dir` to persist deterministic per-run diagnostics without changing the final output contract.

Behavior:

- creates one run directory per execution: `run-YYYYmmddTHHMMSSffffffZ`
- writes sanitized `request.json`
- writes `response.json` on success
- writes `error.json` on runtime failure
- never persists raw API keys

Example:

```bash
ai-prompt-runner \
  --provider openai \
  --api-key "$AI_API_KEY" \
  --log-run-dir logs \
  --prompt "Explain retry strategy"
```

Directory shape:

```text
logs/
└── run-20260315T101530123456Z/
    ├── request.json
    └── response.json
```

On failure, `response.json` is replaced by `error.json`.

## Structured Runtime Errors

Runtime failures are normalized to stable taxonomy codes:

- `auth_error`
- `rate_limit`
- `timeout`
- `invalid_request`
- `network_error`
- `provider_error`

These codes are used for diagnostics payloads (including `error.json` when `--log-run-dir` is enabled).
Exit code behavior remains unchanged:

- `0`: success
- `1`: runtime error
- `2`: usage/validation error

## Execution Metadata

Every successful JSON output includes stable execution metadata:

- `metadata.provider`
- `metadata.timestamp_utc`
- `metadata.execution_ms` (integer, non-negative)
- `metadata.model` (resolved model when available, otherwise requested model)
- `metadata.execution_context` (execution provenance snapshot)

`metadata.execution_context` includes:

- `provider_protocol`
- `api_endpoint`
- `model_requested`
- `model_resolved`
- `runner_version`
- `prompt_hash` (`sha256:<hex>`)
- `runtime` snapshot (`stream`, `system_prompt_provided`, runtime controls, timeout, retries)

Providers that expose usage counters also include optional:

- `metadata.usage.prompt_tokens`
- `metadata.usage.completion_tokens`
- `metadata.usage.total_tokens`

`metadata.usage` remains optional and appears only when upstream provider usage is available.

Custom output paths:

```bash
ai-prompt-runner \
  --prompt "Hello world" \
  --out-json outputs/my_response.json \
  --out-md outputs/my_response.md

python3 -m ai_prompt_runner.cli \
  --prompt "Hello world" \
  --out-json outputs/my_response.json \
  --out-md outputs/my_response.md
```

## Project Structure

```text
Root/
│
├── src/
│   └── ai_prompt_runner/
│       ├── cli.py
│       ├── core/
│       │   ├── errors.py
│       │   ├── error_taxonomy.py
│       │   ├── models.py
│       │   ├── runner.py
│       │   └── validators.py
│       ├── services/
│       │   ├── anthropic_provider.py
│       │   ├── base.py
│       │   ├── google_provider.py
│       │   ├── http_provider.py
│       │   ├── mock_provider.py
│       │   ├── openai_compatible_provider.py
│       │   └── provider_factory.py
│       └── utils/
│           └── file_io.py
│
├── schemas/
│   └── response.schema.json
│
├── docs/
│   ├── architecture.md
│   ├── cli-reference.md
│   ├── configuration.md
│   ├── migration.md
│   ├── output-contract.md
│   ├── release-checklist.md
│   └── testing.md
│
├── prompts/
│
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── e2e/
│
├── .github/workflows/ci.yml
├── requirements.txt
├── pyproject.toml
├── uv.lock
├── README.md
└── AGENT.md
```

## Architecture Principles

- `src/ai_prompt_runner/cli.py`: argument parsing and process-level I/O only.
- `src/ai_prompt_runner/core/`: business rules and payload validation.
- `src/ai_prompt_runner/services/`: external integrations (AI provider implementations).
- Provider layer follows an explicit contract enforced by reusable contract tests.
- `MockProvider` ensures deterministic behavior and decouples validation from network dependencies.
- `src/ai_prompt_runner/utils/`: file persistence helpers.

## Technical Docs

Additional versioned technical documentation is available under [`docs/`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs):

- [`docs/architecture.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/architecture.md)
- [`docs/cli-reference.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/cli-reference.md)
- [`docs/configuration.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/configuration.md)
- [`docs/output-contract.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/output-contract.md)
- [`docs/testing.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/testing.md)
- [`docs/migration.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/migration.md)
- [`docs/release-checklist.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/release-checklist.md)

## Output Contract

The normalized JSON response is treated as a stable contract and is formally defined by [`schemas/response.schema.json`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/schemas/response.schema.json).

Detailed contract documentation is available in [`docs/output-contract.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/output-contract.md).

## Output Examples

Generated JSON (`outputs/response.json`):

```json
{
  "prompt": "Explain retry strategy",
  "response": "Retry strategy improves resilience by handling transient failures with controlled backoff.",
  "metadata": {
    "provider": "openai",
    "timestamp_utc": "2026-03-15T10:21:11.236575+00:00",
    "execution_ms": 412,
    "model": "gpt-4o-mini",
    "execution_context": {
      "provider_protocol": "openai-compatible",
      "api_endpoint": "https://api.openai.com/v1",
      "model_requested": "gpt-4o-mini",
      "model_resolved": "gpt-4o-mini",
      "runner_version": "1.6.0",
      "prompt_hash": "sha256:3a5898f8f9a8c98ef08f2f77ec4d5ffbc5f5f7930fb4780f8114a2abf2ff03f7",
      "runtime": {
        "stream": false,
        "system_prompt_provided": false,
        "temperature": 0.2,
        "max_tokens": 512,
        "top_p": 0.9,
        "timeout_seconds": 30,
        "max_retries": 0
      }
    },
    "usage": {
      "prompt_tokens": 32,
      "completion_tokens": 41,
      "total_tokens": 73
    }
  }
}
```

Generated Markdown (`outputs/response.md`):

```md
# AI Prompt Response

## Prompt

Explain retry strategy

## Response

Retry strategy improves resilience by handling transient failures with controlled backoff.

## Metadata

- Provider: openai
- Timestamp (UTC): 2026-03-15T10:21:11.236575+00:00
```

## Testing

Run all tests:

```bash
python3 -m pytest
```

Using `uv`:

```bash
uv run pytest
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

Using `uv`:

```bash
uv run pytest --cov=src --cov-report=term-missing -q
```

Generate an HTML coverage report:

```bash
python3 -m pytest --cov=src --cov-report=term-missing --cov-report=html -q
```

Using `uv`:

```bash
uv run pytest --cov=src --cov-report=term-missing --cov-report=html -q
```

Coverage gate used in CI:

```bash
python3 -m pytest --cov=src --cov-report=term-missing --cov-fail-under=95
```

Open `htmlcov/index.html` in a browser to inspect file-by-file coverage.

## Lint

```bash
ruff check .
```

Using `uv`:

```bash
uv run ruff check .
```

## CI

GitHub Actions workflow runs on:
- `push`
- `pull_request`

Pipeline includes:
- dependency installation
- lint (`ruff check .`)
- package build verification (`python3 -m build`)
- build artifact verification
- tests with coverage enforcement (`--cov-fail-under=95`)

`uv` is supported for local development workflows, while CI currently installs dependencies from `requirements.txt`.

## Versioning

This project follows semantic versioning.

Create release tags such as:
- `v0.1.0`
- `v1.0.0`

Release history and notes should be published through GitHub Releases.

## Release Notes

See [`CHANGELOG.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/CHANGELOG.md) for version history.

## Release Checklist

See [`docs/release-checklist.md`](https://github.com/damienSavoldelli/ai-prompt-runner/blob/main/docs/release-checklist.md) for the standardized release preparation flow.

## Troubleshooting

- `ModuleNotFoundError: No module named 'ai_prompt_runner'`:
  run commands from repository root and use `python3 -m ...` syntax.
- `Connection refused` on API call:
  verify `AI_API_ENDPOINT`, provider availability, and local network access.
- `requests`/`pytest` not found:
  activate `.venv` and reinstall dependencies with `python3 -m pip install -r requirements.txt`.

## Security

- Never commit `.env` files containing secrets.
- Never hardcode API keys in source code.
- Prefer environment variables over CLI flags for sensitive values like `AI_API_KEY`.
