# Bootstrap Workflow

This document covers both creation with `repo-init` and conflict-aware
adoption with `repo-adopt`. The commands intentionally have different safety
contracts: initialization owns an empty target, while adoption must preserve an
existing project's behavior.

## Adopt An Existing Repository

Run a read-only preview from the existing repository root:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" \
  repo-adopt . --profile python-single --dry-run
```

Use `python-workspace` for a workspace root. When `--profile` is omitted,
`repo-adopt` first uses valid `[tool.repo-standard]` metadata and then the
canonical policy detection markers. It stops and requests an explicit profile
if metadata is invalid or multiple profiles match; it never guesses through an
ambiguity.

After reviewing the preview, apply the reconciliation from a clean checkout:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" \
  repo-adopt . --profile python-single
```

Apply mode requires the target itself to be a Git repository root and refuses
a dirty worktree. The command plans and parses every affected file before it
writes anything. It then leaves all changes unstaged and uncommitted for normal
review. Repeated execution against the same profile and kit version is
idempotent. A repository with no required or recommended structural findings
is already compliant and produces no planned changes.

### Adoption Ownership Model

`repo-adopt` classifies content by ownership rather than copying a starter over
the checkout:

- Standard-owned assets such as the compliance workflow, GitHub Actions
  Dependabot entry, Markdown configuration, changelog skeleton, `.gitignore`,
  and documentation directories are added when missing. Existing non-empty ADR
  and diagram directories are authoritative and are never seeded with starter
  files or conflicting decision numbers. An existing `.gitignore` is left
  untouched; it is never merged with the starter's.
- `pyproject.toml`, `.pre-commit-config.yaml`, and the quality workflow are
  structurally merged. Existing project dependencies, build settings,
  services, custom hooks, and additional steps remain in place.
- Mutable refs on known standard workflow actions are replaced by the immutable
  pins shipped by the selected kit; existing full-SHA pins remain intact. The
  isolated `repo-check` hook moves to the selected kit version. Unknown remote
  Actions without immutable pins are reported for a maintainer-selected SHA.
- `README.md` and `AGENTS.md` remain project-owned. The adopter appends the
  standard reference and missing required sections, and reconciles the exact
  policy-owned Quality Gates command list without replacing other prose.
- A non-`uv_build` package backend is preserved and remains visible as the
  recommended RSK008 finding under strict checking. Unsupported standard
  metadata, malformed configuration, or another merge that changes project
  intent is not guessed through; the command reports an actionable conflict or
  stops before writes.
- License terms are never selected automatically. A missing `LICENSE` remains
  a recommended `repo-check` finding for the maintainer.

`repo-standard-kit` is not added to project dependencies. The compliance
workflow and optional pre-commit hook continue to run the released tool in an
isolated environment.

### Adoption Execution And Options

When dependency metadata changes, normal apply mode runs `uv lock` followed by
`uv sync`. Use `--no-lock` to leave lockfile refresh to the maintainer and
`--no-install` to skip environment synchronization. These flags are independent
because a constrained environment may permit one operation but not the other.
Use `--native-tls` when uv must load certificates from the platform's native
store. The option propagates `UV_NATIVE_TLS=true` to lock, sync, and optional
quality-gate subprocesses.

Pass `--run-gates` to execute the complete ordered quality-gate chain for the
selected profile. After reconciliation, `repo-adopt` runs the same structural
library check as `repo-check .` and summarizes:

- files added, updated, and unchanged;
- conflicts and manual actions;
- remaining required and recommended findings.

If lock, install, or gate execution fails or is interrupted, the command names
the exact failed command and leaves the generated source edits reviewable. A
parse error never partially rewrites the affected file. `--dry-run` performs no
filesystem, Git, dependency, or platform writes.

`repo-adopt` does not stage, commit, push, open a pull request, or mutate GitHub
branch protection and rulesets. Platform enforcement remains the separate,
authenticated operation documented in [quality-gates.md](quality-gates.md).

## Create A New Repository

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
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v2.0.0" repo-init --profile python-single --repo-name widget-service
```

The generated repository derives its `AGENTS.md`, CI workflow, `pyproject.toml`,
and starter files from the version of this repository that `uv` resolves.
Its `pyproject.toml` declares the selected profile and standard major under
`[tool.repo-standard]`, so later checks do not have to guess from layout.

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
4. Run the quality-gate chain stated in `docs/quality-gates.md`
5. Make the initial commit on `main`
6. Push an initial pull request, then configure branch protection on `main`
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
- `--license`
- `--output-dir`
- `--no-lock`
- `--no-install`

`--python-version` sets `requires-python`, and `--author` becomes the
`authors` entry in `pyproject.toml`; an unnamed author leaves the key out
rather than shipping it empty.

`--license` accepts `proprietary`, `mit`, or `apache-2.0`. It writes the full
licence text to `LICENSE` and declares `license` and `license-files` in
`pyproject.toml`. Omit it and no `LICENSE` is written: the README's `License`
section then states that terms have not been selected yet and cites RSK018,
which stays a visible recommendation until they are.

`repo-init` carries the same lock and install split as `repo-adopt`: the
default path runs `uv lock` followed by `uv sync`. Use `--no-lock` to leave
lockfile creation to the maintainer and `--no-install` to skip environment
synchronization and hook installation. These flags are independent because a
constrained environment may permit one operation but not the other. `uv sync`
writes `uv.lock` when none exists, so `--no-lock` on its own still leaves a
lock file behind. Whenever bootstrap ends with no `uv.lock`, `repo-init` names
RSK009 and the `uv lock` command that resolves it.

## Expected Output

Every generated repository should contain a concrete `AGENTS.md`, a README
stating the repository purpose and workflow entry points, a GitHub Actions
workflow running the `docs/quality-gates.md` gate chain, `uv_build` metadata in
each package `pyproject.toml`, and no unresolved template placeholders.

### `python-single`

`repo-init --profile python-single --repo-name widget-service` produces:

```text
widget-service/
  .github/dependabot.yml
  .github/workflows/compliance.yml
  .github/workflows/quality.yml
  .gitignore
  .pre-commit-config.yaml
  .pymarkdown.json
  AGENTS.md
  CHANGELOG.md
  README.md
  pyproject.toml
  uv.lock
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
  .github/dependabot.yml
  .github/workflows/compliance.yml
  .github/workflows/quality.yml
  .gitignore
  .pre-commit-config.yaml
  .pymarkdown.json
  AGENTS.md
  CHANGELOG.md
  README.md
  pyproject.toml
  uv.lock
  docs/adr/0001-template.md
  docs/diagrams/README.md
  packages/.gitkeep
  tests/test_workspace_shell.py
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
- The repository passes the full `docs/quality-gates.md` chain, which needs the
  `uv.lock` the default path produces
- `[tool.repo-standard]` declares the generated profile and standard major
- The quality workflow grants only `contents: read` and pins remote actions to
  full commit SHAs; Dependabot is configured to propose GitHub Actions updates
- Separate `quality` and `compliance` status checks run on pull requests and
  are suitable for branch-protection enforcement

The generated compliance workflow runs the released checker through `uvx` in
an isolated tool environment. It does not add `repo-standard-kit` to the new
repository's dependencies or couple compliance to the generated `uv.lock`.
See [Compliance Checking](compliance.md) for the equivalent reusable-workflow
caller and its immutable workflow pin.

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
