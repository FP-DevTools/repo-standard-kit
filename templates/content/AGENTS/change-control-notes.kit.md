This repository's public interface is the standard itself, so a change here
can put an already-aligned repository out of alignment.

- Every release records its impact in `CHANGELOG.md` under **Adopters must**,
  following the compatibility policy stated there. A change that forces work
  in an adopting repository is a MAJOR bump.
- Adding a mandatory gate to `docs/quality-gates.md`, or a required section to
  the `AGENTS.md` contract in `docs/repo-standard.md`, is a breaking change
  and needs explicit human approval.
- Keep `version` in `pyproject.toml` in step with the release tag; adopters
  pin by Git ref, so a tag that disagrees with the package is a defect.
- Relaxing a documented gate requires explicit instruction, never an
  incidental edit.
