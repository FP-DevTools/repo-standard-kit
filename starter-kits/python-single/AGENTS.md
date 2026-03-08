# AGENTS.md

## Repository Purpose

`__REPO_NAME__` exists to `__DESCRIPTION__`.

## Repository Context

- Repository name: `__REPO_NAME__`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `pyproject.toml`
- Repository type: `__REPO_TYPE__`
- Key directories:
  - `src/`: production package code
  - `tests/`: automated tests
  - `docs/`: durable repository knowledge

## Human And Agent Responsibilities

Humans own:

- product scope and intent
- merge and release authority
- approval of breaking changes
- security exceptions and secrets

Agents own:

- implementation within documented boundaries
- tests and regression coverage
- docs updates for behavior changes
- running documented quality gates

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge through reviewed PRs only
- Keep PRs focused and small

## Quality Gates

Run from repo root:

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`

## Coding Standards

- Type all production function signatures
- Minimize `Any` and justify it when required
- Keep I/O boundaries explicit
- Separate side effects from business logic

## Testing Policy

- Logic changes require unit tests
- Boundary changes require integration tests
- Bug fixes require regression tests

## Documentation Rules

- Update `README.md` when setup or usage changes
- Update `AGENTS.md` when operating rules change
- Add ADRs for significant architecture decisions

## Repository Layout

- `src/`: production package code
- `tests/`: automated tests
- `docs/`: durable project knowledge
- `scripts/`: developer helpers, not core business logic

## Change Control Notes

Document API, schema, or migration-specific rules here when the repository
introduces them.
