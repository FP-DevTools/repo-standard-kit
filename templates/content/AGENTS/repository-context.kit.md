- Repository name: `repo-standard-kit`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `uv_build` in `pyproject.toml`
- Repository type: `python-single`
- Standards source: this repository is the standard's own home, so it states
  the standard rather than referencing it. `docs/repo-standard.md` is the
  normative entry point and indexes every other normative document;
  `docs/quality-gates.md` states the mandatory gates.
- Key directories:
  - `src/repo_standard/`: bootstrap, policy, and compliance implementation
  - `tests/`: automated tests
  - `docs/`: the standard and its companion documents
  - full responsibilities in Repository Layout below
