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

### Goal

Define clear decision boundaries between humans and agents so implementation
work can move quickly without ambiguity or accidental overreach.

### Human Responsibilities

Humans own:

- product scope and intent
- security exceptions and secret handling
- merge and release authority
- production access and production operations sign-off
- approval of breaking API, schema, or migration changes
- architectural exceptions to the documented standard

### Agent Responsibilities

Agents own:

- implementation within documented repository boundaries
- tests, regression coverage, and local verification
- documentation updates tied to behavior changes
- starter-kit and template maintenance
- surfacing risks, missing decisions, and unclear contracts

### Shared Expectations

- Keep code, tests, and docs aligned
- Prefer small, reviewable changes
- Make operational boundaries explicit
- Do not rely on undocumented local knowledge

### Agent Prohibitions

Agents must not:

- bypass documented quality gates
- weaken typing or test expectations without explicit instruction
- make security, release, or breaking-change decisions alone
- modify out-of-scope systems without explicit approval

## Agent Operating Mode

Agent behaviour in this repository is calibrated, not left to model defaults.
Each dial runs from 1 to 5, where 5 is the maximum:

- **Verbosity:** 2 / 5
- **Precision, repeatability, determinism:** 4 / 5

Low verbosity means:

- Answer what was asked; do not restate the request or read the plan back
- Report outcomes, not a narration of the steps taken to reach them
- Prefer a diff, a command, or a `path:line` reference over prose describing it
- Open with the result; no preamble, and no recap the transcript already shows
- Spend words on decisions the reader must make, on risks, and on failures

High precision, repeatability, and determinism mean:

- Verify against the repository before asserting, and cite `path:line`
- Reuse the pattern already in the file rather than introducing a second one
- Make the smallest change that satisfies the requirement, and nothing beyond it
- Run the documented quality gates in order and report their real output
- Pin versions, ordering, and formatting rather than leaving them to chance
- State assumptions explicitly where the repository does not settle a choice
- The same task on the same input should reach the same result on a second run

The levels are policy values, not prose: `repo-check` reports drift from them
and `repo-adopt` restores them.

## Single Source Of Truth

Anything stated twice drifts, and the copy that drifts is the one nobody is
reading when it matters. Before writing, look for what already exists and
derive from it.

- **One home per fact.** A value, a command, a version, a path, a section
  order, a schema: declared in exactly one place, with every other use reading
  from that place
- **Derive, do not copy.** Where two artefacts must agree, generate one from
  the other or both from a shared source, and put the check that they still
  agree in the quality gates
- **Reference, do not restate.** Link to the document that owns a subject
  instead of summarising it somewhere it will go stale
- **Extend rather than parallel.** A second helper, constant, fixture, config
  key, or type that means what an existing one means is duplication even when
  the wording differs — change the original instead
- **Make unavoidable duplication fail loudly.** Where a copy cannot be removed,
  add a test or check that regenerates it and compares, so drift is a failure
  rather than a surprise
- **Deleting the stale copy is part of the change** that made it stale, not a
  follow-up

This applies to code, configuration, documentation, fixtures, and data alike.
When a change means editing the same fact in more than one file, treat that as
the defect to fix first.

## Workflow

### Default Model

Use trunk-based development with pull requests.

### Branching Rules

- `main` is the primary long-lived integration branch and is always releasable
- work happens on short-lived branches
- use one branch per objective
- branch prefixes:
  - `feat/`
  - `fix/`
  - `refactor/`
  - `docs/`
  - `chore/`

### Staging Multi-Phase Work

Prefer additive changes or feature flags directly on `main` for incomplete
work. When a feature's parts are not individually releasable and that is not
viable, a repository may maintain `develop` as a second long-lived
integration branch to stage it. Using `develop` at all is optional per
repository; a repository that keeps `main` as its only long-lived branch is
equally aligned with this standard.

When a repository does maintain `develop`:

- short-lived branches for that feature target `develop`, not `main`
- the staged work reaches `main` one of two ways, chosen once per feature
  and not mixed partway through:
  - `develop` merges to `main` directly, as a single reviewed pull request,
    once the staged work is complete; or
  - a release branch cut from `develop`'s tip carries its accumulated
    commits forward, plus the release-finalizing work (a version bump, a
    changelog entry), to `main` in its own reviewed pull request

### Parallel Collaboration

- prefer small PRs over long-lived branches
- use stacked PRs when a larger change needs sequencing
- rebase private branches frequently to reduce drift
- avoid multiple concurrent branches changing the same subsystem without
  coordination

### History Rules

- rebasing private branches is allowed
- rewriting shared branches is not allowed
- merge through reviewed PRs only
- cut releases from `main` with tags

## Quality Gates

Run from repo root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build --all-packages`

The build step fails until `packages/` holds its first package: on an empty
workspace it exits 2 with `Workspace does not contain any buildable packages`.
Add a package with `repo-add-package` and the chain passes. The quality
workflow guards that step behind `compgen -G "packages/*/pyproject.toml"`, so
CI skips it meanwhile; the chain above is listed unguarded because it is the
exact chain the standard declares.

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
