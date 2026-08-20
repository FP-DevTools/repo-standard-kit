Pick the block that matches this repo's profile and delete the other.

**Single-package (`python-single`)**

```text
.
├── src/<package_name>/   # production code
├── tests/                # unit and integration tests
├── docs/adr/             # architecture decisions
├── docs/diagrams/        # workflow / architecture diagrams
├── scripts/              # dev or operational helpers (not core logic)
├── AGENTS.md             # repo operating contract: workflow, gates, standards
├── README.md
└── pyproject.toml
```

**Workspace (`python-workspace`)**

```text
.
├── packages/<package-slug>/
│   ├── src/<package_name>/
│   └── tests/
├── docs/adr/
├── docs/diagrams/
├── AGENTS.md
├── README.md
└── pyproject.toml        # tooling-only root config
```

<If this is a data repo, note where data-related paths live, e.g.
`data/` (gitignored, local only) or `notebooks/` (exploratory, not
production code), and how they relate to `src/`.>
