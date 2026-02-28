# Architecture

## Purpose

This document describes the stable architectural boundaries of `ai-prompt-runner`.

The project is intentionally designed as a stateless execution layer:

`1 input -> 1 API call -> 1 structured output`

It does not manage conversational state, orchestration, agents, tool calling, multi-step workflows, or memory persistence.

## Layer Overview

The repository is organized around clear separation of concerns:

- [`src/cli.py`](../src/cli.py): argument parsing, process-level I/O, exit codes, and runtime wiring
- [`src/core/`](../src/core): business logic, domain models, and payload validation
- [`src/services/`](../src/services): provider abstractions and provider implementations
- [`src/utils/`](../src/utils): filesystem output helpers
- [`tests/`](../tests): unit, contract, schema, compatibility, and end-to-end validation
- [`schemas/`](../schemas): formal JSON output contract
- [`docs/`](../docs): versioned technical documentation

## CLI Boundary

The CLI layer is responsible for:

- parsing command-line arguments
- loading environment variables and optional config
- applying configuration precedence
- constructing the selected provider
- invoking the runner
- writing JSON and Markdown outputs
- returning stable exit codes

The CLI layer must not contain business logic or provider-specific request logic.

## Core Boundary

The core layer contains the stable execution logic:

- [`src/core/models.py`](../src/core/models.py): request and response domain models
- [`src/core/runner.py`](../src/core/runner.py): stateless prompt execution orchestration
- [`src/core/validators.py`](../src/core/validators.py): normalized payload validation
- [`src/core/errors.py`](../src/core/errors.py): project-level error hierarchy

The runner assumes a provider implementation that conforms to the provider contract and returns response text for a single prompt execution.

## Provider Contract

The provider layer is built around [`src/services/base.py`](../src/services/base.py).

Stable contract:

- providers accept a full prompt string
- providers return a response string on success
- providers raise provider-domain errors on failure

The provider abstraction is validated by reusable contract tests.

Current provider implementations:

- [`src/services/http_provider.py`](../src/services/http_provider.py): real HTTP-backed provider
- [`src/services/mock_provider.py`](../src/services/mock_provider.py): deterministic no-network provider used for contract validation and stable testing

Provider creation and runtime configuration are centralized in [`src/services/provider_factory.py`](../src/services/provider_factory.py).

## Output Contract

The JSON output contract is formally frozen and described in:

- [`schemas/response.schema.json`](../schemas/response.schema.json)
- [`docs/output-contract.md`](./output-contract.md)

The normalized payload shape is:

```json
{
  "prompt": "string",
  "response": "string",
  "metadata": {
    "provider": "string",
    "timestamp_utc": "string"
  }
}
```

This contract is protected by:

- runtime validation
- schema-based validation
- backward compatibility fixtures

## Configuration Precedence

Runtime configuration follows a deterministic precedence model:

`CLI > environment variables > TOML config > built-in defaults`

This precedence is applied in [`src/cli.py`](../src/cli.py) before provider construction.

Important constraint:

- secrets must not be stored in the TOML config file
- `api_key` is intentionally excluded from TOML support

## Stateless Execution Model

Each run is independent.

The project does not maintain:

- session memory
- message history
- agent state
- workflow state

This keeps behavior deterministic and makes the CLI easier to validate, package, and integrate into downstream automation.

## Validation and Quality Boundaries

Project robustness is enforced through:

- unit tests
- end-to-end CLI tests
- provider contract tests
- schema validation tests
- backward compatibility fixtures
- linting and coverage gates in CI
- package build verification in CI

## Architectural Non-Goals

The following concerns are intentionally out of scope for this project:

- conversational state management
- orchestration logic
- tool calling
- multi-step execution workflows
- long-lived agent behavior
- memory persistence

These higher-level concerns belong to a dedicated LLM framework layer, not to `ai-prompt-runner`.
