This section covers working on the kit itself. `AGENTS.md` is the full
operating contract for this repository and governs where it goes further.

Set up a working copy:

```bash
uv sync --locked && uv run pre-commit install
```

The mandatory quality-gate chain is stated once, in `AGENTS.md`; run it locally
before pushing. CI runs the same chain on every pull request through
`.github/workflows/quality.yml`, and a separate `compliance` job checks this
repository against the standard it publishes. Both checks are required to
merge.

`policy/` is the canonical source for machine-enforced rules. After changing
`policy/` or a policy-linked normative section, regenerate the compiled runtime
policy and its documentation, then commit both:

```bash
uv run python scripts/generate_policy.py
```

`uv run pytest` fails when `src/repo_standard/policy/compiled.json` or
[docs/policy-reference.md](docs/policy-reference.md) is stale.
