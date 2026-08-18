# Quality Gates Specification

## 1. Purpose

This specification defines the minimum quality requirements for repositories
using LLM-assisted development.

The objective is to ensure that all changes merged into `main` remain:

- Correct
- Maintainable
- Reproducible
- Secure
- Well-documented

---

## 2. Applicability

This specification applies to:

- All pull requests targeting `main`
- All contributors, whether human- or AI-assisted

---

## 3. Principles

Quality gates shall exist at two levels:

1. **Local developer gates**
   - Provide rapid feedback.
   - Prevent obvious issues from reaching CI.

2. **CI gates**
   - Act as the authoritative merge criteria.
   - Shall be executed automatically on every pull request to `main`.

No pull request may be merged into `main` unless all mandatory CI gates pass.

---

## 4. Local Pre-Commit Gates

Local checks should remain lightweight and fast.

### Mandatory

- Code formatting
- Lint auto-fixes where safe
- YAML validation
- TOML validation
- JSON validation
- Removal of trailing whitespace
- Final newline enforcement
- Detection of merge conflict markers
- Detection of accidentally committed secrets
- Prevention of oversized binary files

### Recommended tools

```bash
uv run ruff format
uv run ruff check --fix
```

### Performance target

Typical execution time should remain below **10 seconds**.

---

## 5. CI Pull Request Gates

The following gates shall execute automatically for every pull request targeting `main`.

### Environment reproducibility

```bash
uv sync --locked
```

Verifies that dependency resolution is reproducible.

---

### Formatting

```bash
uv run ruff format --check
```

Ensures a consistent code style.

---

### Linting

```bash
uv run ruff check
```

Ensures compliance with repository coding standards.

---

### Static type checking

```bash
uv run ty check
```

This standard treats `ty` as the approved equivalent to `mypy` for Python
starter repositories.

Ensures consistency between implementation and declared interfaces.

---

### Automated tests

```bash
uv run pytest
```

Ensures existing functionality remains operational.

---

### Package build validation

```bash
uv build
```

Verifies that distributable artifacts can be produced successfully.

---

## 6. Generated Artifact Consistency

If a repository contains generated artifacts, CI shall verify that generated
outputs remain synchronized with their sources.

Examples include:

- OpenAPI clients
- JSON Schemas
- Pydantic models
- Documentation
- Generated configuration files

Example check:

```bash
uv run python scripts/generate.py
git diff --exit-code
```

---

## 7. Optional CI Gates

Projects may enable additional gates where appropriate.

### Coverage thresholds

```bash
uv run pytest --cov
```

Coverage targets should be defined per repository.

---

### Dependency hygiene

```bash
uv run deptry .
```

Detects unused and undeclared dependencies.

---

### Vulnerability scanning

```bash
uv run pip-audit
```

Identifies known vulnerabilities in dependencies.

---

### Documentation validation

```bash
uv run mkdocs build
```

Ensures documentation can be successfully generated.

---

## 8. Pull Request Requirements

Every pull request targeting `main` shall:

- Pass all mandatory CI gates;
- Include tests for new functionality where applicable;
- Update documentation when user-facing behaviour changes;
- Update generated artifacts when required;
- Contain a description explaining the purpose of the change.

---

## 9. Merge Criteria

A pull request may be merged into `main` only if:

- Formatting checks pass;
- Linting checks pass;
- Type checking passes;
- Automated tests pass;
- Package build validation passes;
- Generated artifacts are up to date;
- All required reviews have been completed.

---

## 10. Enforcement

Running the gates is not the same as enforcing them. A workflow that executes
on every pull request still permits a merge if nothing requires it to pass.

Every repository adopting this specification shall protect `main` so the
mandatory gates are binding rather than advisory.

### Required branch protection

On GitHub, protect `main` with:

- **Require a pull request before merging**, with at least one approving
  review and stale approvals dismissed on new commits.
- **Require status checks to pass before merging**, selecting the `quality`
  check produced by `.github/workflows/quality.yml`, with **Require branches
  to be up to date before merging** enabled.
- **Require conversation resolution before merging**.
- **Do not allow bypassing the above settings**, including for repository
  administrators.

A status check becomes selectable only after the workflow has run at least
once, so open an initial pull request before configuring protection.

### Verification

```bash
gh api repos/<owner>/<repo>/branches/main/protection \
  --jq '{checks: .required_status_checks.contexts,
         reviews: .required_pull_request_reviews.required_approving_review_count,
         enforce_admins: .enforce_admins.enabled}'
```

The `quality` check shall appear in `checks`, `reviews` shall be at least `1`,
and `enforce_admins` shall be `true`.

A repository that cannot produce this configuration is not aligned with this
specification, regardless of whether its workflow passes.

---

## 11. Exceptions

Temporary exemptions to these quality gates require:

- Explicit justification;
- Documentation within the pull request;
- Approval from repository maintainers.

Exemptions shall remain exceptional and time-limited.

---

## 12. Ownership

Repository maintainers are responsible for:

- Keeping the quality gates operational;
- Reviewing the effectiveness of the gates periodically;
- Adjusting thresholds and tooling as the repository evolves.
