# Architecture

## Purpose

This document describes the stable architectural boundaries of `ai-prompt-runner`.

The project is intentionally designed as a stateless execution layer:

`1 input -> 1 API call -> 1 structured output`

It does not manage conversational state, orchestration, agents, tool calling, multi-step workflows, or memory persistence.

## Layer Overview

The repository is organized around clear separation of concerns:

- [`src/ai_prompt_runner/cli.py`](../src/ai_prompt_runner/cli.py): argument parsing, process-level I/O, exit codes, and runtime wiring
- [`src/ai_prompt_runner/core/`](../src/ai_prompt_runner/core): business logic, domain models, and payload validation
- [`src/ai_prompt_runner/services/`](../src/ai_prompt_runner/services): provider abstractions and provider implementations
- [`src/ai_prompt_runner/utils/`](../src/ai_prompt_runner/utils): filesystem output helpers
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

- [`src/ai_prompt_runner/core/models.py`](../src/ai_prompt_runner/core/models.py): request and response domain models
- [`src/ai_prompt_runner/core/runner.py`](../src/ai_prompt_runner/core/runner.py): stateless prompt execution orchestration
- [`src/ai_prompt_runner/core/validators.py`](../src/ai_prompt_runner/core/validators.py): normalized payload validation
- [`src/ai_prompt_runner/core/errors.py`](../src/ai_prompt_runner/core/errors.py): project-level error hierarchy

The runner assumes a provider implementation that conforms to the provider contract and returns response text for a single prompt execution.

Runtime metadata is also produced in the core layer:

- `execution_ms` is measured in the runner for each execution
- optional normalized `usage` is read from providers through the provider contract hook

## Provider Contract

The provider layer is built around [`src/ai_prompt_runner/services/base.py`](../src/ai_prompt_runner/services/base.py).

Stable contract:

- providers accept a user prompt string and optional one-shot `system_prompt`
- providers accept optional runtime controls via `generation_config`
- providers return a response string on success through `generate(prompt, system_prompt=None, generation_config=None)`
- providers may optionally support chunk streaming through `generate_stream(prompt, system_prompt=None, generation_config=None)`
- providers may expose optional normalized usage via `get_last_usage()`
- providers raise provider-domain errors on failure

Streaming behavior is intentionally optional at provider level. The runner keeps deterministic behavior by:

- using stream mode only when requested
- falling back to `generate()` when a provider does not support streaming
- reconstructing a final full response payload from emitted chunks

The provider abstraction is validated by reusable contract tests.

Current provider implementations:

- [`src/ai_prompt_runner/services/http_provider.py`](../src/ai_prompt_runner/services/http_provider.py): legacy generic JSON-over-HTTP provider
- [`src/ai_prompt_runner/services/openai_compatible_provider.py`](../src/ai_prompt_runner/services/openai_compatible_provider.py): protocol provider for OpenAI-compatible APIs
- [`src/ai_prompt_runner/services/anthropic_provider.py`](../src/ai_prompt_runner/services/anthropic_provider.py): protocol provider for Anthropic Messages API
- [`src/ai_prompt_runner/services/google_provider.py`](../src/ai_prompt_runner/services/google_provider.py): protocol provider for Gemini generateContent API
- [`src/ai_prompt_runner/services/mock_provider.py`](../src/ai_prompt_runner/services/mock_provider.py): deterministic no-network provider used for contract validation and stable testing

Provider creation and runtime configuration are centralized in [`src/ai_prompt_runner/services/provider_factory.py`](../src/ai_prompt_runner/services/provider_factory.py).

### Protocol Mapping

Provider selection is protocol-first, with aliases mapped through the registry:

- OpenAI-compatible protocol: `openai_compatible`, `openai`, `openrouter`, `groq`, `together`, `fireworks`, `perplexity`, `inception`, `x`, `xai`, `lmstudio`, `ollama`
- Anthropic Messages protocol: `anthropic`
- Gemini generateContent protocol: `google`
- Legacy generic HTTP protocol: `http`

### Capability Contract and Safety Validation

The provider registry also carries a capability matrix per provider:

- `stream`
- `system`
- `usage`
- `temperature`
- `top_p`
- `max_tokens`
- `tools` (reserved for future checks; currently unsupported)

Each capability uses a tri-state contract:

- `supported`
- `unsupported`
- `unknown`

The CLI evaluates requested runtime options against this matrix before execution.

Safety behavior:

- permissive mode (default): capability mismatches emit warnings and execution continues
- strict mode (`--strict-capabilities`): mismatches are blocking runtime errors

Preflight behavior:

- `--dry-run` validates config resolution and capabilities without provider generation
- `--print-effective-config` emits masked, resolved runtime diagnostics for CI/ops debugging

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
    "timestamp_utc": "string",
    "execution_ms": 123,
    "usage": {
      "prompt_tokens": 42,
      "completion_tokens": 84,
      "total_tokens": 126
    }
  }
}
```

Contract details:

- `metadata.provider` and `metadata.timestamp_utc` are required
- `metadata.execution_ms` is included for successful runs
- `metadata.usage` is optional and appears only when provider usage metrics are available

This contract is protected by:

- runtime validation
- schema-based validation
- backward compatibility fixtures

## Configuration Precedence

Runtime configuration follows a deterministic precedence model:

`CLI > environment variables > TOML config > built-in defaults`

This precedence is applied in [`src/ai_prompt_runner/cli.py`](../src/ai_prompt_runner/cli.py) before provider construction.

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

In stream mode, the architecture remains stateless: chunks are rendered to stdout for UX, then normalized into a single final response payload.

The `--system` input remains single-execution context only; it does not create message history or conversational state.

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
