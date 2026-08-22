# __REPO_NAME__

__DESCRIPTION__

## Overview

This repository contains the `__PACKAGE_NAME__` Python project.

## Install

Requires Python `__PYTHON_VERSION__` or newer.

```bash
uv sync
uv run pre-commit install
```

`uv run pre-commit install` needs Git to be initialized. If you used
`repo-init` without `--no-install`, both steps have already run for you.

## First 10 Minutes

1. Review `AGENTS.md` and confirm the repo-specific scope and constraints.
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

```python
import __PACKAGE_NAME__
```

Replace this with the entry points, commands, or API this repository is
actually for.

## Development

Repository workflow, quality gates, and coding standards are defined in
`AGENTS.md`. The mandatory quality gates derive from [repo-standard-kit] — see
its [quality-gates spec][quality-gates].

This README's section order is RSK023, whose canonical section list lives in
the kit's `policy/shapes.yaml` and is published in the
[policy reference][policy-reference]. Run `repo-check .` after editing this
file and it names any section that is missing or out of order; `repo-adopt .`
inserts the required ones.

## License

__LICENSE_NOTICE__

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
[policy-reference]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/policy-reference.md
