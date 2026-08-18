# <repo-name>

<One-sentence description: what this repo does and who it's for.>

## At A Glance

| | |
|---|---|
| Type | `<python-single \| python-workspace \| other>` |
| Language | `<Python 3.12+>` |
| Package manager | `<uv>` |
| Status | `<active \| maintenance \| deprecated>` |
| License | `<license-name>` |

## Overview

<2-4 sentences: the problem this repo solves, the primary use case (e.g. data
pipeline, service, library, analysis), and anything explicitly out of scope.
For data repos, note the primary data sources/sinks and what the repo does
NOT own (e.g. "reads from `<source>`, writes curated tables to `<sink>`; does
not own orchestration/scheduling, see `<owning-repo>`").>

## Install

Requires `<Python version range>` and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd <repo-name>
uv sync --locked
```

<If this repo publishes an installable package, also document that path:>

```bash
uv add <package-name>
# or
pip install <package-name>
```

## Quick Start

### Configuration

<List required configuration: environment variables, config files, secrets,
credentials for data sources. Copy `.env.example` to `.env` if applicable.>

| Variable | Required | Default | Description |
|---|---|---|---|
| `<VAR_NAME>` | Yes | — | `<what it controls>` |
| `<VAR_NAME>` | No | `<default>` | `<what it controls>` |

### Common Commands

| Command | Purpose |
|---|---|
| `uv run <entrypoint>` | `<run the app / pipeline / CLI>` |
| `uv run pytest` | Run tests |
| `uv run ruff format . && uv run ruff check .` | Format and lint |
| `uv run ty check` | Type check |
| `uv build` | Build distributable package |

<Add repo-specific commands here, e.g. running a pipeline end-to-end,
regenerating a dataset, or launching a notebook kernel.>

## Repo Structure

Pick the block that matches this repo's profile and delete the other.

**Single-package (`python-single`)**

```
.
├── src/<package_name>/   # production code
├── tests/                # unit and integration tests
├── docs/adr/             # architecture decisions
├── docs/diagrams/        # workflow / architecture diagrams
├── scripts/              # dev or operational helpers (not core logic)
├── AGENTS.md             # repo operating contract: workflow, gates, standards
├── README.md
└── pyproject.toml
```

**Workspace (`python-workspace`)**

```
.
├── packages/<package-slug>/
│   ├── src/<package_name>/
│   └── tests/
├── docs/adr/
├── docs/diagrams/
├── AGENTS.md
├── README.md
└── pyproject.toml        # tooling-only root config
```

<If this is a data repo, note where data-related paths live, e.g.
`data/` (gitignored, local only) or `notebooks/` (exploratory, not
production code), and how they relate to `src/`.>

## Development

See `AGENTS.md` for the full repo-level contract (human/agent
responsibilities, workflow rules, coding standards). This section covers what
a new contributor needs first.

This README's structure follows the [repo-standard-kit] standard — see its
[README template][readme-template]. Keep this file's shape aligned with it
when you update it, and check this repository against it periodically for
standards drift.

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

These are mandatory before merge and run in CI on every PR to `main`
(`.github/workflows/quality.yml`). Run them locally first:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run ruff format --check .`
4. `uv run ruff check .`
5. `uv run ty check`
6. `uv run pytest`
7. `uv build`

No PR merges into `main` unless all mandatory gates pass. Temporary
exemptions require explicit justification in the PR and maintainer approval,
and must stay time-limited.

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

### Deployment

<Describe how and where this repo ships: package registry, container image,
deployment target, and what triggers a release (tag push, manual dispatch,
merge to `main`, etc.). Include rollback steps if non-obvious.>

- Cut releases from `main` with tags: `git tag vX.Y.Z && git push --tags`.
- `<CI/CD pipeline name and what it does on tag push>`

### Compatibility And Versioning

- Supported Python: `<version range>` (see `requires-python` in
  `pyproject.toml`).
- Versioned with [Semantic Versioning](https://semver.org/)
  (`MAJOR.MINOR.PATCH`).
- Public interfaces are stable by default; breaking changes bump `MAJOR` and
  require explicit human approval.
- `<Link to CHANGELOG.md or release notes, if maintained.>`

### Maintainers And Support

- Maintainers: `<names / team, @github-handles>`
- Questions: `<Slack channel, mailing list, or discussion board>`
- Bugs and feature requests: `<issue tracker link>`

### License

Licensed under `<license-name>`. See [LICENSE](LICENSE).

[repo-standard-kit]: https://github.com/FP-DevTools/repo-standard-kit
[quality-gates]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/docs/quality-gates.md
[readme-template]: https://github.com/FP-DevTools/repo-standard-kit/blob/main/templates/README.md
