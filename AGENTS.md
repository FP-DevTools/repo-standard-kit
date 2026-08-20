# AGENTS.md

## Repository Purpose

This repository defines portable standards, starter kits, and bootstrap tooling
for creating and maintaining software repositories with clear human and agent
operating boundaries.

## Repository Context

- Repository name: `repo-standard-kit`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `uv_build` in `pyproject.toml`
- Repository type: `python-single`
- Standards source: this repository is the standard's own home, so it states
  the standard rather than referencing it. `docs/repo-standard.md` is the
  normative entry point and indexes every other normative document;
  `docs/quality-gates.md` states the mandatory gates.
- Key directories:
  - `src/repo_standard/`: bootstrap, policy, and compliance implementation
  - `tests/`: automated tests
  - `docs/`: the standard and its companion documents
  - full responsibilities in Repository Layout below

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

1. Update canonical YAML policy and its explanatory normative docs together
   when changing a machine-enforced rule.
2. Update templates and starter kits in the same change. Never edit
   `templates/{README,AGENTS}.md` or a starter kit's Markdown directly: they
   are generated. Edit the prose fragment under `templates/content/` or, for
   section order, `policy/shapes.yaml`.
3. After changing `policy/` or a policy-linked normative section, run
   `uv run python scripts/generate_policy.py` and commit the regenerated
   `src/repo_standard/policy/compiled.json` and `docs/policy-reference.md`;
   `uv run pytest` fails otherwise.
4. After changing `policy/shapes.yaml` or `templates/content/`, run
   `uv run python scripts/generate_docs.py` and commit the regenerated
   templates and starter-kit documents; `uv run pytest` fails otherwise.
5. Validate bootstrap behavior with `uv run pytest`, which generates into a
   temporary directory rather than a fixed path.
6. Keep changes small and focused by concern.

## Quality Gates

Run from repository root:

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

This is exactly the chain in `docs/quality-gates.md`; this repository adds no
gates of its own. Bootstrap behavior needs no separate manual step — `uv run
pytest` exercises the `repo-init` and `repo-add-package` entry points end to
end in a temporary directory, on every platform.

## Coding Standards

- Keep reusable Python logic under `src/`
- Type production function signatures
- Keep starter assets and tests aligned with the documented standard

## Testing Policy

- Changes to bootstrap behavior require automated tests in `tests/`
- Bug fixes require regression coverage
- Generated starter output must be validated when the starter changes

## Documentation Rules

- Changes to standards must update the corresponding document in `docs/`
- Changes to templates or starter kits must stay consistent with each other
- New operating rules belong in docs before they appear in starter assets

## Repository Layout

- `src/repo_standard/`: bootstrap implementation
- `src/repo_standard/starter_kits/`: starter repo skeletons, the single source
  of starter assets for both source checkouts and installed builds
- `src/repo_standard/policy/`: strict models and compiled runtime policy
- `src/repo_standard/compliance/`: the `repo-check` dispatcher and handlers; see
  `docs/compliance.md`
- `scripts/`: developer scripts, including `generate_policy.py`
- `tests/`: automated tests
- `docs/`: normative standards
- `profiles/`: language-specific profiles
- `policy/`: canonical machine-enforced policy and profile detection metadata
- `templates/`: reference documents rendered from the shapes, plus the
  `content/` prose fragments they are rendered from
  by hand

## Change Control Notes

This repository's public interface is the standard itself, so a change here
can put an already-aligned repository out of alignment.

- Every release records its impact in `CHANGELOG.md` under **Adopters must**,
  following the compatibility policy stated there. A change that forces work
  in an adopting repository is a MAJOR bump.
- Adding a mandatory gate to `docs/quality-gates.md`, or a required section to
  the `AGENTS.md` contract in `docs/repo-standard.md`, is a breaking change
  and needs explicit human approval.
- Keep `version` in `pyproject.toml` in step with the release tag; adopters
  pin by Git ref, so a tag that disagrees with the package is a defect.
- Relaxing a documented gate requires explicit instruction, never an
  incidental edit.
