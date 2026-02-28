# Migration Notes

## Purpose

This document summarizes the major compatibility-relevant changes introduced across recent version lines.

It is intended to help maintainers and reviewers understand what became stable, what changed, and which version lines established important project contracts.

## v0.1.x

### Foundation

`v0.1.x` established the initial architectural and process baseline of the project.

Key changes:

- initial modular CLI implementation
- HTTP provider integration
- JSON and Markdown output generation
- unit and end-to-end tests
- CI workflow introduction
- semantic versioning, README, and changelog baseline

Compatibility note:

- this line created the initial CLI surface and output structure that later releases progressively hardened

## v0.2.x

### Runtime Robustness

`v0.2.x` focused on safer runtime behavior and clearer failure handling.

Key changes:

- configurable timeout support
- configurable retry logic
- improved HTTP error classification
- stronger CLI input validation
- version synchronization with project metadata

Compatibility note:

- runtime behavior became more predictable without changing the overall CLI purpose or output model

## v0.3.x

### Test Hardening

`v0.3.x` strengthened the reliability of the test suite and increased coverage.

Key changes:

- broader edge-case coverage
- more stable mocking strategy
- stronger validation of failure scenarios

Compatibility note:

- this line primarily improved confidence in existing behavior rather than expanding runtime features

## v0.4.x

### CLI UX Improvements

`v0.4.x` improved the usability of prompt input and command-line feedback.

Key changes:

- `--prompt-file` support
- stdin prompt support
- explicit exit code documentation
- clearer CLI help output

Compatibility note:

- input modes became more flexible while preserving the single-execution stateless design

## v0.5.x

### Configuration Layer

`v0.5.x` introduced the formal runtime configuration layer.

Key changes:

- optional TOML configuration file support
- deterministic configuration precedence
- config validation for unsupported keys and invalid TOML

Stable rule introduced in this line:

`CLI > environment variables > TOML config > built-in defaults`

Important compatibility note:

- `api_key` remained intentionally unsupported in TOML files

## v0.6.x

### Provider Extensibility Stabilization

`v0.6.x` formalized the provider abstraction without expanding runtime scope.

Key changes:

- explicit `BaseProvider` contract
- official `MockProvider`
- reusable provider contract tests
- shared success and failure contract validation

Compatibility note:

- the runtime provider factory remained intentionally conservative
- `HTTPProvider` remained the primary runtime provider path

## v0.7.x

### Output Contract Freeze

`v0.7.x` turned the normalized JSON response into a formally frozen contract.

Key changes:

- official JSON schema under [`schemas/response.schema.json`](../schemas/response.schema.json)
- schema-based payload validation tests
- backward compatibility fixtures for historical payloads
- versioned documentation in [`docs/output-contract.md`](./output-contract.md)

Compatibility note:

- the payload structure was formalized rather than redesigned
- output drift became a contract regression rather than an informal test failure

## v0.8.x

### CI and Workflow Hardening

`v0.8.x` focused on packaging reliability and development workflow consistency.

Key changes:

- CI package build verification
- CI coverage gate (`95%`)
- explicit Ruff project settings
- `uv` development workflow support
- release checklist documentation

Compatibility note:

- no CLI or output contract changes were introduced
- this line strengthened project reliability rather than runtime surface area

## Migration Guidance

When moving between these version lines:

- review the changelog before release preparation
- validate the output contract against the current schema
- verify CLI and provider behavior with the current test suite
- confirm versioned release notes and documentation remain aligned

## Non-Goals

These migration notes do not document:

- experimental branches
- abandoned spikes
- unmerged workflow experiments

Only versioned, merged project lines that affected stable project behavior or process are summarized here.
