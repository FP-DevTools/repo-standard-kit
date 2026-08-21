1. Update canonical YAML policy and its explanatory normative docs together
   when changing a machine-enforced rule.
2. Update templates and starter kits in the same change. Never edit a
   generated document directly: this repository's own `README.md` and
   `AGENTS.md`, `templates/{README,AGENTS}.md`, and every starter kit's
   Markdown are rendered by `scripts/generate_docs.py`. Edit the prose fragment
   under `templates/content/` or, for section order, `policy/shapes.yaml`.
3. After changing `policy/` or a policy-linked normative section, run
   `uv run python scripts/generate_policy.py` and commit the regenerated
   `src/repo_standard/policy/compiled.json` and `docs/policy-reference.md`;
   `uv run pytest` fails otherwise.
4. After changing `policy/shapes.yaml` or `templates/content/`, run
   `uv run python scripts/generate_docs.py` and commit every regenerated
   document; `uv run pytest` fails otherwise.
5. Validate bootstrap behavior with `uv run pytest`, which generates into a
   temporary directory rather than a fixed path.
6. Keep changes small and focused by concern.
