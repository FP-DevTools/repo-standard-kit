"""Compile canonical YAML policy into packaged runtime data and reference docs."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.policy import load_source_policy  # noqa: E402
from repo_standard.policy.compiler import (  # noqa: E402
    render_compiled,
    render_reference,
)

COMPILED_PATH = REPO_ROOT / "src" / "repo_standard" / "policy" / "compiled.json"
REFERENCE_PATH = REPO_ROOT / "docs" / "policy-reference.md"


def main() -> int:
    policy = load_source_policy(REPO_ROOT)
    COMPILED_PATH.write_text(render_compiled(policy), encoding="utf-8")
    REFERENCE_PATH.write_text(render_reference(policy), encoding="utf-8")
    print(f"Wrote {COMPILED_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {REFERENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
