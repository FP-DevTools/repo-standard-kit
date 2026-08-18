"""Test fixtures, and parsers that make the normative documents authoritative.

The gate chain, the required `AGENTS.md` sections, and the formatting baseline
are defined in `docs/quality-gates.md` and `docs/repo-standard.md`. Parsing them
here rather than restating them as literals means editing a normative document
without updating the assets that implement it fails the suite instead of
drifting silently.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QUALITY_GATES_DOC = REPO_ROOT / "docs" / "quality-gates.md"
REPO_STANDARD_DOC = REPO_ROOT / "docs" / "repo-standard.md"

CI_GATES_SECTION = "## 5. CI Pull Request Gates"
FORMATTING_SECTION = "## 13. Formatting Baseline"
PROSE_WIDTH = 88
REQUIRED_SECTIONS_HEADING = "## Required `AGENTS.md` Sections"


def _section(document: Path, heading: str) -> str:
    """Return the body of a document section, up to the next same-level heading."""
    text = document.read_text(encoding="utf-8")
    if heading not in text:
        raise AssertionError(f"{document.name} no longer contains {heading!r}")
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def mandatory_ci_commands() -> list[str]:
    """The mandatory CI gate chain, in order, as `docs/quality-gates.md` defines it."""
    body = _section(QUALITY_GATES_DOC, CI_GATES_SECTION)
    commands = [
        line.strip()
        for block in re.findall(r"```bash\n(.*?)```", body, re.DOTALL)
        for line in block.strip().splitlines()
        if line.strip()
    ]
    if not commands:
        raise AssertionError(f"No gate commands found under {CI_GATES_SECTION!r}")
    return commands


def required_agents_sections() -> list[str]:
    """The `AGENTS.md` sections every adopting repository must provide."""
    body = _section(REPO_STANDARD_DOC, REQUIRED_SECTIONS_HEADING)
    sections = re.findall(r"^\d+\.\s+(.+?)\s*$", body, re.MULTILINE)
    if not sections:
        raise AssertionError(
            f"No required sections found under {REQUIRED_SECTIONS_HEADING!r}"
        )
    return sections


class RuffBaseline(NamedTuple):
    """The Ruff settings `docs/quality-gates.md` section 13 requires."""

    line_length: int
    select: tuple[str, ...]


def documented_ruff_baseline() -> RuffBaseline:
    """Parse the required Ruff configuration out of the formatting baseline."""
    body = _section(QUALITY_GATES_DOC, FORMATTING_SECTION)
    blocks = re.findall(r"```toml\n(.*?)```", body, re.DOTALL)
    if not blocks:
        raise AssertionError(f"No toml block found under {FORMATTING_SECTION!r}")
    ruff = tomllib.loads(blocks[0])["tool"]["ruff"]
    return RuffBaseline(
        line_length=int(ruff["line-length"]),
        select=tuple(ruff["lint"]["select"]),
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
