# Testing

## Purpose

This document describes the testing strategy used in `ai-prompt-runner`.

The project treats testing as part of its architecture, not only as a correctness afterthought.

The goal is to protect:

- runtime behavior
- provider contracts
- output contract stability
- backward compatibility
- release confidence

## Test Suite Structure

The test suite is organized under [`tests/`](../tests):

- [`tests/unit/`](../tests/unit): unit, contract, and schema-focused tests
- [`tests/e2e/`](../tests/e2e): end-to-end CLI workflow tests
- [`tests/fixtures/`](../tests/fixtures): historical payload fixtures used for compatibility validation

## Unit Tests

Unit tests validate isolated parts of the system, including:

- payload validation
- runner behavior
- provider factory behavior
- HTTP provider behavior
- provider contract behavior
- output schema validation

These tests are intended to fail fast and isolate regressions close to their source.

## End-to-End Tests

End-to-end tests validate the CLI workflow from input parsing to output persistence.

They cover behavior such as:

- CLI argument handling
- provider wiring
- prompt input modes
- output file generation
- error path handling

External API calls must remain mocked in this test layer.

## Provider Contract Tests

Provider implementations are validated through reusable contract tests.

These tests ensure that official providers:

- accept a prompt string
- return response text on success
- raise provider-domain errors on failure

This protects the abstraction defined in [`src/services/base.py`](../src/services/base.py).

## Output Contract and Schema Tests

The response payload is protected by two complementary layers:

1. runtime validation in [`src/core/validators.py`](../src/core/validators.py)
2. schema validation against [`schemas/response.schema.json`](../schemas/response.schema.json)

Schema tests validate:

- current payload conformance
- negative contract cases
- unexpected field rejection
- timestamp format validation

## Backward Compatibility Fixtures

Historical payload fixtures under [`tests/fixtures/`](../tests/fixtures) are validated against the current response schema.

These fixtures ensure that:

- previously valid payloads remain compatible
- silent contract drift is detected
- schema changes require deliberate versioning decisions

## Coverage and CI Gates

The project enforces a coverage threshold in CI:

- `--cov-fail-under=95`

CI also validates:

- linting
- package build generation
- build artifact presence
- full test suite execution

This keeps the test suite tied to release quality rather than local convenience only.

## Local Validation Commands

Primary local validation commands:

```bash
python3 -m pytest
python3 -m pytest --cov=src --cov-report=term-missing --cov-fail-under=95
ruff check .
python3 -m build
```

If the `uv` workflow is being used:

```bash
uv run pytest
uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=95
uv run ruff check .
uv run python3 -m build
```

## Quality Philosophy

`ai-prompt-runner` aims for a test strategy that is:

- contract-aware
- regression-resistant
- deterministic
- CI-enforced

The project favors explicit tests for architecture boundaries and stable contracts over broad but shallow test quantity.
