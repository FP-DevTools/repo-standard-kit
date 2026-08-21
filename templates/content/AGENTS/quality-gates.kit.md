Run from repository root:

__GATE_CHAIN__

The quality job's effective permissions must be exactly `contents: read`, and
every remote action or reusable workflow must be pinned to a full 40-character
commit SHA. Keep version comments and GitHub Actions Dependabot configuration
so those pins remain maintainable.

Branch protection must require the separate `quality` and `compliance` status
checks. Quality executes the gate chain; compliance independently checks the
repository against the standard. Keep these canonical names so the same
ruleset applies to every adopting repository.

This is exactly the chain in `docs/quality-gates.md`; this repository adds no
gates of its own. Bootstrap behavior needs no separate manual step — `uv run
pytest` exercises the `repo-init` and `repo-add-package` entry points end to
end in a temporary directory, on every platform.
