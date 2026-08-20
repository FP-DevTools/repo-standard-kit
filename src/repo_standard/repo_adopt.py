"""Conflict-aware adoption of repo-standard-kit into an existing repository."""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import re
import shlex
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import tomlkit
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from tomlkit.exceptions import ParseError

from repo_standard.compliance.checks import Finding, check_repo, load_policy
from repo_standard.repo_init import PLACEHOLDERS, resolve_starter_dir


class AdoptionError(RuntimeError):
    """An adoption precondition or reconciliation failure."""


class CommandError(AdoptionError):
    """A post-reconciliation command could not complete."""

    def __init__(self, command: list[str], detail: str) -> None:
        self.command = command
        super().__init__(f"command failed: {shlex.join(command)} ({detail})")


@dataclass(frozen=True)
class PlannedFile:
    path: Path
    content: str
    action: str


@dataclass(frozen=True)
class AdoptionPlan:
    root: Path
    profile: str
    version: str
    changes: tuple[PlannedFile, ...]
    unchanged: tuple[str, ...]
    conflicts: tuple[str, ...]
    dependency_metadata_changed: bool


_MANAGED_SURFACES = (
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".github/workflows/quality.yml",
    ".github/workflows/compliance.yml",
    ".github/dependabot.yml",
    ".pymarkdown.json",
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "docs/adr",
    "docs/diagrams",
)
_REMOTE_ACTION = re.compile(r"^[^./\s]+/[^@\s]+@(?P<ref>[^\s]+)$")
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_ROUND_TRIP_YAML = YAML()
_ROUND_TRIP_YAML.preserve_quotes = True
_ROUND_TRIP_YAML.width = 88
_ROUND_TRIP_YAML.indent(mapping=2, sequence=4, offset=2)


def _kit_version() -> str:
    try:
        return importlib.metadata.version("repo-standard-kit")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        return str(
            tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        )


def build_parser() -> argparse.ArgumentParser:
    policy = load_policy()
    parser = argparse.ArgumentParser(
        description="Adopt repo-standard-kit into an existing repository."
    )
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--profile", choices=policy.profile_ids)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-lock", action="store_true")
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument(
        "--run-gates",
        action="store_true",
        help="Run the complete quality-gate chain after reconciliation.",
    )
    return parser


def _parse_toml(path: Path) -> Any:
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AdoptionError(
            f"{path} is missing; repo-adopt requires pyproject.toml"
        ) from error
    except (ParseError, UnicodeDecodeError) as error:
        raise AdoptionError(f"could not parse {path}: {error}") from error


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = _ROUND_TRIP_YAML.load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (YAMLError, UnicodeDecodeError) as error:
        raise AdoptionError(f"could not parse {path}: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise AdoptionError(f"could not reconcile {path}: expected a YAML mapping")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    stream = StringIO()
    _ROUND_TRIP_YAML.dump(data, stream)
    return stream.getvalue()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AdoptionError(f"could not parse {path}: {error}") from error
    if not isinstance(data, dict):
        raise AdoptionError(f"could not reconcile {path}: expected a JSON object")
    return data


def _read_starter(profile: str, relative: str) -> str:
    return (resolve_starter_dir(profile) / relative).read_text(encoding="utf-8")


def _render(text: str, values: dict[str, str]) -> str:
    for placeholder, key in PLACEHOLDERS.items():
        text = text.replace(placeholder, values[key])
    return text


def _project_values(root: Path, document: Any) -> dict[str, str]:
    project = document.get("project", {})
    name = str(project.get("name") or root.name)
    description = str(project.get("description") or "Describe this repository.")
    normalized = re.sub(r"\W", "_", name.replace("-", "_")).lower()
    return {
        "repo_name": name,
        "package_name": normalized,
        "description": description,
        "repo_type": "library",
        "python_version": "3.12",
        "author": "",
    }


def _resolve_profile(root: Path, document: Any, override: str | None) -> str:
    policy = load_policy()
    metadata = document.get("tool", {}).get("repo-standard")
    if override is not None:
        return override
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise AdoptionError("[tool.repo-standard] must be a TOML table")
        profile = metadata.get("profile")
        standard = metadata.get("standard")
        if profile not in policy.profile_ids or standard != policy.standard_major:
            raise AdoptionError(
                "existing [tool.repo-standard] metadata is invalid; pass --profile "
                "to make the intended profile explicit"
            )
        return str(profile)

    matches: list[str] = []
    default: str | None = None
    for candidate in policy.profiles:
        if candidate.detection.default:
            default = candidate.id
            continue
        marker_matches = [
            (root / marker.path).is_file()
            if marker.kind == "file"
            else (root / marker.path).is_dir()
            for marker in candidate.detection.markers
        ]
        if marker_matches and all(marker_matches):
            matches.append(candidate.id)
    if len(matches) > 1:
        raise AdoptionError(
            "profile detection is ambiguous; pass --profile explicitly (matched: "
            + ", ".join(matches)
            + ")"
        )
    if matches:
        return matches[0]
    if default is None:
        raise AdoptionError(
            "profile detection found no match and policy has no default"
        )
    return default


def _ensure_table(parent: Any, key: str) -> Any:
    value = parent.get(key)
    if value is None:
        value = tomlkit.table()
        parent[key] = value
    if not isinstance(value, dict):
        raise AdoptionError(f"cannot merge TOML key {key!r}: expected a table")
    return value


def _merge_pyproject(
    path: Path, document: Any, profile: str
) -> tuple[str, bool, list[str]]:
    starter = tomllib.loads(_read_starter(profile, "pyproject.toml"))
    conflicts: list[str] = []
    dependency_changed = False

    tool = _ensure_table(document, "tool")
    metadata = _ensure_table(tool, "repo-standard")
    unknown = set(metadata) - {"profile", "standard"}
    if unknown:
        conflicts.append(
            "pyproject.toml: [tool.repo-standard] has unsupported keys: "
            + ", ".join(sorted(unknown))
        )
    metadata["profile"] = profile
    metadata["standard"] = load_policy().standard_major

    groups = _ensure_table(document, "dependency-groups")
    dev = groups.get("dev")
    if dev is None:
        dev = tomlkit.array().multiline(True)
        groups["dev"] = dev
    if not isinstance(dev, list):
        raise AdoptionError("cannot merge dependency-groups.dev: expected an array")
    for requirement in starter["dependency-groups"]["dev"]:
        package = re.split(r"[<>=!~\[]", requirement, maxsplit=1)[0].lower()
        existing = [str(item) for item in dev]
        if not any(
            re.split(r"[<>=!~\[]", item, maxsplit=1)[0].lower() == package
            for item in existing
        ):
            dev.append(requirement)
            dependency_changed = True

    ruff = _ensure_table(tool, "ruff")
    if "line-length" not in ruff:
        ruff["line-length"] = starter["tool"]["ruff"]["line-length"]
    lint = _ensure_table(ruff, "lint")
    select = lint.get("select")
    if select is None:
        select = tomlkit.array()
        lint["select"] = select
    if not isinstance(select, list):
        raise AdoptionError("cannot merge tool.ruff.lint.select: expected an array")
    for family in starter["tool"]["ruff"]["lint"]["select"]:
        if family not in select:
            select.append(family)

    if profile == "python-single":
        build = document.get("build-system")
        if build is None:
            build = tomlkit.table()
            build["requires"] = starter["build-system"]["requires"]
            build["build-backend"] = starter["build-system"]["build-backend"]
            document["build-system"] = build
            dependency_changed = True
        elif not isinstance(build, dict):
            raise AdoptionError("cannot merge build-system: expected a table")

    return tomlkit.dumps(document), dependency_changed, conflicts


def _merge_pre_commit(path: Path, profile: str) -> str:
    current = _load_yaml(path)
    expected = _ROUND_TRIP_YAML.load(_read_starter(profile, ".pre-commit-config.yaml"))
    repos = current.setdefault("repos", [])
    if not isinstance(repos, list):
        raise AdoptionError(f"cannot reconcile {path}: repos must be a list")
    for expected_repo in expected["repos"]:
        expected_hooks = expected_repo.get("hooks", [])
        repo = next(
            (
                item
                for item in repos
                if isinstance(item, dict) and item.get("repo") == expected_repo["repo"]
            ),
            None,
        )
        if repo is None:
            repos.append(copy.deepcopy(expected_repo))
            continue
        if "rev" in expected_repo:
            repo["rev"] = expected_repo["rev"]
        hooks = repo.setdefault("hooks", [])
        if not isinstance(hooks, list):
            raise AdoptionError(f"cannot reconcile {path}: hooks must be a list")
        for expected_hook in expected_hooks:
            hook = next(
                (
                    item
                    for item in hooks
                    if isinstance(item, dict) and item.get("id") == expected_hook["id"]
                ),
                None,
            )
            if hook is None:
                hooks.append(copy.deepcopy(expected_hook))
                continue
            if "args" not in expected_hook:
                hook.pop("args", None)
            hook.update(copy.deepcopy(expected_hook))
    return _dump_yaml(current)


def _ensure_trigger(workflow: dict[str, Any], trigger: str) -> None:
    current = workflow.get("on")
    if current is None:
        workflow["on"] = {trigger: None}
    elif isinstance(current, str):
        if current != trigger:
            workflow["on"] = {current: None, trigger: None}
    elif isinstance(current, list):
        if trigger not in current:
            current.append(trigger)
    elif isinstance(current, dict):
        current.setdefault(trigger, None)
    else:
        raise AdoptionError("workflow 'on' value must be a string, list, or mapping")


def _action_family(value: str) -> str:
    return value.split("@", maxsplit=1)[0]


def _merge_workflow(
    path: Path, profile: str, relative: str, job_name: str
) -> tuple[str, list[str]]:
    current = _load_yaml(path)
    expected = _ROUND_TRIP_YAML.load(_read_starter(profile, relative))
    _ensure_trigger(current, "pull_request")
    current.setdefault("name", expected["name"])
    if "permissions" not in current and "permissions" in expected:
        current["permissions"] = copy.deepcopy(expected["permissions"])
    jobs = current.setdefault("jobs", {})
    if not isinstance(jobs, dict):
        raise AdoptionError(f"cannot reconcile {path}: jobs must be a mapping")
    expected_job = expected["jobs"][job_name]
    job = jobs.get(job_name)
    if job is None:
        job = copy.deepcopy(expected_job)
        jobs[job_name] = job
        return _dump_yaml(current), []
    if not isinstance(job, dict):
        raise AdoptionError(
            f"cannot reconcile {path}: job {job_name!r} must be a mapping"
        )
    if (
        job_name in {"quality", "compliance"}
        and job.get("permissions") != {"contents": "read"}
        and current.get("permissions") != {"contents": "read"}
    ):
        job["permissions"] = {"contents": "read"}
    steps = job.setdefault("steps", [])
    if not isinstance(steps, list):
        raise AdoptionError(f"cannot reconcile {path}: job steps must be a list")

    for expected_step in expected_job["steps"]:
        expected_uses = expected_step.get("uses")
        expected_run = expected_step.get("run")
        match = None
        update_run = False
        if isinstance(expected_uses, str):
            family = _action_family(expected_uses)
            match = next(
                (
                    step
                    for step in steps
                    if isinstance(step, dict)
                    and isinstance(step.get("uses"), str)
                    and _action_family(step["uses"]) == family
                ),
                None,
            )
        elif isinstance(expected_run, str):
            expected_tokens = shlex.split(expected_run.replace("\n", " "))
            match = next(
                (
                    step
                    for step in steps
                    if isinstance(step, dict)
                    and isinstance(step.get("run"), str)
                    and shlex.split(step["run"].replace("\n", " ")) == expected_tokens
                ),
                None,
            )
            if match is None and job_name == "compliance":
                match = next(
                    (
                        step
                        for step in steps
                        if isinstance(step, dict)
                        and step.get("name") == expected_step.get("name")
                    ),
                    None,
                )
                update_run = match is not None
            if match is None and job_name == "compliance":
                match = next(
                    (
                        step
                        for step in steps
                        if isinstance(step, dict)
                        and isinstance(step.get("run"), str)
                        and "repo-check" in step["run"]
                    ),
                    None,
                )
        if match is None:
            steps.append(copy.deepcopy(expected_step))
        elif expected_uses is not None:
            current_ref = str(match["uses"]).rsplit("@", maxsplit=1)[-1]
            if not _FULL_SHA.fullmatch(current_ref):
                match["uses"] = expected_uses
        elif job_name == "compliance" and update_run:
            match["run"] = expected_run

    conflicts: list[str] = []
    if job_name == "quality":
        for step in steps:
            uses = step.get("uses") if isinstance(step, dict) else None
            if (
                not isinstance(uses, str)
                or uses.startswith("./")
                or uses.startswith("docker://")
            ):
                continue
            match = _REMOTE_ACTION.match(uses)
            if match is not None and not _FULL_SHA.fullmatch(match.group("ref")):
                conflicts.append(
                    f"{path.relative_to(path.parents[2]).as_posix()}: remote action "
                    f"{uses!r} needs a maintainer-selected full commit SHA"
                )
    return _dump_yaml(current), conflicts


def _deep_fill(current: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, value in expected.items():
        if key not in current:
            current[key] = copy.deepcopy(value)
        elif isinstance(current[key], dict) and isinstance(value, dict):
            _deep_fill(current[key], value)


def _merge_json(path: Path, profile: str, relative: str) -> str:
    current = _load_json(path)
    expected = json.loads(_read_starter(profile, relative))
    _deep_fill(current, expected)
    return json.dumps(current, indent=2, ensure_ascii=False) + "\n"


def _merge_dependabot(path: Path, profile: str) -> str:
    current = _load_yaml(path)
    expected = _ROUND_TRIP_YAML.load(_read_starter(profile, ".github/dependabot.yml"))
    if not current:
        return _dump_yaml(expected)
    current.setdefault("version", expected["version"])
    updates = current.setdefault("updates", [])
    if not isinstance(updates, list):
        raise AdoptionError(f"cannot reconcile {path}: updates must be a list")
    for expected_update in expected["updates"]:
        exists = any(
            isinstance(item, dict)
            and item.get("package-ecosystem") == expected_update["package-ecosystem"]
            and item.get("directory") == expected_update["directory"]
            for item in updates
        )
        if not exists:
            updates.append(copy.deepcopy(expected_update))
    return _dump_yaml(current)


def _section(text: str, heading: str) -> tuple[int, int, str] | None:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n?(?P<body>.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return (match.start(), match.end(), match.group(0)) if match else None


def _merge_agents(path: Path, profile: str, values: dict[str, str]) -> str:
    template = _render(_read_starter(profile, "AGENTS.md"), values)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return template
    except UnicodeDecodeError as error:
        raise AdoptionError(f"could not parse {path} as UTF-8") from error
    headings = load_policy().rule("RSK002").check.config["headings"]
    for heading in headings:
        if _section(text, heading) is not None:
            continue
        source = _section(template, heading)
        assert source is not None
        text = text.rstrip() + "\n\n" + source[2].rstrip() + "\n"

    quality = _section(text, "Quality Gates")
    assert quality is not None
    block = quality[2]
    heading_line, _, body = block.partition("\n")
    body = re.sub(
        r"^\s*(?:\d+[.)]|[-*+])\s+`[^`\r\n]+`\s*$\r?\n?",
        "",
        body,
        flags=re.MULTILINE,
    ).lstrip("\r\n")
    commands = load_policy().rule("RSK003").check.config["commands_by_profile"][profile]
    command_block = "\n".join(
        f"{index}. `{command}`" for index, command in enumerate(commands, 1)
    )
    replacement = f"{heading_line}\n\n{command_block}\n"
    if body:
        replacement += "\n" + body.rstrip() + "\n"
    replacement = replacement.rstrip() + "\n\n"
    text = text[: quality[0]] + replacement + text[quality[1] :]
    if "repo-standard-kit" not in text:
        text = text.rstrip() + (
            "\n\nThis repository adopts [repo-standard-kit] and its documented quality "
            "baseline.\n\n[repo-standard-kit]: "
            "https://github.com/FP-DevTools/repo-standard-kit\n"
        )
    return text


def _merge_readme(path: Path, profile: str, values: dict[str, str]) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _render(_read_starter(profile, "README.md"), values)
    except UnicodeDecodeError as error:
        raise AdoptionError(f"could not parse {path} as UTF-8") from error
    if "repo-standard-kit" in text:
        return text
    return text.rstrip() + (
        "\n\n## Repository Standards\n\nRepository workflow and quality gates follow "
        "[repo-standard-kit]. Review this repository against the pinned standard "
        "when upgrading.\n\n[repo-standard-kit]: "
        "https://github.com/FP-DevTools/repo-standard-kit\n"
    )


def _planned(path: Path, content: str, root: Path) -> PlannedFile | None:
    try:
        before = path.read_text(encoding="utf-8")
        action = "updated"
    except FileNotFoundError:
        before = None
        action = "added"
    if before == content:
        return None
    return PlannedFile(path.relative_to(root), content, action)


def plan_adoption(root: Path, profile: str | None = None) -> AdoptionPlan:
    root = root.resolve()
    document = _parse_toml(root / "pyproject.toml")
    selected = _resolve_profile(root, document, profile)
    policy = load_policy()
    if not check_repo(root, policy, profile=selected):
        unchanged = tuple(
            relative for relative in _MANAGED_SURFACES if (root / relative).exists()
        )
        return AdoptionPlan(
            root=root,
            profile=selected,
            version=_kit_version(),
            changes=(),
            unchanged=unchanged,
            conflicts=(),
            dependency_metadata_changed=False,
        )

    values = _project_values(root, document)
    changes: list[PlannedFile] = []
    unchanged: list[str] = []
    conflicts: list[str] = []

    pyproject, dependency_changed, pyproject_conflicts = _merge_pyproject(
        root / "pyproject.toml", document, selected
    )
    conflicts.extend(pyproject_conflicts)
    generated: dict[str, str] = {
        "pyproject.toml": pyproject,
        ".pre-commit-config.yaml": _merge_pre_commit(
            root / ".pre-commit-config.yaml", selected
        ),
        ".pymarkdown.json": _merge_json(
            root / ".pymarkdown.json", selected, ".pymarkdown.json"
        ),
        ".github/dependabot.yml": _merge_dependabot(
            root / ".github/dependabot.yml", selected
        ),
        "AGENTS.md": _merge_agents(root / "AGENTS.md", selected, values),
        "README.md": _merge_readme(root / "README.md", selected, values),
    }
    for relative, job in (
        (".github/workflows/quality.yml", "quality"),
        (".github/workflows/compliance.yml", "compliance"),
    ):
        content, workflow_conflicts = _merge_workflow(
            root / relative, selected, relative, job
        )
        generated[relative] = content
        conflicts.extend(workflow_conflicts)

    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        unchanged.append("CHANGELOG.md")
    else:
        generated["CHANGELOG.md"] = _render(
            _read_starter(selected, "CHANGELOG.md"), values
        )

    for directory, starter_file in (
        ("docs/adr", "docs/adr/0001-template.md"),
        ("docs/diagrams", "docs/diagrams/README.md"),
    ):
        path = root / directory
        if path.is_dir() and any(path.iterdir()):
            unchanged.append(directory)
        else:
            generated[starter_file] = _render(
                _read_starter(selected, starter_file), values
            )

    for relative, content in generated.items():
        change = _planned(root / relative, content, root)
        if change is None:
            unchanged.append(relative)
        else:
            changes.append(change)
    return AdoptionPlan(
        root=root,
        profile=selected,
        version=_kit_version(),
        changes=tuple(changes),
        unchanged=tuple(sorted(set(unchanged))),
        conflicts=tuple(conflicts),
        dependency_metadata_changed=dependency_changed,
    )


def apply_plan(plan: AdoptionPlan) -> None:
    for change in plan.changes:
        destination = plan.root / change.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(change.content, encoding="utf-8")


def _git_root(root: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip()).resolve()


def _ensure_clean_git_root(root: Path) -> None:
    actual = _git_root(root)
    if actual is None or actual != root:
        raise AdoptionError(
            "apply mode requires the target to be a Git repository root"
        )
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise AdoptionError(
            "refusing to modify a dirty checkout; commit, stash, or remove existing "
            "changes first"
        )


def _run(command: list[str], root: Path) -> None:
    try:
        subprocess.run(command, cwd=root, check=True)
    except FileNotFoundError as error:
        raise CommandError(command, "executable not found") from error
    except subprocess.CalledProcessError as error:
        raise CommandError(command, f"exit code {error.returncode}") from error
    except KeyboardInterrupt as error:
        raise CommandError(command, "interrupted") from error


def _remaining_findings(plan: AdoptionPlan) -> list[Finding]:
    return check_repo(plan.root, load_policy(), profile=plan.profile)


def _print_summary(plan: AdoptionPlan, findings: list[Finding] | None) -> None:
    for action in ("added", "updated"):
        paths = [
            change.path.as_posix() for change in plan.changes if change.action == action
        ]
        print(f"{action}: {', '.join(paths) if paths else 'none'}")
    print(f"unchanged: {', '.join(plan.unchanged) if plan.unchanged else 'none'}")
    print("conflicts/manual actions:")
    if plan.conflicts:
        for conflict in plan.conflicts:
            print(f"  - {conflict}")
    else:
        print("  - none")
    if findings is None:
        print("remaining findings: not evaluated during dry-run")
        return
    required = [finding for finding in findings if finding.level == "required"]
    recommended = [finding for finding in findings if finding.level == "recommended"]
    print(f"remaining required findings: {len(required)}")
    for finding in required:
        print(f"  - {finding.rule_id} {finding.path}: {finding.message}")
    print(f"remaining recommended findings: {len(recommended)}")
    for finding in recommended:
        print(f"  - {finding.rule_id} {finding.path}: {finding.message}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.target).resolve()
    if not root.is_dir():
        print(f"repo-adopt: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        if not args.dry_run:
            _ensure_clean_git_root(root)
        plan = plan_adoption(root, args.profile)
        print(f"repo-standard-kit {plan.version}; profile {plan.profile}")
        if args.dry_run:
            _print_summary(plan, None)
            return 1 if plan.conflicts else 0
        apply_plan(plan)
        if plan.dependency_metadata_changed and not args.no_lock:
            _run(["uv", "lock"], root)
        if plan.dependency_metadata_changed and not args.no_install:
            sync_command = ["uv", "sync"]
            if args.no_lock:
                sync_command.append("--frozen")
            _run(sync_command, root)
        if args.run_gates:
            commands = (
                load_policy()
                .rule("RSK006")
                .check.config["commands_by_profile"][plan.profile]
            )
            for command in commands:
                _run(shlex.split(command), root)
        findings = _remaining_findings(plan)
        _print_summary(plan, findings)
        return (
            1 if plan.conflicts or any(f.level == "required" for f in findings) else 0
        )
    except AdoptionError as error:
        print(f"repo-adopt: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
