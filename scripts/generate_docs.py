"""Render every reference document from the shapes declared in ``policy/``.

Prose lives in ``templates/content/<DOC>/<section-id>.<variant>.md`` fragments
that carry no ordering of their own. This script walks the ordered section list
of the shape a document is bound to, emits the heading, and appends the
fragment resolved for the target's variant. A section the shape does not
declare cannot be emitted, and reordering a document means editing
``policy/shapes.yaml`` -- order is derived here, never asserted twice.

Two fragment ids are reserved and are not shape sections: ``_preamble`` (the
title and any prose before the first heading) and ``_epilogue`` (link reference
definitions). Shape section ids are kebab-case, so the leading underscore
cannot collide with one.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.policy import load_source_policy  # noqa: E402
from repo_standard.policy.models import Policy  # noqa: E402

CONTENT_ROOT = REPO_ROOT / "templates" / "content"
STARTER_KITS = SRC / "repo_standard" / "starter_kits"

# These companion documents own their subjects.  AGENTS.md is a generated
# projection so repositories receive the same guidance without a second prose
# copy to maintain in template fragments.
DERIVED_SECTIONS = {
    ("AGENTS", "human-and-agent-responsibilities"): REPO_ROOT
    / "docs"
    / "agent-operating-model.md",
    ("AGENTS", "workflow"): REPO_ROOT / "docs" / "git-workflow.md",
}

PREAMBLE = "_preamble"
EPILOGUE = "_epilogue"
SHARED = "shared"
TEMPLATE = "template"


class GeneratorError(RuntimeError):
    """A document could not be rendered from the shape and its fragments."""


@dataclass(frozen=True)
class Target:
    """One rendered document.

    ``variant`` selects fragments; ``profile`` selects the policy values that
    fill generator tokens. They are separate because the ``template`` variant
    is not a profile but still has to state a concrete gate chain.
    """

    document: str
    shape: str
    variant: str
    profile: str
    path: Path


TARGETS = (
    Target("README", "readme", TEMPLATE, "python-single", REPO_ROOT / "templates"),
    Target("AGENTS", "agents", TEMPLATE, "python-single", REPO_ROOT / "templates"),
    *(
        Target(document, shape, profile, profile, STARTER_KITS / profile)
        for profile in ("python-single", "python-workspace")
        for document, shape in (
            ("README", "readme"),
            ("AGENTS", "agents"),
            ("CHANGELOG", "changelog"),
        )
    ),
)


def _fragment(document: str, fragment_id: str, variant: str) -> str | None:
    """Resolve ``(document, fragment, variant)``, falling back to ``shared``."""
    for candidate in (variant, SHARED):
        path = CONTENT_ROOT / document / f"{fragment_id}.{candidate}.md"
        if path.is_file():
            return path.read_text(encoding="utf-8").strip("\n")
    return None


def _derived_section(document: str, section_id: str) -> str | None:
    """Project a companion document into its generated AGENTS.md section."""
    path = DERIVED_SECTIONS.get((document, section_id))
    if path is None:
        return None
    title, separator, body = path.read_text(encoding="utf-8").partition("\n")
    if not title.startswith("# ") or not separator or not body.strip():
        raise GeneratorError(
            f"{path.relative_to(REPO_ROOT)} must contain a title and body"
        )
    return re.sub(r"(?m)^#{1,5}(?=\s)", lambda match: f"#{match[0]}", body.strip())


def _tokens(policy: Policy, profile: str) -> dict[str, str]:
    """Generator-owned substitutions, resolved before anything is written.

    These are deliberately not `repo_init.PLACEHOLDERS`: those must survive
    verbatim into the starter kits so `repo-init` can fill them per repository.
    These are filled here, so no shipped file ever carries one.
    """
    commands = policy.rule("RSK003").check.config["commands_by_profile"][profile]
    dials = policy.rule("RSK026").check.config["dials"]
    return {
        "__GATE_CHAIN__": "\n".join(
            f"{index}. `{command}`" for index, command in enumerate(commands, 1)
        ),
        "__AGENT_DIALS__": "\n".join(
            f"- **{dial['label']}:** {dial['level']} / {dial['scale']}"
            for dial in dials
        ),
        "__STANDARD_MAJOR__": policy.standard_major,
    }


def render(policy: Policy, target: Target) -> str:
    shape = policy.shape(target.shape)
    if shape.heading_level is None:
        raise GeneratorError(f"shape {shape.id!r} is not a Markdown shape")
    marks = "#" * shape.heading_level

    preamble = _fragment(target.document, PREAMBLE, target.variant)
    if preamble is None:
        raise GeneratorError(
            f"{target.document}/{PREAMBLE}: no fragment for variant "
            f"{target.variant!r} and no {SHARED} fallback"
        )
    parts = [preamble]

    for section in shape.sections:
        body = _derived_section(target.document, section.id)
        if body is None:
            body = _fragment(target.document, section.id, target.variant)
        if body is None:
            if section.level == "required":
                raise GeneratorError(
                    f"{target.document}/{section.id}: required by shape "
                    f"{shape.id!r} but no fragment for variant {target.variant!r}"
                )
            continue
        parts.append(f"{marks} {section.heading}\n\n{body}")

    epilogue = _fragment(target.document, EPILOGUE, target.variant)
    if epilogue is not None:
        parts.append(epilogue)

    text = "\n\n".join(parts) + "\n"
    for token, value in _tokens(policy, target.profile).items():
        text = text.replace(token, value)
    return text


def render_targets(policy: Policy) -> dict[Path, str]:
    """Render every target, keyed by absolute destination path."""
    return {
        target.path / f"{target.document}.md": render(policy, target)
        for target in TARGETS
    }


def main() -> int:
    policy = load_source_policy(REPO_ROOT)
    for path, content in render_targets(policy).items():
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
