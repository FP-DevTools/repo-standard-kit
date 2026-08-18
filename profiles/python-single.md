# Python Single-Package Profile

## Purpose

Use this profile for repositories that produce a single Python package from the
repo root.

## Layout

- root `pyproject.toml`
- root `src/<package_name>/`
- root `tests/`
- shared tool config at the repo root
- root `uv_build` backend with `module-name` set to the package name
- root pre-commit hooks that run Ruff and generic file checks through `uv`
- root GitHub Actions workflow for quality gates

## Quality Gates

`docs/quality-gates.md` defines the mandatory local and CI gate chain. Run it
from the repository root. This profile adds no extra gates and relaxes none.

## Bootstrap Behavior

- `repo-init --profile python-single`
- `--package-name` optional and inferred from `--repo-name` when omitted
