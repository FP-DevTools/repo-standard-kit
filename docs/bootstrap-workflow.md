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
uv tool install --from "git+ssh://git@github.com/JayTeeBat/repo-bootstrap-kit.git" repo-bootstrap-kit
```

2. Either create and enter an empty target directory, or run `repo-init` from the
   parent directory with `--repo-name` so it creates the repository folder for
   you.
3. Run `repo-init` with the Python profile and repository metadata.
4. Review generated `AGENTS.md`, `README.md`, package naming, and CI.
5. Run the generated repository quality gates.
6. Make the initial commit on `main`.

If the target directory is not yet a Git repository, `repo-init` initializes
one automatically on `main` before installing pre-commit hooks. Add or change
the remote afterward as needed.

### Golden Path: Single Package

From inside the empty target directory:

```bash
repo-init \
  --profile python-single
```

Or from the parent directory, let `repo-init` create the repository folder:

```bash
repo-init \
  --profile python-single \
  --repo-name widget-service
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
  --profile python-workspace
```

Or from the parent directory:

```bash
repo-init \
  --profile python-workspace \
  --repo-name widget-platform
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

Optional:

- `--repo-name`
- `--description`
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
- a GitHub Actions workflow for the quality gate chain
- `uv_build` metadata in package `pyproject.toml` files
- a standard single-package or workspace layout
- a README with the repository purpose and workflow entry points
- no unresolved template placeholders

By default, `repo-init` infers the repository name from the target directory.
If you pass `--repo-name` without `--output-dir`, `repo-init` creates
`./<repo-name>` and bootstraps into that new directory. If you pass both,
`--output-dir` remains the explicit target and `--repo-name` overrides only the
rendered repository metadata.
By default, `repo-init` uses a placeholder description that you can refine
later in `README.md`.
By default, `repo-init` also initializes Git on `main` when needed so hook
installation works in a fresh directory. Use `--no-install` if you want
bootstrap to stop before environment setup and hook installation.
