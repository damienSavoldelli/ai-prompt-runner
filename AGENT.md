# AGENT.md

# AI Prompt Runner – Agent Guidelines

This document defines strict rules and architectural conventions for AI agents (Codex, etc.) working on this repository.

The agent MUST follow these rules.

---

# Core Commands

## Run CLI
python -m src.cli --prompt "Your text here"

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

# Development Tools

- Python 3.11+
- requests
- argparse
- pytest
- unittest.mock
- jsonschema (optional future validation)
- black
- ruff

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
- Database: None (file-based storage for v1.0.0)

No frontend.
No styling.
No framework beyond standard Python tooling.

---

# Project Structure

Root/
│
├── src/
│   ├── cli.py
│   ├── core/
│   │   ├── prompt_runner.py
│   │   └── formatter.py
│   ├── services/
│   │   └── ai_provider.py
│   ├── utils/
│   │   └── file_manager.py
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
└── AGENT.md

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

# State Management

v1.0.0:
- Stateless execution
- Output saved to filesystem
- No in-memory global state

Future:
- Optional history index file (JSON)

---

# Forms and Server Actions

Not applicable in v1.0.0.
This is a CLI project.

---

# Authentication

- API key loaded from environment variable
- Never hardcode API keys
- Use os.environ.get()

---

# Database

None in v1.0.0.
All persistence is file-based.

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

src/cli.py  
Entry point of the application.

src/core/prompt_runner.py  
Main business logic.

src/services/ai_provider.py  
External API communication.

src/utils/file_manager.py  
Filesystem operations.

.github/workflows/ci.yml  
CI pipeline definition.

---

# Development Notes

Always use:

- python -m src.cli
- pytest before committing
- black .
- ruff check .

Never:

- Put logic inside CLI
- Mix I/O and business logic
- Hardcode secrets

Always:

- Add tests when adding logic
- Keep functions small
- Use typing

---

# File Naming Rules

- test files: test_xxx.py
- service files: xxx_service.py
- utilities: xxx_utils.py
- prompt versions: structured_output_vX.txt

---

# Debugging Complete Tasks

When debugging:

1. Reproduce with pytest
2. Add failing test
3. Fix core logic
4. Re-run tests
5. Validate lint
6. Commit with clear message

---

# Important Imports Rules

Always prefer absolute imports:

from src.core.prompt_runner import run_prompt

Never use relative imports across layers.

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

# Versioning

Use semantic versioning:

v1.0.0
v1.1.0
v2.0.0

Prompt changes may require minor or major bump.

---

# Agent Behavior Rules

The agent MUST:

- Never regenerate entire files without reason@
- Propose diff-style changes
- Respect architecture boundaries
- Add tests when modifying core logic
- Keep code modular

The agent MUST NOT:

- Refactor unrelated files
- Modify CI without request
- Introduce unnecessary dependencies
- Break version compatibility
@