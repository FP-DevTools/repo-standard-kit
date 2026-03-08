# Python Service Walkthrough

This example shows the intended first-run workflow for a new Python service
repository.

## Bootstrap Command

Run this from an empty target directory:

```bash
repo-init \
  --profile python-single
```

## Expected Generated Files

The generated repository should contain:

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `src/widget_api/__init__.py`
- `tests/test_smoke.py`
- `docs/adr/0001-template.md`
- `docs/diagrams/README.md`

## First Review

Check these files first:

1. `AGENTS.md` for repo-specific scope and workflow
2. `README.md` for the generated first-10-minutes checklist
3. `pyproject.toml` for package name and Python version

## Golden Path After Bootstrap

1. Run `uv sync`
2. Run `uv run pre-commit install` if you bootstrapped with `--no-install`
   or if you want to reinstall the hooks later
3. Run `uv run pre-commit run --all-files`
4. Run `uv run ty check`
5. Run `uv run pytest`
6. Make the initial commit on `main`

## What Good Looks Like

- No unresolved placeholders remain in generated files
- Package path matches the requested package name
- `AGENTS.md` is concrete enough to be used immediately
- The repo passes the documented Python quality gates
