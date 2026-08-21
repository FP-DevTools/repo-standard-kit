Run from repo root:

__GATE_CHAIN__

The build step fails until `packages/` holds its first package: on an empty
workspace it exits 2 with `Workspace does not contain any buildable packages`.
Add a package with `repo-add-package` and the chain passes. The quality
workflow guards that step behind `compgen -G "packages/*/pyproject.toml"`, so
CI skips it meanwhile; the chain above is listed unguarded because it is the
exact chain the standard declares.

The quality job's effective permissions must be exactly `contents: read`, and
every remote action or reusable workflow must be pinned to a full 40-character
commit SHA. Keep version comments and GitHub Actions Dependabot configuration
so those pins remain maintainable.

Branch protection must require the separate `quality` and `compliance` status
checks. Quality executes the gate chain; compliance independently checks the
repository against the standard. Keep these canonical names so the same
ruleset applies to every adopting repository.
