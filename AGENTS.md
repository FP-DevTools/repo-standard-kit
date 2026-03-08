# AGENTS.md

## Repository Purpose

This repository defines portable standards, starter kits, and bootstrap tooling
for creating and maintaining software repositories with clear human and agent
operating boundaries.

## Repository Context

- Primary focus: repository standards and Python-first starter assets
- Secondary focus: future JavaScript/TypeScript profile scaffolding
- Key directories:
  - `src/`: implementation code for bootstrap tooling
  - `tests/`: automated verification for the tooling
  - `docs/`: normative standards
  - `profiles/`: language-specific standards
  - `templates/`: reusable file templates
  - `starter-kits/`: starter repository skeletons
  - `examples/`: concrete filled examples

## Human And Agent Responsibilities

Humans own:

- product direction for the standard
- approval of breaking changes to the standard contract
- release and publication decisions
- language-profile expansion decisions

Agents own:

- writing and updating the standards docs
- maintaining templates and starter assets
- implementing bootstrap tooling
- keeping examples aligned with the standard

Agents must not:

- invent profile rules that are not documented in the standard
- weaken the documented quality baseline without explicit instruction
- add a first-class language profile without complete documentation and starter
  assets

## Workflow

1. Update the normative docs first when changing the standard.
2. Update templates, starter kits, and examples in the same change.
3. Validate the bootstrap tool against a temporary output directory.
4. Keep changes small and focused by concern.

## Quality Gates

Run from repository root:

1. `uv sync`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`
7. `uv run repo-init --profile python-single --output-dir /tmp/demo-repo --no-install`

## Coding Standards

- Keep reusable Python logic under `src/`
- Keep `tools/` wrappers thin and orchestration-focused
- Type production function signatures
- Keep starter assets and tests aligned with the documented standard

## Testing Policy

- Changes to bootstrap behavior require automated tests in `tests/`
- Bug fixes require regression coverage
- Generated starter output must be validated when the starter changes

## Repository Layout

- `src/`: bootstrap implementation
- `tests/`: automated tests
- `docs/`: normative standards
- `profiles/`: language-specific profiles
- `templates/`: reusable templates
- `starter-kits/`: starter repo skeletons
- `examples/`: filled examples

## Documentation Rules

- Changes to standards must update the corresponding document in `docs/`
- Changes to templates or starter kits must keep examples consistent
- New operating rules belong in docs before they appear in starter assets
