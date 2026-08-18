# Repository Development Standard

## Scope Of This Document

This is the normative entry point for the standard. It states what a repository
must provide to be considered aligned, and indexes the companion documents that
expand each area in detail. Start here, then follow the index below.

It governs repositories that *adopt* the standard. The `README.md` at the root
of `repo-standard-kit` is a non-normative guide to using the kit's tooling and
does not define rules.

## Purpose

This standard defines the baseline operating model for a repository developed by
humans and agents together, covering repository structure, collaboration
workflow, quality gates, coding standards, and repository-level guidance through
`AGENTS.md`.

## Applicability

This standard is intended to be portable. A repository may adopt it directly or
adapt it through its own `AGENTS.md`, but the resulting guidance must remain
concrete and actionable.

## Repository Contract

Every repository adopting this standard should provide:

- a concrete `AGENTS.md`
- a user-facing `README.md`
- an explicit, linked reference to `repo-standard-kit` in both `README.md`
  and `AGENTS.md`, so the repository's alignment with the standard can be
  audited periodically
- exact quality-gate commands
- a CI workflow that runs the same quality gates
- branch protection on `main` that makes those gates binding rather than
  advisory, as specified in `docs/quality-gates.md`
- alignment with `docs/quality-gates.md` for mandatory local and CI quality gates
- a documented repository layout
- clear API, schema, or migration rules where relevant
- `uv` as the default Python package manager and build backend

## Core Rules

- Use a trunk-based PR workflow by default.
- Keep public interfaces stable unless a deliberate breaking change is approved.
- Document exact quality-gate commands in the repository's `AGENTS.md`.
- Treat typing, tests, and docs as part of the implementation, not optional
  polish.
- Keep operational boundaries explicit: product intent and release authority
  remain human-owned.
- Reference `repo-standard-kit` explicitly in `README.md` and `AGENTS.md` so
  standards drift can be checked against it periodically.
- Do not claim support for a language profile in starter kits, tooling, or
  docs until that profile is fully documented and maintained. Python is the
  only such profile today.

## Required Companion Documents

These documents are normative alongside this one. Together with this document
they are the complete normative set; anything else in `repo-standard-kit`,
including its `README.md`, templates, and starter kits, implements them.

- `docs/quality-gates.md`: the mandatory local and CI gate chain
- `docs/agent-operating-model.md`: human and agent decision boundaries
- `docs/git-workflow.md`: branching, collaboration, and history rules
- `docs/repo-layout.md`: canonical directory layout and scope boundaries
- `docs/bootstrap-workflow.md`: how new repositories are generated
- `profiles/python-single.md`: single-package Python repositories
- `profiles/python-workspace.md`: Python monorepos with `packages/`

Where a companion document conflicts with this one, this document governs.

## Required `AGENTS.md` Sections

Every target repository should include:

1. Repository Purpose
2. Repository Context
3. Human And Agent Responsibilities
4. Workflow
5. Quality Gates
6. Coding Standards
7. Testing Policy
8. Documentation Rules
9. Repository Layout
10. Change Control Notes

Committed copies must not contain placeholders or generic filler text.
