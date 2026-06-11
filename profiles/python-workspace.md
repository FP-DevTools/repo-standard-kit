# Python Workspace Profile

## Purpose

Use this profile for monorepos with per-package projects under `packages/`.

## Layout

- root tooling-only `pyproject.toml`
- root `.pre-commit-config.yaml`
- package projects use `uv_build`
- root GitHub Actions workflow for quality gates
- `packages/<package-slug>/pyproject.toml`
- `packages/<package-slug>/src/<package_name>/`
- `packages/<package-slug>/tests/`
- root docs and ADRs

## Quality Gates

Run from workspace root:

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`

## Bootstrap Behavior

- `repo-init --profile python-workspace`
- starts with an empty `packages/` directory
- add packages later with `repo-add-package`
- CI should run the same `uv`, `ruff`, `ty`, and `pytest` chain as local quality gates
