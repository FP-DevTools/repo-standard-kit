# Compliance Checking

`repo-check` verifies that a repository is *structurally* aligned with
`docs/repo-standard.md` and `docs/quality-gates.md`. It does not certify that
a repository is well-engineered — see "What This Cannot Check" below.

## Running It

Against the current directory:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-check
```

Or, inside a checkout with the dev dependency group installed:

```bash
uv run repo-check /path/to/repository
```

Options:

- `--format text|json`: `json` is for aggregating results across repositories.
- `--profile auto|python-single|python-workspace`: reserved for future
  profile-specific rules; `auto` detects by the presence of `packages/`.
- `--check-enforcement`: also checks branch protection (§10). Needs `gh`,
  network access, and authentication, so it is opt-in.
- `--strict`: treats `should` findings as failures too.

Exit codes: `0` aligned, `1` a `shall` rule was violated (or a `should` rule
under `--strict`), `2` usage error.

## Consumption Surfaces

Three ways to run `repo-check` against a repository, from lowest to highest
commitment.

### Ad hoc

No setup: the command shown above, or pinned to a released version:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v0.4.0" repo-check
```

### Local pre-commit hook

This repository ships `.pre-commit-hooks.yaml`, so `pre-commit` can install
and run `repo-check` without the consuming repository declaring it as a
dependency. Add to the consuming repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/FP-DevTools/repo-standard-kit
    rev: v0.4.0
    hooks:
      - id: repo-check
```

Pin `rev` to a released tag and bump it deliberately — `pre-commit
autoupdate` turns that into a one-line PR. The hook always runs (it inspects
the whole tree, not the files staged in a commit) and does not fail the
commit for `should` findings unless `args: [--strict]` is added.

### Reusable CI workflow

This repository's `.github/workflows/compliance.yml` triggers on
`workflow_call`. A consuming repository adds its own workflow that calls it:

```yaml
name: Compliance

on:
  pull_request:

jobs:
  compliance:
    uses: FP-DevTools/repo-standard-kit/.github/workflows/compliance.yml@v0.4.0
```

The called workflow installs `repo-check` at the same ref it was called
with, so nothing needs to be kept in sync by hand. Pass `with: { ref: ... }`
to override that resolution if it ever proves unreliable, and `with: {
strict: true }` or `with: { check-enforcement: true }` to opt into the
stricter modes described above.

## How It Stays Honest

The rule catalogue is not hand-maintained prose duplicating the spec. It is
parsed out of `docs/quality-gates.md` and `docs/repo-standard.md` by
`src/repo_standard/compliance/spec.py`, frozen into
`src/repo_standard/compliance/rules.json` by `scripts/generate_rules.py`, and
shipped inside the package so `repo-check` needs no access to `docs/` at
runtime. `tests/test_compliance.py` fails if `rules.json` drifts from what
regenerating it would produce (§6 Generated Artifact Consistency) — editing a
normative document without running the generator fails the suite instead of
drifting silently.

## The Check Catalogue

Every rule traces to a normative sentence. Severity follows the
specification's own vocabulary: `shall` maps to an error, `should` to a
warning. Rules marked `platform` need `gh`, network, and auth, so they sit
behind `--check-enforcement`.

| ID | Rule | Source | Severity |
| --- | --- | --- | --- |
| `RSK001` | `AGENTS.md` exists | Repository Contract | shall |
| `RSK002` | All required `AGENTS.md` sections present | `repo-standard.md` | shall |
| `RSK003` | `AGENTS.md` states the exact gate chain | §5 | shall |
| `RSK004` | `README.md` exists | Repository Contract | shall |
| `RSK005` | Both reference repo-standard-kit | `repo-standard.md` | shall |
| `RSK006` | `quality.yml` runs the full gate chain | §5 | shall |
| `RSK007` | Mandatory pre-commit hooks present | §4 | shall |
| `RSK008` | `pyproject.toml` uses `uv_build` where a build-system is declared | Repository Contract | shall |
| `RSK009` | `uv.lock` is present | Repository Contract | shall |
| `RSK010` | Ruff `line-length` and `select` match the baseline | §13 | shall |
| `RSK011` | No unresolved `__PLACEHOLDER__` tokens | `repo-standard.md` | shall |
| `RSK012` | `docs/adr/` exists | `repo-layout.md` | should |
| `RSK013` | Markdown wraps at the documented prose width | §13 | should |
| `RSK014` | Branch protection configured on `main` | §10 | platform |

## What This Cannot Check

A checker that implies more coverage than it has is worse than one that
admits its limits.

- **"No placeholders or generic filler text"** is decidable for
  `__REPO_NAME__`-shaped tokens and essentially nothing else. Prose quality
  is not mechanically assessable.
- **"Tests are part of the change, not follow-up work"** is a review
  judgement about a diff, not a property of a tree.
- **§11 Exceptions** — whether an exemption was justified, approved, and
  time-limited — is social, not structural.
- **Gate effectiveness.** The checker confirms `uv run pytest` appears in the
  workflow. It cannot tell you the test suite is meaningful.

## Applying `repo-check` To This Repository

`repo-standard-kit` is the standard's own home, not a repository that adopts
it, so two rules do not apply to it the way they apply everywhere else:
`RSK005` would ask this repository to link itself, and `RSK011` flags the
`__PLACEHOLDER__`-shaped tokens this repository defines and tests for
templating, not leftovers from an unfinished bootstrap.
`tests/test_compliance.py` documents this exception explicitly rather than
special-casing it inside the checker.

## Status

`repo-check` is optional tooling, not a mandatory gate. Adopting it does not
require any change under the compatibility policy in `CHANGELOG.md`. Whether
it becomes mandatory in a future release depends on results from piloting it
against real repositories first.
