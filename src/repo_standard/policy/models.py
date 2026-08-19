"""Strict models for source and compiled repo-standard policy."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

COMPILED_POLICY_PATH = Path(__file__).resolve().parent / "compiled.json"

LEVELS = {"required", "recommended"}
ENFORCEMENT_MODES = {"structural", "platform"}
MARKER_KINDS = {"file", "directory"}
GITHUB_PERMISSION_VALUES = {"none", "read", "write"}

# Each check kind owns its accepted configuration keys. Required keys are the
# first set; optional keys are the second. Value-level validation follows in
# `_validate_check_config` where the shape is more useful than a generic schema.
CHECK_SCHEMAS: dict[str, tuple[set[str], set[str]]] = {
    "path_exists": ({"path", "path_type"}, set()),
    "markdown_headings": ({"path", "headings"}, set()),
    "text_contains_all": ({"path", "values"}, set()),
    "agents_quality_commands": ({"path", "commands_by_profile"}, set()),
    "text_pattern_each": ({"paths", "pattern"}, set()),
    "github_workflow_commands": (
        {"path", "job", "trigger", "commands_by_profile"},
        set(),
    ),
    "pre_commit_hooks": ({"path", "hooks"}, set()),
    "uv_build_backend": ({"path", "backend"}, {"allow_missing_profiles"}),
    "ruff_baseline": ({"path", "required_select", "require_line_length"}, set()),
    "ruff_line_length": ({"path", "value"}, set()),
    "ruff_select": ({"path", "values"}, set()),
    "no_placeholders": ({"placeholders"}, set()),
    "branch_protection": (
        {
            "branch",
            "required_status_checks",
            "minimum_reviews",
            "dismiss_stale_approvals",
            "require_up_to_date",
            "require_conversation_resolution",
            "enforce_admins",
        },
        set(),
    ),
    "branch_protection_minimum_reviews": ({"branch", "minimum_reviews"}, set()),
    "repo_metadata": ({"path", "standard_major"}, set()),
    "github_workflow_permissions": ({"path", "job", "permissions"}, set()),
    "github_workflow_pins": ({"path"}, set()),
}


class PolicyError(ValueError):
    """The source or compiled policy violates its public schema."""


def _fail(location: str, message: str) -> NoReturn:
    raise PolicyError(f"{location}: {message}")


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(location, "expected a mapping with string keys")
    return value


def _string(value: Any, location: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value.strip()):
        _fail(location, "expected a non-empty string")
    return value


def _integer(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(location, "expected an integer")
    return value


def _boolean(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        _fail(location, "expected a boolean")
    return value


def _strings(value: Any, location: str, *, non_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (non_empty and not value):
        _fail(location, "expected a non-empty list of strings")
    result = tuple(
        _string(item, f"{location}[{index}]") for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        _fail(location, "contains duplicate values")
    return result


def _keys(
    data: dict[str, Any],
    location: str,
    *,
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    missing = sorted(required - data.keys())
    unknown = sorted(data.keys() - required - optional)
    if missing:
        _fail(location, f"missing keys: {', '.join(missing)}")
    if unknown:
        _fail(location, f"unknown keys: {', '.join(unknown)}")


@dataclass(frozen=True)
class Marker:
    path: str
    kind: str

    @classmethod
    def from_data(cls, value: Any, location: str) -> Marker:
        data = _mapping(value, location)
        _keys(data, location, required={"path", "kind"})
        path = _string(data["path"], f"{location}.path")
        kind = _string(data["kind"], f"{location}.kind")
        if kind not in MARKER_KINDS:
            _fail(f"{location}.kind", f"unknown marker kind {kind!r}")
        return cls(path=path, kind=kind)


@dataclass(frozen=True)
class Detection:
    priority: int
    default: bool
    markers: tuple[Marker, ...]

    @classmethod
    def from_data(cls, value: Any, location: str) -> Detection:
        data = _mapping(value, location)
        _keys(data, location, required={"priority", "default", "markers"})
        markers_value = data["markers"]
        if not isinstance(markers_value, list):
            _fail(f"{location}.markers", "expected a list")
        markers = tuple(
            Marker.from_data(item, f"{location}.markers[{index}]")
            for index, item in enumerate(markers_value)
        )
        return cls(
            priority=_integer(data["priority"], f"{location}.priority"),
            default=_boolean(data["default"], f"{location}.default"),
            markers=markers,
        )


@dataclass(frozen=True)
class Profile:
    schema_version: int
    id: str
    title: str
    description: str
    detection: Detection

    @classmethod
    def from_data(cls, value: Any, location: str) -> Profile:
        data = _mapping(value, location)
        _keys(
            data,
            location,
            required={"schema_version", "id", "title", "description", "detection"},
        )
        if _integer(data["schema_version"], f"{location}.schema_version") != 1:
            _fail(f"{location}.schema_version", "unsupported profile schema version")
        return cls(
            schema_version=1,
            id=_string(data["id"], f"{location}.id"),
            title=_string(data["title"], f"{location}.title"),
            description=_string(data["description"], f"{location}.description"),
            detection=Detection.from_data(data["detection"], f"{location}.detection"),
        )


@dataclass(frozen=True)
class Source:
    document: str
    section: str

    @classmethod
    def from_data(cls, value: Any, location: str) -> Source:
        data = _mapping(value, location)
        _keys(data, location, required={"document", "section"})
        return cls(
            document=_string(data["document"], f"{location}.document"),
            section=_string(data["section"], f"{location}.section"),
        )


def _validate_hook(value: Any, location: str) -> None:
    data = _mapping(value, location)
    _keys(
        data,
        location,
        required={"id", "entry"},
        optional={"args", "pass_filenames", "types", "types_or", "require_serial"},
    )
    _string(data["id"], f"{location}.id")
    _string(data["entry"], f"{location}.entry")
    for key in ("args", "types", "types_or"):
        if key in data:
            _strings(data[key], f"{location}.{key}", non_empty=False)
    for key in ("pass_filenames", "require_serial"):
        if key in data:
            _boolean(data[key], f"{location}.{key}")


def _validate_check_config(kind: str, config: dict[str, Any], location: str) -> None:
    required, optional = CHECK_SCHEMAS[kind]
    _keys(config, location, required=required, optional=optional)
    for key in (
        "path",
        "path_type",
        "pattern",
        "backend",
        "branch",
        "job",
        "trigger",
        "standard_major",
    ):
        if key in config:
            _string(config[key], f"{location}.{key}")
    for key in (
        "headings",
        "values",
        "paths",
        "required_select",
        "required_status_checks",
        "allow_missing_profiles",
    ):
        if key in config:
            _strings(
                config[key],
                f"{location}.{key}",
                non_empty=key != "allow_missing_profiles",
            )
    if "placeholders" in config:
        placeholders = _mapping(config["placeholders"], f"{location}.placeholders")
        if not placeholders:
            _fail(f"{location}.placeholders", "expected a non-empty mapping")
        for token, field in placeholders.items():
            _string(token, f"{location}.placeholders key")
            _string(field, f"{location}.placeholders.{token}")
    if "permissions" in config:
        permissions = _mapping(config["permissions"], f"{location}.permissions")
        if not permissions:
            _fail(f"{location}.permissions", "expected a non-empty mapping")
        for scope, value in permissions.items():
            _string(scope, f"{location}.permissions key")
            permission = _string(value, f"{location}.permissions.{scope}")
            if permission not in GITHUB_PERMISSION_VALUES:
                _fail(
                    f"{location}.permissions.{scope}",
                    f"unsupported permission value {permission!r}",
                )
    for key in (
        "require_line_length",
        "dismiss_stale_approvals",
        "require_up_to_date",
        "require_conversation_resolution",
        "enforce_admins",
    ):
        if key in config:
            _boolean(config[key], f"{location}.{key}")
    for key in ("value", "minimum_reviews"):
        if key in config:
            _integer(config[key], f"{location}.{key}")
    if config.get("minimum_reviews", 0) < 0:
        _fail(f"{location}.minimum_reviews", "expected a non-negative integer")
    if "commands_by_profile" in config:
        commands = _mapping(
            config["commands_by_profile"], f"{location}.commands_by_profile"
        )
        for profile_id, values in commands.items():
            _strings(values, f"{location}.commands_by_profile.{profile_id}")
    if "hooks" in config:
        hooks = config["hooks"]
        if not isinstance(hooks, list) or not hooks:
            _fail(f"{location}.hooks", "expected a non-empty list")
        for index, hook in enumerate(hooks):
            _validate_hook(hook, f"{location}.hooks[{index}]")


@dataclass(frozen=True)
class Check:
    kind: str
    config: dict[str, Any]

    @classmethod
    def from_data(cls, value: Any, location: str) -> Check:
        data = _mapping(value, location)
        _keys(data, location, required={"kind"}, optional={"config"})
        kind = _string(data["kind"], f"{location}.kind")
        if kind not in CHECK_SCHEMAS:
            _fail(f"{location}.kind", f"unregistered check kind {kind!r}")
        config = _mapping(data.get("config", {}), f"{location}.config")
        _validate_check_config(kind, config, f"{location}.config")
        return cls(kind=kind, config=config)


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    level: str
    profiles: tuple[str, ...]
    source: Source
    enforcement: str
    check: Check
    rationale: str
    remediation: str

    @property
    def severity(self) -> str:
        """Legacy JSON compatibility field retained through v1."""
        return "shall" if self.level == "required" else "should"

    @classmethod
    def from_data(cls, value: Any, location: str) -> Rule:
        data = _mapping(value, location)
        _keys(
            data,
            location,
            required={
                "id",
                "title",
                "level",
                "profiles",
                "source",
                "enforcement",
                "check",
                "rationale",
                "remediation",
            },
        )
        rule_id = _string(data["id"], f"{location}.id")
        if re.fullmatch(r"RSK\d{3}", rule_id) is None:
            _fail(f"{location}.id", "expected RSK followed by three digits")
        level = _string(data["level"], f"{location}.level")
        if level not in LEVELS:
            _fail(f"{location}.level", f"unknown level {level!r}")
        enforcement = _string(data["enforcement"], f"{location}.enforcement")
        if enforcement not in ENFORCEMENT_MODES:
            _fail(f"{location}.enforcement", f"unknown mode {enforcement!r}")
        return cls(
            id=rule_id,
            title=_string(data["title"], f"{location}.title"),
            level=level,
            profiles=_strings(data["profiles"], f"{location}.profiles"),
            source=Source.from_data(data["source"], f"{location}.source"),
            enforcement=enforcement,
            check=Check.from_data(data["check"], f"{location}.check"),
            rationale=_string(data["rationale"], f"{location}.rationale"),
            remediation=_string(data["remediation"], f"{location}.remediation"),
        )


@dataclass(frozen=True)
class Policy:
    schema_version: int
    standard_version: str
    standard_major: str
    retired_rule_ids: tuple[str, ...]
    profiles: tuple[Profile, ...]
    rules: tuple[Rule, ...]

    @property
    def profile_ids(self) -> tuple[str, ...]:
        return tuple(profile.id for profile in self.profiles)

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def profile(self, profile_id: str) -> Profile:
        try:
            return next(
                profile for profile in self.profiles if profile.id == profile_id
            )
        except StopIteration as error:
            raise PolicyError(f"unknown profile {profile_id!r}") from error

    def rule(self, rule_id: str) -> Rule:
        try:
            return next(rule for rule in self.rules if rule.id == rule_id)
        except StopIteration as error:
            raise PolicyError(f"unknown rule {rule_id!r}") from error

    def to_data(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_data(cls, value: Any, location: str = "policy") -> Policy:
        data = _mapping(value, location)
        _keys(
            data,
            location,
            required={
                "schema_version",
                "standard_version",
                "standard_major",
                "retired_rule_ids",
                "profiles",
                "rules",
            },
        )
        schema_version = _integer(data["schema_version"], f"{location}.schema_version")
        if schema_version != 1:
            _fail(
                f"{location}.schema_version",
                f"unsupported schema version {schema_version}",
            )
        profiles_value = data["profiles"]
        rules_value = data["rules"]
        if not isinstance(profiles_value, list) or not profiles_value:
            _fail(f"{location}.profiles", "expected a non-empty list")
        if not isinstance(rules_value, list) or not rules_value:
            _fail(f"{location}.rules", "expected a non-empty list")
        profiles = tuple(
            Profile.from_data(item, f"{location}.profiles[{index}]")
            for index, item in enumerate(profiles_value)
        )
        rules = tuple(
            Rule.from_data(item, f"{location}.rules[{index}]")
            for index, item in enumerate(rules_value)
        )
        retired = _strings(
            data["retired_rule_ids"], f"{location}.retired_rule_ids", non_empty=False
        )
        policy = cls(
            schema_version=schema_version,
            standard_version=_string(
                data["standard_version"], f"{location}.standard_version"
            ),
            standard_major=_string(
                data["standard_major"], f"{location}.standard_major"
            ),
            retired_rule_ids=retired,
            profiles=profiles,
            rules=rules,
        )
        policy._validate_relations(location)
        return policy

    def _validate_relations(self, location: str) -> None:
        profile_ids = self.profile_ids
        if len(profile_ids) != len(set(profile_ids)):
            _fail(f"{location}.profiles", "duplicate profile IDs")
        defaults = [
            profile.id for profile in self.profiles if profile.detection.default
        ]
        if len(defaults) != 1:
            _fail(
                f"{location}.profiles", "exactly one detection profile must be default"
            )
        priorities = [profile.detection.priority for profile in self.profiles]
        if len(priorities) != len(set(priorities)):
            _fail(f"{location}.profiles", "detection priorities must be unique")

        rule_ids = self.rule_ids
        if len(rule_ids) != len(set(rule_ids)):
            _fail(f"{location}.rules", "duplicate rule IDs")
        numbers = [int(rule_id[3:]) for rule_id in rule_ids]
        if numbers != sorted(numbers):
            _fail(f"{location}.rules", "rule IDs must be numerically ordered")
        retired_numbers = {int(rule_id[3:]) for rule_id in self.retired_rule_ids}
        if any(
            re.fullmatch(r"RSK\d{3}", rule_id) is None
            for rule_id in self.retired_rule_ids
        ):
            _fail(f"{location}.retired_rule_ids", "invalid retired rule ID")
        if set(rule_ids) & set(self.retired_rule_ids):
            _fail(f"{location}.retired_rule_ids", "a retired rule ID is still active")
        gaps = set(range(numbers[0], numbers[-1] + 1)) - set(numbers)
        if gaps != retired_numbers:
            _fail(
                f"{location}.retired_rule_ids",
                f"must exactly preserve numeric gaps: {sorted(gaps)}",
            )
        known_profiles = set(profile_ids)
        for rule in self.rules:
            unknown = set(rule.profiles) - known_profiles
            if unknown:
                _fail(
                    f"{location}.rules.{rule.id}.profiles",
                    f"unknown profiles: {sorted(unknown)}",
                )
            commands = rule.check.config.get("commands_by_profile")
            if isinstance(commands, dict):
                unknown_commands = set(commands) - known_profiles
                if unknown_commands:
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.commands_by_profile",
                        f"unknown profiles: {sorted(unknown_commands)}",
                    )
                missing_commands = set(rule.profiles) - set(commands)
                if missing_commands:
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.commands_by_profile",
                        f"missing profiles: {sorted(missing_commands)}",
                    )
            allowed_missing = rule.check.config.get("allow_missing_profiles")
            if isinstance(allowed_missing, list):
                unknown_allowed = set(allowed_missing) - known_profiles
                if unknown_allowed:
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.allow_missing_profiles",
                        f"unknown profiles: {sorted(unknown_allowed)}",
                    )


def _safe_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f"{path}:{mark.line + 1}:{mark.column + 1}" if mark else str(path)
        raise PolicyError(f"{location}: malformed YAML: {error}") from error


def _markdown_section(document: Path, heading: str) -> str | None:
    text = document.read_text(encoding="utf-8")
    match = re.search(
        rf"^(?P<marks>##+)\s+{re.escape(heading)}\s*$",
        text,
        re.MULTILINE,
    )
    if match is None:
        return None
    level = len(match.group("marks"))
    tail = text[match.end() :]
    next_heading = re.search(rf"^#{{1,{level}}}\s+", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def _validate_sources(policy: Policy, repo_root: Path) -> None:
    for rule in policy.rules:
        document = repo_root / rule.source.document
        if not document.is_file():
            _fail(
                f"rule {rule.id}.source",
                f"document does not exist: {rule.source.document}",
            )
        section = _markdown_section(document, rule.source.section)
        if section is None:
            _fail(
                f"rule {rule.id}.source",
                f"section {rule.source.section!r} does not exist in "
                f"{rule.source.document}",
            )
        if rule.id not in section:
            _fail(
                f"rule {rule.id}.source", "source section does not mention the rule ID"
            )
        if rule.level not in section.lower():
            _fail(
                f"rule {rule.id}.source",
                f"source section does not mention canonical level {rule.level!r}",
            )


def load_source_policy(repo_root: Path) -> Policy:
    """Load, expand, and validate `policy/base.yaml` and its profile files."""
    base_path = repo_root / "policy" / "base.yaml"
    data = _mapping(_safe_yaml(base_path), str(base_path))
    _keys(
        data,
        str(base_path),
        required={
            "schema_version",
            "standard_version",
            "standard_major",
            "retired_rule_ids",
            "profile_files",
            "rules",
        },
    )
    profile_files = _strings(data.pop("profile_files"), f"{base_path}.profile_files")
    profiles = []
    for relative in profile_files:
        profile_path = repo_root / "policy" / relative
        profiles.append(_safe_yaml(profile_path))
    data["profiles"] = profiles
    policy = Policy.from_data(data, str(base_path))
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    package_version = str(pyproject["project"]["version"])
    if policy.standard_version != package_version:
        _fail(
            "policy.standard_version",
            f"{policy.standard_version!r} does not match package version "
            f"{package_version!r}",
        )
    if policy.standard_version.split(".", 1)[0] != policy.standard_major:
        _fail("policy.standard_major", "does not match standard_version")
    _validate_sources(policy, repo_root)
    return policy


def load_compiled_policy(path: Path = COMPILED_POLICY_PATH) -> Policy:
    """Load the deterministic policy artifact shipped in wheels."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise PolicyError(
            f"could not load compiled policy at {path}: {error}"
        ) from error
    return Policy.from_data(data, str(path))
