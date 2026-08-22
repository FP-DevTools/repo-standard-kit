"""Conflict-aware adoption of repo-standard-kit into an existing repository."""

from __future__ import annotations

import argparse
import copy
import json
import os
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

from repo_standard.bootstrap_defaults import DEFAULT_PYTHON_VERSION
from repo_standard.compliance.checks import (
    Finding,
    _shell_commands,
    check_repo,
    load_policy,
)
from repo_standard.github_references import is_full_commit_sha
from repo_standard.policy import Shape
from repo_standard.policy.models import LEVEL_ORDER
from repo_standard.project_metadata import kit_version
from repo_standard.repo_init import (
    PLACEHOLDERS,
    UNLICENSED_NOTICE,
    resolve_starter_dir,
)

ADOPTED_LICENSE_NOTICE = "See [`LICENSE`](LICENSE) for the terms that apply."

_KIT_REPOSITORY = "FP-DevTools/repo-standard-kit"
_STANDARDS_LINK = f"[repo-standard-kit]: https://github.com/{_KIT_REPOSITORY}"
# Standard 2 moved the reusable workflow to its own file and left it one input,
# so a caller written against an earlier release resolves to nothing.
_REUSABLE_COMPLIANCE = f"{_KIT_REPOSITORY}/.github/workflows/compliance-reusable.yml"
_REUSABLE_INPUTS = ("standard-ref",)
# RSK005 wants an explicit, linked reference in both documents. Rather than
# inventing a heading no shape declares, the note goes into a section the shape
# already requires, so adoption never introduces a section shape of its own.
_STANDARDS_NOTE = {
    "agents": (
        "repository-context",
        "Standards source: [repo-standard-kit] — quality gates derive from it, "
        "and this repository is reviewed against it periodically for standards "
        "drift.",
    ),
    "readme": (
        "development",
        "Repository workflow and quality gates follow [repo-standard-kit]. "
        "Review this repository against the pinned standard when upgrading.",
    ),
}


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
    # Stated facts about the adoption that ask nothing of the maintainer, so
    # they belong neither in the conflict list nor in the finding counts.
    notices: tuple[str, ...] = ()


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
    ".gitignore",
    "docs/adr",
)
_REMOTE_ACTION = re.compile(r"^[^./\s]+/[^@\s]+@(?P<ref>[^\s]+)$")
_COMMAND_LIST_BLOCK = re.compile(
    r"(?:^[ \t]*(?:\d+[.)]|[-*+])[ \t]+`[^`\r\n]+`[ \t]*\r?\n?)+",
    re.MULTILINE,
)
_DIAL_LIST_BLOCK = re.compile(
    r"(?:^[ \t]*[-*+][ \t]+\*\*[^*\r\n]+\*\*[ \t]*\d+[ \t]*/[ \t]*\d+[ \t]*\r?\n?)+",
    re.MULTILINE,
)
_ROUND_TRIP_YAML = YAML()
_ROUND_TRIP_YAML.preserve_quotes = True
_ROUND_TRIP_YAML.width = 88
_ROUND_TRIP_YAML.indent(mapping=2, sequence=4, offset=2)


def build_parser() -> argparse.ArgumentParser:
    policy = load_policy()
    parser = argparse.ArgumentParser(
        description="Adopt repo-standard-kit into an existing repository."
    )
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--profile", choices=policy.profile_ids)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and print the reconciliation without writing, staging, or "
        "running any command.",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Skip uv lock, leaving lockfile refresh to the maintainer.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip environment synchronization after reconciliation.",
    )
    parser.add_argument(
        "--native-tls",
        action="store_true",
        help="Use the platform certificate store for child uv commands.",
    )
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
    requires = str(project.get("requires-python") or "")
    floor = re.search(r">=\s*(\d+\.\d+)", requires)
    return {
        "repo_name": name,
        "package_name": normalized,
        "description": description,
        "repo_type": "library",
        "python_version": floor.group(1) if floor else DEFAULT_PYTHON_VERSION,
        "author": "",
        # Adoption never chooses licence terms for a repository; it only
        # reports whether the repository has already stated them.
        "license_notice": (
            ADOPTED_LICENSE_NOTICE
            if (root / "LICENSE").is_file()
            else UNLICENSED_NOTICE
        ),
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
        # A stale standard major is the upgrade adoption exists to perform, so
        # only an unrecognized profile leaves the intended profile in doubt.
        if profile not in policy.profile_ids:
            raise AdoptionError(
                f"[tool.repo-standard] profile {profile!r} is not a profile this "
                f"kit knows ({', '.join(policy.profile_ids)}); pass --profile to "
                "make the intended profile explicit"
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


def _standard_major_notice(document: Any) -> str | None:
    """Name both standard majors when the repository is on an earlier one.

    This is the state every repository adopted under an earlier major is in,
    and it is what adoption repairs, so it is reported rather than refused.
    """
    metadata = document.get("tool", {}).get("repo-standard")
    if not isinstance(metadata, dict):
        return None
    declared = metadata.get("standard")
    current = load_policy().standard_major
    if declared is None or str(declared) == current:
        return None
    return (
        f"this repository declares standard {str(declared)!r} and this kit is "
        f"standard {current!r}; adoption upgrades [tool.repo-standard] to it"
    )


def _sibling_order(shape: Shape, prefix: tuple[str, ...]) -> list[str]:
    """Child names the shape declares under `prefix`, in declared order."""
    order: list[str] = []
    for heading in shape.headings:
        parts = heading.split(".")
        if len(parts) <= len(prefix) or tuple(parts[: len(prefix)]) != prefix:
            continue
        if parts[len(prefix)] not in order:
            order.append(parts[len(prefix)])
    return order


def _place(
    parent: Any, key: str, value: Any, shape: Shape, prefix: tuple[str, ...]
) -> None:
    """Add `key` where the shape says it belongs among its siblings.

    tomlkit appends, and a table appended past the ones that should follow it is
    an RSK025 finding. There is no insert-before in the public API, so the
    declared tables that come after `key` are lifted out and put back in order;
    each carries its own contents and trivia, so only their position moves.
    """
    order = _sibling_order(shape, prefix)
    if key not in order:
        parent[key] = value
        return
    following = [name for name in order[order.index(key) + 1 :] if name in parent]
    moved = [(name, parent.pop(name)) for name in following]
    parent[key] = value
    for name, table in moved:
        parent[name] = table


def _ensure_table(
    parent: Any, key: str, shape: Shape, prefix: tuple[str, ...] = ()
) -> Any:
    value = parent.get(key)
    if value is None:
        _place(parent, key, tomlkit.table(), shape, prefix)
        value = parent[key]
    if not isinstance(value, dict):
        raise AdoptionError(f"cannot merge TOML key {key!r}: expected a table")
    return value


def _reorder_tables(parent: Any, shape: Shape, prefix: tuple[str, ...] = ()) -> None:
    """Put the shape's declared tables back into canonical order, in place.

    Placing each new table correctly is not enough: a table the repository
    already had can sit anywhere, and adoption has no business handing back a
    manifest that fails the rule it just rewrote the file for. RSK025 reads
    table headers as a subsequence, so only the declared ones move -- each
    takes a slot a declared table already occupied, and a table the shape does
    not list keeps its position.
    """
    order = _sibling_order(shape, prefix)
    keys = list(parent)
    declared = [name for name in order if name in keys]
    slots = [index for index, name in enumerate(keys) if name in declared]
    if [keys[index] for index in slots] != declared:
        for index, name in zip(slots, declared, strict=True):
            keys[index] = name
        # tomlkit has no reorder and no insert-before, so every key is lifted
        # out and put back; each carries its own contents and trivia.
        lifted = {name: parent.pop(name) for name in list(parent)}
        for name in keys:
            parent[name] = lifted[name]
    for name in order:
        child = parent.get(name)
        if isinstance(child, dict):
            _reorder_tables(child, shape, (*prefix, name))


# The families a rule of each kind names, so adoption reads the requirement
# from policy rather than from whatever the starter happens to select.
_RUFF_SELECT_KINDS = {"ruff_baseline": "required_select", "ruff_select": "values"}


def _required_ruff_families() -> list[str]:
    """Lint families a `required` rule demands, in policy order.

    Adoption may repair a `required` rule unasked. A `recommended` family is
    the maintainer's call and adding one has turned a passing `ruff check` red,
    so the level decides rather than the starter's `select` list.
    """
    families: list[str] = []
    for rule in load_policy().rules:
        key = _RUFF_SELECT_KINDS.get(rule.check.kind)
        if key is None or rule.level != "required":
            continue
        families.extend(
            family for family in rule.check.config[key] if family not in families
        )
    return families


def _merge_pyproject(
    path: Path, document: Any, profile: str
) -> tuple[str, bool, list[str]]:
    starter = tomllib.loads(_read_starter(profile, "pyproject.toml"))
    shape = _shape_for("RSK025")
    conflicts: list[str] = []
    dependency_changed = False

    tool = _ensure_table(document, "tool", shape)
    metadata = _ensure_table(tool, "repo-standard", shape, ("tool",))
    unknown = set(metadata) - {"profile", "standard"}
    if unknown:
        conflicts.append(
            "pyproject.toml: [tool.repo-standard] has unsupported keys: "
            + ", ".join(sorted(unknown))
        )
    metadata["profile"] = profile
    metadata["standard"] = load_policy().standard_major

    groups = _ensure_table(document, "dependency-groups", shape)
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

    ruff = _ensure_table(tool, "ruff", shape, ("tool",))
    if "line-length" not in ruff:
        ruff["line-length"] = starter["tool"]["ruff"]["line-length"]
    lint = _ensure_table(ruff, "lint", shape, ("tool", "ruff"))
    select = lint.get("select")
    if select is None:
        select = tomlkit.array()
        lint["select"] = select
    if not isinstance(select, list):
        raise AdoptionError("cannot merge tool.ruff.lint.select: expected an array")
    for family in _required_ruff_families():
        if family not in select:
            select.append(family)

    if profile == "python-single":
        build = document.get("build-system")
        if build is None:
            build = tomlkit.table()
            build["requires"] = starter["build-system"]["requires"]
            build["build-backend"] = starter["build-system"]["build-backend"]
            _place(document, "build-system", build, shape, ())
            dependency_changed = True
        elif not isinstance(build, dict):
            raise AdoptionError("cannot merge build-system: expected a table")

    _reorder_tables(document, shape)
    return tomlkit.dumps(document), dependency_changed, conflicts


def _merge_pre_commit(path: Path, profile: str) -> tuple[str, list[str]]:
    current = _load_yaml(path)
    conflicts: list[str] = []
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
            # `args` the starter does not model are load-bearing: dropping the
            # baseline from `detect-secrets` turned a clean gate into 98
            # findings. RSK007 compares the whole argument list, so keeping
            # them leaves a finding -- one the maintainer can answer, unlike a
            # silent deletion.
            if "args" in hook and "args" not in expected_hook:
                conflicts.append(
                    f"{path.name}: hook {hook['id']!r} keeps args "
                    f"{[str(arg) for arg in hook['args']]}, which the standard's "
                    "hook shape does not model; RSK007 reports the difference"
                )
            hook.update(copy.deepcopy(expected_hook))
    return _dump_yaml(current), conflicts


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


def _uses_comment(step: Any) -> str | None:
    """The `# v7.0.1` version annotation beside a step's `uses` value."""
    comments = getattr(step, "ca", None)
    token = comments.items.get("uses") if comments is not None else None
    value = token[2].value if token is not None and token[2] is not None else ""
    return value.split("\n", maxsplit=1)[0].strip() or None


def _set_uses_comment(step: Any, comment: str) -> None:
    """Rewrite the version annotation the repinned SHA just invalidated.

    A stale annotation is worse than an absent one, because Dependabot reads
    it as the pinned version. The existing token also carries whatever blank
    line followed the step, so only its first line is replaced.
    """
    comments = getattr(step, "ca", None)
    token = comments.items.get("uses") if comments is not None else None
    if token is None or token[2] is None:
        # Column 0 lets the emitter place the comment one space after the
        # value; leaving the column to ruamel aligns it to whatever it last
        # saw, which is not the same file twice.
        step.yaml_add_eol_comment(comment, "uses", column=0)
        return
    existing = token[2].value
    token[2].value = comment + existing[len(existing.split("\n", maxsplit=1)[0]) :]


def _reconcile_reusable_call(path: Path, job: Any, called: str) -> list[str]:
    """Reconcile a job that calls a reusable workflow instead of running steps.

    Such a job has no steps of its own, and a `steps:` list beside its `uses:`
    is a job GitHub refuses to schedule. What the kit can reconcile is what the
    kit knows: where its own reusable workflow now lives and which inputs it
    still accepts. Which revision to trust stays the maintainer's, so the
    release tag goes in and the pin RSK029 wants is reported.
    """
    relative = path.relative_to(path.parents[2]).as_posix()
    workflow, _, ref = called.rpartition("@")
    if not workflow.startswith(f"{_KIT_REPOSITORY}/.github/workflows/"):
        return [
            f"{relative}: the job calls reusable workflow {called!r}, which this "
            "kit does not publish; reconcile it by hand"
        ]
    conflicts: list[str] = []
    version = f"v{kit_version()}"
    if workflow != _REUSABLE_COMPLIANCE or not is_full_commit_sha(ref):
        job["uses"] = f"{_REUSABLE_COMPLIANCE}@{version}"
    if not is_full_commit_sha(str(job["uses"]).rsplit("@", maxsplit=1)[-1]):
        conflicts.append(
            f"{relative}: reusable workflow {job['uses']!r} needs a "
            "maintainer-selected full commit SHA"
        )
    inputs = job.get("with")
    if not isinstance(inputs, dict):
        inputs = {}
        job["with"] = inputs
    dropped = sorted(set(inputs) - set(_REUSABLE_INPUTS))
    for name in dropped:
        del inputs[name]
    inputs["standard-ref"] = version
    if dropped:
        conflicts.append(
            f"{relative}: reusable workflow inputs {', '.join(dropped)} no longer "
            "exist and were removed; own the command to keep what they asked for"
        )
    conflicts.append(
        f"{relative}: the job calls the reusable workflow, so it runs repo-check "
        "from the called workflow and no step of its own; RSK030 reports that"
    )
    return conflicts


def _run_commands(run: str) -> set[tuple[str, ...]]:
    """The commands a `run` scalar executes, whatever conditions gate them.

    The same gate is spelled differently in different repositories -- a bare
    `uv build --all-packages` against the starter's `compgen`-guarded form --
    and comparing whole `run` bodies read those as two steps, so both were
    written out under one name. Reusing the checker's own parser keeps one
    answer to what a step executes.
    """
    return {command.tokens for command in _shell_commands(run)}


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
    if isinstance(job.get("uses"), str):
        called_conflicts = _reconcile_reusable_call(path, job, job["uses"])
        return _dump_yaml(current), called_conflicts
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
            expected_commands = _run_commands(expected_run)
            match = next(
                (
                    step
                    for step in steps
                    if isinstance(step, dict)
                    and isinstance(step.get("run"), str)
                    and _run_commands(step["run"]) & expected_commands
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
            if not is_full_commit_sha(current_ref):
                match["uses"] = expected_uses
                # The starter's SHA and its version comment are one fact, so
                # the pin carries the comment across rather than leaving the
                # adopter's annotation describing the ref it replaced.
                starter_comment = _uses_comment(expected_step)
                if starter_comment is not None:
                    _set_uses_comment(match, starter_comment)
        elif job_name == "compliance" and update_run:
            match["run"] = expected_run

    # Both governed workflows are under a pin rule, and only actions the kit
    # ships can be repinned from the starter. An action the repository added
    # needs a SHA nobody but its maintainer can choose, so it is reported.
    conflicts: list[str] = []
    for step in steps:
        uses = step.get("uses") if isinstance(step, dict) else None
        if (
            not isinstance(uses, str)
            or uses.startswith("./")
            or uses.startswith("docker://")
        ):
            continue
        match = _REMOTE_ACTION.match(uses)
        if match is not None and not is_full_commit_sha(match.group("ref")):
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


_LINK_DEFINITIONS = re.compile(r"(?:^\[[^\]\r\n]+\]:[^\r\n]*\r?\n?)+\Z", re.MULTILINE)


def _append_block(text: str, block: str) -> str:
    """Append `block`, keeping any trailing link-reference definitions last."""
    body = text.rstrip() + "\n"
    match = _LINK_DEFINITIONS.search(body)
    if match is None:
        return f"{body.rstrip()}\n\n{block.rstrip()}\n"
    head = body[: match.start()].rstrip()
    return f"{head}\n\n{block.rstrip()}\n\n{body[match.start() :].strip()}\n"


def _append_link_definition(text: str, definition: str) -> str:
    body = text.rstrip() + "\n"
    match = _LINK_DEFINITIONS.search(body)
    if match is None:
        return f"{body}\n{definition}\n"
    return f"{body[: match.end()].rstrip()}\n{definition}\n"


def _insert_section(text: str, shape: Shape, heading: str, block: str) -> str:
    """Insert `block` where `shape` says the section belongs.

    Appending was safe while RSK002 checked presence alone. Shapes are
    order-enforced, so a repaired section has to land before the first declared
    section that follows it canonically, or the repair trades a missing-section
    finding for an out-of-order one.
    """
    order = list(shape.headings)
    for following in order[order.index(heading) + 1 :]:
        location = _section(text, following)
        if location is None:
            continue
        head = text[: location[0]].rstrip()
        return f"{head}\n\n{block.rstrip()}\n\n{text[location[0] :]}"
    return _append_block(text, block)


def _fill_required_sections(text: str, shape: Shape, reference: str) -> str:
    """Add every required section `text` lacks, taken from `reference`."""
    for section in shape.sections:
        if section.level != "required" or _section(text, section.heading) is not None:
            continue
        source = _section(reference, section.heading)
        if source is None:
            raise AdoptionError(
                f"cannot reconcile {shape.path}: the reference document has no "
                f"{section.heading!r} section"
            )
        text = _insert_section(text, shape, section.heading, source[2])
    return text


def _ensure_standards_reference(text: str, shape: Shape) -> str:
    """Satisfy RSK005 inside a section the shape already declares."""
    if "repo-standard-kit" in text:
        return text
    section_id, note = _STANDARDS_NOTE[shape.id]
    location = _section(text, shape.section(section_id).heading)
    if location is None:
        return _append_block(text, f"{note}\n\n{_STANDARDS_LINK}")
    block = f"{location[2].rstrip()}\n\n{note}\n\n"
    return _append_link_definition(
        text[: location[0]] + block + text[location[1] :], _STANDARDS_LINK
    )


def _reconcile_block(
    text: str, heading: str, block: str, pattern: re.Pattern[str]
) -> str:
    """Restate a policy-owned block inside a section the document already has.

    An existing block is replaced where it stands, so surrounding prose keeps
    its position; a section that states nothing gets the block first, ahead of
    whatever prose it does carry.
    """
    location = _section(text, heading)
    assert location is not None
    heading_line, _, body = location[2].partition("\n")
    match = pattern.search(body)
    if match is not None:
        body = body[: match.start()] + block + "\n" + body[match.end() :]
        replacement = f"{heading_line}\n{body}"
    else:
        replacement = f"{heading_line}\n\n{block}\n"
        if body.strip():
            replacement += "\n" + body.strip("\r\n") + "\n"
    replacement = replacement.rstrip() + "\n\n"
    return text[: location[0]] + replacement + text[location[1] :]


def _reconcile_gate_chain(text: str, profile: str) -> str:
    commands = load_policy().rule("RSK003").check.config["commands_by_profile"][profile]
    block = "\n".join(
        f"{index}. `{command}`" for index, command in enumerate(commands, 1)
    )
    return _reconcile_block(text, "Quality Gates", block, _COMMAND_LIST_BLOCK)


def _reconcile_operating_dials(text: str) -> str:
    """RSK026: the dial levels come from policy, never from the existing text."""
    config = load_policy().rule("RSK026").check.config
    block = "\n".join(
        f"- **{dial['label']}:** {dial['level']} / {dial['scale']}"
        for dial in config["dials"]
    )
    return _reconcile_block(text, config["section"], block, _DIAL_LIST_BLOCK)


def _existing(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as error:
        raise AdoptionError(f"could not parse {path} as UTF-8") from error


def _shape_for(rule_id: str) -> Shape:
    """Resolve a shape through the rule that enforces it, never by literal id."""
    policy = load_policy()
    return policy.shape(policy.rule(rule_id).check.config["shape"])


def _merge_agents(path: Path, profile: str, values: dict[str, str]) -> str:
    reference = _render(_read_starter(profile, "AGENTS.md"), values)
    text = _existing(path)
    if text is None:
        return reference
    shape = _shape_for("RSK002")
    text = _fill_required_sections(text, shape, reference)
    text = _reconcile_gate_chain(text, profile)
    text = _reconcile_operating_dials(text)
    return _ensure_standards_reference(text, shape)


_README_GAP = "`repo-adopt` added this required heading; it has no content yet."


def _fill_missing_readme_sections(text: str, shape: Shape) -> str:
    """Add every required README section as a stated gap.

    The starter's bodies describe a repository `repo-init` has just generated
    -- add the first package, replace this section -- which is false of a
    repository that already exists and leaves the reader prose to delete. An
    inserted section says it is empty and stops there.
    """
    for section in shape.sections:
        if section.level != "required" or _section(text, section.heading) is not None:
            continue
        text = _insert_section(
            text, shape, section.heading, f"## {section.heading}\n\n{_README_GAP}\n"
        )
    return text


def _merge_readme(path: Path, profile: str, values: dict[str, str]) -> str:
    text = _existing(path)
    if text is None:
        return _render(_read_starter(profile, "README.md"), values)
    shape = _shape_for("RSK023")
    text = _fill_missing_readme_sections(text, shape)
    return _ensure_standards_reference(text, shape)


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
    # The short circuit below returns an empty plan when `check_repo` finds
    # nothing to repair. No rule checks .gitignore -- a file this repo-specific
    # is a poor fit for a structural rule -- so a repository can be clean by
    # every rule and still have none, which is why presence is asked here
    # rather than inferred from the findings.
    gitignore_present = (root / ".gitignore").is_file()
    # Only a `violation` names something adoption could repair: a report about
    # the exemption configuration, active or dead, must not turn a repository
    # that is clean by every rule into one adoption starts rewriting.
    repairable = [
        finding
        for finding in check_repo(root, policy, profile=selected)
        if finding.status == "violation"
    ]
    if not repairable and gitignore_present:
        unchanged = tuple(
            relative for relative in _MANAGED_SURFACES if (root / relative).exists()
        )
        return AdoptionPlan(
            root=root,
            profile=selected,
            version=kit_version(),
            changes=(),
            unchanged=unchanged,
            conflicts=(),
            dependency_metadata_changed=False,
        )

    values = _project_values(root, document)
    changes: list[PlannedFile] = []
    unchanged: list[str] = []
    conflicts: list[str] = []
    notices = [notice for notice in (_standard_major_notice(document),) if notice]

    pyproject, dependency_changed, pyproject_conflicts = _merge_pyproject(
        root / "pyproject.toml", document, selected
    )
    conflicts.extend(pyproject_conflicts)
    pre_commit, pre_commit_conflicts = _merge_pre_commit(
        root / ".pre-commit-config.yaml", selected
    )
    conflicts.extend(pre_commit_conflicts)
    generated: dict[str, str] = {
        "pyproject.toml": pyproject,
        ".pre-commit-config.yaml": pre_commit,
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

    gitignore = root / ".gitignore"
    if gitignore.exists():
        unchanged.append(".gitignore")
    else:
        generated[".gitignore"] = _read_starter(selected, ".gitignore")

    # A repository that already keeps decision records keeps its own; the
    # template is only seeded where there is nothing to overwrite.
    adr = root / "docs/adr"
    if adr.is_dir() and any(adr.iterdir()):
        unchanged.append("docs/adr")
    else:
        template = "docs/adr/0001-template.md"
        generated[template] = _render(_read_starter(selected, template), values)

    for relative, content in generated.items():
        change = _planned(root / relative, content, root)
        if change is None:
            unchanged.append(relative)
        else:
            changes.append(change)
    return AdoptionPlan(
        root=root,
        profile=selected,
        version=kit_version(),
        changes=tuple(changes),
        unchanged=tuple(sorted(set(unchanged))),
        conflicts=tuple(conflicts),
        dependency_metadata_changed=dependency_changed,
        notices=tuple(notices),
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


def _run(command: list[str], root: Path, *, native_tls: bool = False) -> None:
    environment = os.environ.copy()
    if native_tls:
        environment["UV_NATIVE_TLS"] = "true"
    try:
        subprocess.run(command, cwd=root, check=True, env=environment)
    except FileNotFoundError as error:
        raise CommandError(command, "executable not found") from error
    except subprocess.CalledProcessError as error:
        raise CommandError(command, f"exit code {error.returncode}") from error
    except KeyboardInterrupt as error:
        raise CommandError(command, "interrupted") from error


def _remaining_findings(plan: AdoptionPlan) -> list[Finding]:
    return check_repo(plan.root, load_policy(), profile=plan.profile)


def _print_summary(plan: AdoptionPlan, findings: list[Finding] | None) -> None:
    for notice in plan.notices:
        print(f"note: {notice}")
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
    # Walking the declared levels keeps this summary complete when policy gains
    # one; naming them here is how `advisory` findings went unreported.
    suppressed = [finding for finding in findings if finding.status == "suppressed"]
    for level in LEVEL_ORDER:
        matching = [
            finding
            for finding in findings
            if finding.level == level and finding.status != "suppressed"
        ]
        print(f"remaining {level} findings: {len(matching)}")
        for finding in matching:
            print(f"  - {finding.rule_id} {finding.path}: {finding.message}")
    # A silenced finding counted as remaining would contradict the exit code,
    # and dropped from the summary it is the same blind spot `repo-check` just
    # closed, so it is reported on a line of its own.
    print(f"suppressed by [tool.repo-check.ignore]: {len(suppressed)}")
    for finding in suppressed:
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
            _run(["uv", "lock"], root, native_tls=args.native_tls)
        if plan.dependency_metadata_changed and not args.no_install:
            sync_command = ["uv", "sync"]
            if args.no_lock:
                sync_command.append("--frozen")
            _run(sync_command, root, native_tls=args.native_tls)
        if args.run_gates:
            commands = (
                load_policy()
                .rule("RSK006")
                .check.config["commands_by_profile"][plan.profile]
            )
            for command in commands:
                _run(shlex.split(command), root, native_tls=args.native_tls)
        findings = _remaining_findings(plan)
        _print_summary(plan, findings)
        # Same rule `repo-check` applies: only a `violation` can fail a run.
        # An `unused-exemption` is reported at its rule's canonical level and
        # must not turn adoption into a failure.
        blocking = [
            finding
            for finding in findings
            if finding.level == "required" and finding.status == "violation"
        ]
        return 1 if plan.conflicts or blocking else 0
    except AdoptionError as error:
        print(f"repo-adopt: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
