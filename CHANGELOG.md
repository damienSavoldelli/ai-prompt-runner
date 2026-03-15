# Changelog

All notable changes to this project are documented in this file.

## [v1.7.1] - 2026-03-15

### Added

- Added CI artifact smoke-install validation for both wheel and sdist build outputs.
- Added end-to-end taxonomy audit tests to verify normalized runtime error codes in `error.json`.
- Added an operations runbook: `docs/ops-runbook.md` with error-code triage guidance and CI incident procedures.

### Changed

- Hardened run-log sanitization to redact runtime secrets from `error.json` message payloads.
- Extended E2E log checks to enforce:
    - no raw API key leakage in `request.json` / `error.json`
    - masked `effective_config.provider.api_key`
    - prompt not persisted in clear text (hash-only logging)
- Linked runbook guidance from `README.md` and `docs/release-checklist.md`.

### Notes

- `v1.7.1` is a hardening and operations-readiness patch release.
- No CLI interface changes.
- No output schema/contract changes.
- Stateless execution architecture remains unchanged.

## [v1.7.0] - 2026-03-15

### Added

- Added core runtime error taxonomy normalization with stable codes:
    - `auth_error`
    - `rate_limit`
    - `timeout`
    - `invalid_request`
    - `network_error`
    - `provider_error`
- Added per-run observability artifact support via `--log-run-dir`:
    - `request.json` (sanitized diagnostics)
    - `response.json` on success
    - `error.json` on runtime failure
- Added structured error payload generation for runtime failures using normalized taxonomy.

### Changed

- Extended runtime config support to include `log_run_dir` in TOML/CLI resolution.
- Updated documentation for v1.7 observability features:
    - `README.md`
    - `docs/cli-reference.md`
    - `docs/architecture.md`
    - `docs/configuration.md`
- Expanded unit and E2E coverage for error taxonomy classification and run-log artifact behavior.

### Notes

- `v1.7.0` is a stable observability release focused on CI/ops diagnostics.
- No CLI breaking changes.
- No output contract/schema breaking changes.
- Stateless execution architecture remains unchanged.

## [v1.6.2] - 2026-03-15

### Changed

- Removed `tools` from the provider capability matrix to keep the capability contract aligned with currently supported runtime features.
- Cleaned related capability assertions and documentation references.

### Notes

- `v1.6.2` is a patch cleanup release.
- No CLI behavior changes.
- No provider execution behavior changes.
- No output contract/schema changes.

## [v1.6.1] - 2026-03-15

### Changed

- Updated package metadata license declaration to modern PEP 621 style:
    - `license = "MIT"`
    - `license-files = ["LICENSE"]`
- Removed deprecated license classifier from `classifiers` to eliminate setuptools deprecation warnings during build.

### Notes

- `v1.6.1` is a packaging metadata maintenance release.
- No runtime behavior changes.
- No CLI, provider, or output contract changes.

## [v1.6.0] - 2026-03-15

### Added

- Added execution provenance metadata to normalized payloads:
    - `metadata.model`
    - `metadata.execution_context`
    - `metadata.execution_context.runtime`
- Added provenance context fields:
    - `provider_protocol`
    - `api_endpoint`
    - `model_requested`
    - `model_resolved`
    - `runner_version`
    - `prompt_hash` (`sha256:<hex>`)
    - runtime snapshot (`stream`, `system_prompt_provided`, controls, timeout, retries)
- Added provider contract hook for resolved model capture (`get_last_model_resolved`).
- Added schema and runtime validator support for the new additive provenance fields.

### Changed

- Updated runner metadata assembly to compute provenance centrally from request, provider config, and provider-reported metadata.
- Updated protocol providers to capture resolved model metadata when upstream responses expose it.
- Expanded unit/schema coverage for provenance serialization, validation, and runner error-path guards.

### Notes

- `v1.6.0` is a stable feature release focused on reproducibility and traceability.
- No CLI breaking changes.
- No output contract breaking changes (additive metadata only).
- Stateless execution architecture remains unchanged.

## [v1.5.0] - 2026-03-15

### Added

- Added provider capability contracts in the registry with tri-state feature support:
    - `supported`
    - `unsupported`
    - `unknown`
- Added CLI safety and diagnostics flags:
    - `--strict-capabilities`
    - `--dry-run`
    - `--print-effective-config`
- Added capability validation before execution with strict/permissive behavior controls.
- Added dry-run preflight mode to validate resolved provider/runtime configuration without generation.
- Added effective configuration diagnostics output with masked API key handling.
- Added capability coverage for stream/system/usage/runtime controls and reserved `tools` capability metadata.

### Changed

- Updated runtime validation flow to check provider capability compatibility before provider execution.
- Kept default behavior permissive (warning + continue) and introduced strict mode for fail-fast validation.
- Extended tests for capability contracts, strict/permissive safety behavior, dry-run flow, and effective-config diagnostics.
- Updated technical documentation for v1.5 safety modes across README and docs.

### Notes

- `v1.5.0` is a stable feature release focused on execution safety and operator diagnostics.
- No CLI breaking changes.
- No output JSON schema/contract breaking changes.
- Stateless execution architecture remains unchanged.

## [v1.4.0] - 2026-03-15

### Added

- Added runtime generation controls:
    - `--temperature`
    - `--max-tokens`
    - `--top-p`
- Added optional runtime controls to TOML config (`temperature`, `max_tokens`, `top_p`) with CLI precedence unchanged.
- Added execution metadata to normalized JSON payload:
    - `metadata.execution_ms`
    - optional `metadata.usage` with normalized token counters
- Added provider usage hook in the provider contract (`get_last_usage`) for optional token accounting.
- Added provider-level runtime control mapping and usage normalization across:
    - OpenAI-compatible protocol provider
    - Anthropic Messages provider
    - Google Gemini provider

### Changed

- Updated runner orchestration to forward optional generation controls in both non-stream and stream execution paths.
- Updated JSON schema and runtime validators to support additive metadata fields (`execution_ms`, `usage`) without breaking existing contract keys.
- Expanded test coverage for runtime controls, usage extraction, stream/non-stream invariants, and metadata validation paths.
- Updated technical documentation to reflect v1.4 runtime controls and metadata behavior.

### Notes

- `v1.4.0` is a stable feature release focused on observability and runtime control.
- No CLI breaking changes.
- No stateless-execution boundary changes.

## [v1.3.0] - 2026-03-15

### Added

- Added optional CLI flag `--system` to pass one-shot instruction context alongside `--prompt`.
- Added `system_prompt` support to the execution contract:
    - `PromptRequest.system_prompt`
    - `BaseProvider.generate(prompt, system_prompt=None)`
    - `BaseProvider.generate_stream(prompt, system_prompt=None)`
- Added provider-level system prompt handling:
    - OpenAI-compatible providers use a role-aware `system` message
    - Anthropic provider uses the `system` payload field
    - Google provider uses `systemInstruction`
    - HTTP and Mock providers use deterministic fallback prompt composition
- Added targeted unit and E2E tests for system prompt forwarding and provider branch coverage.

### Changed

- Updated runner orchestration to forward `system_prompt` in both standard and stream execution paths.
- Kept stream and non-stream final artifact behavior deterministic and contract-compatible.

### Notes

- `v1.3.0` is a stable feature release focused on structured one-shot prompt control.
- No output JSON schema/contract changes.
- No CLI breaking changes.

## [v1.2.1] - 2026-03-15

### Added

- Added a runner invariant test ensuring stream and non-stream execution produce equivalent final payloads (excluding runtime timestamp differences).

### Changed

- Strengthened regression protection for artifact determinism in stream mode without changing runtime behavior.

### Notes

- `v1.2.1` is a patch release focused on test hardening.
- No CLI, provider implementation, or output schema changes.

## [v1.2.0] - 2026-03-15

### Added

- Added provider streaming contract support through `generate_stream(prompt)` with explicit fallback semantics.
- Added CLI stream mode via `--stream` for progressive chunk rendering on stdout.
- Added streaming implementations for:
    - OpenAI-compatible protocol provider
    - Anthropic Messages protocol provider
    - Google Gemini protocol provider
    - MockProvider (deterministic test stream)
- Added comprehensive streaming coverage across:
    - provider unit tests (nominal, retries, malformed events, protocol errors)
    - provider contract tests
    - runner/CLI stream behavior tests

### Changed

- Preserved deterministic final artifact behavior: stream mode still writes complete JSON and Markdown outputs after full response assembly.
- Updated technical documentation for streaming behavior and provider support:
    - README
    - docs/cli-reference.md
    - docs/architecture.md
    - docs/configuration.md

### Notes

- `v1.2.0` improves runtime execution feedback without changing architectural boundaries.
- No output JSON schema/contract changes.
- No CLI breaking changes.

## [v1.1.0] - 2026-03-06

### Added

- Added protocol-level provider implementations:
    - AnthropicProvider (Anthropic Messages API)
    - GoogleProvider (Gemini generateContent API)
- Added provider registry aliases for:
    - x
    - xai
    - ollama
- Added comprehensive provider protocol test suites:
    - tests/unit/test_anthropic_provider.py
    - tests/unit/test_google_provider.py
- Extended provider factory and contract tests for new providers and aliases.

### Changed

- Extended provider registry defaults for protocol routing and alias resolution.
- Maintained thin factory design (create_provider remains registry-driven with no provider-
  specific branching).
- Updated documentation to reflect v1.1 provider support:
    - README provider matrix and usage examples
    - CLI reference provider coverage
    - architecture protocol mapping
    - configuration examples for anthropic, google, and ollama
- Updated README repository-file links to absolute GitHub URLs for PyPI-safe rendering.

### Notes

- v1.1.0 expands provider coverage while preserving the stateless execution model.
- No output JSON schema/contract changes.
- No orchestration, memory, or multi-step workflow behavior introduced.

## [v1.0.1] - 2026-03-01

### Added
- Added public PyPI packaging metadata, including README-based project description, project
URLs, classifiers, keywords, and license declaration.
- Added `twine` to the development workflow to validate publishable distribution artifacts.
- Added PyPI installation instructions and badge to the README.

### Changed
- Aligned the public Python package namespace with `ai_prompt_runner` for cleaner
distribution and import behavior.
- Updated the console entrypoint and module execution path to use `ai_prompt_runner.cli`.
- Improved distribution readiness for public package publication without changing runtime
behavior or stable contracts.

### Notes
- `v1.0.1` activates public distribution readiness for PyPI.
- No CLI interface, provider contract, or output contract changes were introduced.

## [v1.0.0] - 2026-02-28

### Added
- Added complete technical documentation covering architecture, CLI reference,
configuration, testing, migration history, output contract, and release workflow.
- Added formal output contract schema validation and backward compatibility fixtures.
- Added reusable provider contract tests with an official deterministic `MockProvider`.
- Added package build verification, CI coverage enforcement, and a documented `uv`development workflow.

### Changed
- Stabilized the CLI as a stateless execution layer with documented configuration precedence and clear exit-code behavior.
- Formalized the provider abstraction and the JSON output contract as stable project interfaces.
- Hardened CI, packaging, and release discipline for production-ready validation.

### Notes
- `v1.0.0` marks the first stable release of `ai-prompt-runner`.
- The project is now positioned as a stable, extensible, stateless AI CLI with versioned output contracts and reproducible validation workflows.
- Streaming, orchestration, agents, memory, and higher-level workflow behavior remain intentionally out of scope.

## [v0.9.0] - 2026-02-28

### Added
- Added `docs/architecture.md` to formalize the repository structure, architectural boundaries, and stateless execution model.
- Added `docs/cli-reference.md` to document the CLI interface, prompt input modes, arguments, and exit codes.
- Added `docs/configuration.md` to document configuration sources, precedence, supported TOML keys, and secret-handling expectations.
- Added `docs/testing.md` to document the test strategy, contract validation layers, and CI quality gates.
- Added `docs/migration.md` to summarize compatibility-relevant project evolution from `v0.1.x` through `v0.8.x`.

### Changed
- Updated `README.md` to reference the technical documentation set under `docs/`.
- Aligned the documented project structure with the current repository layout. 
- Consolidated the documentation baseline for the release-candidate phase. 

### Notes
- `v0.9.0` is the release-candidate documentation consolidation milestone.
- No CLI interface, provider contract, or output contract changes were introduced.

## [v0.8.0] - 2026-02-28

### Added
- Added package build verification in CI using `python3 -m build`.
- Added coverage enforcement in CI with `--cov-fail-under=95`.
- Added `uv` development workflow support with declared development dependencies and `uv.lock`.
- Added a versioned release checklist in `docs/release-checklist.md`.

### Changed
- Hardened the CI workflow to validate lint, build artifacts, and coverage gates.
- Declared explicit Ruff project settings in `pyproject.toml`.
- Updated the README to document the `uv` workflow, CI expectations, and release checklist.

### Notes
- `v0.8.0` focuses on CI hardening, packaging reliability, and development workflow modernization.
- Docker exploration was intentionally deferred and is not part of this release.

## [v0.7.0] - 2026-02-28

### Added
- Added `schemas/response.schema.json` to formalize the official JSON output contract.
- Added schema-based contract tests for current response payload validation.
- Added backward compatibility fixtures and schema compatibility tests for historical payloads.
- Added `docs/output-contract.md` to document the response structure, stability guarantees, and compatibility policy.

### Changed
- Updated `README.md` to reference the formal output contract documentation.
- Added `jsonschema` support to validate the output contract in automated tests.

### Notes
- `v0.7.0` freezes the JSON output contract as a stable interface.
- No CLI interface or provider runtime behavior changed.

## [v0.6.1] - 2026-02-28

### Changed
- Clarified the README design philosophy to emphasize the project's stateless execution model and architectural boundaries.
- Documented the provider contract architecture, including reusable contract tests and the role of `MockProvider` in deterministic validation.

### Notes
- `v0.6.1` is a documentation-only patch release.
- No runtime behavior, CLI interface, or provider selection logic changed.

## [v0.6.0] - 2026-02-28

### Added
- Added `MockProvider` as an official deterministic provider implementation for architecture validation and local tests.
- Added reusable provider contract tests covering shared success and failure behavior.

### Changed
- Formalized the `BaseProvider` contract documentation for stable multi-provider support.

### Notes
- `HTTPProvider` remains the only runtime provider exposed by the factory in `v0.6.0`.
- This release focuses on provider abstraction stability without expanding CLI or runtime features.

## [v0.5.0] - 2026-02-24

### Added
- Added optional TOML config file support via `--config` for non-sensitive runtime defaults.
- Added config validation for file access errors, invalid TOML, invalid section type, and unsupported keys.
- Added `config.example.toml` with a safe starter configuration (no secrets).
- Added CLI and E2E tests covering config parsing, precedence, and validation edge cases.

### Changed
- Introduced explicit configuration precedence: `CLI > environment variables > TOML config > built-in defaults`.
- Improved README documentation for config usage, precedence, and security guidance.

### Notes
- `api_key` is intentionally not supported in TOML config in `v0.5.x`; use `AI_API_KEY` or `--api-key`.
- Configuration layer release focused on safe defaults and predictable override behavior.

## [v0.4.0] - 2026-02-24

### Added
- Added `--prompt-file` support to load prompt text from a UTF-8 file.
- Added stdin prompt fallback when no `--prompt` / `--prompt-file` is provided.
- Added CLI examples and exit code documentation in `--help`.
- Added README coverage command documentation (`pytest-cov` and HTML report).

### Changed
- Improved CLI prompt input UX with explicit source priority (`--prompt` > `--prompt-file` > piped stdin).
- Improved CLI help text with clearer prompt-source guidance and usage examples.
- Introduced named CLI exit code constants for clearer process-level behavior.

### Notes
- CLI UX release focused on prompt input ergonomics and user-facing help clarity.

## [v0.3.2] - 2026-02-23

### Fixed
- Restored `ai-prompt-runner` console script usability in editable installs by configuring setuptools package discovery for `src*`.

### Notes
- Patch release for packaging/entrypoint reliability in local development environments.
- No runtime behavior changes.

## [v0.3.1] - 2026-02-22

### Fixed
- Removed a duplicated CLI E2E test definition in `tests/e2e/test_cli.py` that caused CI lint failure (`ruff` F811).

### Notes
- Patch release to restore CI health for the v0.3.x test hardening release line.
- No runtime behavior changes.

## [v0.3.0] - 2026-02-22

### Added
- Added edge-case tests for HTTP provider bad responses (invalid JSON, invalid `response` type, unmapped 4xx).
- Added validator contract tests for missing metadata keys and invalid field types.
- Added CLI error-path tests for provider configuration errors and runner failures.
- Added CLI helper/validator tests for version fallback and argument parsing validation.

### Changed
- Hardened test suite mocking strategy with deterministic monkeypatch-based doubles for CLI and provider paths.
- Increased overall test coverage to 99% (`src/`), with 100% coverage on `http_provider` and `validators`.

### Notes
- Test hardening release focused on edge-case reliability and stable test behavior.

## [v0.2.0] - 2026-02-22

### Added
- Configurable HTTP timeout and retry support (`--timeout`, `--retries`) with provider/factory wiring.
- Provider factory validation for retry configuration (`max_retries >= 0`).

### Changed
- Improved HTTP provider error mapping by classifying failures by HTTP status code.
- Strengthened CLI input validation for prompt text, API endpoint URL, timeout, and retries.
- CLI `--version` now resolves package metadata version (aligned with release metadata).

### Notes
- Runtime robustness release focused on safer failure handling and input validation.

## [v0.1.2] - 2026-02-18

### Changed
- Updated `README.md` to document both CLI invocation modes consistently:
  - `ai-prompt-runner ...` (console script)
  - `python3 -m ai_prompt_runner.cli ...` (module fallback)

### Notes
- Documentation-only patch release.
- No runtime behavior changes.

## [v0.1.1] - 2026-02-18

### Changed
- Added console script entrypoint in `pyproject.toml`:
  - `ai-prompt-runner = "src.cli:main"`

### Notes
- Patch release focused on packaging usability.
- No breaking changes.

## [v0.1.0] - 2026-02-18

### Added
- Initial modular CLI architecture under `src/` (`cli`, `core`, `services`, `utils`).
- Core runner, domain models, and structured error handling.
- HTTP provider implementation using `requests`.
- Environment variable support (`.env`) with safe CLI help previews.
- JSON and Markdown output persistence helpers.
- Response payload contract validation.
- Unit tests and end-to-end CLI test coverage.
- GitHub Actions CI workflow (lint + tests).
- Project documentation baseline in `README.md`.

### Notes
- First stable public baseline for the project.
