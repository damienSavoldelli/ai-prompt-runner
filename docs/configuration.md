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
timeout = 30
retries = 0
out_json = "outputs/response.json"
out_md = "outputs/response.md"
```

Supported TOML keys:

- `provider`
- `api_endpoint`
- `api_model`
- `timeout`
- `retries`
- `out_json`
- `out_md`

Unsupported TOML key:

- `api_key`

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

## Validation Rules

Configuration values are validated before provider execution.

Examples:

- endpoint must use `http://` or `https://`
- timeout must be greater than `0`
- retries must be greater than or equal to `0`
- unsupported TOML keys are rejected

## Related Documentation

- [`docs/cli-reference.md`](./cli-reference.md)
- [`README.md`](../README.md)
