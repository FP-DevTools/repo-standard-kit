"""Shared policy-derived test fixtures."""

from __future__ import annotations

import sys
import tomllib
from io import StringIO
from pathlib import Path
from typing import Any, NamedTuple

from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.policy import Shape, load_compiled_policy  # noqa: E402

_SAFE_YAML = YAML(typ="safe")
_SAFE_YAML.default_flow_style = False
_SAFE_YAML.width = 4096
_SAFE_YAML.representer.sort_base_mapping_type_on_output = False


def load_yaml(text: str) -> Any:
    """Load YAML the way the checkers do, without round-trip decoration."""
    return _SAFE_YAML.load(text)


def dump_yaml(data: Any) -> str:
    """Dump YAML in declaration order, matching the loader's plain types."""
    stream = StringIO()
    _SAFE_YAML.dump(data, stream)
    return stream.getvalue()


class RuffBaseline(NamedTuple):
    line_length: int
    select: tuple[str, ...]


class RuffPolicy(NamedTuple):
    mandatory_select: tuple[str, ...]
    recommended_line_length: int
    recommended_select: tuple[str, ...]


def mandatory_ci_commands(profile: str = "python-single") -> list[str]:
    policy = load_compiled_policy()
    rule = policy.rule("RSK006")
    return list(rule.check.config["commands_by_profile"][profile])


def required_agents_sections(profile: str = "python-single") -> list[str]:
    return list(shape_of("RSK002").required_for(profile))


def shape_of(rule_id: str) -> Shape:
    """Return the shape a shape-driven rule enforces."""
    policy = load_compiled_policy()
    return policy.shape(policy.rule(rule_id).check.config["shape"])


def documented_ruff_policy() -> RuffPolicy:
    policy = load_compiled_policy()
    return RuffPolicy(
        mandatory_select=tuple(policy.rule("RSK010").check.config["required_select"]),
        recommended_line_length=policy.rule("RSK015").check.config["value"],
        recommended_select=tuple(policy.rule("RSK016").check.config["values"]),
    )


def ruff_config_of(pyproject_path: Path) -> RuffBaseline:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    ruff = data["tool"]["ruff"]
    return RuffBaseline(
        line_length=int(ruff["line-length"]),
        select=tuple(ruff["lint"]["select"]),
    )
