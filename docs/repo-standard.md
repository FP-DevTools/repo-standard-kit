# Repository Development Standard

## Purpose

This standard defines the baseline operating model for a software repository
developed by humans and agents together. It focuses on practical repository
structure, collaboration workflow, quality gates, coding standards, and
repository-level guidance through `AGENTS.md`.

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
- alignment with `spec.md` for mandatory local and CI quality gates
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

## Required Companion Documents

Use these documents together:

- `spec.md`
- `docs/agent-operating-model.md`
- `docs/git-workflow.md`
- `docs/repo-layout.md`
- `docs/bootstrap-workflow.md`
- `profiles/python-single.md`
- `profiles/python-workspace.md`

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
