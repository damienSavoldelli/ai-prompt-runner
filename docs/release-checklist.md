# Release Checklist

## Purpose

This checklist defines the standard release preparation flow for `ai-prompt-runner`.

It is intended to reduce release mistakes, keep versioning disciplined, and ensure that each release is backed by validated code, packaging, and documentation.

## Pre-Release Validation

Run these checks from the repository root before preparing a release:

```bash
git status
python3 -m pytest
python3 -m pytest --cov=src --cov-report=term-missing --cov-fail-under=95
ruff check .
python3 -m build
```

If the `uv` workflow is being used locally, validate that path as well:

```bash
uv run pytest
uv run ruff check .
uv run python -m build
```

## Version Preparation

1. Update the project version in [`pyproject.toml`](../pyproject.toml).
2. Refresh the local editable install if needed:

```bash
python3 -m pip install -e .
```

3. Verify both CLI entrypoints report the expected version:

```bash
python3 -m src.cli --version
ai-prompt-runner --version
```

## Changelog Update

1. Add the new release section at the top of [`CHANGELOG.md`](../CHANGELOG.md).
2. Keep the entry focused on:
   - what changed
   - why it matters
   - any important scope or compatibility notes

## Release Commit

Prepare the release commit only after version and changelog updates are complete:

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "release: prepare vX.Y.Z"
```

## Tagging

Create an annotated tag using the normalized release message:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

Verify the tagged release contents:

```bash
git show --stat vX.Y.Z
git log --oneline --decorate -n 6
```

## Publish

Push the branch and the tag:

```bash
git push origin main
git push origin vX.Y.Z
```

Then publish the GitHub Release using the matching tag and release notes.

## Release Quality Rules

- Do not ship with a dirty working tree.
- Do not skip packaging validation.
- Do not skip coverage validation.
- Do not introduce breaking behavior without an explicit versioning decision.
- Do not create a release tag before the release commit exists.
