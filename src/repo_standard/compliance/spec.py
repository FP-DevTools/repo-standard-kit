"""Parsers that make the normative documents authoritative.

The gate chain, the required `AGENTS.md` sections, and the formatting baseline
are defined in `docs/quality-gates.md` and `docs/repo-standard.md`. Parsing
them here rather than restating them as literals means editing a normative
document without regenerating `compliance/rules.json` fails the suite instead
of drifting silently. `tests/conftest.py` and `scripts/generate_rules.py` both
import from this module so there is exactly one parser implementation.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, NamedTuple

from repo_standard.repo_init import PLACEHOLDERS

CI_GATES_SECTION = "## 5. CI Pull Request Gates"
FORMATTING_SECTION = "## 13. Formatting Baseline"
PROSE_WIDTH = 88
REQUIRED_SECTIONS_HEADING = "## Required `AGENTS.md` Sections"

# The exact bootstrap placeholder vocabulary `repo_init.py` substitutes, not
# every dunder-shaped token — a repository's own code may legitimately use
# `__SOME_CONSTANT__`-style names for reasons that have nothing to do with
# this standard's templating. See docs/compliance.md's RSK011 note.
KNOWN_PLACEHOLDER_TOKENS: tuple[str, ...] = tuple(PLACEHOLDERS)

# docs/quality-gates.md §4 lists hook *categories* ("YAML validation", ...),
# not literal commands, so this baseline is a maintained constant rather than
# a parse — the same approach the test suite has always used for it.
MANDATORY_PRE_COMMIT_ENTRIES: tuple[str, ...] = (
    "uv run check-yaml",
    "uv run check-toml",
    "uv run check-json",
    "uv run trailing-whitespace-fixer",
    "uv run end-of-file-fixer",
    "uv run check-merge-conflict",
    "uv run detect-private-key",
    "uv run detect-secrets-hook",
    "uv run check-added-large-files",
    "uv run ruff check --force-exclude",
    "uv run ruff format --force-exclude",
    "uv run ty check",
)


def _section(document: Path, heading: str) -> str:
    """Return the body of a document section, up to the next same-level heading."""
    text = document.read_text(encoding="utf-8")
    if heading not in text:
        raise AssertionError(f"{document.name} no longer contains {heading!r}")
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def mandatory_ci_commands(quality_gates_doc: Path) -> list[str]:
    """The mandatory CI gate chain, in order, as `docs/quality-gates.md` defines it."""
    body = _section(quality_gates_doc, CI_GATES_SECTION)
    commands = [
        line.strip()
        for block in re.findall(r"```bash\n(.*?)```", body, re.DOTALL)
        for line in block.strip().splitlines()
        if line.strip()
    ]
    if not commands:
        raise AssertionError(f"No gate commands found under {CI_GATES_SECTION!r}")
    return commands


def required_agents_sections(repo_standard_doc: Path) -> list[str]:
    """The `AGENTS.md` sections every adopting repository must provide."""
    body = _section(repo_standard_doc, REQUIRED_SECTIONS_HEADING)
    sections = re.findall(r"^\d+\.\s+(.+?)\s*$", body, re.MULTILINE)
    if not sections:
        raise AssertionError(
            f"No required sections found under {REQUIRED_SECTIONS_HEADING!r}"
        )
    return sections


class RuffBaseline(NamedTuple):
    """A Ruff configuration as actually declared: `line-length` and `select`."""

    line_length: int
    select: tuple[str, ...]


class RuffPolicy(NamedTuple):
    """What §13 requires versus recommends for Ruff configuration.

    `mandatory_select` families must be present, and `line-length` must be
    declared explicitly to *some* value — but which value, and whether
    `recommended_select` is also selected, are recommendations (should), not
    requirements.
    """

    mandatory_select: tuple[str, ...]
    recommended_line_length: int
    recommended_select: tuple[str, ...]


def documented_ruff_policy(quality_gates_doc: Path) -> RuffPolicy:
    """Parse the mandatory and recommended Ruff configuration out of §13."""
    body = _section(quality_gates_doc, FORMATTING_SECTION)
    blocks = re.findall(r"```toml\n(.*?)```", body, re.DOTALL)
    if len(blocks) < 2:
        raise AssertionError(
            f"Expected a mandatory and a recommended toml block under "
            f"{FORMATTING_SECTION!r}"
        )
    mandatory = tomllib.loads(blocks[0])["tool"]["ruff"]
    recommended = tomllib.loads(blocks[1])["tool"]["ruff"]["lint"]
    return RuffPolicy(
        mandatory_select=tuple(mandatory["lint"]["select"]),
        recommended_line_length=int(mandatory["line-length"]),
        recommended_select=tuple(recommended["select"]),
    )


def ruff_config_of(pyproject_path: Path) -> RuffBaseline:
    """Read the Ruff settings a pyproject.toml actually declares."""
    ruff = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["tool"]["ruff"]
    return RuffBaseline(
        line_length=int(ruff["line-length"]),
        select=tuple(ruff["lint"]["select"]),
    )


def prose_offenders(path: Path, limit: int = PROSE_WIDTH) -> list[tuple[int, int]]:
    """Over-long markdown lines, ignoring what cannot reasonably be wrapped.

    Exempt, per the formatting baseline: fenced code blocks, table rows, link
    reference definitions, and lines whose length comes from one unbreakable
    token such as a URL.
    """
    offenders: list[tuple[int, int]] = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or len(line) <= limit:
            continue
        if stripped.startswith("|"):
            continue
        if stripped.startswith("[") and "]: http" in line:
            continue
        if max((len(word) for word in line.split()), default=0) > limit - 20:
            continue
        offenders.append((number, len(line)))
    return offenders


class Rules(NamedTuple):
    """The frozen, machine-readable form of the normative documents.

    `compliance/rules.json` is this object serialized; `checks.py` loads it at
    runtime so a repository can be judged without `docs/` being present.
    """

    standard_version: str
    mandatory_ci_commands: tuple[str, ...]
    required_agents_sections: tuple[str, ...]
    ruff_mandatory_select: tuple[str, ...]
    ruff_recommended_line_length: int
    ruff_recommended_select: tuple[str, ...]
    prose_width: int
    mandatory_pre_commit_entries: tuple[str, ...]
    known_placeholder_tokens: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "standard_version": self.standard_version,
            "mandatory_ci_commands": list(self.mandatory_ci_commands),
            "required_agents_sections": list(self.required_agents_sections),
            "ruff_mandatory_select": list(self.ruff_mandatory_select),
            "ruff_recommended_line_length": self.ruff_recommended_line_length,
            "ruff_recommended_select": list(self.ruff_recommended_select),
            "prose_width": self.prose_width,
            "mandatory_pre_commit_entries": list(self.mandatory_pre_commit_entries),
            "known_placeholder_tokens": list(self.known_placeholder_tokens),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Rules:
        return cls(
            standard_version=data["standard_version"],
            mandatory_ci_commands=tuple(data["mandatory_ci_commands"]),
            required_agents_sections=tuple(data["required_agents_sections"]),
            ruff_mandatory_select=tuple(data["ruff_mandatory_select"]),
            ruff_recommended_line_length=data["ruff_recommended_line_length"],
            ruff_recommended_select=tuple(data["ruff_recommended_select"]),
            prose_width=data["prose_width"],
            mandatory_pre_commit_entries=tuple(data["mandatory_pre_commit_entries"]),
            known_placeholder_tokens=tuple(data["known_placeholder_tokens"]),
        )


def _standard_version(repo_root: Path) -> str:
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    return str(pyproject["project"]["version"])


def build_rules(repo_root: Path) -> Rules:
    """Parse the normative documents under `repo_root` into a `Rules` object."""
    quality_gates_doc = repo_root / "docs" / "quality-gates.md"
    repo_standard_doc = repo_root / "docs" / "repo-standard.md"
    ruff_policy = documented_ruff_policy(quality_gates_doc)
    return Rules(
        standard_version=_standard_version(repo_root),
        mandatory_ci_commands=tuple(mandatory_ci_commands(quality_gates_doc)),
        required_agents_sections=tuple(required_agents_sections(repo_standard_doc)),
        ruff_mandatory_select=ruff_policy.mandatory_select,
        ruff_recommended_line_length=ruff_policy.recommended_line_length,
        ruff_recommended_select=ruff_policy.recommended_select,
        prose_width=PROSE_WIDTH,
        mandatory_pre_commit_entries=MANDATORY_PRE_COMMIT_ENTRIES,
        known_placeholder_tokens=KNOWN_PLACEHOLDER_TOKENS,
    )
