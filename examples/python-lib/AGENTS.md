# AGENTS.md

## Repository Purpose

`widget-core` provides a typed Python library for validating and transforming
widget payloads used by internal services.

## Repository Context

- Repository name: `widget-core`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `pyproject.toml`
- Repository type: `library`
- Key directories:
  - `src/`: reusable library code
  - `tests/`: unit and integration tests
  - `docs/`: ADRs and public usage notes

## Human And Agent Responsibilities

Humans own:

- release management
- approval of public API breaking changes
- security review for dependency changes

Agents own:

- implementation and refactors inside `src/`
- tests for behavior and regressions
- README and ADR updates when behavior changes

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge through reviewed PRs only
- Keep PRs single-purpose

## Quality Gates

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`
7. `uv build`

## Coding Standards

- Public APIs under `src/widget_core/` must remain backward compatible by
  default
- Type all public function signatures
- Keep parsing I/O separate from domain transformations

## Testing Policy

- Add unit tests for transformation logic
- Add regression tests for bug fixes
- Add integration tests when file or network boundaries are introduced

## Documentation Rules

- Update `README.md` for public API usage changes
- Add ADRs for significant architectural changes

## Repository Layout

- `src/`: library code
- `tests/`: automated tests
- `docs/`: durable project knowledge
- `scripts/`: development helpers only

## Change Control Notes

Breaking changes to public symbols require migration notes in `README.md`.
