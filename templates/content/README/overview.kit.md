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

### Current Profiles

- `python-single`: one package rooted at `src/<package_name>/`
- `python-workspace`: monorepo with per-package projects under `packages/`

Python is the only supported language today. The generated
[policy profile catalogue](docs/policy-reference.md#profiles) is authoritative;
other languages are added only once their policy profile is maintained.
