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
    "provider": "http",
    "timestamp_utc": "2026-02-18T13:43:51.236575+00:00"
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

## Validation Model

The contract is validated through two layers:

1. Runtime validation in [`src/core/validators.py`](../src/core/validators.py)
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
