# Changelog

All notable changes to this project are documented in this file.

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
