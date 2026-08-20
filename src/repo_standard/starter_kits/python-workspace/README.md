# __REPO_NAME__

__DESCRIPTION__

## Overview

This repository is a Python workspace with independently structured package
projects under `packages/`.

## Install

Requires Python `__PYTHON_VERSION__` or newer.

```bash
uv sync
uv run pre-commit install
```

`uv run pre-commit install` needs Git to be initialized. If you used
`repo-init` without `--no-install`, both steps have already run for you.

## First 10 Minutes

1. Review `AGENTS.md`.
2. Run `uv sync`.
3. Run `uv run pre-commit install` after Git is initialized. If you used
   `repo-init` without `--no-install`, this is already done for you.
4. Run `uv run pre-commit run --all-files`.
5. Run `uv run ruff format --check .`.
6. Run `uv run ruff check .`.
7. Run `uv run ty check`.
8. Run `uv run pytest`.
9. Run `uv build`.
10. Review `.github/workflows/quality.yml`.
11. Commit the generated `uv.lock`, then make the initial commit on `main`.

## Usage

Add the first package with `repo-add-package --package-name your_pkg`, then
import it from `packages/`. Replace this section with what the workspace is
actually for once it holds real packages.

## Repo Structure

- `packages/`: one directory per workspace package.
- `tests/`: workspace-level tests that span packages.
- `docs/`: architecture decision records and diagrams.

## Development

Repository workflow, quality gates, and coding standards are defined in
`AGENTS.md`. The mandatory quality gates and this README's structure derive
from [repo-standard-kit] — see its [quality-gates spec][quality-gates] and
[README template][readme-template]. Keep this file's shape aligned with those
when you update it, and check this repository against it periodically for
standards drift.

## License

__LICENSE_NOTICE__

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
[readme-template]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/templates/README.md
