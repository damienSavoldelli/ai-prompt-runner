# Output Contract

## Purpose

This document defines the stable JSON output contract produced by `ai-prompt-runner`.

The output contract is treated as a stable interface:

- formally described by [`schemas/response.schema.json`](../schemas/response.schema.json)
- validated by automated tests
- protected by backward compatibility fixtures

The goal is to prevent accidental output drift and make the CLI safe to integrate into larger automation pipelines.

## Stability Guarantees

The response payload structure is considered stable within the current contract line.

The project guarantees:

- required fields will not be removed without an explicit version bump
- field names will not be renamed silently
- field types will not change silently
- schema validation failures are treated as regressions

Breaking changes to the response contract must not be introduced in a patch or minor release without an explicit contract versioning decision.

## Official Response Structure

The normalized response payload has this shape:

```json
{
  "prompt": "Hello world",
  "response": "Echo: Hello world",
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

## Field Reference

### `prompt`

Original prompt string provided by the caller.

Type:
- `string`

### `response`

Raw textual response returned by the selected provider implementation.

Type:
- `string`

### `metadata`

Object containing stable output metadata.

Type:
- `object`

Required fields:
- `provider`
- `timestamp_utc`

Optional fields:
- `execution_ms`
- `model`
- `execution_context`
- `usage`

### `metadata.provider`

Identifier of the provider implementation used to generate the response.

Type:
- `string`

Examples:
- `http`
- `fake`
- `mock`

### `metadata.timestamp_utc`

UTC timestamp describing when the normalized response payload was created.

Type:
- `string`

Format:
- RFC 3339 / JSON Schema `date-time`

Example:
- `2026-02-18T13:43:51.236575+00:00`

### `metadata.execution_ms`

Execution duration measured by the runner in milliseconds.

Type:
- `integer`

Constraints:
- must be greater than or equal to `0`

### `metadata.model`

Provider model metadata attached by the runner.

Type:
- `string`

Resolution behavior:
- prefers provider-reported resolved model when available
- otherwise falls back to requested model from provider config

### `metadata.execution_context`

Execution provenance snapshot assembled by the runner for reproducibility and auditability.

Type:
- `object`

Required keys when present:
- `provider_protocol`
- `api_endpoint`
- `model_requested`
- `model_resolved`
- `runner_version`
- `prompt_hash`
- `runtime`

Field notes:
- `provider_protocol`, `api_endpoint`, `model_requested`, `model_resolved` may be `null`
- `runner_version` is resolved from installed package metadata
- `prompt_hash` is `sha256:` prefixed lowercase hex digest of the effective prompt sent to the provider

### `metadata.execution_context.runtime`

Resolved runtime snapshot captured at execution time.

Type:
- `object`

Required keys:
- `stream` (`boolean`)
- `system_prompt_provided` (`boolean`)
- `temperature` (`number|null`)
- `max_tokens` (`integer|null`)
- `top_p` (`number|null`)
- `timeout_seconds` (`integer|null`)
- `max_retries` (`integer|null`)

### `metadata.usage`

Optional normalized token usage object captured from providers when available.

Type:
- `object`

Known fields:
- `prompt_tokens` (`integer`, optional)
- `completion_tokens` (`integer`, optional)
- `total_tokens` (`integer`, optional)

Notes:
- `usage` may be absent when upstream providers do not expose token counters.
- when present, usage fields are normalized to provider-agnostic names.

## Validation Model

The contract is validated through two layers:

1. Runtime validation in [`src/ai_prompt_runner/core/validators.py`](../src/ai_prompt_runner/core/validators.py)
2. Schema validation in automated tests using [`schemas/response.schema.json`](../schemas/response.schema.json)

This dual approach keeps runtime behavior explicit while also freezing the contract through a standard schema artifact.

## Backward Compatibility Policy

Backward compatibility is validated with historical JSON fixtures stored under [`tests/fixtures/`](../tests/fixtures/).

These fixtures represent payloads compatible with previous releases and are validated against the current schema in automated tests.

This means:

- previously valid payloads should remain schema-compatible
- accidental renames or structural drift should fail tests
- contract changes require deliberate review and versioning

## CI Enforcement

Schema validation is enforced through the normal test suite executed in CI.

Any change that breaks:

- current schema conformance
- historical fixture compatibility

will fail CI and must be treated as a contract regression unless accompanied by an explicit versioning decision.
