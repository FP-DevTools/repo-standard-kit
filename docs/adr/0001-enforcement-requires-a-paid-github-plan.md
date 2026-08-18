# ADR-0001: Enforcement Requires A Paid GitHub Plan

## Status

Accepted — 2026-08-18

## Context

`docs/quality-gates.md` §9 has always defined merge criteria, but until v0.3.0
the standard shipped no way to make them binding. A workflow that runs on every
pull request still permits a merge when it fails, so the gates were advisory.
§10 was added to close that gap by requiring branch protection on `main`.

While preparing to apply that configuration to this repository, both the branch
protection and the repository rulesets endpoints returned `403`:

```text
GET /repos/FP-DevTools/repo-standard-kit/branches/main/protection
GET /repos/FP-DevTools/repo-standard-kit/rulesets
403 Upgrade to GitHub Pro or make this repository public to enable this feature.
```

The token holds `admin: true` on the repository, so this is a plan limitation
rather than a permissions problem. The organization is on the GitHub Free plan
and owns 15 private repositories. Required status checks on private
repositories need GitHub Team or higher.

The consequence is that §10 as written could not be satisfied by any repository
it governs, including this one. Left unaddressed, the standard would define a
requirement that makes every adopting repository non-compliant by definition.

## Decision

State the plan as an explicit precondition rather than weakening the
requirement.

`docs/quality-gates.md` §10 now documents that a private repository on GitHub
Free cannot require a status check, that no configuration closes the gap, and
that such a repository is not aligned with the specification.

Enforcement is not softened to "where supported". A `SHOULD` would let every
repository claim alignment while leaving the gates advisory, which is the
condition §10 exists to end.

The plan upgrade is not being pursued at this time. Pilot adoption proceeds
with gates advisory and enforcement recorded as a known, bounded gap.

## Consequences

- The standard is honest about what it requires, and the upgrade becomes a
  visible decision with a named owner rather than a silent gap.
- Until the plan changes, repositories adopting this standard on private
  repositories — including this one — are not fully aligned. Gate failures are
  visible in CI but do not block a merge.
- Pilot findings about gate ergonomics remain valid, since the gates still run.
  Findings about enforcement do not, and should be revisited after any upgrade.
- The exact settings and their verification command are documented, so applying
  them is mechanical on the day the plan supports it.
- Public repositories are unaffected; branch protection is available to them on
  every plan.

## Revisit When

The organization moves to GitHub Team or higher, or a decision is taken to keep
enforcement permanently advisory — in which case §10 needs rewriting rather than
this ADR amending.
