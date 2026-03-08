# AGENTS.md

## Repository Purpose

`__REPO_NAME__` is a Python workspace repository with per-package projects under
`packages/`.

## Repository Context

- Repository name: `__REPO_NAME__`
- Primary language(s): `Python`
- Runtime/build system: `uv` with shared root tooling
- Repository type: `workspace`
- Key directories:
  - `packages/`: independently structured package projects
  - `docs/`: durable repository knowledge
  - `scripts/`: workspace-level helpers

## Human And Agent Responsibilities

Humans own:

- workspace scope and package boundaries
- merge and release authority
- approval of breaking cross-package changes
- security exceptions and secrets

Agents own:

- implementation within package or workspace boundaries
- tests and regression coverage
- docs updates for behavior changes
- running repo-wide quality gates

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge through reviewed PRs only
- Keep PRs package-scoped or clearly cross-cutting

## Quality Gates

Run from repo root:

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`

## Coding Standards

- Shared tool config lives at the repo root
- Package metadata lives in each package's `pyproject.toml`
- Cross-package changes must be explicit and small
- Treat package boundaries as stable by default

## Testing Policy

- Logic changes require unit tests
- Cross-package boundary changes require integration coverage where relevant
- Bug fixes require regression tests

## Documentation Rules

- Update root `README.md` when workspace usage changes
- Add ADRs for significant workspace or package-boundary decisions
- Document package-specific public usage in package-local READMEs

## Repository Layout

- `packages/`: package projects under `packages/<package-slug>/`
- `docs/`: durable workspace knowledge
- `scripts/`: workspace-level helpers

## Change Control Notes

Document cross-package API or dependency rules here when the workspace evolves.
