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
- a JavaScript/TypeScript profile scaffold for later expansion

## What Is Normative

The normative source documents are:

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
- `templates/`: reusable templates for repo-level files
- `starter-kits/`: copyable repository skeletons
- `src/repo_standard/`: packaged bootstrap implementation
- `examples/`: filled examples showing the standard in practice

## Bootstrap A New Python Repository

The recommended workflow is:

1. Install the tool once:

```bash
uv tool install --from "git+ssh://git@github.com/JayTeeBat/repo-standard-kit.git" repo-standard-kit
```

That gives you:

- `repo-init`
- `repo-add-package`

2. Create and enter an empty target repository or working directory.
3. Run the bootstrap tool in that directory:

```bash
repo-init \
  --profile python-single
```

4. Review the generated `AGENTS.md` and `README.md`.
5. Run the quality gates in the generated repository.
6. Make the initial commit on `main`.

Do not clone this standards repository as the starting point for a product
repository. Generate or template the target repository separately.

If you prefer HTTPS instead of SSH, use the same command shape with the HTTPS
Git URL for this repository.

`--repo-name` is optional. By default, `repo-init` infers the repository name
from the target directory name.
`--description` is also optional and can be refined later in `README.md`.
If the target directory is not yet a Git repository, `repo-init` initializes
one automatically on `main` before installing pre-commit hooks. You can add or
change the remote afterward.

## Current Profiles

- `python-single`: one package rooted at `src/<package_name>/`
- `python-workspace`: monorepo with per-package projects under `packages/`
- `javascript-typescript`: scaffold only for future expansion

## Adoption Paths

Use this repository in one of two ways:

- New repository: bootstrap from `starter-kits/python-single/` or
  `starter-kits/python-workspace/` via `repo-init`
- Existing repository: adapt the repo to match the standard and populate
  `AGENTS.md` using `templates/AGENTS.md`

## Golden Path Example

See [examples/python-service/walkthrough.md](/home/thomazo/dev/repo-standard-kit/examples/python-service/walkthrough.md)
for a concrete service-oriented bootstrap flow and the expected generated shape.
See [examples/python-workspace/walkthrough.md](/home/thomazo/dev/repo-standard-kit/examples/python-workspace/walkthrough.md)
for the workspace bootstrap and package-add flow.

## Design Principles

- Portable: no workspace-specific filesystem assumptions
- Practical: exact commands and concrete file layouts, not abstract policy only
- Collaborative: explicit human and agent responsibility boundaries
- Typed: strong typing expectations for Python code
- Small-batch: trunk-based PR workflow for parallel work
