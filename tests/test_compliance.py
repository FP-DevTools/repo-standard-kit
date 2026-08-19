"""Tests for the `repo_standard.compliance` package: rules, checks, and the CLI.

`check_repo` is exercised two ways: synthetic minimal repositories built in
`tmp_path`, one mutation away from compliant, so each rule's pass and fail
branch is covered directly; and the real starter kits, bootstrapped by
`bootstrap_repo` the same way `repo-init` does, so it is impossible for a
generated repository to drift out of alignment with what the checker accepts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT

from repo_standard.compliance import cli
from repo_standard.compliance.checks import (
    RULES_JSON_PATH,
    Finding,
    check_repo,
    load_rules,
)
from repo_standard.compliance.spec import build_rules
from repo_standard.repo_init import bootstrap_repo

STARTER_KIT_PROFILES = ("python-single", "python-workspace")

RULES = load_rules()

# Rules that cannot meaningfully apply to repo-standard-kit's own repository:
# RSK005 asks a repo to link back to repo-standard-kit, which does not apply
# to repo-standard-kit itself; RSK011 flags "__TOKEN__"-shaped strings, and
# this repo's source is where those tokens are defined and tested, not a
# leftover from an unfinished bootstrap. See docs/compliance.md.
SELF_APPLICATION_EXCEPTIONS = {"RSK005", "RSK011"}


def _minimal_repo(tmp_path: Path) -> Path:
    """A repository that satisfies every structural (non-platform) rule."""
    root = tmp_path / "compliant-repo"
    root.mkdir()

    agents_sections = "\n\n".join(
        f"## {s}\n\nDetail." for s in RULES.required_agents_sections
    )
    gate_chain = "\n".join(
        f"{i}. `{c}`" for i, c in enumerate(RULES.mandatory_ci_commands, 1)
    )
    (root / "AGENTS.md").write_text(
        f"# AGENTS.md\n\n{agents_sections}\n\n## Quality Gates\n\n{gate_chain}\n\n"
        "See [repo-standard-kit](https://github.com/FP-DevTools/repo-standard-kit).\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# compliant-repo\n\nSee [repo-standard-kit]"
        "(https://github.com/FP-DevTools/repo-standard-kit).\n",
        encoding="utf-8",
    )

    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    steps = "\n".join(f"      - run: {c}" for c in RULES.mandatory_ci_commands)
    (workflow_dir / "quality.yml").write_text(
        f"name: Quality\non: [pull_request]\njobs:\n  quality:\n    steps:\n{steps}\n",
        encoding="utf-8",
    )

    hooks = "\n".join(f"        entry: {e}" for e in RULES.mandatory_pre_commit_entries)
    (root / ".pre-commit-config.yaml").write_text(
        f"repos:\n  - repo: local\n    hooks:\n{hooks}\n",
        encoding="utf-8",
    )

    select = ", ".join(
        f'"{s}"' for s in (*RULES.ruff_mandatory_select, *RULES.ruff_recommended_select)
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "compliant-repo"\n'
        'version = "0.1.0"\n\n'
        "[build-system]\n"
        'requires = ["uv_build>=0.11.20,<0.12"]\n'
        'build-backend = "uv_build"\n\n'
        "[tool.uv.build-backend]\n"
        'module-name = "compliant_repo"\n\n'
        "[tool.ruff]\n"
        f"line-length = {RULES.ruff_recommended_line_length}\n\n"
        "[tool.ruff.lint]\n"
        f"select = [{select}]\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("", encoding="utf-8")
    (root / "docs" / "adr").mkdir(parents=True)

    return root


def _rule_ids(findings: list[Finding]) -> set[str]:
    return {finding.rule_id for finding in findings}


def test_minimal_repo_has_no_structural_findings(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    findings = check_repo(root, RULES)
    assert findings == []


def test_missing_agents_md_reports_rsk001(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "AGENTS.md").unlink()
    assert "RSK001" in _rule_ids(check_repo(root, RULES))


def test_agents_md_missing_section_reports_rsk002(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    stripped = text.replace(
        f"## {RULES.required_agents_sections[0]}", "## Something Else"
    )
    (root / "AGENTS.md").write_text(stripped, encoding="utf-8")
    assert "RSK002" in _rule_ids(check_repo(root, RULES))


def test_agents_md_missing_gate_command_reports_rsk003(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    stripped = text.replace(f"`{RULES.mandatory_ci_commands[0]}`", "`echo hi`")
    (root / "AGENTS.md").write_text(stripped, encoding="utf-8")
    assert "RSK003" in _rule_ids(check_repo(root, RULES))


def test_missing_readme_reports_rsk004(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "README.md").unlink()
    assert "RSK004" in _rule_ids(check_repo(root, RULES))


def test_readme_without_kit_reference_reports_rsk005(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "README.md").write_text(
        "# compliant-repo\n\nNo reference here.\n", encoding="utf-8"
    )
    assert "RSK005" in _rule_ids(check_repo(root, RULES))


def test_ci_workflow_missing_gate_reports_rsk006(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    workflow_path = root / ".github" / "workflows" / "quality.yml"
    text = workflow_path.read_text(encoding="utf-8")
    workflow_path.write_text(
        text.replace(f"run: {RULES.mandatory_ci_commands[0]}", "run: echo hi"),
        encoding="utf-8",
    )
    assert "RSK006" in _rule_ids(check_repo(root, RULES))


def test_pre_commit_missing_hook_reports_rsk007(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    config_path = root / ".pre-commit-config.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace(
            f"entry: {RULES.mandatory_pre_commit_entries[0]}", "entry: echo hi"
        ),
        encoding="utf-8",
    )
    assert "RSK007" in _rule_ids(check_repo(root, RULES))


def test_wrong_build_backend_reports_rsk008(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    pyproject_path.write_text(
        text.replace('build-backend = "uv_build"', 'build-backend = "hatchling.build"'),
        encoding="utf-8",
    )
    assert "RSK008" in _rule_ids(check_repo(root, RULES))


def test_missing_uv_lock_reports_rsk009(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "uv.lock").unlink()
    assert "RSK009" in _rule_ids(check_repo(root, RULES))


def test_missing_line_length_reports_rsk010(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    pyproject_path.write_text(
        text.replace(f"line-length = {RULES.ruff_recommended_line_length}\n", ""),
        encoding="utf-8",
    )
    assert "RSK010" in _rule_ids(check_repo(root, RULES))


def test_different_but_declared_line_length_does_not_report_rsk010(
    tmp_path: Path,
) -> None:
    """§13: the value is a per-repository choice; only its absence is a shall."""
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    pyproject_path.write_text(
        text.replace(
            f"line-length = {RULES.ruff_recommended_line_length}", "line-length = 79"
        ),
        encoding="utf-8",
    )
    assert "RSK010" not in _rule_ids(check_repo(root, RULES))


def test_dropped_mandatory_rule_family_reports_rsk010(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    select = ", ".join(
        f'"{s}"'
        for s in (*RULES.ruff_mandatory_select[1:], *RULES.ruff_recommended_select)
    )
    pyproject_path.write_text(
        text.split("[tool.ruff.lint]")[0] + f"[tool.ruff.lint]\nselect = [{select}]\n",
        encoding="utf-8",
    )
    assert "RSK010" in _rule_ids(check_repo(root, RULES))


def test_non_recommended_line_length_reports_rsk015_as_should(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    pyproject_path.write_text(
        text.replace(
            f"line-length = {RULES.ruff_recommended_line_length}", "line-length = 100"
        ),
        encoding="utf-8",
    )
    findings = [f for f in check_repo(root, RULES) if f.rule_id == "RSK015"]
    assert len(findings) == 1
    assert findings[0].severity == "should"


def test_dropped_recommended_rule_family_reports_rsk016_as_should(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    select = ", ".join(f'"{s}"' for s in RULES.ruff_mandatory_select)
    pyproject_path.write_text(
        text.split("[tool.ruff.lint]")[0] + f"[tool.ruff.lint]\nselect = [{select}]\n",
        encoding="utf-8",
    )
    findings = [f for f in check_repo(root, RULES) if f.rule_id == "RSK016"]
    assert len(findings) == 1
    assert findings[0].severity == "should"


def test_unresolved_placeholder_reports_rsk011(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "NOTES.md").write_text("leftover __REPO_NAME__ token\n", encoding="utf-8")
    findings = check_repo(root, RULES)
    assert "RSK011" in _rule_ids(findings)
    [finding] = [f for f in findings if f.rule_id == "RSK011"]
    assert finding.path == "NOTES.md"


def test_unrelated_dunder_constant_does_not_report_rsk011(tmp_path: Path) -> None:
    """RSK011 matches repo_init.py's known placeholder vocabulary, not any
    dunder-shaped token.

    A pilot run against a real repository (wombat_configs) flagged its own
    `__PDC_GENERATED_NAME__` sentinel constant as an "unresolved placeholder"
    — a false positive, since that token has nothing to do with this
    standard's bootstrap templating.
    """
    root = _minimal_repo(tmp_path)
    (root / "NOTES.md").write_text(
        'SENTINEL = "__PDC_GENERATED_NAME__"\n', encoding="utf-8"
    )
    assert "RSK011" not in _rule_ids(check_repo(root, RULES))


def test_missing_adr_dir_reports_rsk012_as_should(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "docs" / "adr").rmdir()
    findings = [f for f in check_repo(root, RULES) if f.rule_id == "RSK012"]
    assert len(findings) == 1
    assert findings[0].severity == "should"


def test_platform_check_excluded_by_default(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    findings = check_repo(root, RULES, include_platform=False)
    assert "RSK014" not in _rule_ids(findings)


def test_platform_check_included_with_flag_reports_something(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    findings = check_repo(root, RULES, include_platform=True)
    assert "RSK014" in _rule_ids(findings)


# --- the dogfood tests -------------------------------------------------


@pytest.mark.parametrize("profile", STARTER_KIT_PROFILES)
def test_generated_repos_pass_their_own_compliance_check(
    profile: str, tmp_path: Path
) -> None:
    """The highest-value test: repo-init cannot generate a repo repo-check rejects."""
    output_dir = tmp_path / "generated"
    bootstrap_repo(
        profile=profile,
        repo_name="generated",
        package_name=None,
        description="Generated repo",
        repo_type="service",
        python_version="3.12",
        author="",
        output_dir=output_dir,
        no_install=True,
    )
    # `no_install=True` skips `uv sync`, which normally creates uv.lock, so
    # tests avoid a real network call the way the rest of this suite does.
    (output_dir / "uv.lock").write_text("", encoding="utf-8")

    findings = check_repo(output_dir, RULES)
    shall_findings = [f for f in findings if f.severity == "shall"]
    assert shall_findings == []


def test_repo_root_has_no_unexpected_shall_findings() -> None:
    """repo-standard-kit checks itself, modulo the rules that cannot apply to it.

    RSK005 and RSK011 are structurally inapplicable to the standard's own
    repository; see SELF_APPLICATION_EXCEPTIONS.
    """
    findings = check_repo(REPO_ROOT, RULES)
    unexpected = [
        f
        for f in findings
        if f.severity == "shall" and f.rule_id not in SELF_APPLICATION_EXCEPTIONS
    ]
    assert unexpected == []


def test_rules_json_matches_generated_output() -> None:
    """§6 Generated Artifact Consistency: rules.json must match its sources."""
    regenerated = build_rules(REPO_ROOT)
    committed = load_rules()
    assert regenerated == committed, (
        f"{RULES_JSON_PATH} is stale; run `uv run python scripts/generate_rules.py` "
        "and commit the result."
    )


# --- CLI --------------------------------------------------------------


def test_cli_reports_shall_findings_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "empty-repo"
    root.mkdir()
    exit_code = cli.main([str(root)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "RSK001" in captured.out


def test_cli_exits_zero_for_a_compliant_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _minimal_repo(tmp_path)
    exit_code = cli.main([str(root)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "no findings" in captured.out


def test_cli_json_format_is_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "empty-repo"
    root.mkdir()
    cli.main([str(root), "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert any(item["rule_id"] == "RSK001" for item in payload)


def test_cli_strict_mode_fails_on_should_findings(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "docs" / "adr").rmdir()
    assert cli.main([str(root)]) == 0
    assert cli.main([str(root), "--strict"]) == 1


def test_repo_check_console_script_runs_end_to_end(tmp_path: Path) -> None:
    root = tmp_path / "empty-repo"
    root.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "repo_standard.compliance.cli", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "RSK001" in result.stdout


# --- consumption surfaces -----------------------------------------------


def test_pre_commit_hooks_manifest_declares_repo_check() -> None:
    manifest = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    )
    [hook] = manifest
    assert hook["id"] == "repo-check"
    assert hook["entry"] == "repo-check"
    assert hook["language"] == "python"
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True


def test_compliance_workflow_is_reusable_and_pinned_to_setup_uv() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "compliance.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    # PyYAML parses the bare `on:` key as boolean True.
    assert "workflow_call" in workflow[True]
    assert workflow["permissions"] == {"contents": "read"}

    # `ref` must be required, with no default: a called reusable workflow has
    # no reliable way to read its own `uses: ...@ref` pin from the inside, so
    # the caller states it explicitly instead of this workflow guessing.
    ref_input = workflow[True]["workflow_call"]["inputs"]["ref"]
    assert ref_input["required"] is True
    assert "default" not in ref_input

    text = workflow_path.read_text(encoding="utf-8")
    assert "astral-sh/setup-uv@v5" in text
    assert "actions/checkout@v5" in text
    assert (
        "git+https://github.com/FP-DevTools/repo-standard-kit.git@${{ inputs.ref }}"
        in text
    )
