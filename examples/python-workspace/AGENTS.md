# AGENTS.md

## Repository Purpose

`widget-platform` is a Python workspace repo containing multiple package
projects under `packages/`.

## Repository Context

- Repository name: `widget-platform`
- Primary language(s): `Python`
- Runtime/build system: `uv` with shared root tooling
- Repository type: `workspace`
- Key directories:
  - `packages/`: package projects
  - `docs/`: ADRs and workflow docs
  - `scripts/`: workspace helpers

## Human And Agent Responsibilities

Humans own:

- package ownership boundaries
- cross-package API decisions
- release and merge authority

Agents own:

- package-local implementation
- shared tooling updates
- tests and docs updates

## Workflow

- Long-lived branch: `main`
- Keep PRs package-scoped where possible
- Cross-package changes must list impacted packages

## Quality Gates

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`

## Repository Layout

- `packages/widget-api/`: service package project
- `packages/widget-core/`: library package project
- `docs/`: durable workspace documentation
