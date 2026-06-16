# AI Prompt Runner – Agent Guidelines

This document defines strict rules and architectural conventions for AI agents (Codex, etc.) working on this repository.

---

# Agent Behavior Rules

The agent MUST:

- Never regenerate entire files without reason
- Propose diff-style changes
- Respect architecture boundaries
- Add tests when modifying core logic
- Keep code modular

The agent MUST NOT:

- Refactor unrelated files
- Modify CI without request
- Introduce unnecessary dependencies
- Break version compatibility

---

# Environment Setup

## Bootstrap

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

```bash
export AI_API_KEY="your-api-key-here"       # required
export AI_API_ENDPOINT="https://..."         # required
export AI_API_MODEL="model-name"             # optional
```

Never hardcode these values. Always load from environment.

---

# Core Commands

## Run CLI
python3 -m ai_prompt_runner.cli --prompt "Your text here"

## Run Tests
pytest

## Run Specific Test File
pytest tests/unit/test_xxx.py

## Run With Coverage
pytest --cov=src

## Lint
ruff check .

## Format
black .

---

# Architecture Overview

## Technology Stack

- Language: Python 3.11+
- CLI Framework: argparse
- HTTP Client: requests
- Testing: pytest
- Linting: ruff
- Formatting: black
- CI: GitHub Actions

No frontend.
No styling.
No framework beyond standard Python tooling.

---

# Project Structure

Root/
│
├── src/
│   └── ai_prompt_runner/       # package root — imports start here
│       ├── cli.py
│       ├── api.py
│       ├── core/
│       │   ├── runner.py
│       │   ├── models.py
│       │   ├── validators.py
│       │   ├── errors.py
│       │   └── error_taxonomy.py
│       ├── services/
│       │   ├── provider_factory.py
│       │   ├── anthropic_provider.py
│       │   ├── openai_compatible_provider.py
│       │   ├── google_provider.py
│       │   ├── http_provider.py
│       │   ├── mock_provider.py
│       │   └── base.py
│       └── utils/
│           └── file_io.py
│
├── prompts/
│   └── structured_output_v1.txt
│
├── tests/
│   ├── unit/
│   └── e2e/
│
├── .github/workflows/ci.yml
├── requirements.txt
├── README.md
└── AGENTS.md

NOTE: physical path src/ai_prompt_runner/ maps to ai_prompt_runner. in imports.
→ from ai_prompt_runner.core.runner import PromptRunner  ✓
→ from src.core.runner import PromptRunner               ✗

IMPORTANT:
- Business logic MUST stay in src/core
- CLI must ONLY parse arguments and call core
- No API logic inside CLI

---

# Important Features

- Send prompt to AI API
- Validate JSON response
- Save output as JSON
- Save output as Markdown
- Maintain history folder
- Future-ready for multiple providers
- Versionable prompts

---

# Code Conventions

## Naming Conventions

- Files: snake_case.py
- Classes: PascalCase
- Functions: snake_case
- Constants: UPPER_CASE
- Private methods: _leading_underscore

## Language Conventions

- Use type hints everywhere
- Avoid dynamic typing when possible
- Always return explicit types
- Avoid global state

## Style Conventions

- Follow PEP8
- Max 88 characters per line
- Functions < 40 lines
- One responsibility per function
- No business logic in CLI layer

---

# Authentication

- `AI_API_KEY` — API key (required)
- `AI_API_ENDPOINT` — API endpoint URL (required)
- `AI_API_MODEL` — model name (optional)
- Never hardcode these values
- Always use `os.getenv()`

---

# State Management

v1.0.0:
- Stateless execution
- Output saved to filesystem
- No in-memory global state

Future:
- Optional history index file (JSON)

---

# Testing

## Unit Testing

Location:
tests/unit/

Test:
- core logic
- formatting
- JSON validation
- error handling

Run:
pytest tests/unit/

Mocks:
- Mock external API calls
- Use unittest.mock or pytest-mock

Helpers:
tests/helpers/ (if needed)

---

## E2E Testing

Location:
tests/e2e/

Test:
- full CLI execution flow
- file generation
- integration behavior

Run:
pytest tests/e2e/

API calls must be mocked.
Never hit real API in CI.

---

# Important Files

src/ai_prompt_runner/cli.py
Entry point of the application.

src/ai_prompt_runner/core/runner.py
Main business logic.

src/ai_prompt_runner/services/provider_factory.py
Provider selection and API communication.

src/ai_prompt_runner/utils/file_io.py
Filesystem operations.

.github/workflows/ci.yml
CI pipeline definition.

---

# File Naming Rules

- test files: test_xxx.py
- service files: xxx_service.py
- utilities: xxx_utils.py
- prompt versions: structured_output_vX.txt

---

# Important Imports Rules

Always prefer absolute imports:

from ai_prompt_runner.core.runner import PromptRunner

Never use relative imports across layers.

---

# Debugging

1. Reproduce with pytest
2. Add failing test
3. Fix core logic
4. Re-run tests
5. Validate lint
6. Commit with clear message

---

# Workflow

1. Create feature branch
2. Implement change
3. Add tests
4. Run lint + tests
5. Open Pull Request
6. CI must pass
7. Tag version if release

---

# Pull Request Standard

For every pull request, use this exact section order:

1. `## Scope`
2. `## Why`
3. `## Validation`
4. `## Out of Scope`

## Content Rules

- `Scope`: describe concrete code changes (files/components/behaviors).
- `Why`: explain architectural or product rationale (not implementation details).
- `Validation`: list executed commands and their result status.
- `Out of Scope`: explicitly state what was intentionally not changed.

## Validation Format

Use command bullets, for example:

- `ruff check .`
- `python3 -m pytest`
- `python3 -m pytest --cov=src --cov-report=term-missing --cov-fail-under=95 -q`

Then add a short result line:

- `All checks passed locally.`

## Discipline

- Keep PR text factual and concise.
- Do not mix future roadmap work into current PR scope.
- If docs are not updated in the PR, state it explicitly in `Out of Scope`.

---

# Versioning

Use semantic versioning:

v1.0.0
v1.1.0
v2.0.0

Prompt changes may require minor or major bump.

---

# Development Tools

- Python 3.11+
- requests
- argparse
- pytest
- unittest.mock
- jsonschema (optional future validation)
- black
- ruff
