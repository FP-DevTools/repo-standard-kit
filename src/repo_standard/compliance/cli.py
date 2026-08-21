"""`repo-check` — verify a repository's structural alignment with the standard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from repo_standard.compliance.checks import Finding, check_repo, load_policy
from repo_standard.policy.models import DEFAULT_LEVELS, STRICT_LEVELS
from repo_standard.project_metadata import kit_version

_POSITIVE = "\033[38;2;35;209;111m"
_RESET = "\033[0m"


def build_parser() -> argparse.ArgumentParser:
    policy = load_policy()
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
        choices=["auto", *policy.profile_ids],
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
        help="Treat recommended findings as failures too. Advisory never fails.",
    )
    parser.add_argument(
        "--version",
        action="version",
        # Adopters pin by Git ref, so a disputed finding starts with which
        # checker ran and which compiled policy it carried.
        version=(
            f"repo-check {kit_version()} (standard {policy.standard_version}, "
            f"standard major {policy.standard_major})"
        ),
        help="Print the checker and compiled standard versions, then exit.",
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
        return f"{_POSITIVE}{message}{_RESET}\n" if color else f"{message}\n"
    lines = []
    for finding in findings:
        location = finding.path + (
            f":{finding.line}" if finding.line is not None else ""
        )
        # The level column names how binding the rule is; a status other than
        # `violation` means this line is not the rule failing, so say so
        # rather than let the column read as a failure.
        status = "" if finding.status == "violation" else f" [{finding.status}]"
        lines.append(
            f"{finding.level.upper():11} {finding.rule_id}{status}  {location}  "
            f"{finding.title}: {finding.message}"
        )
        if finding.actual is not None:
            lines.append(f"  actual: {finding.actual!r}")
        if finding.expected is not None:
            lines.append(f"  expected: {finding.expected!r}")
        lines.append(f"  remediation: {finding.remediation}")
    lines.append(f"\n{len(findings)} finding(s).")
    return "\n".join(lines) + "\n"


def _format_json(findings: list[Finding]) -> str:
    return (
        json.dumps(
            [
                {
                    "rule_id": finding.rule_id,
                    "title": finding.title,
                    "level": finding.level,
                    "path": finding.path,
                    "line": finding.line,
                    "message": finding.message,
                    "actual": finding.actual,
                    "expected": finding.expected,
                    "remediation": finding.remediation,
                    "status": finding.status,
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

    policy = load_policy()
    profile = None if args.profile == "auto" else args.profile
    findings = check_repo(
        root, policy, profile=profile, include_platform=args.check_enforcement
    )

    output = (
        _format_json(findings)
        if args.format == "json"
        else _format_text(findings, color=_supports_color())
    )
    print(output, end="")

    if any(finding.status == "indeterminate" for finding in findings):
        return 2
    # `advisory` belongs to neither set: those findings are always printed
    # above and never reach the exit code, not even under `--strict`. Only a
    # `violation` can fail a run at all — an `unused-exemption` is a report
    # about the configuration, not a rule the repository broke.
    levels = STRICT_LEVELS if args.strict else DEFAULT_LEVELS
    if any(
        finding.level in levels and finding.status == "violation"
        for finding in findings
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
