<A checklist a new contributor can finish in one sitting. Keep it to commands
that verify the checkout is healthy, and delete any that do not apply.>

1. Read `AGENTS.md` and confirm this repo's scope and constraints.
2. Run `uv sync --locked`.
3. Run `uv run pre-commit install`.
4. Run `uv run pre-commit run --all-files` to confirm a clean baseline.
5. Run `uv run pytest`.
6. Run `<the repo's primary entry point>` against `<sample or local input>`.
7. Skim `.github/workflows/quality.yml` to see what CI enforces.
