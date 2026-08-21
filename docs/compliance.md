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
- `--strict` promotes recommended findings to failures. It does not promote
  advisory findings.
- `--version` prints the running `repo-check` package version and the
  `standard_version` and standard major compiled into its policy, then exits.
  Adopters pin the checker by Git ref, so this is how a disputed finding is
  attributed to a revision.

Exit code `0` means no blocking findings. Exit code `1` means a required rule
failed, or a recommended rule failed under `--strict`. Exit code `2` is a
usage or indeterminate command error, including an explicitly requested
platform check whose evidence could not be obtained. Only a finding whose
`status` is `violation` can produce exit code `1`.

Required findings fail by default. Recommended findings are always visible but
fail only under `--strict`. Advisory findings are always visible and never
affect the exit code, because the underlying decision belongs to the
repository; `docs/repo-standard.md` defines the three levels.

## Profile Resolution

Resolution is deterministic:

1. an explicit `--profile` override;
2. valid repository metadata;
3. policy-owned auto-detection metadata.

Every adopting repository declares:

```toml
[tool.repo-standard]
profile = "python-single" # or "python-workspace"
standard = "2"
```

An explicit declaration wins even when conflicting markers such as
`packages/` exist. Missing metadata, an unknown profile, or a standard-major
mismatch produces required RSK019, while auto-detection still lets all other
checks execute for the best deterministic profile.

## Findings And JSON Compatibility

Every finding includes the rule ID, title, canonical level, path and line when
available, message, actual value, expected value, remediation, and status.
`level` is the sole name for how binding the *rule* is, and `status` reports
what *this* finding is:

- `violation` — the rule failed. The only status that can reach exit code `1`.
- `indeterminate` — an explicitly requested platform command produced no
  usable evidence. Exit code `2`.
- `suppressed` — an exemption silenced the findings this rule produced.
  Reported below, and never blocking.
- `unused-exemption` — the rule passed while an exemption for it was declared.
  Reported below, and never blocking.

`level` never changes to express one of these; a finding for a required rule
reports `required` whatever its status. The legacy `severity` field that
restated `level` as `shall` or `should`, and an unavailable platform command
as `platform`, is removed in v2; read `level` and `status` instead.

Text output prints the status beside the rule ID as `RSK012
[unused-exemption]` whenever it is not `violation`, so the level column is
never read as a failure that did not happen. Its last line counts the findings
printed and, when any exemption is active, how many rules it silenced.

`actual` is omitted where quoting it is not evidence: a rule that searches a
whole document for a pattern reports the pattern it wanted, not the document
it read.

YAML and TOML parse failures report parser locations. Workflow findings report
the relevant node line when the YAML parser exposes one.

## Suppressing A Rule

The v2 exception shape remains deliberately small:

```toml
[tool.repo-check.ignore]
RSK012 = "This repository records decisions in its own decision log."
```

Only a known rule ID with a non-empty string reason suppresses findings. Empty
reasons, unknown IDs, malformed TOML, and non-string values suppress nothing.
Owner, expiry, and reference metadata remain deferred.

An exemption that suppressed something is reported. `repo-check` emits one
finding against `pyproject.toml` per exemption that silenced anything, with
status `suppressed`, at the rule's own level, carrying the declared reason,
how many findings it hid, and the paths in `actual`. It is reported once
beside the exemption rather than once per silenced finding, so the entry a
reviewer has to weigh is not buried under what it hid. It never affects the
exit code — silencing the failure is what the exemption is for — but a green
run and a run that only looks green stop being the same output, in text and in
`--format json` alike. `repo-adopt` counts the same reports on a line of its
own, apart from the findings it left unfixed.

An exemption that suppressed nothing is reported. When a rule this run
evaluated produced no finding and an exemption for it is declared, `repo-check`
emits a finding against `pyproject.toml` with status `unused-exemption`, at the
rule's own level, remediating to deleting the entry. It never affects the exit
code: a dead exemption is information about the configuration, not a rule the
repository broke. A rule the resolved profile excludes, and a platform rule
under a run without `--check-enforcement`, are not evaluated and so are never
reported this way.

That second report exists because an exemption is a claim, and a claim nothing
exercises stops being reviewed. The `Single Source Of Truth` section every
`AGENTS.md` carries requires one home per fact and treats deleting the stale
copy as part of the change: an exemption that outlives the finding it was
written for is a second, silently wrong statement about the repository.

## Consumption Surfaces

Every pull request shall produce an independently enforceable `compliance`
status. This CI check does not replace `quality`: compliance verifies the
standard-owned structure, while quality executes the declared gate chain.

The starter kits and this standards repository all use the canonical
`.github/workflows/compliance.yml` name and emit a `compliance` job. A
repository may instead call the reusable workflow this repository publishes at
`.github/workflows/compliance-reusable.yml` from its canonical file, provided
the resulting required status is named `compliance`.

An adopter executes the selected checker with `uvx`, in either form. The
isolated tool environment neither reads nor changes the adopter's `uv.lock`,
and `repo-standard-kit` does not belong in the adopter's project dependencies.
Direct pull requests in `repo-standard-kit` are the exception: its own
`compliance.yml` runs the checked-out implementation with
`uv run --locked --no-dev` so changes to the checker itself receive coverage
before release. Each trigger owns a file rather than sharing one, so neither
workflow branches on the event name — which is still `pull_request` when an
adopter calls a reusable workflow — nor on whether a ref input was supplied.

Together with the `quality` job, this gives every adopting repository the same
two required status names and therefore the same branch-protection ruleset.

### Local pre-commit feedback

The pre-commit hook exists for local feedback: it reports a structural defect
before the push rather than after the pull request opens. Both starter kits
wire it in.

```yaml
repos:
  - repo: https://github.com/FP-DevTools/repo-standard-kit
    rev: v2.0.0
    hooks:
      - id: repo-check
```

In CI the check runs once, in `compliance`. The starter quality workflows set
`SKIP: repo-check` on the pre-commit step, because running every hook is itself
a gate and would otherwise run the same check a second time. A single
compliance defect would then turn both required statuses red, and neither
status would say which of the two it failed on. Skipping the hook in
`quality` weakens nothing: `compliance` is independently required, so the
defect still blocks the merge, and it blocks it in exactly one place.

This repository configures the hook as a `repo: local` hook running
`uv run repo-check .`, the invocation its own compliance workflow uses. Pinning
a `rev:` here would check the working tree against a published release rather
than against itself.

### Required CI workflow

The required shape is the one both starter kits ship: a workflow the repository
owns, running the released checker directly.

```yaml
name: Compliance

on:
  pull_request:

permissions:
  contents: read

jobs:
  compliance:
    name: compliance
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Set up uv
        uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1

      - name: Check repository compliance
        run: >-
          uvx --from
          "git+https://github.com/FP-DevTools/repo-standard-kit.git@v2.0.0"
          repo-check .
```

Every remote action SHALL be pinned to a full commit SHA; keep the version
comment beside it so dependency updates stay readable. The ref in the `--from`
URL selects the released `repo-standard-kit` revision whose packaged checker
and compiled policy are executed. A commit SHA gives the strongest
reproducibility. A human-readable release tag such as `v2.0.0` is permitted
only when repository governance keeps release tags immutable.

Because the repository owns the command, any option the checker accepts —
`--strict`, `--check-enforcement`, `--profile` — is an edit to that line rather
than a request for a new workflow input.

### Alternative: calling the reusable workflow

The caller is one job:

```yaml
name: Compliance

on:
  pull_request:

jobs:
  compliance:
    uses: FP-DevTools/repo-standard-kit/.github/workflows/compliance-reusable.yml@<full-sha>
    with:
      standard-ref: v2.0.0
```

This form is shorter and the runner is maintained centrally, at the cost of
running exactly one command with no options. `standard-ref` is the sole input,
and it selects which checker runs rather than what that checker does: a
repository that wants `--strict`, `--check-enforcement` or `--profile` owns
the command instead, which is the prescribed form above. The reusable workflow
SHALL itself be pinned to a full commit SHA, which selects the workflow
implementation the caller trusts; the distinct `standard-ref` input selects
the checker revision, on the same terms as the `--from` ref above. That input
reaches the step through the environment and never through interpolation into
Bash source, so a caller's value is always one quoted argument and never shell
to parse — which is why the step needs no validation of its own.

Confirm the caller emits the required `compliance` status before relying on
this form, and treat the following as the reason it is the alternative rather
than the prescribed shape. A called workflow's job is widely reported to
surface as `<caller-job-id> / <called-job-name>`, which would make this example
report as `compliance / compliance` and not as `compliance`. RSK014 requires
the context names to be exactly `quality` and `compliance`, and GitHub matches
a required status check by exact name. **This behaviour is unverified**:
GitHub's own Actions documentation does not state how a called workflow's check
is named, and this repository has not observed it. Do not treat it as settled
in either direction — observe the check name your caller actually produces.

`--check-enforcement` remains a distinct, authenticated platform audit. Add it
to the command only when the job has GitHub CLI authentication and the
repository plan exposes branch protection or rulesets; wanting it is itself a
reason to own the command rather than call the reusable workflow. A green
default `compliance` job proves structural alignment; it does not prove that
GitHub requires `quality` and `compliance` before merge.

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
  shell-wrapper strings do not satisfy commands, and neither does a command
  reachable only under a condition the policy does not declare for the
  profile.
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
- RSK027 requires `.github/workflows/compliance.yml` to exist. RSK028 and
  RSK029 apply the permission and pin obligations above to that workflow and
  its `compliance` job. RSK030 requires the workflow to trigger on
  `pull_request` — the other three pass on one that never runs — and reads its
  `run` steps for one executed command containing `repo-check`. Policy owns
  that token, and the match is
  containment rather than an exact command, because the released and
  working-tree invocations differ legitimately. It therefore proves the job
  invokes the checker, not that the invocation is meaningful: a contrived
  command naming the token passes, while a token inside a comment or a
  shell-wrapper string does not, and neither does an invocation reachable only
  under a guard policy does not declare.
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

Vulnerability scanning remains optional. Mandatory scanning, SAST, SBOMs,
signing, richer exception metadata, and non-Python profiles are deferred.
