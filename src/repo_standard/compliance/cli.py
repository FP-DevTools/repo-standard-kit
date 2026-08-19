"""`repo-check` — verify a repository's structural alignment with the standard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from repo_standard.compliance.checks import Finding, check_repo, load_rules

_GREEN = "\033[32m"
_RESET = "\033[0m"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a repository's structural alignment with repo-standard-kit."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository to check. Defaults to the current directory.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--profile",
        choices=["auto", "python-single", "python-workspace"],
        default="auto",
    )
    parser.add_argument(
        "--check-enforcement",
        action="store_true",
        help="Also check branch protection (§10). Needs gh, network, and auth.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat 'should' findings as failures too.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _supports_color() -> bool:
    """Follows ruff/ty: colored unless NO_COLOR is set or stdout isn't a tty."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def _format_text(findings: list[Finding], *, color: bool) -> str:
    if not findings:
        message = "All checks passed!"
        return f"{_GREEN}{message}{_RESET}\n" if color else f"{message}\n"
    lines = [
        f"{finding.severity.upper():8} {finding.rule_id}  {finding.path}"
        + (f":{finding.line}" if finding.line is not None else "")
        + f"  {finding.message}"
        for finding in findings
    ]
    lines.append(f"\n{len(findings)} finding(s).")
    return "\n".join(lines) + "\n"


def _format_json(findings: list[Finding]) -> str:
    return (
        json.dumps(
            [
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "path": finding.path,
                    "line": finding.line,
                    "message": finding.message,
                }
                for finding in findings
            ],
            indent=2,
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"repo-check: {root} is not a directory", file=sys.stderr)
        return 2

    rules = load_rules()
    profile = None if args.profile == "auto" else args.profile
    findings = check_repo(
        root, rules, profile=profile, include_platform=args.check_enforcement
    )

    output = (
        _format_json(findings)
        if args.format == "json"
        else _format_text(findings, color=_supports_color())
    )
    print(output, end="")

    severities = {"shall", "should"} if args.strict else {"shall"}
    if any(finding.severity in severities for finding in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
