1. Review `AGENTS.md` and confirm the repo-specific scope and constraints.
2. Run `uv sync`.
3. Run `uv run pre-commit install` after Git is initialized. If you used
   `repo-init` without `--no-install`, this is already done for you.
4. Run `uv run pre-commit run --all-files`.
5. Run `uv run ruff format --check .`.
6. Run `uv run ruff check .`.
7. Run `uv run ty check`.
8. Run `uv run pytest`.
9. Run `uv build`.
10. Review `.github/workflows/quality.yml`.
11. Commit the generated `uv.lock`, then make the initial commit on `main`.
