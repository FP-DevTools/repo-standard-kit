"""Check a repository by dispatching canonical policy check kinds."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_standard.compliance.yaml_support import (
    YamlDocument,
    YamlParseError,
    load_github_yaml,
)
from repo_standard.policy import Policy, Rule, load_compiled_policy

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
_GITHUB_REMOTE_PATTERN = re.compile(
    r"github\.com[:/](?P<owner_repo>[^/]+/[^/]+?)(?:\.git)?/?$"
)
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class Finding:
    """One actionable policy finding."""

    rule_id: str
    title: str
    level: str
    severity: str
    path: str
    line: int | None
    message: str
    actual: Any
    expected: Any
    remediation: str
    status: str = "violation"


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    actual: Any = None
    expected: Any = None
    line: int | None = None
    status: str = "violation"


@dataclass(frozen=True)
class CheckContext:
    root: Path
    policy: Policy
    profile: str


CheckHandler = Callable[[CheckContext, dict[str, Any]], list[Issue]]


def load_policy() -> Policy:
    """Load the packaged deterministic policy artifact."""
    return load_compiled_policy()


# Compatibility alias for callers that used the v0.4 name.
load_rules = load_policy


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
        return None


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _toml_error_line(error: tomllib.TOMLDecodeError) -> int | None:
    line = getattr(error, "lineno", None)
    if isinstance(line, int):
        return line
    match = re.search(r"line (\d+)", str(error))
    return int(match.group(1)) if match else None


def _load_toml(path: Path) -> tuple[dict[str, Any] | None, Issue | None]:
    text = _read(path)
    if text is None:
        return None, Issue(path.name, f"{path.name} is missing.", None, "valid TOML")
    try:
        return tomllib.loads(text), None
    except tomllib.TOMLDecodeError as error:
        return (
            None,
            Issue(
                path.name,
                f"Could not parse TOML: {error}",
                text,
                "valid TOML",
                _toml_error_line(error),
            ),
        )


def _load_yaml(path: Path, root: Path) -> tuple[YamlDocument | None, Issue | None]:
    text = _read(path)
    relative = _relative(root, path)
    if text is None:
        return None, Issue(relative, f"{relative} is missing.", None, "valid YAML")
    try:
        return load_github_yaml(text), None
    except YamlParseError as error:
        return (
            None,
            Issue(
                relative,
                f"Could not parse YAML: {error}",
                text,
                "valid YAML",
                error.line,
            ),
        )


def _git_tracked_files(root: Path) -> list[Path] | None:
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
    tracked = _git_tracked_files(root)
    if tracked is not None:
        return [path for path in tracked if path.is_file()]
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in _IGNORED_DIR_PARTS for part in path.relative_to(root).parts)
    ]


def _detect_profile(root: Path, policy: Policy) -> str:
    profiles = sorted(
        policy.profiles, key=lambda profile: profile.detection.priority, reverse=True
    )
    for profile in profiles:
        if profile.detection.default:
            continue
        matches = []
        for marker in profile.detection.markers:
            path = root / marker.path
            matches.append(path.is_file() if marker.kind == "file" else path.is_dir())
        if matches and all(matches):
            return profile.id
    return next(profile.id for profile in profiles if profile.detection.default)


def _valid_metadata_profile(root: Path, policy: Policy) -> str | None:
    data, error = _load_toml(root / "pyproject.toml")
    if error is not None or data is None:
        return None
    metadata = data.get("tool", {}).get("repo-standard")
    if not isinstance(metadata, dict):
        return None
    profile = metadata.get("profile")
    standard = metadata.get("standard")
    if profile not in policy.profile_ids or standard != policy.standard_major:
        return None
    return profile


def resolve_profile(root: Path, policy: Policy, override: str | None = None) -> str:
    """Resolve CLI override, then valid metadata, then deterministic detection."""
    if override is not None:
        if override not in policy.profile_ids:
            raise ValueError(f"unknown profile {override!r}")
        return override
    return _valid_metadata_profile(root, policy) or _detect_profile(root, policy)


def _path_exists(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    path = context.root / config["path"]
    kind = config["path_type"]
    exists = path.is_file() if kind == "file" else path.is_dir()
    if exists:
        return []
    return [Issue(config["path"], f"Required {kind} is missing.", "missing", kind)]


def _markdown_headings(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    text = _read(context.root / config["path"])
    if text is None:
        return []
    actual = re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE)
    missing = [heading for heading in config["headings"] if heading not in actual]
    if not missing:
        return []
    return [
        Issue(
            config["path"],
            f"Missing required headings: {', '.join(missing)}.",
            actual,
            config["headings"],
        )
    ]


def _text_contains_all(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    text = _read(context.root / config["path"])
    if text is None:
        return []
    missing = [value for value in config["values"] if value not in text]
    if not missing:
        return []
    return [
        Issue(
            config["path"],
            f"Missing required values: {', '.join(missing)}.",
            missing,
            config["values"],
        )
    ]


def _text_pattern_each(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    pattern = re.compile(config["pattern"])
    issues = []
    for relative in config["paths"]:
        text = _read(context.root / relative)
        if text is not None and pattern.search(text) is None:
            issues.append(
                Issue(
                    relative,
                    f"{relative} does not match {pattern.pattern!r}.",
                    text,
                    pattern.pattern,
                )
            )
    return issues


def _shell_commands(run: str) -> list[list[str]]:
    """Return executable command token lists from an Actions `run` scalar."""
    normalized = re.sub(r"\\\r?\n", " ", run)
    commands: list[list[str]] = []
    for line in normalized.splitlines() or [normalized]:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        segment: list[str] = []
        try:
            tokens = list(lexer)
        except ValueError:
            continue
        for token in [*tokens, ";"]:
            if token in {";", "&&", "||", "&", "|"}:
                while segment and segment[0] in {"then", "do", "{"}:
                    segment.pop(0)
                while segment and segment[-1] in {"fi", "done", "}"}:
                    segment.pop()
                if segment:
                    commands.append(segment)
                segment = []
            else:
                segment.append(token)
    return commands


def _trigger_present(on_value: Any, trigger: str) -> bool:
    if isinstance(on_value, str):
        return on_value == trigger
    if isinstance(on_value, list):
        return trigger in on_value
    if isinstance(on_value, dict):
        return trigger in on_value
    return False


def _workflow_job(
    context: CheckContext, config: dict[str, Any]
) -> tuple[YamlDocument | None, dict[str, Any] | None, list[Issue]]:
    path = context.root / config["path"]
    document, error = _load_yaml(path, context.root)
    if error is not None:
        return None, None, [error]
    assert document is not None
    if not isinstance(document.data, dict):
        return (
            document,
            None,
            [
                Issue(
                    config["path"],
                    "Workflow root must be a mapping.",
                    document.data,
                    "mapping",
                )
            ],
        )
    jobs = document.data.get("jobs")
    if not isinstance(jobs, dict) or not isinstance(jobs.get(config["job"]), dict):
        return (
            document,
            None,
            [
                Issue(
                    config["path"],
                    f"Workflow has no executable {config['job']!r} job.",
                    jobs,
                    config["job"],
                    document.line("jobs"),
                )
            ],
        )
    return document, jobs[config["job"]], []


def _github_workflow_commands(
    context: CheckContext, config: dict[str, Any]
) -> list[Issue]:
    document, job, errors = _workflow_job(context, config)
    if errors:
        return errors
    assert document is not None
    assert job is not None
    assert isinstance(document.data, dict)
    issues: list[Issue] = []
    if not _trigger_present(document.data.get("on"), config["trigger"]):
        issues.append(
            Issue(
                config["path"],
                f"Workflow does not trigger on {config['trigger']}.",
                document.data.get("on"),
                config["trigger"],
                document.line("on"),
            )
        )
    steps = job.get("steps")
    if not isinstance(steps, list):
        issues.append(
            Issue(
                config["path"],
                f"Job {config['job']!r} has no executable steps.",
                steps,
                "list of run steps",
                document.line("jobs", config["job"], "steps"),
            )
        )
        return issues
    actual_commands: list[list[str]] = []
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            actual_commands.extend(_shell_commands(step["run"]))
    required = [
        shlex.split(command)
        for command in config["commands_by_profile"][context.profile]
    ]
    missing = [tokens for tokens in required if tokens not in actual_commands]
    if missing:
        issues.append(
            Issue(
                config["path"],
                "Quality job is missing complete executable commands: "
                + ", ".join(shlex.join(tokens) for tokens in missing)
                + ".",
                [shlex.join(tokens) for tokens in actual_commands],
                [shlex.join(tokens) for tokens in required],
                document.line("jobs", config["job"], "steps"),
            )
        )
    return issues


def _normalized_tokens(
    entry: Any, args: Any
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], tuple[str, ...]] | None:
    if not isinstance(entry, str):
        return None
    try:
        tokens = shlex.split(entry)
        if args is not None:
            if isinstance(args, str):
                args = [args]
            if not isinstance(args, list) or not all(
                isinstance(arg, str) for arg in args
            ):
                return None
            for arg in args:
                tokens.extend(shlex.split(arg))

        prefix: list[str] = []
        options: list[tuple[str, ...]] = []
        suffix: list[str] = []
        index = 0
        saw_option = False
        while index < len(tokens):
            token = tokens[index]
            if token.startswith("-"):
                saw_option = True
                if (
                    "=" not in token
                    and index + 1 < len(tokens)
                    and not tokens[index + 1].startswith("-")
                ):
                    options.append((token, tokens[index + 1]))
                    index += 2
                    continue
                options.append((token,))
            elif saw_option:
                suffix.append(token)
            else:
                prefix.append(token)
            index += 1
        return tuple(prefix), tuple(sorted(options)), tuple(suffix)
    except ValueError:
        return None


def _hook_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if actual.get("id") != expected["id"]:
        return False
    if _normalized_tokens(
        actual.get("entry"), actual.get("args")
    ) != _normalized_tokens(expected["entry"], expected.get("args")):
        return False
    for key in ("types", "types_or"):
        if key in expected:
            actual_values = actual.get(key)
            if not isinstance(actual_values, list) or set(actual_values) != set(
                expected[key]
            ):
                return False
    for key in ("pass_filenames", "require_serial"):
        if key in expected and actual.get(key) is not expected[key]:
            return False
    return True


def _pre_commit_hooks(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    document, error = _load_yaml(context.root / config["path"], context.root)
    if error is not None:
        return [error]
    assert document is not None
    data = document.data
    repos = data.get("repos") if isinstance(data, dict) else None
    if not isinstance(repos, list):
        return [
            Issue(
                config["path"],
                "Pre-commit config has no repositories list.",
                repos,
                "repositories list",
            )
        ]
    hooks: list[tuple[dict[str, Any], int | None]] = []
    for repo_index, repo in enumerate(repos):
        if not isinstance(repo, dict) or not isinstance(repo.get("hooks"), list):
            continue
        for hook_index, hook in enumerate(repo["hooks"]):
            if isinstance(hook, dict):
                hooks.append(
                    (hook, document.line("repos", repo_index, "hooks", hook_index))
                )
    issues = []
    for expected in config["hooks"]:
        candidates = [
            (hook, line) for hook, line in hooks if hook.get("id") == expected["id"]
        ]
        if any(_hook_matches(candidate, expected) for candidate, _line in candidates):
            continue
        issues.append(
            Issue(
                config["path"],
                f"Hook {expected['id']!r} is missing or has incompatible "
                "command/fields.",
                [candidate for candidate, _line in candidates],
                expected,
                candidates[0][1] if candidates else document.line("repos"),
            )
        )
    return issues


def _uv_build_backend(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    data, error = _load_toml(context.root / config["path"])
    if error is not None:
        return [error]
    assert data is not None
    build_system = data.get("build-system")
    if build_system is None and context.profile in config.get(
        "allow_missing_profiles", []
    ):
        return []
    backend = (
        build_system.get("build-backend") if isinstance(build_system, dict) else None
    )
    if backend == config["backend"]:
        return []
    return [
        Issue(
            config["path"],
            "Build backend does not match policy.",
            backend,
            config["backend"],
        )
    ]


def _ruff(
    context: CheckContext, path: str
) -> tuple[dict[str, Any] | None, Issue | None]:
    data, error = _load_toml(context.root / path)
    if error is not None:
        return None, error
    assert data is not None
    ruff = data.get("tool", {}).get("ruff")
    if not isinstance(ruff, dict):
        return None, Issue(path, "No usable [tool.ruff] configuration.", ruff, "table")
    return ruff, None


def _ruff_baseline(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    ruff, error = _ruff(context, config["path"])
    if error is not None:
        return [error]
    assert ruff is not None
    issues = []
    if config["require_line_length"] and "line-length" not in ruff:
        issues.append(
            Issue(
                config["path"],
                "Ruff line-length is not explicit.",
                None,
                "declared integer",
            )
        )
    select = ruff.get("lint", {}).get("select", [])
    actual = set(select) if isinstance(select, list) else set()
    missing = sorted(set(config["required_select"]) - actual)
    if missing:
        issues.append(
            Issue(
                config["path"],
                f"Ruff drops required families: {missing}.",
                sorted(actual),
                config["required_select"],
            )
        )
    return issues


def _ruff_line_length(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    ruff, error = _ruff(context, config["path"])
    if error is not None or ruff is None or "line-length" not in ruff:
        return []
    actual = ruff["line-length"]
    if actual == config["value"]:
        return []
    return [
        Issue(
            config["path"],
            "Ruff line-length differs from the recommendation.",
            actual,
            config["value"],
        )
    ]


def _ruff_select(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    ruff, error = _ruff(context, config["path"])
    if error is not None or ruff is None:
        return []
    select = ruff.get("lint", {}).get("select", [])
    actual = set(select) if isinstance(select, list) else set()
    missing = sorted(set(config["values"]) - actual)
    if not missing:
        return []
    return [
        Issue(
            config["path"],
            f"Ruff omits recommended families: {missing}.",
            sorted(actual),
            config["values"],
        )
    ]


def _no_placeholders(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    issues = []
    for path in _iter_scannable_files(context.root):
        text = _read(path)
        if text is None:
            continue
        matches = sorted(token for token in config["placeholders"] if token in text)
        if matches:
            issues.append(
                Issue(
                    _relative(context.root, path),
                    f"Unresolved placeholder tokens: {', '.join(matches)}.",
                    matches,
                    [],
                )
            )
    return issues


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


def _branch_protection(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    remote = _git_remote_url(context.root)
    match = _GITHUB_REMOTE_PATTERN.search(remote) if remote else None
    if match is None:
        return [
            Issue(
                ".",
                "Could not resolve GitHub origin for platform check.",
                remote,
                "GitHub origin",
                status="indeterminate",
            )
        ]
    endpoint = (
        f"repos/{match.group('owner_repo')}/branches/{config['branch']}/protection"
    )
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            cwd=context.root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return [
            Issue(
                ".",
                f"Platform command unavailable: {error}",
                None,
                "branch protection response",
                status="indeterminate",
            )
        ]
    if result.returncode != 0:
        status = (
            "violation"
            if re.search(r"\b(?:403|404)\b", result.stderr)
            else "indeterminate"
        )
        return [
            Issue(
                ".",
                f"Branch protection query failed: {result.stderr.strip()}",
                result.stderr.strip(),
                "configured protection",
                status=status,
            )
        ]
    try:
        protection = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        return [
            Issue(
                ".",
                f"Platform response was not JSON: {error}",
                result.stdout,
                "JSON response",
                status="indeterminate",
            )
        ]
    issues = []
    contexts = protection.get("required_status_checks", {}).get("contexts", [])
    if config["status_check"] not in contexts:
        issues.append(
            Issue(
                ".",
                "Required status check is absent.",
                contexts,
                config["status_check"],
            )
        )
    reviews = protection.get("required_pull_request_reviews", {}).get(
        "required_approving_review_count", 0
    )
    if reviews < config["minimum_reviews"]:
        issues.append(
            Issue(
                ".",
                "Too few approving reviews are required.",
                reviews,
                config["minimum_reviews"],
            )
        )
    if not protection.get("enforce_admins", {}).get("enabled", False):
        issues.append(Issue(".", "Administrators may bypass protection.", False, True))
    return issues


def _repo_metadata(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    data, error = _load_toml(context.root / config["path"])
    if error is not None:
        return [error]
    assert data is not None
    metadata = data.get("tool", {}).get("repo-standard")
    expected = {
        "profile": list(context.policy.profile_ids),
        "standard": config["standard_major"],
    }
    if not isinstance(metadata, dict):
        return [
            Issue(
                config["path"],
                "Missing [tool.repo-standard] metadata.",
                metadata,
                expected,
            )
        ]
    unknown = set(metadata) - {"profile", "standard"}
    profile = metadata.get("profile")
    standard = metadata.get("standard")
    if (
        not unknown
        and profile in context.policy.profile_ids
        and standard == config["standard_major"]
    ):
        return []
    return [
        Issue(
            config["path"],
            "Invalid [tool.repo-standard] profile or standard major.",
            metadata,
            expected,
        )
    ]


def _effective_permissions(workflow: dict[str, Any], job: dict[str, Any]) -> Any:
    return job["permissions"] if "permissions" in job else workflow.get("permissions")


def _github_workflow_permissions(
    context: CheckContext, config: dict[str, Any]
) -> list[Issue]:
    document, job, errors = _workflow_job(context, config)
    if errors:
        return []
    assert document is not None
    assert job is not None
    assert isinstance(document.data, dict)
    permissions = _effective_permissions(document.data, job)
    valid = permissions == "read-all" or (
        isinstance(permissions, dict)
        and permissions.get("contents") == "read"
        and not any(value == "write" for value in permissions.values())
    )
    if valid:
        return []
    line = document.line("jobs", config["job"], "permissions") or document.line(
        "permissions"
    )
    return [
        Issue(
            config["path"],
            "Quality job permissions are not least privilege.",
            permissions,
            {"contents": "read", "writes": "none"},
            line,
        )
    ]


def _remote_uses(reference: str) -> bool:
    return not reference.startswith("./") and not reference.startswith("docker://")


def _immutable_reference(reference: str) -> bool:
    return (
        "@" in reference
        and _FULL_SHA.fullmatch(reference.rsplit("@", 1)[1]) is not None
    )


def _github_workflow_pins(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    document, job, errors = _workflow_job(context, config)
    if errors:
        return []
    assert document is not None
    assert job is not None
    assert isinstance(document.data, dict)
    jobs = document.data.get("jobs")
    assert isinstance(jobs, dict)
    references: list[tuple[str, int | None]] = []
    for job_id, workflow_job in jobs.items():
        if not isinstance(job_id, str) or not isinstance(workflow_job, dict):
            continue
        if isinstance(workflow_job.get("uses"), str):
            references.append(
                (workflow_job["uses"], document.line("jobs", job_id, "uses"))
            )
        steps = workflow_job.get("steps")
        if not isinstance(steps, list):
            continue
        for index, step in enumerate(steps):
            if isinstance(step, dict) and isinstance(step.get("uses"), str):
                references.append(
                    (
                        step["uses"],
                        document.line("jobs", job_id, "steps", index, "uses"),
                    )
                )
    return [
        Issue(
            config["path"],
            f"Remote reference is not pinned to a full commit SHA: {reference}.",
            reference,
            "remote@40-character-SHA",
            line,
        )
        for reference, line in references
        if _remote_uses(reference) and not _immutable_reference(reference)
    ]


CHECK_HANDLERS: dict[str, CheckHandler] = {
    "path_exists": _path_exists,
    "markdown_headings": _markdown_headings,
    "text_contains_all": _text_contains_all,
    "text_pattern_each": _text_pattern_each,
    "github_workflow_commands": _github_workflow_commands,
    "pre_commit_hooks": _pre_commit_hooks,
    "uv_build_backend": _uv_build_backend,
    "ruff_baseline": _ruff_baseline,
    "ruff_line_length": _ruff_line_length,
    "ruff_select": _ruff_select,
    "no_placeholders": _no_placeholders,
    "branch_protection": _branch_protection,
    "repo_metadata": _repo_metadata,
    "github_workflow_permissions": _github_workflow_permissions,
    "github_workflow_pins": _github_workflow_pins,
}


def _finding(rule: Rule, issue: Issue) -> Finding:
    severity = "platform" if issue.status == "indeterminate" else rule.severity
    return Finding(
        rule.id,
        rule.title,
        rule.level,
        severity,
        issue.path,
        issue.line,
        issue.message,
        issue.actual,
        issue.expected,
        rule.remediation,
        issue.status,
    )


def _load_ignore_config(root: Path, policy: Policy) -> dict[str, str]:
    data, error = _load_toml(root / "pyproject.toml")
    if error is not None or data is None:
        return {}
    ignore = data.get("tool", {}).get("repo-check", {}).get("ignore", {})
    if not isinstance(ignore, dict):
        return {}
    known = set(policy.rule_ids)
    return {
        rule_id: reason
        for rule_id, reason in ignore.items()
        if rule_id in known and isinstance(reason, str) and reason.strip()
    }


def check_repo(
    root: Path,
    policy: Policy,
    *,
    profile: str | None = None,
    include_platform: bool = False,
) -> list[Finding]:
    """Check structural alignment using profile-filtered canonical rules."""
    resolved_profile = resolve_profile(root, policy, profile)
    context = CheckContext(root=root, policy=policy, profile=resolved_profile)
    findings: list[Finding] = []
    for rule in policy.rules:
        if resolved_profile not in rule.profiles:
            continue
        if rule.enforcement == "platform" and not include_platform:
            continue
        handler = CHECK_HANDLERS[rule.check.kind]
        findings.extend(
            _finding(rule, issue) for issue in handler(context, rule.check.config)
        )
    ignored = _load_ignore_config(root, policy)
    return [finding for finding in findings if finding.rule_id not in ignored]
