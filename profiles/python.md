# Python Profiles

Python support is split into two first-class repo shapes:

- `python-single`: one package repo using a root `src/<package_name>/` layout
- `python-workspace`: monorepo with per-package projects under `packages/`

Both profiles use `uv` as the package manager, `uv_build` for package build
metadata, and local pre-commit hooks that delegate to `uv run ruff ...`.

Use:

- `profiles/python-single.md` for single-package repositories
- `profiles/python-workspace.md` for workspace repositories
