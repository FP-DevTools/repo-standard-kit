"""Validation helpers for immutable GitHub references."""

from __future__ import annotations

import re

_FULL_COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def is_full_commit_sha(reference: str) -> bool:
    """Return whether ``reference`` is a full Git commit SHA."""
    return _FULL_COMMIT_SHA.fullmatch(reference) is not None
