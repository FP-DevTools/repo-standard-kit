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

1. Update canonical YAML policy and its explanatory normative docs together
   when changing a machine-enforced rule.
2. Update templates and starter kits in the same change.
3. After changing `policy/` or a policy-linked normative section, run
   `uv run python scripts/generate_policy.py` and commit the regenerated
   `src/repo_standard/policy/compiled.json` and `docs/policy-reference.md`;
   `uv run pytest` fails otherwise.
4. Validate bootstrap behavior with `uv run pytest`, which generates into a
   temporary directory rather than a fixed path.
5. Keep changes small and focused by concern.

## Quality Gates

Run from repository root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build`

The quality workflow must grant effective `contents: read` permission with no
write permissions, and pin every remote action or reusable workflow to a full
40-character commit SHA. Keep version comments and GitHub Actions Dependabot
configuration so those pins remain maintainable.

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
- `templates/`: reusable templates for adopting the standard in an existing repo

## Documentation Rules

- Changes to standards must update the corresponding document in `docs/`
- Changes to templates or starter kits must stay consistent with each other
- New operating rules belong in docs before they appear in starter assets

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
