# AGENTS.md

## Repository Purpose

`__REPO_NAME__` is a Python workspace repository with per-package projects under
`packages/`.

## Repository Context

- Repository name: `__REPO_NAME__`
- Primary language(s): `Python`
- Runtime/build system: `uv` with shared root tooling and `uv_build` for
  package projects
- Repository type: `workspace`
- Standards source: [repo-standard-kit] — quality gates derive from its
  [quality-gates spec][quality-gates]; review this repository against it
  periodically for standards drift
- Key directories:
  - `packages/`: independently structured package projects
  - `docs/`: durable repository knowledge
  - `scripts/`: workspace-level helpers

## Human And Agent Responsibilities

Humans own:

- workspace scope and package boundaries
- security exceptions and secret handling
- merge and release authority
- approval of breaking cross-package changes

Agents own:

- implementation within package or workspace boundaries
- tests and regression coverage
- docs updates tied to behavior changes
- running repo-wide quality gates

## Workflow

- Long-lived branch: `main`
- Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- Merge via reviewed PRs only
- Keep PRs package-scoped or clearly cross-cutting
- CI must mirror the documented local quality gates

## Quality Gates

Run from repo root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build --all-packages`

The build step is a documented no-op before the workspace contains its first
package, matching the workspace quality workflow.

The quality job's effective permissions must be exactly `contents: read`, and
every remote action or reusable workflow must be pinned to a full 40-character
commit SHA. Keep version comments and GitHub Actions Dependabot configuration
so those pins remain maintainable.

Branch protection must require the separate `quality` and `compliance` status
checks. Quality executes the gate chain; compliance independently checks the
repository against the standard. Keep these canonical names so the same
ruleset applies to every adopting repository.

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
- Keep the `repo-standard-kit` reference in `README.md` and `AGENTS.md`
  current, and check this repository against it periodically

## Repository Layout

- `packages/`: package projects under `packages/<package-slug>/`
- `docs/`: durable workspace knowledge
- `scripts/`: workspace-level helpers

## Change Control Notes

Document cross-package API or dependency rules here when the workspace evolves.

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
