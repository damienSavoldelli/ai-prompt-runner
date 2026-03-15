# Configuration

## Purpose

This document explains how runtime configuration is resolved in `ai-prompt-runner`.

It covers:

- configuration sources
- precedence rules
- supported TOML keys
- environment variable usage
- secret-handling expectations

## Configuration Sources

The CLI can read configuration from four sources:

1. command-line arguments
2. environment variables
3. optional TOML configuration file
4. built-in defaults

## Precedence

Configuration is resolved in this order:

`CLI > environment variables > TOML config > built-in defaults`

This precedence is deterministic and is applied before provider construction.

Provider-specific endpoint/model defaults are resolved in the factory after CLI/env/TOML values.

## Environment Variables

Supported environment variables:

- `AI_API_ENDPOINT`
- `AI_API_KEY`
- `AI_API_MODEL`

These variables are intended for normal development and runtime environments.

## TOML Configuration

The CLI accepts an optional TOML file through `--config`.

Expected section:

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
```

Supported TOML keys:

- `provider`
- `api_endpoint`
- `api_model`
- `temperature`
- `max_tokens`
- `top_p`
- `timeout`
- `retries`
- `out_json`
- `out_md`

CLI-only runtime flag (not supported in env/TOML):

- `--stream`
- `--system`

Example protocol provider configurations:

```toml
[ai_prompt_runner]
provider = "anthropic"
api_model = "claude-3-7-sonnet-latest"
temperature = 0.2
max_tokens = 512
top_p = 0.9
timeout = 30
retries = 0
```

```toml
[ai_prompt_runner]
provider = "google"
api_model = "gemini-2.5-flash"
temperature = 0.2
max_tokens = 512
top_p = 0.9
timeout = 30
retries = 0
```

```toml
[ai_prompt_runner]
provider = "ollama"
api_endpoint = "http://localhost:11434/v1"
api_model = "gemma3:latest"
temperature = 0.2
max_tokens = 512
top_p = 0.9
timeout = 30
retries = 0
```

Unsupported TOML key:

- `api_key`
- `stream`
- `system`

## Secret Handling

Secrets must not be stored in the TOML configuration file.

Use one of these instead:

- `AI_API_KEY`
- `--api-key`

Recommended practice:

- use environment variables for secrets
- reserve TOML for non-sensitive defaults

## Defaults

If no higher-precedence value is provided, the CLI falls back to built-in defaults.

Current defaults include:

- `provider = "http"`
- `timeout = 30`
- `retries = 0`
- `out_json = "outputs/response.json"`
- `out_md = "outputs/response.md"`

Runtime controls default to provider behavior when omitted:

- `temperature = None`
- `max_tokens = None`
- `top_p = None`

Selected providers may also supply endpoint/model defaults through the registry when these values are omitted.

## Validation Rules

Configuration values are validated before provider execution.

Examples:

- endpoint must use `http://` or `https://`
- timeout must be greater than `0`
- retries must be greater than or equal to `0`
- temperature must be greater than or equal to `0`
- max_tokens must be greater than `0`
- top_p must be greater than `0` and less than or equal to `1`
- unsupported TOML keys are rejected

Streaming note:

- `--stream` is intentionally CLI-only so execution intent stays explicit per run.
- Stream mode changes console rendering only; final JSON/Markdown output contract remains unchanged.

System prompt note:

- `--system` is intentionally CLI-only so one-shot instruction context is explicit per run.
- It does not introduce conversation history or persistent prompt state.

## Related Documentation

- [`docs/cli-reference.md`](./cli-reference.md)
- [`README.md`](../README.md)
