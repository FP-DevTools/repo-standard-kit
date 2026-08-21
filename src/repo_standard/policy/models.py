"""Strict models for source and compiled repo-standard policy."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, NoReturn

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

COMPILED_POLICY_PATH = Path(__file__).resolve().parent / "compiled.json"

_SAFE_YAML = YAML(typ="safe")

# Policy levels, ordered from most to least binding. `required` fails by
# default; `recommended` fails only under strict checking; `advisory` is always
# reported and never fails, because the prose it comes from leaves the choice
# to the repository.
LEVEL_ORDER = ("required", "recommended", "advisory")
LEVELS = set(LEVEL_ORDER)
STRICT_LEVELS = {"required", "recommended"}
DEFAULT_LEVELS = {"required"}
ENFORCEMENT_MODES = {"structural", "platform"}
MARKER_KINDS = {"file", "directory"}
GITHUB_PERMISSION_VALUES = {"none", "read", "write"}
SECTION_LEVELS = {"required", "optional"}
# Shape kinds double as the check kinds that consume them, so a rule that
# names a shape always dispatches to the handler built for that shape's kind.
SHAPE_KINDS = {"markdown_shape", "toml_table_order"}
MARKDOWN_SHAPE_KINDS = {"markdown_shape"}

# Each check kind owns its accepted configuration keys. Required keys are the
# first set; optional keys are the second. Value-level validation follows in
# `_validate_check_config` where the shape is more useful than a generic schema.
CHECK_SCHEMAS: dict[str, tuple[set[str], set[str]]] = {
    "path_exists": ({"path", "path_type"}, set()),
    "markdown_shape": ({"shape"}, set()),
    "toml_table_order": ({"shape"}, set()),
    "text_contains_all": ({"path", "values"}, set()),
    "agents_quality_commands": ({"path", "commands_by_profile"}, set()),
    "agents_operating_dials": ({"path", "section", "dials"}, set()),
    "text_pattern_each": ({"paths", "pattern"}, set()),
    "github_workflow_commands": (
        {"path", "job", "trigger", "commands_by_profile", "guards_by_profile"},
        set(),
    ),
    "github_workflow_invocation": (
        {"path", "job", "trigger", "token", "guards_by_profile"},
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
class ShapeSection:
    """One ordered, addressable part of a governed document."""

    id: str
    heading: str
    level: str

    @classmethod
    def from_data(cls, value: Any, location: str) -> ShapeSection:
        data = _mapping(value, location)
        _keys(data, location, required={"id", "heading", "level"})
        level = _string(data["level"], f"{location}.level")
        if level not in SECTION_LEVELS:
            _fail(f"{location}.level", f"unknown section level {level!r}")
        return cls(
            id=_string(data["id"], f"{location}.id"),
            heading=_string(data["heading"], f"{location}.heading"),
            level=level,
        )


@dataclass(frozen=True)
class Shape:
    """The canonical section list and order for one governed document.

    A shape is the single source for both directions of the contract: the
    check that rejects a document departing from it, and the generator that
    emits documents by walking `sections` in declaration order.
    """

    id: str
    path: str
    kind: str
    rule: str
    allow_unlisted: bool
    sections: tuple[ShapeSection, ...]
    heading_level: int | None = None

    @property
    def headings(self) -> tuple[str, ...]:
        return tuple(section.heading for section in self.sections)

    @property
    def required(self) -> tuple[str, ...]:
        """Headings a conforming document must carry, in canonical order."""
        return tuple(
            section.heading for section in self.sections if section.level == "required"
        )

    @property
    def optional_ordered(self) -> tuple[str, ...]:
        """Headings a document may omit but must not reorder when present."""
        return tuple(
            section.heading for section in self.sections if section.level == "optional"
        )

    def section(self, section_id: str) -> ShapeSection:
        try:
            return next(
                section for section in self.sections if section.id == section_id
            )
        except StopIteration as error:
            raise PolicyError(
                f"unknown section {section_id!r} in shape {self.id!r}"
            ) from error

    @classmethod
    def from_data(cls, value: Any, location: str) -> Shape:
        data = _mapping(value, location)
        _keys(
            data,
            location,
            required={"id", "path", "kind", "rule", "allow_unlisted", "sections"},
            optional={"heading_level"},
        )
        kind = _string(data["kind"], f"{location}.kind")
        if kind not in SHAPE_KINDS:
            _fail(f"{location}.kind", f"unknown shape kind {kind!r}")
        sections_value = data["sections"]
        if not isinstance(sections_value, list) or not sections_value:
            _fail(f"{location}.sections", "expected a non-empty list")
        sections = tuple(
            ShapeSection.from_data(item, f"{location}.sections[{index}]")
            for index, item in enumerate(sections_value)
        )
        section_ids = [section.id for section in sections]
        if len(section_ids) != len(set(section_ids)):
            _fail(f"{location}.sections", "duplicate section IDs")
        headings = [section.heading for section in sections]
        if len(headings) != len(set(headings)):
            _fail(f"{location}.sections", "duplicate section headings")
        # Compiled policy round-trips the dataclass, so an inapplicable
        # heading_level arrives as an explicit null rather than as an absent key.
        declared_level = data.get("heading_level")
        heading_level: int | None = None
        if kind in MARKDOWN_SHAPE_KINDS:
            if declared_level is None:
                _fail(location, "missing keys: heading_level")
            heading_level = _integer(declared_level, f"{location}.heading_level")
            if heading_level < 1 or heading_level > 6:
                _fail(f"{location}.heading_level", "expected a level between 1 and 6")
        elif declared_level is not None:
            _fail(f"{location}.heading_level", f"unsupported for shape kind {kind!r}")
        return cls(
            id=_string(data["id"], f"{location}.id"),
            path=_string(data["path"], f"{location}.path"),
            kind=kind,
            rule=_string(data["rule"], f"{location}.rule"),
            allow_unlisted=_boolean(
                data["allow_unlisted"], f"{location}.allow_unlisted"
            ),
            sections=sections,
            heading_level=heading_level,
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


def _validate_dials(value: Any, location: str) -> None:
    """A dial is one calibrated behaviour, stated as a level out of a scale."""
    if not isinstance(value, list) or not value:
        _fail(location, "expected a non-empty list")
    labels: list[str] = []
    for index, item in enumerate(value):
        where = f"{location}[{index}]"
        data = _mapping(item, where)
        _keys(data, where, required={"label", "level", "scale"})
        labels.append(_string(data["label"], f"{where}.label"))
        level = _integer(data["level"], f"{where}.level")
        scale = _integer(data["scale"], f"{where}.scale")
        if not 1 <= level <= scale:
            _fail(f"{where}.level", f"expected 1..{scale}, got {level}")
    if len(labels) != len(set(labels)):
        _fail(location, "contains duplicate labels")


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
        "shape",
        "section",
        "token",
    ):
        if key in config:
            _string(config[key], f"{location}.{key}")
    for key in (
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
    # A profile with no permitted guard states an empty list: policy owning the
    # guard form means the absence of one is declared, not merely unwritten.
    if "guards_by_profile" in config:
        guards = _mapping(config["guards_by_profile"], f"{location}.guards_by_profile")
        for profile_id, values in guards.items():
            _strings(
                values, f"{location}.guards_by_profile.{profile_id}", non_empty=False
            )
    if "hooks" in config:
        hooks = config["hooks"]
        if not isinstance(hooks, list) or not hooks:
            _fail(f"{location}.hooks", "expected a non-empty list")
        for index, hook in enumerate(hooks):
            _validate_hook(hook, f"{location}.hooks[{index}]")
    if "dials" in config:
        _validate_dials(config["dials"], f"{location}.dials")


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
    shapes: tuple[Shape, ...]
    rules: tuple[Rule, ...]

    @property
    def profile_ids(self) -> tuple[str, ...]:
        return tuple(profile.id for profile in self.profiles)

    @property
    def shape_ids(self) -> tuple[str, ...]:
        return tuple(shape.id for shape in self.shapes)

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def shape(self, shape_id: str) -> Shape:
        try:
            return next(shape for shape in self.shapes if shape.id == shape_id)
        except StopIteration as error:
            raise PolicyError(f"unknown shape {shape_id!r}") from error

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
                "shapes",
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
        shapes_value = data["shapes"]
        rules_value = data["rules"]
        if not isinstance(profiles_value, list) or not profiles_value:
            _fail(f"{location}.profiles", "expected a non-empty list")
        if not isinstance(shapes_value, list) or not shapes_value:
            _fail(f"{location}.shapes", "expected a non-empty list")
        if not isinstance(rules_value, list) or not rules_value:
            _fail(f"{location}.rules", "expected a non-empty list")
        profiles = tuple(
            Profile.from_data(item, f"{location}.profiles[{index}]")
            for index, item in enumerate(profiles_value)
        )
        shapes = tuple(
            Shape.from_data(item, f"{location}.shapes[{index}]")
            for index, item in enumerate(shapes_value)
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
            shapes=shapes,
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

        shape_ids = self.shape_ids
        if len(shape_ids) != len(set(shape_ids)):
            _fail(f"{location}.shapes", "duplicate shape IDs")
        shape_paths = [shape.path for shape in self.shapes]
        if len(shape_paths) != len(set(shape_paths)):
            _fail(f"{location}.shapes", "two shapes govern the same path")

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
            for key in ("commands_by_profile", "guards_by_profile"):
                by_profile = rule.check.config.get(key)
                if not isinstance(by_profile, dict):
                    continue
                where = f"{location}.rules.{rule.id}.check.config.{key}"
                unknown_declared = set(by_profile) - known_profiles
                if unknown_declared:
                    _fail(where, f"unknown profiles: {sorted(unknown_declared)}")
                missing_declared = set(rule.profiles) - set(by_profile)
                if missing_declared:
                    _fail(where, f"missing profiles: {sorted(missing_declared)}")
            allowed_missing = rule.check.config.get("allow_missing_profiles")
            if isinstance(allowed_missing, list):
                unknown_allowed = set(allowed_missing) - known_profiles
                if unknown_allowed:
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.allow_missing_profiles",
                        f"unknown profiles: {sorted(unknown_allowed)}",
                    )
            shape_id = rule.check.config.get("shape")
            if isinstance(shape_id, str):
                if shape_id not in set(shape_ids):
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.shape",
                        f"unknown shape {shape_id!r}",
                    )
                elif self.shape(shape_id).kind != rule.check.kind:
                    _fail(
                        f"{location}.rules.{rule.id}.check.config.shape",
                        f"shape {shape_id!r} is not a {rule.check.kind} shape",
                    )

        # A shape and its rule must name each other, so neither the check nor
        # the generator can be pointed at a document the other does not govern.
        for shape in self.shapes:
            shape_location = f"{location}.shapes.{shape.id}.rule"
            if shape.rule not in set(rule_ids):
                _fail(shape_location, f"unknown rule {shape.rule!r}")
            if self.rule(shape.rule).check.config.get("shape") != shape.id:
                _fail(shape_location, f"rule {shape.rule} does not enforce this shape")


def _safe_yaml(path: Path) -> Any:
    try:
        return _SAFE_YAML.load(path.read_text(encoding="utf-8"))
    except YAMLError as error:
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
            "shape_files",
            "rules",
        },
    )
    profile_files = _strings(data.pop("profile_files"), f"{base_path}.profile_files")
    profiles = []
    for relative in profile_files:
        profile_path = repo_root / "policy" / relative
        profiles.append(_safe_yaml(profile_path))
    data["profiles"] = profiles
    shape_files = _strings(data.pop("shape_files"), f"{base_path}.shape_files")
    shapes: list[Any] = []
    for relative in shape_files:
        shape_path = repo_root / "policy" / relative
        shape_data = _mapping(_safe_yaml(shape_path), str(shape_path))
        _keys(shape_data, str(shape_path), required={"schema_version", "shapes"})
        if _integer(shape_data["schema_version"], f"{shape_path}.schema_version") != 1:
            _fail(f"{shape_path}.schema_version", "unsupported shape schema version")
        shape_list = shape_data["shapes"]
        if not isinstance(shape_list, list) or not shape_list:
            _fail(f"{shape_path}.shapes", "expected a non-empty list")
        shapes.extend(shape_list)
    data["shapes"] = shapes
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
