# Compliance Checking

`repo-check` evaluates a repository against the compiled form of the canonical
YAML policy. It checks structural facts; it does not certify engineering
quality or replace review judgement.

## Running It

```bash
uvx --from "git+ssh://git@github.com/FP-DevTools/repo-standard-kit.git" repo-check
uv run repo-check /path/to/repository
```

Options:

- `--format text|json` selects human-readable or stable machine output.
- `--profile auto|python-single|python-workspace` selects an explicit override.
- `--check-enforcement` also queries classic branch protection or effective
  active rulesets for RSK014.
- `--strict` promotes recommended findings to failures.

Exit code `0` means no blocking findings. Exit code `1` means a required rule
failed, or a recommended rule failed under `--strict`. Exit code `2` is a
usage or indeterminate command error, including an explicitly requested
platform check whose evidence could not be obtained.

Required findings fail by default. Recommended findings are always visible but
fail only under `--strict`; this behavior is unchanged from the pre-v1 `shall`
and `should` contract.

## Profile Resolution

Resolution is deterministic:

1. an explicit `--profile` override;
2. valid repository metadata;
3. policy-owned auto-detection metadata.

Every adopting repository declares:

```toml
[tool.repo-standard]
profile = "python-single" # or "python-workspace"
standard = "1"
```

An explicit declaration wins even when conflicting markers such as
`packages/` exist. Missing metadata, an unknown profile, or a standard-major
mismatch produces required RSK019, while auto-detection still lets all other
checks execute for the best deterministic profile.

## Findings And JSON Compatibility

Every finding includes the rule ID, title, canonical level, path and line when
available, message, actual value, expected value, remediation, and status.
The JSON `severity` field remains present through v1 for existing consumers:
`required` derives `shall`, `recommended` derives `should`, and an unavailable
platform command derives the legacy `platform` value plus
`status: "indeterminate"`.

YAML and TOML parse failures report parser locations. Workflow findings report
the relevant node line when PyYAML exposes one.

## Suppressing A Rule

The v1 exception shape remains deliberately small:

```toml
[tool.repo-check.ignore]
RSK005 = "This repository is the standard's own home."
```

Only a known rule ID with a non-empty string reason suppresses findings. Empty
reasons, unknown IDs, malformed TOML, and non-string values suppress nothing.
Owner, expiry, and reference metadata are deferred beyond v1.

## Consumption Surfaces

Every pull request shall produce an independently enforceable `compliance`
status. This CI check does not replace `quality`: compliance verifies the
standard-owned structure, while quality executes the declared gate chain.

The starter kits and this standards repository all use the canonical
`.github/workflows/compliance.yml` name and emit a `compliance` job. The
standards repository's workflow also remains callable by adopters. A repository
may instead call that reusable workflow from its canonical file, provided the
resulting required status is named `compliance`.

Both adopter forms execute the selected checker with `uvx`. The isolated tool
environment neither reads nor changes the adopter's `uv.lock`, and
`repo-standard-kit` does not belong in the adopter's project dependencies.
Direct pull requests in `repo-standard-kit` are the exception: the root workflow
runs the checked-out implementation with `uv run --locked --no-dev` so changes
to the checker itself receive coverage before release. The reusable workflow
selects these paths from the required `standard-ref` input; it does not use the
inherited event name, which is still `pull_request` when an adopter calls it.

Together with the `quality` job, this gives every adopting repository the same
two required status names and therefore the same branch-protection ruleset.

### Optional pre-commit feedback

The pre-commit hook provides earlier local feedback. When it is configured,
the quality workflow repeats the structural check before the independently
required compliance job; that defense-in-depth duplication is intentional.

```yaml
repos:
  - repo: https://github.com/FP-DevTools/repo-standard-kit
    rev: v1.0.0
    hooks:
      - id: repo-check
```

### Required CI workflow

```yaml
name: Compliance

on:
  pull_request:

jobs:
  compliance:
    uses: FP-DevTools/repo-standard-kit/.github/workflows/compliance.yml@<full-sha>
    with:
      standard-ref: v1.0.0
```

The reusable workflow itself SHALL be pinned to a full commit SHA. That
immutable `uses:` reference selects the workflow implementation the caller
trusts. The distinct `standard-ref` input selects the released
`repo-standard-kit` revision whose packaged checker and compiled policy are
executed. A commit SHA gives the strongest reproducibility. A human-readable
release tag such as `v1.0.0` is permitted only when repository governance keeps
release tags immutable.
The workflow passes that input through the environment, validates it against a
narrow Git-ref character allowlist, and never interpolates caller-controlled
inputs directly into Bash source. Confirm the caller emits the required
`compliance` status.

`--check-enforcement` remains a distinct, authenticated platform audit. Enable
the reusable workflow's `check-enforcement` input only when the job has GitHub
CLI authentication and the repository plan exposes branch protection or
rulesets. A green default `compliance` job proves structural alignment; it does
not prove that GitHub requires `quality` and `compliance` before merge.

The isolated `uvx` path is portable within the maintained profiles, not fully
hermetic or universal: it currently assumes GitHub Actions on `ubuntu-latest`,
network access to this repository and PyPI, and the pinned checkout and
setup-uv actions.

## Canonical Policy And Generation

`policy/base.yaml` and `policy/profiles/` are the sole source of every
machine-enforced value. Strict models reject unknown fields, bad types,
duplicate or unordered rule IDs, unrecorded gaps, unknown profiles, invalid
source references, and unregistered check kinds. Policy YAML is loaded with
`yaml.safe_load`.

Run:

```bash
uv run python scripts/generate_policy.py
```

It deterministically produces:

- `src/repo_standard/policy/compiled.json`, the wheel runtime artifact;
- `docs/policy-reference.md`, the normative human-readable catalogue.

Runtime checks dispatch through the `check.kind` registry. Handlers receive
typed configuration and never own rule IDs, levels, applicability, titles, or
remediation. Markdown explains policy but supplies no executable values.

## Structural Boundaries

- GitHub Actions are parsed with safe GitHub-compatible YAML semantics, so
  `on` remains a string. RSK006 inspects only executable
  `jobs.quality.steps[*].run` nodes. Comments, echo, unrelated fields, and
  shell-wrapper strings do not satisfy commands.
- Pre-commit is parsed structurally. RSK007 matches hook IDs, normalized entry
  and argument tokens, and policy-owned material fields such as filters and
  `pass_filenames`.
- RSK003 compares the standalone inline-code list entries under
  `## Quality Gates` with the exact ordered chain for the resolved profile.
  Commands elsewhere in AGENTS.md do not count, and unrelated section prose is
  not scored.
- RSK020 requires the quality job's effective permissions to exactly match the
  policy-owned `contents: read` mapping; extra read scopes and all write scopes
  fail. RSK021 requires full SHA pins for remote actions and reusable workflows
  in every job in the quality workflow; local and Docker actions are exempt.
- RSK014 requires pull request protection, stale approval dismissal, required
  status checks, strict up-to-date branches, conversation resolution, and
  administrator enforcement when platform checks are requested, but permits a
  zero approval count. RSK022 separately recommends at least one approving
  review. If classic branch protection is absent, both checks evaluate active
  repository and organization rulesets; RSK014 also requires visible, empty
  bypass actor lists.

## What This Cannot Check

- Whether prose is thoughtful rather than generic beyond known bootstrap
  tokens.
- Whether a test suite or review is meaningful.
- Whether an exception reason is wise, approved, or still timely.
- Human-owned release, product, architectural, and security decisions.

Vulnerability scanning remains optional in v1.0. Mandatory scanning, SAST,
SBOMs, signing, richer exception metadata, and non-Python profiles are deferred.
