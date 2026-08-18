# Python Workspace Profile

## Purpose

Use this profile for monorepos with per-package projects under `packages/`.

## Layout

- root tooling-only `pyproject.toml`
- root `.pre-commit-config.yaml` with hooks that run Ruff and generic file
  checks through `uv`
- package projects use `uv_build`
- root GitHub Actions workflow for quality gates
- `packages/<package-slug>/pyproject.toml`
- `packages/<package-slug>/src/<package_name>/`
- `packages/<package-slug>/tests/`
- root docs and ADRs

## Quality Gates

`docs/quality-gates.md` defines the mandatory local and CI gate chain. Run it
once from the workspace root so it covers every package. This profile adds no
extra gates and relaxes none.

## Bootstrap Behavior

- `repo-init --profile python-workspace`
- starts with an empty `packages/` directory
- add packages later with `repo-add-package`
