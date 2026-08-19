# Python Workspace Profile

## Purpose

Use this profile for monorepos with per-package projects under `packages/`.

## Layout

- root tooling-only `pyproject.toml`, registered as a `uv` workspace
  (`[tool.uv.workspace] members = ["packages/*"]`) and marked `package =
  false` — the root itself is never installed or built, only the packages
  under it are
- root `tests/` with a smoke test asserting the workspace shell is
  well-formed, so the test suite has something real to collect before the
  first package exists
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

Building from the root builds every workspace member (`--all-packages`), not
the root itself — the root carries no distributable artifact of its own, so
building it directly would otherwise fall back to the implicit `setuptools`
backend PEP 517 provides for a project with no declared `[build-system]`.
Before the first package exists, that step is a documented no-op rather than
a failure.

## Bootstrap Behavior

- `repo-init --profile python-workspace`
- starts with an empty `packages/` directory
- add packages later with `repo-add-package`
