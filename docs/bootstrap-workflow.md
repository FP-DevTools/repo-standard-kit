# Bootstrap Workflow

## Goal

Create new repositories that begin aligned with the standard by default instead
of relying on manual copy-paste and post-hoc cleanup.

## Default Bootstrap Model

Use a template-plus-initializer approach:

- starter kit provides the file and directory skeleton
- bootstrap tool fills repository-specific metadata and paths

Do not clone the standards repository as the base of a product repository.

## Recommended New Repository Flow

1. Install the tool once:

```bash
uv tool install --from "git+ssh://git@github.com/JayTeeBat/repo-standard-kit.git" repo-init
```

2. Create and enter an empty target repository or working directory.
3. Run `repo-init` with the Python profile and repository metadata.
4. Review generated `AGENTS.md`, `README.md`, and package naming.
5. Run the generated repository quality gates.
6. Make the initial commit on `main`.

### Golden Path: Single Package

From inside the empty target directory:

```bash
repo-init \
  --profile python-single \
  --repo-name widget-api \
  --description "Receive and validate widget payloads"
```

After generation:

1. Review `AGENTS.md`
2. Run `uv sync`
3. Run `uv run pre-commit install`
4. Run `uv run pre-commit run --all-files`
5. Run `uv run ty check`
6. Run `uv run pytest`
7. Make the initial commit on `main`

### Golden Path: Workspace

From inside the empty workspace directory, bootstrap the workspace shell:

```bash
repo-init \
  --profile python-workspace \
  --repo-name widget-platform \
  --description "Workspace for widget services and libraries"
```

Then add the first package from the workspace root:

```bash
repo-add-package \
  --package-name widget_api \
  --description "Service package for widget API behavior"
```

If you prefer HTTPS instead of SSH, use the same command shape with the HTTPS
Git URL for this repository.

## `repo-init` Inputs

Required:

- `--profile`
- `--repo-name`
- `--description`

Optional:

- `--package-name`
- `--repo-type`
- `--python-version`
- `--author`
- `--output-dir`
- `--no-install`

## Expected Output

The generated repository should contain:

- a concrete `AGENTS.md`
- baseline Python tooling files
- a standard single-package or workspace layout
- a README with the repository purpose and workflow entry points
- no unresolved template placeholders
