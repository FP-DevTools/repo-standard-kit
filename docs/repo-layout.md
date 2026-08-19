# Repository Layout

## Canonical Python Layout

Use this layout by default for Python repositories:

- `AGENTS.md`
- `README.md`
- `CHANGELOG.md`
- `LICENSE`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `src/<package_name>/`
- `tests/`
- `docs/adr/`
- `docs/diagrams/`
- `scripts/`
- `examples/` when useful

## Directory Responsibilities

- `src/`: production code only
- `tests/`: test code only
- `docs/`: durable project knowledge
- `docs/adr/`: architecture decisions
- `docs/diagrams/`: workflow or architecture diagrams
- `scripts/`: developer or operational helpers, not core business logic
- `examples/`: user-facing or integration examples when they add value

## Scope Boundaries

- Reusable logic belongs in `src/`
- Scripts may orchestrate but should not own durable domain logic
- Tests should exercise public behavior and integration boundaries
- Docs should explain workflows, contracts, and decisions that matter over time
