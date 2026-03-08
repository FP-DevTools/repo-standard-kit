# Python Workspace Walkthrough

## Bootstrap Workspace

From inside the empty workspace directory:

```bash
repo-init \
  --profile python-workspace \
  --repo-name widget-platform \
  --description "Workspace for widget services and libraries"
```

## Add First Package

From the generated workspace root:

```bash
repo-add-package \
  --package-name widget_api \
  --description "Service package for widget API behavior"
```

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
