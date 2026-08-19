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

`should` findings are non-blocking by design, everywhere `repo-check` runs —
the CLI's default exit code, the pre-commit hook (`.pre-commit-hooks.yaml`
passes no `--strict`), and the reusable CI workflow (`strict` defaults to
`false`) all agree on this. They are visible in every output format, just
never the reason a run fails, unless something explicitly opts into
`--strict`.

## Consumption Surfaces

Three ways to run `repo-check` against a repository, from lowest to highest
commitment. **Pick one, not several.** In particular, the pre-commit hook and
the reusable CI workflow both run the full check — CI already re-runs the
pre-commit hook (see §5, "Local gate verification"), so wiring in both means
`repo-check` runs twice on every pull request for no additional coverage.
Prefer the pre-commit hook; reach for the reusable CI workflow instead of it
only for a repository that does not want `repo-check` as a pre-commit
dependency at all.

### Ad hoc

No setup: the command shown above, or pinned to a released version:

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git@v1.0.0" repo-check
```

### Local pre-commit hook

This repository ships `.pre-commit-hooks.yaml`, so `pre-commit` can install
and run `repo-check` without the consuming repository declaring it as a
dependency. Add to the consuming repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/FP-DevTools/repo-standard-kit
    rev: v1.0.0
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
    uses: FP-DevTools/repo-standard-kit/.github/workflows/compliance.yml@v1.0.0
    with:
      ref: v1.0.0
```

`ref` is required and must match the pin in `uses:`. GitHub Actions does not
give a called reusable workflow a reliable way to read that pin from inside
itself — an earlier version of this workflow tried the `GITHUB_WORKFLOW_REF`
self-resolution trick and it silently installed the wrong ref in a live
cross-repo test, so the caller states it explicitly instead. Add `with: {
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
| `RSK007` | Mandatory pre-commit hooks present (incl. `ty check`) | §4 | shall |
| `RSK008` | `pyproject.toml` uses `uv_build` where a build-system is declared | Repository Contract | shall |
| `RSK009` | `uv.lock` is present | Repository Contract | shall |
| `RSK010` | Ruff `line-length` declared and mandatory rule families selected | §13 | shall |
| `RSK011` | No unresolved `__PLACEHOLDER__` tokens | `repo-standard.md` | shall |
| `RSK012` | `docs/adr/` exists | `repo-layout.md` | should |
| `RSK013` | `docs/`, `README.md`, `AGENTS.md` wrap at the prose width | §13 | should |
| `RSK014` | Branch protection configured on `main` | §10 | platform |
| `RSK015` | Ruff `line-length` matches the recommended value (`88`) | §13 | should |
| `RSK016` | Recommended rule family `PT` is selected | §13 | should |

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
