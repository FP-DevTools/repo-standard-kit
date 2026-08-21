# repo-standard-kit

Portable development standards, starter kits, and bootstrap tooling for modern
software repositories.

## Overview

`repo-standard-kit` packages a repository development standard together with the
starter assets and tooling that put it into practice, so good defaults are cheap
to adopt in a new repository and easy to check against in an existing one.

This README is a guide to using the kit. It is **not normative**. Normative
prose starts at [docs/repo-standard.md](docs/repo-standard.md); executable rule
values live in `policy/`, with the generated catalogue in
[docs/policy-reference.md](docs/policy-reference.md). Where this README and the
standard differ, the standard governs.

This repository provides:

- normative documentation for repository development standards
- a required `AGENTS.md` contract for repository-level guidance
- first-class Python profiles for single-package and workspace repositories
- a trunk-based collaboration workflow for parallel development
- a standard Python repository layout
- starter-kit assets for new repositories
- a thin bootstrap tool for generating a new repository from the starter kit
- a conflict-aware adoption tool for reconciling an existing repository
- a `repo-check` CLI and library that verify a repository's structural
  alignment with the standard
- versioned canonical YAML policy plus deterministic runtime and documentation
  generation
- GitHub Actions CI that mirrors the documented local quality gates
- `uv`-based dependency and build configuration for Python projects

### The Standard

[docs/repo-standard.md](docs/repo-standard.md) is the normative entry point. It
states the contract a repository must satisfy and indexes the companion
documents covering quality gates, the agent operating model, Git workflow,
repository layout, bootstrapping, and the Python profiles.

Templates and starter kits implement that standard; the documents it indexes
define the intent and rules.

### Current Profiles

- `python-single`: one package rooted at `src/<package_name>/`
- `python-workspace`: monorepo with per-package projects under `packages/`

Python is the only supported language today. The generated
[policy profile catalogue](docs/policy-reference.md#profiles) is authoritative;
other languages are added only once their policy profile is maintained.

## Install

Requires [uv](https://docs.astral.sh/uv/). Nothing needs installing to use the
kit — every command below runs on demand through `uvx`, as described under
[Usage](#usage).

For repeated use, install the kit once to put `repo-init`, `repo-add-package`,
`repo-adopt`, and `repo-check` on your path:

```bash
uv tool install --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-standard-kit
```

## Usage

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

## Repo Structure

- `docs/`: the standard and its companion documents
- `policy/`: canonical machine-enforced rules, profile detection metadata, and
  the file shapes governed documents must follow
- `templates/`: reference documents rendered from the shapes, plus the
  `content/` prose fragments they are rendered from
- `src/repo_standard/`: packaged bootstrap implementation
- `src/repo_standard/policy/`: strict policy models and compiled runtime policy
- `src/repo_standard/starter_kits/`: copyable repository skeletons
- `scripts/`: developer scripts, including `generate_policy.py`
- `tests/`: automated tests

For the layout the standard prescribes for *your* repository, see
[docs/repo-layout.md](docs/repo-layout.md).

## Development

This section covers working on the kit itself. `AGENTS.md` is the full
operating contract for this repository and governs where it goes further.

Set up a working copy:

```bash
uv sync --locked && uv run pre-commit install
```

The mandatory quality-gate chain is stated once, in `AGENTS.md`; run it locally
before pushing. CI runs the same chain on every pull request through
`.github/workflows/quality.yml`, and a separate `compliance` job checks this
repository against the standard it publishes. Both checks are required to
merge.

`policy/` is the canonical source for machine-enforced rules. After changing
`policy/` or a policy-linked normative section, regenerate the compiled runtime
policy and its documentation, then commit both:

```bash
uv run python scripts/generate_policy.py
```

`uv run pytest` fails when `src/repo_standard/policy/compiled.json` or
[docs/policy-reference.md](docs/policy-reference.md) is stale.

### Design Principles

Why the standard is shaped the way it is. These are rationale, not rules — each
is enforced by the document named beside it.

- **Portable**: no workspace-specific filesystem assumptions, so the standard
  travels between organizations — `docs/repo-standard.md`
- **Practical**: exact commands and concrete file layouts, not abstract policy —
  `docs/quality-gates.md`
- **Collaborative**: explicit human and agent responsibility boundaries —
  `docs/agent-operating-model.md`
- **Typed**: strong typing expectations for Python code —
  `docs/quality-gates.md`, `docs/policy-reference.md#profiles`
- **Small-batch**: short-lived branches and small PRs for parallel work —
  `docs/git-workflow.md`

## License

Proprietary and confidential. Copyright (c) 2026 FP-DevTools. All rights
reserved. See [LICENSE](LICENSE).
