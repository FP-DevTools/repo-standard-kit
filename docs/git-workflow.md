# Git Workflow

## Default Model

Use trunk-based development with pull requests.

## Branching Rules

- `main` is the primary long-lived integration branch and is always releasable
- a repository may also maintain `develop` as a second long-lived
  integration branch, to stage a multi-phase feature whose parts are not
  individually releasable, when additive changes on `main` are not viable.
  Prefer landing on `main` directly; reach for `develop` only when a feature
  cannot yet stand on its own
- when a repository maintains `develop`, short-lived branches for that
  feature target `develop`, and `develop` merges to `main` as a single
  reviewed pull request once the staged work is complete
- work happens on short-lived branches
- use one branch per objective
- branch prefixes:
  - `feat/`
  - `fix/`
  - `refactor/`
  - `docs/`
  - `chore/`

## Parallel Collaboration

- prefer small PRs over long-lived branches
- use stacked PRs when a larger change needs sequencing
- rebase private branches frequently to reduce drift
- avoid multiple concurrent branches changing the same subsystem without
  coordination
- prefer feature flags or additive changes on `main` for incomplete work over
  a `develop` branch; reach for `develop` only when even that is not viable

## History Rules

- rebasing private branches is allowed
- rewriting shared branches is not allowed
- merge through reviewed PRs only
- cut releases from `main` with tags
