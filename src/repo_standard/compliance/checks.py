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
from repo_standard.github_references import is_full_commit_sha
from repo_standard.policy import Policy, Rule, Shape, load_compiled_policy

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


def _shape_issues(shape: Shape, path: str, actual: list[str]) -> list[Issue]:
    """Compare observed section names against one canonical shape.

    Presence is checked for required sections only. Order is checked as a
    subsequence: sections the shape does not list are ignored entirely, and a
    listed section that is absent simply drops out of the comparison.
    """
    issues: list[Issue] = []
    missing = [heading for heading in shape.required if heading not in actual]
    if missing:
        issues.append(
            Issue(
                path,
                f"Missing required sections: {', '.join(missing)}.",
                actual,
                list(shape.required),
            )
        )
    listed = set(shape.headings)
    observed: list[str] = []
    for heading in actual:
        if heading in listed and heading not in observed:
            observed.append(heading)
    expected = [heading for heading in shape.headings if heading in observed]
    if observed != expected:
        issues.append(
            Issue(
                path,
                "Declared sections are out of canonical order.",
                observed,
                expected,
            )
        )
    if not shape.allow_unlisted:
        unlisted = [heading for heading in actual if heading not in listed]
        if unlisted:
            issues.append(
                Issue(
                    path,
                    f"Sections the shape does not declare: {', '.join(unlisted)}.",
                    unlisted,
                    list(shape.headings),
                )
            )
    return issues


def _markdown_shape(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    shape = context.policy.shape(config["shape"])
    text = _read(context.root / shape.path)
    if text is None:
        return []
    marks = "#" * (shape.heading_level or 2)
    actual = re.findall(rf"^{marks}\s+(.+?)\s*$", text, re.MULTILINE)
    return _shape_issues(shape, shape.path, actual)


def _toml_table_names(text: str) -> list[str]:
    """Return table headers in document order, ignoring multi-line strings."""
    names: list[str] = []
    delimiter: str | None = None
    for line in text.splitlines():
        if delimiter is not None:
            if delimiter in line:
                delimiter = None
            continue
        stripped = line.strip()
        match = re.fullmatch(r"\[\[?\s*(?P<name>[^\[\]]+?)\s*\]\]?", stripped)
        if match is not None:
            names.append(match.group("name"))
            continue
        for candidate in ('"""', "'''"):
            if line.count(candidate) % 2 == 1:
                delimiter = candidate
                break
    return names


def _toml_table_order(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    shape = context.policy.shape(config["shape"])
    path = context.root / shape.path
    text = _read(path)
    if text is None:
        return []
    _data, error = _load_toml(path)
    if error is not None:
        return [error]
    return _shape_issues(shape, shape.path, _toml_table_names(text))


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


def _section_body(text: str, heading: str) -> str | None:
    """Return the body of the level-two section named `heading`, if present."""
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n?(?P<body>.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match is not None else None


def _agents_quality_commands(
    context: CheckContext, config: dict[str, Any]
) -> list[Issue]:
    text = _read(context.root / config["path"])
    if text is None:
        return []
    body = _section_body(text, "Quality Gates")
    actual: list[str] = []
    if body is not None:
        actual = [
            re.sub(r"\s+", " ", command).strip()
            for command in re.findall(
                r"^\s*(?:\d+[.)]|[-*+])\s+`([^`\r\n]+)`\s*$",
                body,
                re.MULTILINE,
            )
        ]
    expected = config["commands_by_profile"][context.profile]
    if actual == expected:
        return []
    return [
        Issue(
            config["path"],
            "Quality Gates must list the exact ordered commands for profile "
            f"{context.profile!r}.",
            actual,
            expected,
        )
    ]


_DIAL_LINE = re.compile(
    r"^[ \t]*[-*+][ \t]+\*\*(?P<label>[^*\r\n]+?)[ \t]*:?\*\*[ \t]*"
    r"(?P<level>\d+)[ \t]*/[ \t]*(?P<scale>\d+)[ \t]*$",
    re.MULTILINE,
)


def _dial(label: str, level: object, scale: object) -> str:
    return f"{label}: {level} / {scale}"


def _agents_operating_dials(
    context: CheckContext, config: dict[str, Any]
) -> list[Issue]:
    """RSK026: the operating dials are policy values, not prose an editor owns.

    Deliberately parallel to `_agents_quality_commands`: the section must state
    every dial, in the declared order, at the declared level. Prose around them
    is the repository's business.
    """
    text = _read(context.root / config["path"])
    if text is None:
        return []
    body = _section_body(text, config["section"])
    actual: list[str] = []
    if body is not None:
        actual = [
            _dial(
                match.group("label").strip(), match.group("level"), match.group("scale")
            )
            for match in _DIAL_LINE.finditer(body)
        ]
    expected = [_dial(d["label"], d["level"], d["scale"]) for d in config["dials"]]
    if actual == expected:
        return []
    return [
        Issue(
            config["path"],
            f"{config['section']} must state every dial, in order, at the level "
            "policy declares.",
            actual,
            expected,
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


def _workflow_jobs(
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
    if not isinstance(jobs, dict):
        return (
            document,
            None,
            [
                Issue(
                    config["path"],
                    "Workflow jobs must be a mapping.",
                    jobs,
                    "mapping",
                    document.line("jobs"),
                )
            ],
        )
    return document, jobs, []


def _workflow_job(
    context: CheckContext, config: dict[str, Any]
) -> tuple[YamlDocument | None, dict[str, Any] | None, list[Issue]]:
    document, jobs, errors = _workflow_jobs(context, config)
    if errors:
        return document, None, errors
    assert document is not None
    assert jobs is not None
    if not isinstance(jobs.get(config["job"]), dict):
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


def _gh_api(
    context: CheckContext, endpoint: str, *, paginate: bool = False
) -> tuple[subprocess.CompletedProcess[str] | None, Issue | None]:
    command = ["gh", "api"]
    if paginate:
        command.extend(("--paginate", "--slurp"))
    command.append(endpoint)
    try:
        result = subprocess.run(
            command,
            cwd=context.root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return None, (
            Issue(
                ".",
                f"Platform command unavailable: {error}",
                None,
                "GitHub enforcement response",
                status="indeterminate",
            )
        )
    return result, None


def _platform_query_failure(
    message: str, stderr: str, expected: Any, *, unsupported_is_violation: bool = True
) -> Issue:
    unsupported = unsupported_is_violation and re.search(
        r"upgrade to github pro|branch protection (?:is )?not available",
        stderr,
        re.IGNORECASE,
    )
    return Issue(
        ".",
        f"{message}: {stderr}",
        stderr,
        expected,
        status="violation" if unsupported else "indeterminate",
    )


def _json_response(
    result: subprocess.CompletedProcess[str], expected: str
) -> tuple[Any | None, Issue | None]:
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as error:
        return None, (
            Issue(
                ".",
                f"Platform response was not JSON: {error}",
                result.stdout,
                expected,
                status="indeterminate",
            )
        )


def _ruleset_detail_endpoint(
    owner_repo: str, source_type: str, source: str, ruleset_id: int
) -> str | None:
    if source_type == "Repository":
        repository = source if "/" in source else owner_repo
        return f"repos/{repository}/rulesets/{ruleset_id}"
    if source_type == "Organization":
        return f"orgs/{source}/rulesets/{ruleset_id}"
    return None


def _ruleset_branch_protection(
    context: CheckContext, owner_repo: str, config: dict[str, Any]
) -> list[Issue]:
    endpoint = f"repos/{owner_repo}/rules/branches/{config['branch']}"
    result, error = _gh_api(context, endpoint, paginate=True)
    if error is not None:
        return [error]
    assert result is not None
    if result.returncode != 0:
        stderr = result.stderr.strip()
        return [
            _platform_query_failure(
                "Ruleset query failed",
                stderr,
                "effective rules for branch",
            )
        ]
    pages, error = _json_response(result, "paginated ruleset response")
    if error is not None:
        return [error]
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        return [
            Issue(
                ".",
                "Effective rules response was not a paginated list.",
                pages,
                "list of rule pages",
                status="indeterminate",
            )
        ]

    rules = [rule for page in pages for rule in page]
    needs_pull_request_rule = any(
        key in config
        for key in (
            "minimum_reviews",
            "dismiss_stale_approvals",
            "require_conversation_resolution",
        )
    )
    needs_status_check_rule = any(
        key in config for key in ("required_status_checks", "require_up_to_date")
    )
    relevant_types = set()
    if needs_pull_request_rule:
        relevant_types.add("pull_request")
    if needs_status_check_rule:
        relevant_types.add("required_status_checks")
    relevant_rules: list[dict[str, Any]] = []
    ruleset_sources: set[tuple[str, str, int]] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            return [
                Issue(
                    ".",
                    "Could not interpret an effective ruleset rule.",
                    rule,
                    "rule object",
                    status="indeterminate",
                )
            ]
        if rule.get("type") not in relevant_types:
            continue
        parameters = rule.get("parameters")
        source_type = rule.get("ruleset_source_type")
        source = rule.get("ruleset_source")
        ruleset_id = rule.get("ruleset_id")
        if (
            not isinstance(parameters, dict)
            or not isinstance(source_type, str)
            or not isinstance(source, str)
            or isinstance(ruleset_id, bool)
            or not isinstance(ruleset_id, int)
        ):
            return [
                Issue(
                    ".",
                    "Could not interpret effective ruleset metadata.",
                    rule,
                    "rule parameters and source metadata",
                    status="indeterminate",
                )
            ]
        relevant_rules.append(rule)
        ruleset_sources.add((source_type, source, ruleset_id))

    bypass_actors: list[Any] = []
    if "enforce_admins" in config:
        for source_type, source, ruleset_id in sorted(ruleset_sources):
            detail_endpoint = _ruleset_detail_endpoint(
                owner_repo, source_type, source, ruleset_id
            )
            if detail_endpoint is None:
                return [
                    Issue(
                        ".",
                        f"Unsupported ruleset source type: {source_type}.",
                        source_type,
                        "Repository or Organization",
                        status="indeterminate",
                    )
                ]
            detail_result, detail_error = _gh_api(context, detail_endpoint)
            if detail_error is not None:
                return [detail_error]
            assert detail_result is not None
            if detail_result.returncode != 0:
                stderr = detail_result.stderr.strip()
                return [
                    _platform_query_failure(
                        "Ruleset detail query failed",
                        stderr,
                        "ruleset bypass actors",
                        unsupported_is_violation=False,
                    )
                ]
            detail, detail_error = _json_response(
                detail_result, "ruleset detail response"
            )
            if detail_error is not None:
                return [detail_error]
            actors = detail.get("bypass_actors") if isinstance(detail, dict) else None
            if not isinstance(actors, list):
                return [
                    Issue(
                        ".",
                        "Could not obtain ruleset bypass actors.",
                        actors,
                        "bypass actor list",
                        status="indeterminate",
                    )
                ]
            bypass_actors.extend(actors)

    pull_request_rules = [
        rule for rule in relevant_rules if rule["type"] == "pull_request"
    ]
    status_check_rules = [
        rule for rule in relevant_rules if rule["type"] == "required_status_checks"
    ]
    review_counts: list[int] = []
    dismiss_stale: list[bool] = []
    conversation_resolution: list[bool] = []
    for rule in pull_request_rules:
        parameters = rule["parameters"]
        if "minimum_reviews" in config:
            reviews = parameters.get("required_approving_review_count")
            if isinstance(reviews, bool) or not isinstance(reviews, int):
                return [
                    Issue(
                        ".",
                        "Could not interpret required approving review count.",
                        reviews,
                        config["minimum_reviews"],
                        status="indeterminate",
                    )
                ]
            review_counts.append(reviews)
        if "dismiss_stale_approvals" in config:
            stale = parameters.get("dismiss_stale_reviews_on_push")
            if not isinstance(stale, bool):
                return [
                    Issue(
                        ".",
                        "Could not interpret stale approval dismissal.",
                        stale,
                        config["dismiss_stale_approvals"],
                        status="indeterminate",
                    )
                ]
            dismiss_stale.append(stale)
        if "require_conversation_resolution" in config:
            resolution = parameters.get("required_review_thread_resolution")
            if not isinstance(resolution, bool):
                return [
                    Issue(
                        ".",
                        "Could not interpret required review thread resolution.",
                        resolution,
                        config["require_conversation_resolution"],
                        status="indeterminate",
                    )
                ]
            conversation_resolution.append(resolution)

    contexts: set[str] = set()
    strict_checks: list[bool] = []
    for rule in status_check_rules:
        parameters = rule["parameters"]
        checks = parameters.get("required_status_checks")
        strict = parameters.get("strict_required_status_checks_policy")
        if (
            not isinstance(checks, list)
            or not isinstance(strict, bool)
            or not all(
                isinstance(check, dict) and isinstance(check.get("context"), str)
                for check in checks
            )
        ):
            return [
                Issue(
                    ".",
                    "Could not interpret required status check ruleset parameters.",
                    parameters,
                    "status check contexts and strict policy",
                    status="indeterminate",
                )
            ]
        contexts.update(check["context"] for check in checks)
        strict_checks.append(strict)

    protection: dict[str, Any] = {}
    if needs_pull_request_rule:
        review_protection: dict[str, Any] | None = None
        if pull_request_rules:
            review_protection = {}
            if "minimum_reviews" in config:
                review_protection["required_approving_review_count"] = max(
                    review_counts
                )
            if "dismiss_stale_approvals" in config:
                review_protection["dismiss_stale_reviews"] = any(dismiss_stale)
        protection["required_pull_request_reviews"] = review_protection
    if needs_status_check_rule:
        status_checks: dict[str, Any] | None = None
        if status_check_rules:
            status_checks = {}
            if "required_status_checks" in config:
                status_checks["contexts"] = sorted(contexts)
            if "require_up_to_date" in config:
                status_checks["strict"] = any(strict_checks)
        protection["required_status_checks"] = status_checks
    if "require_conversation_resolution" in config:
        protection["required_conversation_resolution"] = {
            "enabled": any(conversation_resolution)
        }
    if "enforce_admins" in config:
        protection["enforce_admins"] = {
            "enabled": not bypass_actors and bool(relevant_rules)
        }
    return _branch_protection_issues(protection, config)


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
    owner_repo = match.group("owner_repo")
    endpoint = f"repos/{owner_repo}/branches/{config['branch']}/protection"
    result, error = _gh_api(context, endpoint)
    if error is not None:
        return [error]
    assert result is not None
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if re.search(r"branch not protected", stderr, re.IGNORECASE):
            return _ruleset_branch_protection(context, owner_repo, config)
        return [
            _platform_query_failure(
                "Branch protection query failed", stderr, "configured protection"
            )
        ]
    protection, error = _json_response(result, "branch protection response")
    if error is not None:
        return [error]
    if not isinstance(protection, dict):
        return [
            Issue(
                ".",
                "Platform response root was not an object.",
                protection,
                "branch protection object",
                status="indeterminate",
            )
        ]
    return _branch_protection_issues(protection, config)


def _branch_protection_issues(
    protection: dict[str, Any], config: dict[str, Any]
) -> list[Issue]:

    branch = config["branch"]
    issues: list[Issue] = []

    if "minimum_reviews" in config or "dismiss_stale_approvals" in config:
        review_protection = protection.get("required_pull_request_reviews")
        if review_protection is None:
            issues.append(
                Issue(
                    ".",
                    f"{branch} does not require pull requests.",
                    review_protection,
                    "pull request review protection",
                )
            )
        elif not isinstance(review_protection, dict):
            issues.append(
                Issue(
                    ".",
                    "Could not interpret pull request review protection.",
                    review_protection,
                    "pull request review protection object",
                    status="indeterminate",
                )
            )
        else:
            if "minimum_reviews" in config:
                reviews = review_protection.get("required_approving_review_count")
                if isinstance(reviews, bool) or not isinstance(reviews, int):
                    issues.append(
                        Issue(
                            ".",
                            "Could not interpret required approving review count.",
                            reviews,
                            config["minimum_reviews"],
                            status="indeterminate",
                        )
                    )
                elif reviews < config["minimum_reviews"]:
                    issues.append(
                        Issue(
                            ".",
                            f"{branch} requires too few approving reviews.",
                            reviews,
                            config["minimum_reviews"],
                        )
                    )
            if "dismiss_stale_approvals" in config:
                dismiss_stale = review_protection.get("dismiss_stale_reviews")
                if not isinstance(dismiss_stale, bool):
                    issues.append(
                        Issue(
                            ".",
                            "Could not interpret stale approval dismissal.",
                            dismiss_stale,
                            config["dismiss_stale_approvals"],
                            status="indeterminate",
                        )
                    )
                elif dismiss_stale != config["dismiss_stale_approvals"]:
                    issues.append(
                        Issue(
                            ".",
                            f"{branch} does not dismiss stale approvals.",
                            dismiss_stale,
                            config["dismiss_stale_approvals"],
                        )
                    )

    if "required_status_checks" in config or "require_up_to_date" in config:
        status_checks = protection.get("required_status_checks")
        if status_checks is None:
            expected = config.get(
                "required_status_checks", {"strict": config["require_up_to_date"]}
            )
            issues.append(
                Issue(
                    ".",
                    f"{branch} does not require status checks.",
                    status_checks,
                    expected,
                )
            )
        elif not isinstance(status_checks, dict):
            issues.append(
                Issue(
                    ".",
                    "Could not interpret required status checks.",
                    status_checks,
                    "required status checks object",
                    status="indeterminate",
                )
            )
        else:
            if "required_status_checks" in config:
                contexts = status_checks.get("contexts")
                if not isinstance(contexts, list) or not all(
                    isinstance(context, str) for context in contexts
                ):
                    issues.append(
                        Issue(
                            ".",
                            "Could not interpret required status check contexts.",
                            contexts,
                            config["required_status_checks"],
                            status="indeterminate",
                        )
                    )
                else:
                    missing_contexts = [
                        context
                        for context in config["required_status_checks"]
                        if context not in contexts
                    ]
                    if missing_contexts:
                        issues.append(
                            Issue(
                                ".",
                                f"{branch} omits required status checks: "
                                f"{', '.join(missing_contexts)}.",
                                contexts,
                                config["required_status_checks"],
                            )
                        )
            if "require_up_to_date" in config:
                strict = status_checks.get("strict")
                if not isinstance(strict, bool):
                    issues.append(
                        Issue(
                            ".",
                            "Could not interpret the up-to-date branch requirement.",
                            strict,
                            config["require_up_to_date"],
                            status="indeterminate",
                        )
                    )
                elif strict != config["require_up_to_date"]:
                    issues.append(
                        Issue(
                            ".",
                            f"{branch} does not require branches to be up to date.",
                            strict,
                            config["require_up_to_date"],
                        )
                    )

    for response_key, config_key, message in (
        (
            "required_conversation_resolution",
            "require_conversation_resolution",
            f"{branch} does not require conversation resolution.",
        ),
        (
            "enforce_admins",
            "enforce_admins",
            f"{branch} allows administrator bypass.",
        ),
    ):
        if config_key not in config:
            continue
        setting = protection.get(response_key)
        if setting is None:
            issues.append(Issue(".", message, False, config[config_key]))
            continue
        if not isinstance(setting, dict) or not isinstance(
            setting.get("enabled"), bool
        ):
            issues.append(
                Issue(
                    ".",
                    f"Could not interpret {response_key.replace('_', ' ')}.",
                    setting,
                    {"enabled": config[config_key]},
                    status="indeterminate",
                )
            )
            continue
        enabled = setting["enabled"]
        if enabled != config[config_key]:
            issues.append(Issue(".", message, enabled, config[config_key]))
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
    expected = config["permissions"]
    if permissions == expected:
        return []
    line = document.line("jobs", config["job"], "permissions") or document.line(
        "permissions"
    )
    return [
        Issue(
            config["path"],
            "Quality job permissions do not match the least-privilege policy.",
            permissions,
            expected,
            line,
        )
    ]


def _remote_uses(reference: str) -> bool:
    return not reference.startswith("./") and not reference.startswith("docker://")


def _immutable_reference(reference: str) -> bool:
    return "@" in reference and is_full_commit_sha(reference.rsplit("@", 1)[1])


def _github_workflow_pins(context: CheckContext, config: dict[str, Any]) -> list[Issue]:
    document, jobs, errors = _workflow_jobs(context, config)
    if errors:
        return errors
    assert document is not None
    assert jobs is not None
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
    "markdown_shape": _markdown_shape,
    "toml_table_order": _toml_table_order,
    "text_contains_all": _text_contains_all,
    "agents_quality_commands": _agents_quality_commands,
    "agents_operating_dials": _agents_operating_dials,
    "text_pattern_each": _text_pattern_each,
    "github_workflow_commands": _github_workflow_commands,
    "pre_commit_hooks": _pre_commit_hooks,
    "uv_build_backend": _uv_build_backend,
    "ruff_baseline": _ruff_baseline,
    "ruff_line_length": _ruff_line_length,
    "ruff_select": _ruff_select,
    "no_placeholders": _no_placeholders,
    "branch_protection": _branch_protection,
    "branch_protection_minimum_reviews": _branch_protection,
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
