- `docs/`: the standard and its companion documents
- `policy/`: canonical machine-enforced rules, profile detection metadata, and
  the file shapes governed documents must follow
- `templates/`: reference documents rendered from the shapes, plus the
  `content/` prose fragments they are rendered from
- `src/repo_standard/`: packaged bootstrap implementation
- `src/repo_standard/policy/`: strict policy models and compiled runtime policy
- `src/repo_standard/starter_kits/`: copyable repository skeletons
- `scripts/`: developer scripts — `generate_policy.py` compiles the canonical
  policy, `generate_docs.py` renders every governed Markdown document
- `tests/`: automated tests

For the layout the standard prescribes for *your* repository, see
[docs/repo-layout.md](docs/repo-layout.md).
