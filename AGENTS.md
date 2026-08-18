# AGENTS.md

## Repository Purpose

This repository defines portable standards, starter kits, and bootstrap tooling
for creating and maintaining software repositories with clear human and agent
operating boundaries.

## Repository Context

- Primary focus: repository standards and Python starter assets
- Normative entry point: `docs/repo-standard.md`, which indexes every other
  normative document
- Normative quality gates: `docs/quality-gates.md`
- Directory responsibilities: see Repository Layout below

## Human And Agent Responsibilities

Humans own:

- product direction for the standard
- approval of breaking changes to the standard contract
- release and publication decisions
- language-profile expansion decisions

Agents own:

- writing and updating the standards docs
- implementing bootstrap tooling
- keeping templates and starter assets aligned with the standard

Agents must not:

- invent profile rules that are not documented in the standard
- weaken the documented quality baseline without explicit instruction
- add a first-class language profile without complete documentation and starter
  assets

## Workflow

1. Update the normative docs first when changing the standard.
2. Update templates and starter kits in the same change.
3. Validate the bootstrap tool against a temporary output directory.
4. Keep changes small and focused by concern.

## Quality Gates

Run from repository root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`
7. `uv build`
8. `uv run repo-init --profile python-single --output-dir /tmp/demo-repo --no-install`

## Coding Standards

- Keep reusable Python logic under `src/`
- Type production function signatures
- Keep starter assets and tests aligned with the documented standard

## Testing Policy

- Changes to bootstrap behavior require automated tests in `tests/`
- Bug fixes require regression coverage
- Generated starter output must be validated when the starter changes

## Repository Layout

- `src/repo_standard/`: bootstrap implementation
- `src/repo_standard/starter_kits/`: starter repo skeletons, the single source
  of starter assets for both source checkouts and installed builds
- `tests/`: automated tests
- `docs/`: normative standards
- `profiles/`: language-specific profiles
- `templates/`: reusable templates for adopting the standard in an existing repo

## Documentation Rules

- Changes to standards must update the corresponding document in `docs/`
- Changes to templates or starter kits must stay consistent with each other
- New operating rules belong in docs before they appear in starter assets
