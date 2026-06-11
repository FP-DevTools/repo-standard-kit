# __REPO_NAME__

__DESCRIPTION__

## Purpose

This repository is a Python workspace with independently structured package
projects under `packages/`.

## First 10 Minutes

1. Review `AGENTS.md`.
2. Run `uv sync`.
3. Run `uv run pre-commit install` after Git is initialized. If you used
   `repo-init` without `--no-install`, this is already done for you.
4. Run `uv run pre-commit run --all-files`.
5. Review `.github/workflows/quality.yml`.
6. Run `uv run ty check`.
7. Run `uv run pytest`.
8. Make the initial commit on `main`.

## Next Step

Add the first package with `repo-add-package --package-name your_pkg`.
