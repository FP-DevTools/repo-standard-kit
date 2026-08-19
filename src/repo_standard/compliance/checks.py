"""Judge an arbitrary repository against a frozen `Rules` object.

Pure filesystem inspection. `check_repo` never looks at its own installation
directory — only at the `root` it is given — so the same logic runs against
this checkout and against any repository that adopts the standard.

Every rule traces to a normative sentence; see the docstring on each `_check_*`
function for its source. What this module cannot check is documented in
`docs/compliance.md`: prose quality, review judgement, and exception hygiene
are not mechanically decidable.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_standard.compliance.spec import Rules

RULES_JSON_PATH = Path(__file__).resolve().parent / "rules.json"

_IGNORED_DIR_PARTS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}

_KIT_REFERENCE_PATTERN = re.compile(r"repo-standard-kit")
_GITHUB_REMOTE_PATTERN = re.compile(
    r"github\.com[:/](?P<owner_repo>[^/]+/[^/]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class Finding:
    """One rule violation: which rule, how severe, where, and why."""

    rule_id: str
    severity: str  # "shall", "should", or "platform"
    path: str
    line: int | None
    message: str


def load_rules() -> Rules:
    """Load the frozen rule set shipped inside this package."""
    data = json.loads(RULES_JSON_PATH.read_text(encoding="utf-8"))
    return Rules.from_json(data)


def detect_profile(root: Path) -> str:
    """Autodetect a repository's profile: `packages/` means workspace."""
    if (root / "packages").is_dir():
        return "python-workspace"
    return "python-single"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
        return None


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _git_tracked_files(root: Path) -> list[Path] | None:
    """Files git tracks under `root`, or `None` if `root` is not a git repo."""
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return [root / line for line in result.stdout.splitlines() if line]


def _iter_scannable_files(root: Path) -> list[Path]:
    """Files a full-tree rule should inspect.

    Git-tracked files when `root` is a git repository — so caches, vendored
    dependencies, and anything else nobody committed are never scanned,
    however they happen to be named — falling back to a filtered walk only
    for a repository that has no `.git` yet, such as freshly bootstrapped
    output a test inspects before it has been committed.
    """
    tracked = _git_tracked_files(root)
    if tracked is not None:
        return [path for path in tracked if path.is_file()]
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in _IGNORED_DIR_PARTS for part in path.relative_to(root).parts)
    ]


# --- individual rule checks -------------------------------------------------
# Each function takes (root, rules) so `check_repo` can run them uniformly,
# even though most rules do not need `rules` to decide pass or fail.


def _check_agents_exists(root: Path, rules: Rules) -> list[Finding]:
    """RSK001: `AGENTS.md` exists (Repository Contract)."""
    if (root / "AGENTS.md").exists():
        return []
    return [Finding("RSK001", "shall", "AGENTS.md", None, "AGENTS.md is required.")]


def _check_agents_sections(root: Path, rules: Rules) -> list[Finding]:
    """RSK002: all required `AGENTS.md` sections are present (repo-standard.md)."""
    text = _read(root / "AGENTS.md")
    if text is None:
        return []
    headings = re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE)
    missing = [s for s in rules.required_agents_sections if s not in headings]
    if not missing:
        return []
    return [
        Finding(
            "RSK002",
            "shall",
            "AGENTS.md",
            None,
            f"Missing required sections: {', '.join(missing)}.",
        )
    ]


def _check_agents_gate_chain(root: Path, rules: Rules) -> list[Finding]:
    """RSK003: `AGENTS.md` states the exact mandatory gate chain (§5)."""
    text = _read(root / "AGENTS.md")
    if text is None:
        return []
    missing = [c for c in rules.mandatory_ci_commands if c not in text]
    if not missing:
        return []
    return [
        Finding(
            "RSK003",
            "shall",
            "AGENTS.md",
            None,
            f"Omits mandatory gate commands: {', '.join(missing)}.",
        )
    ]


def _check_readme_exists(root: Path, rules: Rules) -> list[Finding]:
    """RSK004: `README.md` exists (Repository Contract)."""
    if (root / "README.md").exists():
        return []
    return [Finding("RSK004", "shall", "README.md", None, "README.md is required.")]


def _check_kit_reference(root: Path, rules: Rules) -> list[Finding]:
    """RSK005: `README.md` and `AGENTS.md` both reference repo-standard-kit."""
    findings = []
    for name in ("README.md", "AGENTS.md"):
        text = _read(root / name)
        if text is not None and not _KIT_REFERENCE_PATTERN.search(text):
            findings.append(
                Finding(
                    "RSK005",
                    "shall",
                    name,
                    None,
                    f"{name} does not reference repo-standard-kit.",
                )
            )
    return findings


def _check_ci_gate_chain(root: Path, rules: Rules) -> list[Finding]:
    """RSK006: the CI workflow runs the full mandatory gate chain (§5)."""
    workflow_path = root / ".github" / "workflows" / "quality.yml"
    text = _read(workflow_path)
    rel = _relative(root, workflow_path)
    if text is None:
        return [
            Finding(
                "RSK006",
                "shall",
                rel,
                None,
                "No CI workflow runs the mandatory gate chain.",
            )
        ]
    missing = [c for c in rules.mandatory_ci_commands if c not in text]
    if not missing:
        return []
    return [
        Finding(
            "RSK006",
            "shall",
            rel,
            None,
            f"CI workflow is missing mandatory gates: {', '.join(missing)}.",
        )
    ]


def _check_pre_commit_hooks(root: Path, rules: Rules) -> list[Finding]:
    """RSK007: mandatory local pre-commit hooks are configured (§4)."""
    config_path = root / ".pre-commit-config.yaml"
    text = _read(config_path)
    if text is None:
        return [
            Finding(
                "RSK007",
                "shall",
                ".pre-commit-config.yaml",
                None,
                "No .pre-commit-config.yaml.",
            )
        ]
    missing = [e for e in rules.mandatory_pre_commit_entries if e not in text]
    if not missing:
        return []
    return [
        Finding(
            "RSK007",
            "shall",
            ".pre-commit-config.yaml",
            None,
            f"Missing mandatory hooks: {', '.join(missing)}.",
        )
    ]


def _check_uv_build_backend(root: Path, rules: Rules) -> list[Finding]:
    """RSK008: `pyproject.toml` builds with `uv_build` (Repository Contract)."""
    pyproject_path = root / "pyproject.toml"
    text = _read(pyproject_path)
    if text is None:
        return [
            Finding(
                "RSK008", "shall", "pyproject.toml", None, "pyproject.toml is required."
            )
        ]
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return [
            Finding(
                "RSK008", "shall", "pyproject.toml", None, f"Could not parse: {error}"
            )
        ]
    if "build-system" not in data:
        # No build-system at all is legitimate for a workspace root that
        # builds nothing itself; per-package pyproject.toml files carry it.
        return []
    backend = data["build-system"].get("build-backend")
    if backend == "uv_build":
        return []
    return [
        Finding(
            "RSK008",
            "shall",
            "pyproject.toml",
            None,
            f"build-backend is {backend!r}, expected 'uv_build'.",
        )
    ]


def _check_uv_lock(root: Path, rules: Rules) -> list[Finding]:
    """RSK009: `uv.lock` is present (Repository Contract)."""
    if (root / "uv.lock").exists():
        return []
    return [Finding("RSK009", "shall", "uv.lock", None, "uv.lock is not present.")]


def _read_ruff_config(pyproject_path: Path) -> dict[str, Any] | None:
    """The `[tool.ruff]` table, or `None` if the file/table is missing or unparsable."""
    text = _read(pyproject_path)
    if text is None:
        return None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    return data.get("tool", {}).get("ruff")


def _check_ruff_baseline(root: Path, rules: Rules) -> list[Finding]:
    """RSK010: `line-length` is declared explicitly and mandatory rule families
    are selected (§13). The specific `line-length` *value* is not checked here —
    see RSK015."""
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    ruff = _read_ruff_config(pyproject_path)
    if ruff is None:
        return [
            Finding(
                "RSK010",
                "shall",
                "pyproject.toml",
                None,
                "No usable [tool.ruff] configuration.",
            )
        ]

    findings = []
    if "line-length" not in ruff:
        findings.append(
            Finding(
                "RSK010",
                "shall",
                "pyproject.toml",
                None,
                "[tool.ruff] does not declare an explicit line-length.",
            )
        )
    actual_select = set(ruff.get("lint", {}).get("select", []))
    missing_families = sorted(set(rules.ruff_mandatory_select) - actual_select)
    if missing_families:
        findings.append(
            Finding(
                "RSK010",
                "shall",
                "pyproject.toml",
                None,
                f"Ruff select drops required rule families: {missing_families}.",
            )
        )
    return findings


def _check_ruff_recommended_line_length(root: Path, rules: Rules) -> list[Finding]:
    """RSK015: declared `line-length` matches the recommended value (§13)."""
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    ruff = _read_ruff_config(pyproject_path)
    if ruff is None or "line-length" not in ruff:
        return []  # RSK010 already covers an undeclared line-length.
    try:
        actual_line_length = int(ruff["line-length"])
    except (TypeError, ValueError):
        return []
    if actual_line_length == rules.ruff_recommended_line_length:
        return []
    return [
        Finding(
            "RSK015",
            "should",
            "pyproject.toml",
            None,
            f"line-length is {actual_line_length}; "
            f"{rules.ruff_recommended_line_length} is recommended so formatting "
            "stays comparable across repositories.",
        )
    ]


def _check_ruff_recommended_select(root: Path, rules: Rules) -> list[Finding]:
    """RSK016: recommended rule families (`PT`) are also selected (§13)."""
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    ruff = _read_ruff_config(pyproject_path)
    if ruff is None:
        return []
    actual_select = set(ruff.get("lint", {}).get("select", []))
    missing = sorted(set(rules.ruff_recommended_select) - actual_select)
    if not missing:
        return []
    return [
        Finding(
            "RSK016",
            "should",
            "pyproject.toml",
            None,
            f"Ruff select does not include recommended rule families: {missing}.",
        )
    ]


def _check_no_placeholders(root: Path, rules: Rules) -> list[Finding]:
    """RSK011: no unresolved bootstrap placeholder tokens remain (repo-standard.md).

    Matches only `repo_init.py`'s known placeholder vocabulary, not every
    dunder-shaped token — a repository's own code may legitimately use
    `__SOME_CONSTANT__`-style names unrelated to this standard's templating.
    """
    findings = []
    for path in _iter_scannable_files(root):
        text = _read(path)
        if text is None:
            continue
        matches = sorted(
            token for token in rules.known_placeholder_tokens if token in text
        )
        if matches:
            findings.append(
                Finding(
                    "RSK011",
                    "shall",
                    _relative(root, path),
                    None,
                    f"Unresolved placeholder tokens: {', '.join(matches)}.",
                )
            )
    return findings


def _check_adr_dir(root: Path, rules: Rules) -> list[Finding]:
    """RSK012: `docs/adr/` exists (repo-layout.md)."""
    if (root / "docs" / "adr").is_dir():
        return []
    return [Finding("RSK012", "should", "docs/adr", None, "docs/adr/ is missing.")]


def _check_changelog_exists(root: Path, rules: Rules) -> list[Finding]:
    """RSK017: `CHANGELOG.md` exists (repo-layout.md)."""
    if (root / "CHANGELOG.md").is_file():
        return []
    return [
        Finding("RSK017", "should", "CHANGELOG.md", None, "CHANGELOG.md is missing.")
    ]


def _check_license_exists(root: Path, rules: Rules) -> list[Finding]:
    """RSK018: `LICENSE` exists (repo-layout.md)."""
    if (root / "LICENSE").is_file():
        return []
    return [Finding("RSK018", "should", "LICENSE", None, "LICENSE is missing.")]


def _git_remote_url(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _owner_repo_from_remote(remote: str) -> str | None:
    match = _GITHUB_REMOTE_PATTERN.search(remote)
    return match.group("owner_repo") if match else None


def _check_branch_protection(root: Path, rules: Rules) -> list[Finding]:
    """RSK014: `main` has the required branch protection (§10). Needs `gh` + auth."""
    remote = _git_remote_url(root)
    owner_repo = _owner_repo_from_remote(remote) if remote else None
    if owner_repo is None:
        return [
            Finding(
                "RSK014",
                "platform",
                ".",
                None,
                "Could not resolve a GitHub owner/repo from the origin remote.",
            )
        ]
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}/branches/main/protection"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return [
            Finding(
                "RSK014",
                "platform",
                ".",
                None,
                "gh CLI unavailable or timed out; could not verify branch protection.",
            )
        ]
    if result.returncode != 0:
        return [
            Finding(
                "RSK014",
                "shall",
                ".",
                None,
                f"Branch protection is not configured on main: {result.stderr.strip()}",
            )
        ]
    try:
        protection = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [
            Finding(
                "RSK014",
                "platform",
                ".",
                None,
                "Unexpected response from gh api; could not verify branch protection.",
            )
        ]

    findings = []
    contexts = protection.get("required_status_checks", {}).get("contexts", [])
    if "quality" not in contexts:
        findings.append(
            Finding(
                "RSK014",
                "shall",
                ".",
                None,
                "Required status checks do not include 'quality'.",
            )
        )
    reviews = protection.get("required_pull_request_reviews", {}).get(
        "required_approving_review_count", 0
    )
    if reviews < 1:
        findings.append(
            Finding(
                "RSK014",
                "shall",
                ".",
                None,
                "Must require at least one approving review.",
            )
        )
    if not protection.get("enforce_admins", {}).get("enabled", False):
        findings.append(
            Finding(
                "RSK014",
                "shall",
                ".",
                None,
                "Must not allow administrators to bypass protection.",
            )
        )
    return findings


def _load_ignore_config(root: Path) -> dict[str, str]:
    """`[tool.repo-check.ignore]`: rule ID -> recorded reason for suppression (§11).

    A malformed or absent table suppresses nothing — an entry only takes
    effect once it has a non-empty string reason recorded against it.
    """
    text = _read(root / "pyproject.toml")
    if text is None:
        return {}
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    ignore = data.get("tool", {}).get("repo-check", {}).get("ignore", {})
    if not isinstance(ignore, dict):
        return {}
    return {
        rule_id: reason
        for rule_id, reason in ignore.items()
        if isinstance(rule_id, str) and isinstance(reason, str) and reason.strip()
    }


_STRUCTURAL_CHECKS = (
    _check_agents_exists,
    _check_agents_sections,
    _check_agents_gate_chain,
    _check_readme_exists,
    _check_kit_reference,
    _check_ci_gate_chain,
    _check_pre_commit_hooks,
    _check_uv_build_backend,
    _check_uv_lock,
    _check_ruff_baseline,
    _check_ruff_recommended_line_length,
    _check_ruff_recommended_select,
    _check_no_placeholders,
    _check_adr_dir,
    _check_changelog_exists,
    _check_license_exists,
)


def check_repo(
    root: Path,
    rules: Rules,
    *,
    profile: str | None = None,
    include_platform: bool = False,
) -> list[Finding]:
    """Check `root` for structural alignment with the standard `rules` define.

    `profile` is accepted for forward compatibility with profile-specific
    rules; none of the current catalogue differs by profile, so it does not
    yet change which checks run. `include_platform` opts into RSK014, which
    needs `gh`, network access, and auth (§10).

    A rule with a recorded reason in `root`'s `[tool.repo-check.ignore]` is
    dropped from the result entirely — this is the §11 exception mechanism,
    not a report of what was excused.
    """
    checks = list(_STRUCTURAL_CHECKS)
    if include_platform:
        checks.append(_check_branch_protection)

    findings: list[Finding] = []
    for check in checks:
        findings.extend(check(root, rules))

    ignored = _load_ignore_config(root)
    if ignored:
        findings = [f for f in findings if f.rule_id not in ignored]
    return findings
