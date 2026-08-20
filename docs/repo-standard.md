# Repository Development Standard

## Scope Of This Document

This is the normative entry point for the standard. It states what a repository
must provide to be considered aligned, and indexes the companion documents that
expand each area in detail. Start here, then follow the index below.

It governs repositories that *adopt* the standard. The `README.md` at the root
of `repo-standard-kit` is a non-normative guide to using the kit's tooling and
does not define rules.

## Normative Language

The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, and **MAY** are normative throughout every document indexed
below. MUST and SHALL identify a required policy level; SHOULD identifies a
recommended policy level whose finding is non-blocking unless strict checking
is requested; MAY identifies an optional choice. Plain imperatives carry the
same level made explicit by their surrounding section or policy reference.

`policy/base.yaml` and `policy/profiles/` are the sole source of executable
values, applicability, and check configuration for machine-enforced rules.
Normative Markdown explains those rules and human-review-only guidance but is
never parsed to obtain executable values. `docs/policy-reference.md` is the
generated, normative human-readable catalogue of machine-enforced policy.

## Purpose

This standard defines the baseline operating model for a repository developed by
humans and agents together, covering repository structure, collaboration
workflow, quality gates, coding standards, and repository-level guidance through
`AGENTS.md`.

## Applicability

This standard is intended to be portable. A repository may adopt it directly or
adapt it through its own `AGENTS.md`, but the resulting guidance must remain
concrete and actionable.

## Repository Contract

Every repository adopting this standard must provide:

- a concrete `AGENTS.md`
- a user-facing `README.md`
- an explicit, linked reference to `repo-standard-kit` in both `README.md`
  and `AGENTS.md`, so the repository's alignment with the standard can be
  audited periodically
- exact quality-gate commands
- a CI workflow that runs the same quality gates
- branch protection on `main` that makes those gates binding rather than
  advisory, as specified in `docs/quality-gates.md`
- alignment with `docs/quality-gates.md` for mandatory local and CI quality gates
- a documented repository layout
- clear API, schema, or migration rules where relevant
- `uv` as the default Python project and package manager

The following machine-enforced rules are **required**: RSK001 requires the
root `AGENTS.md`; RSK004 requires the root `README.md`; RSK005 requires both
documents to reference `repo-standard-kit`; RSK009 requires `uv.lock`; RSK011
rejects only the kit's known unresolved bootstrap tokens; and RSK019 requires
this explicit repository metadata:

```toml
[tool.repo-standard]
profile = "python-single" # or "python-workspace"
standard = "2"
```

The declaration wins over filesystem heuristics. A missing or invalid
declaration is an RSK019 required finding, but deterministic auto-detection
still selects a profile so all other applicable checks can run.

RSK008 is **recommended** and checks for `uv_build` in Python packages. It
remains the generated default for starter repositories and new workspace
packages, while an established package may retain another PEP 517 backend
without failing normal compliance. Strict checking keeps the recommendation
visible. A tooling-only workspace root may omit a build system entirely.

## Core Rules

- Use a trunk-based PR workflow by default.
- Keep public interfaces stable unless a deliberate breaking change is approved.
- Document exact quality-gate commands in the repository's `AGENTS.md`.
- Treat typing, tests, and docs as part of the implementation, not optional
  polish.
- Keep operational boundaries explicit: product intent and release authority
  remain human-owned.
- Reference `repo-standard-kit` explicitly in `README.md` and `AGENTS.md` so
  standards drift can be checked against it periodically.
- Do not claim support for a language profile in starter kits, tooling, or
  docs until that profile is fully documented and maintained. Python is the
  only such profile today.

## Required Companion Documents

These documents are normative alongside this one. Together with this document
they are the complete normative set; anything else in `repo-standard-kit`,
including its `README.md`, templates, and starter kits, implements them.

- `docs/quality-gates.md`: the mandatory local and CI gate chain
- `docs/agent-operating-model.md`: human and agent decision boundaries
- `docs/git-workflow.md`: branching, collaboration, and history rules
- `docs/repo-layout.md`: canonical directory layout and scope boundaries
- `docs/bootstrap-workflow.md`: how new repositories are generated
- `docs/policy-reference.md#profiles`: the supported profiles and their
  canonical detection metadata

Where a companion document conflicts with this one, this document governs.

`docs/quality-gates.md` keeps numbered sections so requirements can be cited
precisely. The normative-keyword meanings above apply consistently to it and
every other indexed document.

## Required `AGENTS.md` Sections

Every target repository must carry the required sections and order declared by
the [`agents` shape in the generated policy reference](policy-reference.md#agents).

Committed copies must not contain placeholders or generic filler text.

RSK002 enforces those headings at the **required** level in the declared order;
sections the standard does not name may appear anywhere. RSK003 enforces at the
**required** level that the `## Quality Gates` section in `AGENTS.md` states the
exact ordered command chain defined by policy for the resolved profile. Commands
elsewhere in the document do not count. These checks do not attempt subjective
scoring of the section prose.

## Agent Operating Mode

Agent behaviour left to model defaults varies between runs and between
repositories, which is the opposite of what a standard is for. The standard
therefore calibrates two dials — *verbosity*, and *precision, repeatability,
and determinism* — and calibrates them the way it calibrates the gate chain: as
policy values a check reports drift from, not as prose an adopter silently
rewrites.

*Low verbosity* means answering what was asked, reporting outcomes rather than
narrating steps, preferring a diff or a `path:line` reference to prose
describing it, and spending words on decisions, risks, and failures.

*High precision, repeatability, and determinism* mean verifying against the
repository before asserting, reusing the pattern already in the file, making
the smallest change that satisfies the requirement, running the documented
gates in order and reporting their real output, pinning what can be pinned,
stating assumptions where the repository does not settle a choice, and reaching
the same result when the same task runs again.

RSK026 enforces at the **required** level that the `## Agent Operating Mode`
section of `AGENTS.md` states every dial, in the declared order, at the level
`policy/base.yaml` declares. The level of each dial is published in
[`docs/policy-reference.md`](policy-reference.md#rsk026-agentsmd-states-the-calibrated-agent-operating-dials)
and stated nowhere by hand: the generator renders it into every reference
document from the rule, `repo-check` reports a document that has drifted, and
`repo-adopt` restores it. The surrounding prose is the repository's own — the
check reads the dial lines and nothing else.

## File Shapes

A *shape* is the canonical section list for one governed file: which sections
exist, what they are called, which are mandatory, and in what order they
appear. Shapes are declared in `policy/shapes.yaml` and compiled into the
[policy reference's authoritative section tables](policy-reference.md#file-shapes).

Every shape is checked as a **subsequence**. A section the shape does not
declare is legal anywhere and is ignored. A declared section may be absent
unless it is marked required. What a shape forbids is *reordering*: the
declared sections a file does carry must appear in the declared order. Markdown
shapes govern level-two headings only, matching RSK002's semantics.

RSK023 (`README.md`), RSK024 (`CHANGELOG.md`), and RSK025 (`pyproject.toml`)
each refer to their generated shape table. The tables distinguish required from
optional sections; undeclared sections and tables stay legal in any position.
RSK023, RSK024, and RSK025 enforce their respective shapes at the **required**
level.
