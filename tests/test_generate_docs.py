"""The shape produces the reference documents; nothing else may.

These tests guard the property that makes `policy/shapes.yaml` a single source
rather than one of two things kept in agreement: every shipped reference
document is a fresh render of the shape, and no fragment carries ordering of
its own.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from repo_standard.policy import load_source_policy

_SPEC = importlib.util.spec_from_file_location(
    "generate_docs", REPO_ROOT / "scripts" / "generate_docs.py"
)
assert _SPEC is not None and _SPEC.loader is not None
generate_docs = importlib.util.module_from_spec(_SPEC)
# `dataclasses` resolves annotations through `sys.modules`, so the module has to
# be registered before it executes, not after.
sys.modules[_SPEC.name] = generate_docs
_SPEC.loader.exec_module(generate_docs)

POLICY = load_source_policy(REPO_ROOT)
RESERVED = (generate_docs.PREAMBLE, generate_docs.EPILOGUE)
FRAGMENT = re.compile(r"^(?P<id>.+)\.(?P<variant>[^.]+)\.md$")


def _fragment_files() -> list[Path]:
    return sorted(generate_docs.CONTENT_ROOT.rglob("*.md"))


def _headings_outside_code(text: str) -> list[tuple[int, str]]:
    """Return `(level, heading)` pairs, ignoring anything inside a code fence."""
    headings: list[tuple[int, str]] = []
    fence: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if fence is None:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence = stripped[:3]
                continue
        else:
            if stripped.startswith(fence):
                fence = None
            continue
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match is not None:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


@pytest.mark.parametrize(
    "target", generate_docs.TARGETS, ids=lambda t: f"{t.variant}-{t.document}"
)
def test_shipped_documents_are_not_stale(target: Any) -> None:
    """`scripts/generate_docs.py` must be a no-op against a clean checkout."""
    path = target.path / f"{target.document}.md"
    assert path.read_text(encoding="utf-8") == generate_docs.render(POLICY, target), (
        f"{path.relative_to(REPO_ROOT).as_posix()} is stale; "
        "run `uv run python scripts/generate_docs.py`"
    )


@pytest.mark.parametrize(
    "target", generate_docs.TARGETS, ids=lambda t: f"{t.variant}-{t.document}"
)
def test_rendered_headings_are_exactly_the_shape_in_order(target: Any) -> None:
    """Order is derived from the shape, so a render cannot deviate from it."""
    shape = POLICY.shape(target.shape)
    rendered = generate_docs.render(POLICY, target)
    emitted = [
        heading
        for level, heading in _headings_outside_code(rendered)
        if level == shape.heading_level
    ]
    declared = [h for h in shape.headings if h in emitted]
    assert emitted == declared, (
        f"{target.variant} {target.document} emitted headings the shape does not "
        f"declare, or declared ones out of order: {emitted}"
    )
    missing = [s.heading for s in shape.sections if s.level == "required"]
    assert [h for h in missing if h not in emitted] == []


@pytest.mark.parametrize("path", _fragment_files(), ids=lambda p: p.name)
def test_fragments_carry_no_ordering_of_their_own(path: Path) -> None:
    """A fragment that opens its own section would escape the shape's order."""
    document = path.parent.name
    fragment_id = path.name.split(".", maxsplit=1)[0]
    shape = next(
        POLICY.shape(t.shape) for t in generate_docs.TARGETS if t.document == document
    )
    assert shape.heading_level is not None
    ceiling = shape.heading_level if fragment_id != generate_docs.PREAMBLE else 0
    offenders = [
        heading
        for level, heading in _headings_outside_code(
            path.read_text(encoding="utf-8")
        )
        if level <= ceiling
    ]
    assert not offenders, (
        f"{path.name} declares its own section headings {offenders}; sections come "
        "from policy/shapes.yaml, fragments carry prose only"
    )


@pytest.mark.parametrize("path", _fragment_files(), ids=lambda p: p.name)
def test_every_fragment_is_bound_to_a_declared_section(path: Path) -> None:
    """An orphan fragment is prose nothing will ever emit."""
    match = FRAGMENT.match(path.name)
    assert match is not None, f"{path.name} is not <section-id>.<variant>.md"
    fragment_id = match.group("id")
    document = path.parent.name
    targets = [t for t in generate_docs.TARGETS if t.document == document]
    assert targets, f"{document}/ has no target that renders it"
    if fragment_id in RESERVED:
        return
    section_ids = {s.id for s in POLICY.shape(targets[0].shape).sections}
    assert fragment_id in section_ids, (
        f"{path.name} keys off {fragment_id!r}, which no section of shape "
        f"{targets[0].shape!r} declares"
    )
    variants = {generate_docs.SHARED, *(t.variant for t in targets)}
    assert match.group("variant") in variants, (
        f"{path.name} has variant {match.group('variant')!r}; {document} renders "
        f"only {sorted(variants)}"
    )


def test_generator_tokens_never_reach_shipped_output() -> None:
    """Generator tokens are resolved here, unlike the repo-init placeholders."""
    tokens = generate_docs._tokens(POLICY, "python-single")
    for target in generate_docs.TARGETS:
        rendered = generate_docs.render(POLICY, target)
        leftover = [token for token in tokens if token in rendered]
        assert not leftover, f"{target.variant} {target.document} leaked {leftover}"


def test_the_gate_chain_is_injected_from_policy_not_written_by_hand() -> None:
    """The chain had four hand-maintained copies; there must now be none."""
    fragments = [
        path
        for path in _fragment_files()
        if path.parent.name == "AGENTS" and path.name.startswith("quality-gates.")
    ]
    assert fragments, "the AGENTS quality-gates fragments disappeared"
    for path in fragments:
        text = path.read_text(encoding="utf-8")
        assert "__GATE_CHAIN__" in text, f"{path.name} must defer to policy"
        for profile in ("python-single", "python-workspace"):
            commands = POLICY.rule("RSK003").check.config["commands_by_profile"][
                profile
            ]
            restated = [command for command in commands if command in text]
            assert not restated, f"{path.name} restates the chain: {restated}"
