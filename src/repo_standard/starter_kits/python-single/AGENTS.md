# AGENTS.md

## Repository Purpose

`__REPO_NAME__` exists to `__DESCRIPTION__`.

## Repository Context

- Repository name: `__REPO_NAME__`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `uv_build` in `pyproject.toml`
- Repository type: `__REPO_TYPE__`
- Standards source: [repo-standard-kit] — quality gates derive from its
  [quality-gates spec][quality-gates]; review this repository against it
  periodically for standards drift
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
- CI must mirror the documented local quality gates

## Quality Gates

Run from repo root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build`

The quality workflow must grant effective `contents: read` permission with no
write permissions, and pin every remote action or reusable workflow to a full
40-character commit SHA. Keep version comments and GitHub Actions Dependabot
configuration so those pins remain maintainable.

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
- Keep the `repo-standard-kit` reference in `README.md` and `AGENTS.md`
  current, and check this repository against it periodically

## Repository Layout

- `src/`: production package code
- `tests/`: automated tests
- `docs/`: durable project knowledge
- `scripts/`: developer helpers, not core business logic

## Change Control Notes

Document API, schema, or migration-specific rules here when the repository
introduces them.

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
