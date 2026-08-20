# AGENTS.md

## Repository Purpose

Describe what this repository exists to do, for whom, and what is out of scope.

## Repository Context

- Repository name: `<repo-name>`
- Primary language(s): `<languages>`
- Runtime/build system: `<runtime>`
- Standards source: [repo-standard-kit] — quality gates derive from its
  [quality-gates spec][quality-gates]; review this repository against it
  periodically for standards drift
- Key directories:
  - `src/`: `<production-code-scope>`
  - `tests/`: `<test-scope>`
  - `docs/`: `<documentation-scope>`

## Human And Agent Responsibilities

Humans own:

- product scope and intent
- security exceptions and secret handling
- merge and release authority
- approval of breaking changes

Agents own:

- implementation within documented repo boundaries
- tests and regression coverage
- docs updates tied to behavior changes
- running documented quality gates

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge via reviewed PRs only
- Keep PRs small and single-purpose
- CI must mirror the documented local quality gates

## Quality Gates

Run from repo root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build`

The quality job's effective permissions must be exactly `contents: read`, and
every remote action or reusable workflow must be pinned to a full 40-character
commit SHA. Keep version comments and GitHub Actions Dependabot configuration
so those pins remain maintainable.

Branch protection must require the separate `quality` and `compliance` status
checks. Quality executes the gate chain; compliance independently checks the
repository against the standard. Keep these canonical names so the same
ruleset applies to every adopting repository.

## Coding Standards

- Type all production function signatures
- Minimize `Any` and justify it when required
- Keep I/O boundaries explicit
- Separate side effects from business logic
- Separate durable logic from scripts
- Preserve public interface stability by default

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

Document any repo-specific API, schema, migration, or operational constraints
here when the repository introduces them.

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
