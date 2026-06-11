# Python Single-Package Profile

## Purpose

Use this profile for repositories that produce a single Python package from the
repo root.

## Layout

- root `pyproject.toml`
- root `src/<package_name>/`
- root `tests/`
- shared tool config at the repo root
- root GitHub Actions workflow for quality gates

## Quality Gates

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`

## Bootstrap Behavior

- `repo-init --profile python-single`
- `--package-name` optional and inferred from `--repo-name` when omitted
- CI should run the same `uv`, `ruff`, `ty`, and `pytest` chain as local quality gates
