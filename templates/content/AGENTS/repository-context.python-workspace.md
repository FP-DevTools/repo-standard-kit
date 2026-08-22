- Repository name: `__REPO_NAME__`
- Primary language(s): `Python`
- Runtime/build system: `uv` with shared root tooling and `uv_build` for
  package projects
- Repository type: `workspace`
- Standards source: [repo-standard-kit] — quality gates derive from its
  [quality-gates spec][quality-gates]; review this repository against it
  periodically for standards drift
- Key directories:
  - `packages/`: independently structured package projects
  - `docs/`: durable repository knowledge
  - `scripts/`: workspace-level helpers
