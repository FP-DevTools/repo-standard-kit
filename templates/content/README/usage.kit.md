Every command below ships in this package and runs without installing it,
through `uvx` — the short form of `uv tool run`. `uvx` installs the kit from
this standards repository into an isolated tool environment and then runs the
requested command, so the version `uv` resolves determines the assets and rules
that get applied.

Pick the entry point that matches the target repository:

- new repository: [bootstrap](#bootstrap-a-new-repository) it with `repo-init`,
  which renders the `python-single` or `python-workspace` starter kit
- existing repository:
  [adopt](#adopt-the-standard-in-an-existing-repository) the standard with
  `repo-adopt`, review the unstaged result, and resolve any manual findings

The examples use SSH. If you prefer HTTPS, use the same command shape with the
HTTPS Git URL for this repository. Do not clone this standards repository as
the starting point for a product repository; generate or reconcile the target
repository instead.

### Bootstrap A New Repository

Run `repo-init` from the parent directory of the repository you want to create:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init --profile python-single --repo-name widget-service
```

Use `--profile python-workspace` instead for a monorepo with per-package
projects under `packages/`. The generated repository derives its `AGENTS.md`,
CI workflow, `pyproject.toml`, and starter files from the resolved version of
this repository.

Add `--license proprietary`, `--license mit`, or `--license apache-2.0` to write
a real `LICENSE` and declare it in `pyproject.toml`. Without it the repository
starts with no licence file and a `License` section saying terms have not been
chosen, which RSK018 keeps reporting as a recommendation until they are.

Then:

1. Review the generated `AGENTS.md`, `README.md`, and CI workflow.
2. Run the quality gates in the generated repository.
3. Make the initial commit on `main`.

See [docs/bootstrap-workflow.md](docs/bootstrap-workflow.md) for the full
option reference and the expected generated output.

### Add A Package To A Workspace

Run `repo-add-package` from the root of a `python-workspace` repository:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-add-package --package-name widget_api --description "Service package for widget API behavior"
```

The new package lands under `packages/<package-slug>/` with its own
`pyproject.toml`, `README.md`, source package, and tests.

### Adopt The Standard In An Existing Repository

From a clean existing Git repository, preview the reconciliation first:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-adopt . --profile python-single --dry-run
```

Then apply it:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-adopt . --profile python-single
```

`repo-adopt` adds missing standard-owned assets and structurally reconciles
TOML, pre-commit, and workflow configuration while retaining unrelated project
settings and steps. It updates human-owned `README.md` and `AGENTS.md` only in
mechanically safe standard sections, reports conflicts for maintainer action,
runs `repo-check`, and leaves every change unstaged and uncommitted.

Use `--no-lock` or `--no-install` in constrained environments,
`--native-tls` when child uv commands need the platform certificate store, and
`--run-gates` when the full profile gate chain should run immediately. Omit
`--profile` to let the command resolve the profile from repository metadata and
policy detection markers. The command never changes GitHub branch protection or
rulesets. See [docs/bootstrap-workflow.md](docs/bootstrap-workflow.md) for the
ownership and safety contract.

### Check A Repository's Alignment

Run `repo-check` from the root of the repository you want to check:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-check .
```

Replace `.` with any repository path. It reports structural findings from the
same compiled YAML policy that drives `repo-init` and `repo-adopt`. Add
`--strict` to fail on recommended findings and `--format json` for stable
machine output. See [docs/policy-reference.md](docs/policy-reference.md) for
the generated rule catalogue and [docs/compliance.md](docs/compliance.md) for
resolution, output, and structural-check details.

### Pin A Standards Version

Add a Git ref to the `--from` URL. This works for every command above:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v2.0.0" repo-init --profile python-single --repo-name widget-service
```
