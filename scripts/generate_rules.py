"""Regenerate `compliance/rules.json` from the normative documents.

Run after editing `docs/quality-gates.md` or `docs/repo-standard.md`, then
commit the result. `tests/test_compliance.py` fails CI if the committed file
drifts from what this script would produce (§6 Generated Artifact Consistency).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_standard.compliance.spec import build_rules  # noqa: E402

RULES_JSON_PATH = REPO_ROOT / "src" / "repo_standard" / "compliance" / "rules.json"


def main() -> int:
    rules = build_rules(REPO_ROOT)
    RULES_JSON_PATH.write_text(
        json.dumps(rules.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {RULES_JSON_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
