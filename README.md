# repo-standard-kit

Portable development standards, starter kits, and bootstrap tooling for modern
software repositories.

## Purpose

`repo-standard-kit` packages a repository development standard together with the
starter assets and tooling that put it into practice, so good defaults are cheap
to adopt in a new repository and easy to check against in an existing one.

This README is a guide to using the kit. It is **not normative**: the rules live
in [docs/repo-standard.md](docs/repo-standard.md) and the companion documents it
indexes. Where this README and the standard differ, the standard governs.

This repository provides:

- normative documentation for repository development standards
- a required `AGENTS.md` contract for repository-level guidance
- first-class Python profiles for single-package and workspace repositories
- a trunk-based collaboration workflow for parallel development
- a standard Python repository layout
- starter-kit assets for new repositories
- a thin bootstrap tool for generating a new repository from the starter kit
- GitHub Actions CI that mirrors the documented local quality gates
- `uv`-based dependency and build configuration for Python projects

## The Standard

[docs/repo-standard.md](docs/repo-standard.md) is the normative entry point. It
states the contract a repository must satisfy and indexes the companion
documents covering quality gates, the agent operating model, Git workflow,
repository layout, bootstrapping, and the Python profiles.

Templates and starter kits implement that standard; the documents it indexes
define the intent and rules.

## What Is In This Repo

- `docs/`: the standard and its companion documents
- `profiles/`: language or repo-type specific standards
- `templates/`: reusable templates for adopting the standard in an existing repo
- `src/repo_standard/`: packaged bootstrap implementation
- `src/repo_standard/starter_kits/`: copyable repository skeletons

For the layout the standard prescribes for *your* repository, see
[docs/repo-layout.md](docs/repo-layout.md).

## Bootstrap A New Python Repository

Run the initializer directly with `uvx`, from the parent directory of the
repository you want to create:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-init --profile python-single --repo-name widget-service
```

Use `--profile python-workspace` instead for a monorepo with per-package
projects under `packages/`.

`uvx` is the short form of `uv tool run`. It installs the bootstrap package
from this standards repository into an isolated tool environment, then runs
the packaged `repo-init` command. The generated repository derives its
`AGENTS.md`, CI workflow, `pyproject.toml`, and starter files from the version
of this repository that `uv` resolves.

Then:

1. Review the generated `AGENTS.md`, `README.md`, and CI workflow.
2. Run the quality gates in the generated repository.
3. Make the initial commit on `main`.

Pin a standards version by adding a Git ref:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v0.3.0" repo-init --profile python-single --repo-name widget-service
```

For repeated use, install the tool once. That puts `repo-init` and
`repo-add-package` on your path:

```bash
uv tool install --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-standard-kit
```

If you prefer HTTPS instead of SSH, use the same command shape with the HTTPS
Git URL for this repository.

Do not clone this standards repository as the starting point for a product
repository. Generate or template the target repository separately.

See [docs/bootstrap-workflow.md](docs/bootstrap-workflow.md) for the full
option reference, the workspace `repo-add-package` flow, and the expected
generated output.

## Current Profiles

- `python-single`: one package rooted at `src/<package_name>/`
- `python-workspace`: monorepo with per-package projects under `packages/`

Python is the only supported language today. Other languages are added only
once a profile is fully documented and maintained.

## Adoption Paths

Use this repository in one of two ways:

- New repository: bootstrap with `repo-init`, which renders the
  `python-single` or `python-workspace` starter kit
- Existing repository: adapt the repo to match the standard and populate
  `AGENTS.md` and `README.md` using `templates/AGENTS.md` and
  `templates/README.md`

## Design Principles

Why the standard is shaped the way it is. These are rationale, not rules — each
is enforced by the document named beside it.

- **Portable**: no workspace-specific filesystem assumptions, so the standard
  travels between organizations — `docs/repo-standard.md`
- **Practical**: exact commands and concrete file layouts, not abstract policy —
  `docs/quality-gates.md`
- **Collaborative**: explicit human and agent responsibility boundaries —
  `docs/agent-operating-model.md`
- **Typed**: strong typing expectations for Python code —
  `docs/quality-gates.md`, `profiles/python-single.md`
- **Small-batch**: short-lived branches and small PRs for parallel work —
  `docs/git-workflow.md`
