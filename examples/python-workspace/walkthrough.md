# Python Workspace Walkthrough

## Bootstrap Workspace

From inside the empty workspace directory:

```bash
repo-init \
  --profile python-workspace
```

## Add First Package

From the generated workspace root:

```bash
repo-add-package \
  --package-name widget_api \
  --description "Service package for widget API behavior"
```

## Golden Path After Bootstrap

1. Run `uv sync`
2. Run `uv run pre-commit install` if you bootstrapped with `--no-install`
3. Run `uv run pre-commit run --all-files`
4. Run `uv run ruff format --check .`
5. Run `uv run ruff check .`
6. Run `uv run ty check`
7. Run `uv run pytest`
8. Run `uv build`
9. Make the initial commit on `main`

## Expected Shape

```text
widget-platform/
  AGENTS.md
  README.md
  pyproject.toml
  packages/
    widget-api/
      pyproject.toml
      README.md
      src/widget_api/
      tests/
```
