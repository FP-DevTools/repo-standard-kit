# Python Single-Package Profile

## Purpose

Use this profile for repositories that produce a single Python package from the
repo root.

## Layout

- root `pyproject.toml`
- root `src/<package_name>/`
- root `tests/`
- shared tool config at the repo root
- root PEP 517 build backend; `uv_build` with `module-name` set to the package
  name is the recommended and generated default
- root pre-commit hooks that run Ruff and generic file checks through `uv`
- root GitHub Actions workflow for quality gates

## Quality Gates

`docs/quality-gates.md` defines the mandatory local and CI gate chain. Run it
from the repository root. This profile adds no extra gates and relaxes none.

## Policy Declaration

Declare `profile = "python-single"` and `standard = "1"` under
`[tool.repo-standard]`. This explicit declaration wins over filesystem
markers. In its absence, this profile is the deterministic fallback after
higher-priority profile markers do not match.

## Bootstrap Behavior

- `repo-init --profile python-single`
- `--package-name` optional and inferred from `--repo-name` when omitted
