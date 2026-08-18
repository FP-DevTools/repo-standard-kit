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

1. Run the initializer directly with `uvx`:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init --profile python-single --repo-name widget-service
```

`uvx` is the short form of `uv tool run`. It installs the bootstrap package
from this standards repository into an isolated tool environment, then runs
the packaged `repo-init` command.

2. Either create and enter an empty target directory, or run `repo-init` through
   `uvx` from the parent directory with `--repo-name` so it creates the
   repository folder for you.
3. Run `repo-init` with the Python profile and repository metadata.
4. Review generated `AGENTS.md`, `README.md`, package naming, and CI.
5. Run the generated repository quality gates.
6. Make the initial commit on `main`.

If the target directory is not yet a Git repository, `repo-init` initializes
one automatically on `main` before installing pre-commit hooks. Add or change
the remote afterward as needed.

For repeated use, install the tool once:

```bash
uv tool install --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-standard-kit
```

Pin a standards version by adding a Git ref:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v0.3.0" repo-init --profile python-single --repo-name widget-service
```

The generated repository derives its `AGENTS.md`, CI workflow, `pyproject.toml`,
and starter files from the version of this repository that `uv` resolves.

### Golden Path: Single Package

From inside the empty target directory:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init \
  --profile python-single
```

Or from the parent directory, let `repo-init` create the repository folder:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init \
  --profile python-single \
  --repo-name widget-service
```

After generation:

1. Review `AGENTS.md`
2. Run `uv sync`
3. Run `uv run pre-commit install`
4. Run `uv run pre-commit run --all-files`
5. Run `uv run ruff format --check .`
6. Run `uv run ruff check .`
7. Run `uv run ty check`
8. Run `uv run pytest`
9. Run `uv build`
10. Make the initial commit on `main`
11. Push an initial pull request, then configure branch protection on `main`
    as specified in `docs/quality-gates.md` so the gates become binding

### Golden Path: Workspace

From inside the empty workspace directory, bootstrap the workspace shell:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init \
  --profile python-workspace
```

Or from the parent directory:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init \
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

Every generated repository should contain a concrete `AGENTS.md`, a README
stating the repository purpose and workflow entry points, a GitHub Actions
workflow running the `docs/quality-gates.md` gate chain, `uv_build` metadata in
each package `pyproject.toml`, and no unresolved template placeholders.

### `python-single`

`repo-init --profile python-single --repo-name widget-service` produces:

```text
widget-service/
  .github/workflows/quality.yml
  .pre-commit-config.yaml
  AGENTS.md
  README.md
  pyproject.toml
  docs/adr/0001-template.md
  docs/diagrams/README.md
  src/widget_service/__init__.py
  tests/test_smoke.py
```

The package directory is named from `--package-name`, or inferred from the
repository name when that flag is omitted.

### `python-workspace`

`repo-init --profile python-workspace --repo-name widget-platform` produces the
workspace shell with an empty `packages/` directory:

```text
widget-platform/
  .github/workflows/quality.yml
  .pre-commit-config.yaml
  AGENTS.md
  README.md
  pyproject.toml
  docs/adr/0001-template.md
  docs/diagrams/README.md
  packages/.gitkeep
```

Each later `repo-add-package --package-name widget_api` run adds:

```text
  packages/widget-api/
    pyproject.toml
    README.md
    src/widget_api/__init__.py
    tests/test_smoke.py
```

### What Good Looks Like

- No unresolved placeholders remain in generated files
- The package directory matches the requested package name
- `AGENTS.md` is concrete enough to use immediately, with no generic filler
- The repository passes the full `docs/quality-gates.md` chain

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
