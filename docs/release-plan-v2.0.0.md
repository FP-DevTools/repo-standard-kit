# Release Plan: v2.0.0 Corrections

This is a working tracker, not part of the standard. It records the audit
findings for `chore/release-v2.0.0`, the decisions taken about them, and the
phase each correction belongs to.

**P7 deletes this file.** It exists to keep seven phases coordinated while the
release branch is open, and `pyproject.toml` ships `docs/**` to adopters, so it
must not survive the tag.

## Context

An audit of `chore/release-v2.0.0` found 22 issues the gates do not catch.
`uv run pytest` passes and `repo-check . --strict` is clean; that is part of
the finding rather than a reassurance.

## Decisions

| | Decision | Consequence |
| --- | --- | --- |
| D1 | Policy owns the permitted guard form for RSK006 | The workspace starter's `compgen` guard becomes canonical; other conditionals are rejected |
| D2 | New rules may land in v2.0.0 | The release is unmade, so a new required rule costs nothing now and a major later |
| D3 | Root `README.md` and `AGENTS.md` become generated | Closes the drift class that produced findings 5 and 6 |
| D4 | New `advisory` policy level; RSK015 moves to it | `line-length = 88` stays visible and stops failing `--strict` |
| D5 | `repo-init` gains `repo-adopt`'s `--no-lock` / `--no-install` split | Bootstrapped repositories stop failing required RSK009 |
| D6 | Drop `load_rules` and the JSON `severity` field | Must land with D4, or `advisory` needs an invented `shall`/`should` value |

## Phases

Each phase is a sub-issue and one PR into `chore/release-v2.0.0`. Critical path
is P3 → P5 → P7; P1, P2, P4 and P6 run alongside it.

| Phase | Scope | Findings | Depends on | Status |
| --- | --- | --- | --- | --- |
| P1 | Factual corrections | 4, 5, 6, 8, 10, 15, 18 | — | In progress |
| P2 | Root documents under the generator | 7 | P1 | Not started |
| P3 | Policy schema: `advisory`, drop `severity` | 19, dead weight | — | Not started |
| P4 | Checker correctness | 13, 14, 20, 22 | — | Not started |
| P5 | Coverage: compliance workflow and shapes | 11, 12, 16, 17 | P3 | Not started |
| P6 | Bootstrap contract and dead weight | 9, 21 | — | In progress |
| P7 | Release finalization | 1, 2, 3 | all | Not started |

P1 precedes P2 so the corrected prose is what gets migrated into fragments,
rather than migrating the defects and fixing them twice.

## Findings Index

Numbers are stable identifiers referenced by the phase table and the sub-issues.

### Release blockers

- **1.** `CHANGELOG.md:58-60` — the 2.0.0 entry says RSK023–025 are
  "recommended as of this commit and are promoted to required later on this
  branch". They are `required` in `policy/base.yaml`. The note contradicts the
  release.
- **2.** `CHANGELOG.md` tail — no `[2.0.0]:` link definition; `[Unreleased]`
  still compares `v1.2.0...HEAD`.
- **3.** `CHANGELOG.md:27-43` — four `Fixed` entries that landed on this
  release branch sit under `[Unreleased]`, above a dated `[2.0.0]` heading.
- **4.** `docs/compliance.md:56,66,75,110,127,209` and
  `docs/quality-gates.md:239` — v1 described as the current release; examples
  pin `v1.2.0`.

### Inaccuracies

- **5.** `README.md:182`, `AGENTS.md:175`, `pyproject.toml:43` — `profiles/`
  was removed in 0.3.0 and is still referenced; `source-include` packages it.
- **6.** `README.md:184-185`, `AGENTS.md:178-179` — sentence ends in a dangling
  "by hand" clause.
- **7.** `scripts/generate_docs.py:70-82` — root `README.md` and `AGENTS.md`
  are the only governed documents the generator skips, and both defects above
  live in them.
- **8.** `starter_kits/*/.github/workflows/quality.yml:17,20` — v5 pins beside
  a `compliance.yml` pinning v7.0.1 and v10.0.1.
- **9.** `repo_init.py:293-301,364` — `--no-install` skips `uv sync`, so no
  `uv.lock`, so required RSK009 fails on a fresh repository.
- **10.** `docs/bootstrap-workflow.md:170-179` — an eight-step gate chain that
  `docs/quality-gates.md:157-161` rules out and `AGENTS.md:206` says is stated
  once.

### Enforceability gaps

- **11.** Nothing structurally checks `.github/workflows/compliance.yml`,
  though `docs/quality-gates.md:118-122` makes it a SHALL.
- **12.** RSK020 and RSK021 cover `quality.yml` only — the compliance
  workflow's permissions and pins are unchecked, and it is the workflow that
  fetches remote code.
- **13.** RSK006 accepts a command inside a false guard. Verified:
  `if false; then uv build --all-packages; fi` satisfies the rule. The
  workspace starter depends on this, so its build gate never runs.
- **14.** `checks.py:1427-1428` — RSK020 returns no findings on a missing
  workflow while RSK021 returns the error.
- **15.** `docs/repo-layout.md:20-21` — claims required-rule coverage that
  `tests/`, `src/<package_name>/`, `docs/diagrams/` and `scripts/` do not have.
- **16.** RSK011 knows only `__DUNDER__` tokens; `templates/README.md` ships 27
  angle-bracket placeholders with no check.
- **17.** `policy/shapes.yaml:105-137` — the pyproject shape omits
  `[project.scripts]` and `[tool.repo-check.ignore]`, both used by this
  repository.
- **18.** `.pymarkdown.json` relaxes `md024`; `docs/quality-gates.md` §4
  documents only md013, md033 and md036.

### Rules worth reconsidering

- **19.** RSK015 recommends `line-length = 88` while
  `docs/quality-gates.md:440-445` says the value is not prescribed. Resolved by
  D4.
- **20.** `checks.py:1512` — RSK022 reuses the full branch-protection handler,
  so `--check-enforcement` queries the platform twice.
- **21.** RSK005 cannot be satisfied by the standard's own home and is
  suppressed in `pyproject.toml:69`.
- **22.** `checks.py:238-243` — shape order checking dedupes repeated headings,
  so a declared heading repeated out of position is invisible.

### Dead weight

- `checks.py:82-83` — `load_rules`, a compatibility alias for the v0.4 name.
- `models.py:470-473` and `cli.py:90` — the JSON `severity` field, carrying an
  expired "through v1" promise.
- `pyproject.toml:43` — `profiles/**` in `source-include`.
- `docs/diagrams/README.md` — a placeholder shipped into every generated
  repository that no rule references.
