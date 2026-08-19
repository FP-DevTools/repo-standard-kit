# Quality Gates Specification

> **How to read this document.** This is a specification, not guidance, and it
> is written differently from the rest of `docs/` on purpose. Sections are
> numbered so other documents can cite them precisely — `§10` in `CHANGELOG.md`
> and in the ADRs means this document's section 10, and those references stay
> valid as the text around them changes. "Shall" marks a requirement; "should"
> marks a recommendation. The companion documents indexed by
> `docs/repo-standard.md` are guidance and use plain imperative voice instead.
> Renumbering a section here breaks existing citations, so add new sections at
> the end rather than inserting them.

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
- Static type checking
- Markdown structural linting
- YAML validation
- TOML validation
- JSON validation
- Removal of trailing whitespace
- Final newline enforcement
- Detection of merge conflict markers
- Detection of accidentally committed secrets
- Prevention of oversized binary files

This standard treats `ty` as the approved equivalent to `mypy` for Python
starter repositories, and `pymarkdown` as the approved Markdown linter.
Markdown structural linting shall not re-check prose width — section 13
already owns that, with exemptions the linter's own line-length rule does
not know about, so a repository shall disable it there (`md013` for
`pymarkdown`) rather than run two disagreeing checks.

### Recommended tools

```bash
uv run ruff format
uv run ruff check --fix
uv run ty check
uv run pymarkdown --config .pymarkdown.json scan
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

### Local gate verification

```bash
uv run pre-commit run --all-files
```

Confirms in CI that the mandatory local gates of section 4 — formatting,
linting, static type checking, and file hygiene — were applied, so a bypassed
or missing local hook cannot reach `main`. This is the sole CI enforcement of
those gates; they are not separately re-run as standalone CI steps, since
that would only repeat the same tools against the same files a second time.

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

### Platform prerequisite

Requiring a status check on a **private** repository needs GitHub Team or
higher for an organization, or GitHub Pro for a personal account. On the
GitHub Free plan a private repository cannot require any status check, and
neither branch protection nor repository rulesets are available:

```text
GET /repos/{owner}/{repo}/branches/main/protection
403 Upgrade to GitHub Pro or make this repository public to enable this feature.
```

No configuration closes this gap. A private repository on GitHub Free can run
every gate in this document and still permit a merge when they fail, which
means it does not meet section 9 and is **not aligned** with this
specification.

Treat a plan that supports branch protection as a precondition for adopting
this standard on private repositories, not as an implementation detail to
settle later. Public repositories have branch protection on every plan.

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

A `403` response means the repository is on a plan that does not support
branch protection; see the platform prerequisite above.

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

---

## 13. Formatting Baseline

Passing the formatting and linting gates of section 5 is not sufficient on its
own. Two repositories can both pass while disagreeing about what formatted code
looks like. This section fixes the configuration those gates run with.

### Ruff configuration

Every adopting repository shall declare an explicit `line-length` in
`[tool.ruff]`, and shall select at least the following rule families:

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

The selected families are pycodestyle errors, Pyflakes, import sorting,
flake8-bugbear, and pyupgrade. A repository shall not drop one of them
without recording an exemption under section 11.

The specific `line-length` value is a per-repository decision, not
prescribed by this standard — the requirement is that a value is declared
explicitly, not left as an inherited default. `88` matches Ruff's own
default; a repository should prefer it, so formatting stays comparable
across repositories, but a different declared value does not need an
exemption under section 11.

A repository should additionally select the following rule family; dropping
it does not need an exemption under section 11 either:

```toml
[tool.ruff.lint]
select = ["PT"]
```

`PT` is flake8-pytest-style. A repository may select further rule families
beyond both lists above.

### Prose width

Markdown under `docs/`, along with `README.md` and `AGENTS.md`, should wrap at
the same 88 columns, so documentation and code share one measure and diffs stay
reviewable line by line.

Four things are exempt, because wrapping them harms them: fenced code blocks,
table rows, link reference definitions, and any line whose length comes from a
single unbreakable token such as a URL.
