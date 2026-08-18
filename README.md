# repo-standard-kit

Portable development standards, starter kits, and bootstrap tooling for modern
software repositories.

## Purpose

This repository defines a practical operating model for building repositories
with humans and agents working together. It is designed to make good defaults
easy to adopt when creating a new repository and easy to reference when
maintaining an existing one.

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
- a JavaScript/TypeScript profile scaffold for later expansion

## What Is Normative

The normative source documents are:

- `spec.md`
- `docs/repo-standard.md`
- `docs/agent-operating-model.md`
- `docs/git-workflow.md`
- `docs/repo-layout.md`
- `docs/bootstrap-workflow.md`
- `profiles/python-single.md`
- `profiles/python-workspace.md`

Templates and starter kits implement those standards, but the documents above
define the intent and rules.

## Repository Layout

- `docs/`: standards and operating guidance
- `profiles/`: language or repo-type specific standards
- `templates/`: reusable templates for adopting the standard in an existing repo
- `src/repo_standard/`: packaged bootstrap implementation
- `src/repo_standard/starter_kits/`: copyable repository skeletons
- `examples/`: filled examples showing the standard in practice

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
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v0.2.0" repo-init --profile python-single --repo-name widget-service
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
- `javascript-typescript`: scaffold only for future expansion

## Adoption Paths

Use this repository in one of two ways:

- New repository: bootstrap with `repo-init`, which renders the
  `python-single` or `python-workspace` starter kit
- Existing repository: adapt the repo to match the standard and populate
  `AGENTS.md` and `README.md` using `templates/AGENTS.md` and
  `templates/README.md`

## Golden Path Example

See [examples/python-service/walkthrough.md](examples/python-service/walkthrough.md)
for a concrete service-oriented bootstrap flow and the expected generated shape.
See [examples/python-workspace/walkthrough.md](examples/python-workspace/walkthrough.md)
for the workspace bootstrap and package-add flow.

## Design Principles

- Portable: no workspace-specific filesystem assumptions
- Practical: exact commands and concrete file layouts, not abstract policy only
- Collaborative: explicit human and agent responsibility boundaries
- Typed: strong typing expectations for Python code
- Small-batch: trunk-based PR workflow for parallel work
