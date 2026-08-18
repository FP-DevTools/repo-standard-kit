# Git Workflow

## Default Model

Use trunk-based development with pull requests.

## Branching Rules

- `main` is the primary long-lived integration branch and is always releasable
- work happens on short-lived branches
- use one branch per objective
- branch prefixes:
  - `feat/`
  - `fix/`
  - `refactor/`
  - `docs/`
  - `chore/`

## Staging Multi-Phase Work

Prefer additive changes or feature flags directly on `main` for incomplete
work. When a feature's parts are not individually releasable and that is not
viable, a repository may maintain `develop` as a second long-lived
integration branch to stage it. Using `develop` at all is optional per
repository; a repository that keeps `main` as its only long-lived branch is
equally aligned with this standard.

When a repository does maintain `develop`:

- short-lived branches for that feature target `develop`, not `main`
- the staged work reaches `main` one of two ways, chosen once per feature
  and not mixed partway through:
  - `develop` merges to `main` directly, as a single reviewed pull request,
    once the staged work is complete; or
  - a release branch cut from `develop`'s tip carries its accumulated
    commits forward, plus the release-finalizing work (a version bump, a
    changelog entry), to `main` in its own reviewed pull request

## Parallel Collaboration

- prefer small PRs over long-lived branches
- use stacked PRs when a larger change needs sequencing
- rebase private branches frequently to reduce drift
- avoid multiple concurrent branches changing the same subsystem without
  coordination

## History Rules

- rebasing private branches is allowed
- rewriting shared branches is not allowed
- merge through reviewed PRs only
- cut releases from `main` with tags
