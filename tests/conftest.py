"""Test fixtures.

The parsers that make the normative documents authoritative used to live
here; they now live in `repo_standard.compliance.spec` so the packaged
checker and this test suite share one implementation instead of two copies
drifting apart. This module keeps the zero-argument API the test suite
already uses, bound to this checkout's own documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.compliance import spec  # noqa: E402

PROSE_WIDTH = spec.PROSE_WIDTH
RuffBaseline = spec.RuffBaseline
prose_offenders = spec.prose_offenders
ruff_config_of = spec.ruff_config_of

QUALITY_GATES_DOC = REPO_ROOT / "docs" / "quality-gates.md"
REPO_STANDARD_DOC = REPO_ROOT / "docs" / "repo-standard.md"


def mandatory_ci_commands() -> list[str]:
    """The mandatory CI gate chain, in order, as `docs/quality-gates.md` defines it."""
    return spec.mandatory_ci_commands(QUALITY_GATES_DOC)


def required_agents_sections() -> list[str]:
    """The `AGENTS.md` sections every adopting repository must provide."""
    return spec.required_agents_sections(REPO_STANDARD_DOC)


def documented_ruff_baseline() -> RuffBaseline:
    """Parse the required Ruff configuration out of the formatting baseline."""
    return spec.documented_ruff_baseline(QUALITY_GATES_DOC)
