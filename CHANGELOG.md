# Changelog

All notable changes to this project are documented in this file.

## [v0.6.1] - 2026-02-28

### Changed
- Clarified the README design philosophy to emphasize the project's stateless execution
model and architectural boundaries.
- Documented the provider contract architecture, including reusable contract tests and the
role of `MockProvider` in deterministic validation.

### Notes
- `v0.6.1` is a documentation-only patch release.
- No runtime behavior, CLI interface, or provider selection logic changed.

## [v0.6.0] - 2026-02-28

### Added
- Added `MockProvider` as an official deterministic provider implementation for
architecture validation and local tests.
- Added reusable provider contract tests covering shared success and failure behavior.

### Changed
- Formalized the `BaseProvider` contract documentation for stable multi-provider support.

### Notes
- `HTTPProvider` remains the only runtime provider exposed by the factory in `v0.6.0`.
- This release focuses on provider abstraction stability without expanding CLI or runtime
features.

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
- Restored `ai-prompt-runner` console script usability in editable installs by configuring setuptools package discovery
for `src*`.

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
  - `python3 -m src.cli ...` (module fallback)

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
