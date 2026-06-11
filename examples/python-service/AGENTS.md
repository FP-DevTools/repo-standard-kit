# AGENTS.md

## Repository Purpose

`widget-api` exposes a Python service for receiving, validating, and storing
widget payloads.

## Repository Context

- Repository name: `widget-api`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `pyproject.toml`
- Repository type: `service`
- Key directories:
  - `src/`: service code
  - `tests/`: unit and integration tests
  - `docs/`: ADRs and operational workflows

## Human And Agent Responsibilities

Humans own:

- production rollout decisions
- secret handling and environment approvals
- approval of API-breaking changes

Agents own:

- service implementation within repo boundaries
- automated tests and regression coverage
- docs updates for behavior changes

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge through reviewed PRs only
- Prefer small PRs and additive changes

## Quality Gates

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`
7. `uv build`

## Coding Standards

- Keep transport logic separate from domain logic
- Type all production function signatures
- Treat API schemas as stable by default

## Testing Policy

- Logic changes require unit tests
- Handler and storage boundaries require integration tests
- Bug fixes require regression tests

## Documentation Rules

- Update API usage docs when request/response behavior changes
- Add ADRs for significant architecture or operational decisions

## Repository Layout

- `src/`: production service code
- `tests/`: automated tests
- `docs/`: runbooks, ADRs, and workflow docs
- `scripts/`: development and operational helpers

## Change Control Notes

Request or response schema changes require explicit migration notes.
