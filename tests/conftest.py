"""Shared policy-derived test fixtures."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.policy import load_compiled_policy  # noqa: E402


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


def required_agents_sections() -> list[str]:
    policy = load_compiled_policy()
    return list(policy.rule("RSK002").check.config["headings"])


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
