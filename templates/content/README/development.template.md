This repository declares its machine-enforced standard contract in
`pyproject.toml`:

```toml
[tool.repo-standard]
profile = "<python-single or python-workspace>"
standard = "__STANDARD_MAJOR__"
```

See `AGENTS.md` for the full repo-level contract (human/agent
responsibilities, workflow rules, coding standards). This section covers what
a new contributor needs first.

This README's section order is not a convention to remember: it is RSK023,
whose canonical section list lives in the kit's `policy/shapes.yaml` and is
published in the [policy reference][policy-reference]. Run `repo-check .` after
editing this file and it names any section that is missing or out of order;
`repo-adopt .` inserts the required ones. This file is a rendering of that
shape, not the source of it.

### Set Up Your Dev Environment

1. Clone the repo and run `uv sync --locked`.
2. Run `uv run pre-commit install`.
3. Run `uv run pre-commit run --all-files` to confirm a clean baseline.
4. Copy `.env.example` to `.env` (if present) and fill in local config.

### Guidelines

- Follow the workflow and standards in `AGENTS.md`.
- Trunk-based development: short-lived branches off `main`, merged via
  reviewed PRs only. Branch prefixes: `feat/`, `fix/`, `refactor/`, `docs/`,
  `chore/`.
- Keep PRs small and single-purpose.
- Type all production function signatures; keep I/O boundaries explicit.
- Tests are part of the change, not follow-up work: logic changes need unit
  tests, boundary changes need integration tests, bug fixes need regression
  tests.
- Update `README.md` when setup or usage changes; update `AGENTS.md` when
  operating rules change; add an ADR under `docs/adr/` for significant
  architecture decisions.

### Quality Gates

The mandatory gate chain is listed in `AGENTS.md`, which is the one place this
repository states it, and runs in CI on every PR to `main`
(`.github/workflows/quality.yml`). A separate
`.github/workflows/compliance.yml` job checks that the repository and quality
workflow still match repo-standard-kit. Run the gate chain locally before
pushing.

No PR merges into `main` unless both `quality` and `compliance` pass, and
branch protection enforces that rather than convention — see the
[quality-gates spec][quality-gates]. Temporary exemptions require explicit
justification in the PR and maintainer approval, and must stay time-limited.

### Dependency Management

- `uv` is the only supported package manager; `pyproject.toml` and `uv.lock`
  are the source of truth. Commit `uv.lock`.
- Add a runtime dependency: `uv add <package>`.
- Add a dev-only dependency: `uv add --group dev <package>`.
- Upgrade a dependency: `uv lock --upgrade-package <package>` then
  `uv sync --locked`.
- `uv run deptry .` and `uv run pip-audit` are recommended for dependency
  hygiene and vulnerability scanning (see the [quality-gates spec][quality-gates]).
- Workspace repos: each package under `packages/<slug>/` declares its own
  dependencies; the root `pyproject.toml` is tooling-only.
