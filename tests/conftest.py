"""Test fixtures, and parsers that make the normative documents authoritative.

The gate chain and the required `AGENTS.md` sections are defined in
`docs/quality-gates.md` and `docs/repo-standard.md`. Parsing them here rather
than restating them as literals means editing a normative document without
updating the assets that implement it fails the suite instead of drifting
silently.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QUALITY_GATES_DOC = REPO_ROOT / "docs" / "quality-gates.md"
REPO_STANDARD_DOC = REPO_ROOT / "docs" / "repo-standard.md"

CI_GATES_SECTION = "## 5. CI Pull Request Gates"
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
