"""Policy schema, structural checker, profile, output, and dogfood tests."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, dump_yaml, load_yaml

from repo_standard.compliance import checks, cli
from repo_standard.compliance.checks import (
    CHECK_HANDLERS,
    Finding,
    check_repo,
    load_policy,
    resolve_profile,
)
from repo_standard.policy import (
    PolicyError,
    Shape,
    load_compiled_policy,
    load_source_policy,
)
from repo_standard.policy.compiler import render_compiled, render_reference
from repo_standard.policy.models import CHECK_SCHEMAS
from repo_standard.repo_init import bootstrap_repo

POLICY = load_policy()
STARTER_KIT_PROFILES = POLICY.profile_ids


def _rule_ids(findings: list[Finding]) -> set[str]:
    return {finding.rule_id for finding in findings}


def _write_pre_commit(root: Path, hooks: list[dict[str, object]]) -> None:
    data = {"repos": [{"repo": "local", "hooks": hooks}]}
    (root / ".pre-commit-config.yaml").write_text(dump_yaml(data), encoding="utf-8")


def _workflow_text(profile: str = "python-single") -> str:
    commands = POLICY.rule("RSK006").check.config["commands_by_profile"][profile]
    steps = "\n".join(f"      - run: {command}" for command in commands)
    return (
        "name: Quality\n"
        "on:\n"
        "  pull_request:\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"{steps}\n"
    )


def _shape(rule_id: str) -> Shape:
    return POLICY.shape(POLICY.rule(rule_id).check.config["shape"])


def _markdown_shaped(title: str, body: str = "Detail.") -> str:
    """Render a document carrying exactly the required sections of a shape."""
    sections = "\n\n".join(
        f"## {heading}\n\n{body}" for heading in _shape(title).required
    )
    return sections


def _minimal_repo(tmp_path: Path, profile: str = "python-single") -> Path:
    root = tmp_path / "compliant-repo"
    root.mkdir()
    headings = _shape("RSK002").required
    gate_chain = "\n".join(
        f"{index}. `{command}`"
        for index, command in enumerate(
            POLICY.rule("RSK003").check.config["commands_by_profile"][profile], 1
        )
    )
    dials_config = POLICY.rule("RSK026").check.config
    dial_block = "\n".join(
        f"- **{dial['label']}:** {dial['level']} / {dial['scale']}"
        for dial in dials_config["dials"]
    )
    bodies = {"Quality Gates": gate_chain, dials_config["section"]: dial_block}
    agents_sections = "\n\n".join(
        f"## {heading}\n\n{bodies.get(heading, 'Detail.')}" for heading in headings
    )
    (root / "AGENTS.md").write_text(
        f"# AGENTS.md\n\n{agents_sections}\n\nSee repo-standard-kit.\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# Repository\n\nSee repo-standard-kit.\n\n{_markdown_shaped('RSK023')}\n",
        encoding="utf-8",
    )
    workflow = root / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "quality.yml").write_text(_workflow_text(profile), encoding="utf-8")
    hooks = [dict(hook) for hook in POLICY.rule("RSK007").check.config["hooks"]]
    for hook in hooks:
        hook["language"] = "system"
    _write_pre_commit(root, hooks)
    select = [
        *POLICY.rule("RSK010").check.config["required_select"],
        *POLICY.rule("RSK016").check.config["values"],
    ]
    build = (
        "[build-system]\n"
        'requires = ["uv_build>=0.11.20,<0.12"]\n'
        'build-backend = "uv_build"\n\n'
        if profile == "python-single"
        else "[tool.uv]\npackage = false\n\n"
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "compliant-repo"\n'
        'version = "0.1.0"\n\n'
        f"{build}"
        "[tool.repo-standard]\n"
        f'profile = "{profile}"\n'
        f'standard = "{POLICY.standard_major}"\n\n'
        "[tool.ruff]\n"
        f"line-length = {POLICY.rule('RSK015').check.config['value']}\n\n"
        "[tool.ruff.lint]\n"
        f"select = {json.dumps(select)}\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("", encoding="utf-8")
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n{_markdown_shaped('RSK024')}\n", encoding="utf-8"
    )
    (root / "LICENSE").write_text("Proprietary.\n", encoding="utf-8")
    return root


def _load_pre_commit(root: Path) -> list[dict[str, object]]:
    data = load_yaml((root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return data["repos"][0]["hooks"]


def _policy_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "policy-checkout"
    shutil.copytree(REPO_ROOT / "policy", root / "policy")
    shutil.copytree(REPO_ROOT / "docs", root / "docs")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "policy-test"\nversion = "{POLICY.standard_version}"\n',
        encoding="utf-8",
    )
    return root


def _mutate_base(root: Path, mutation: Callable[[dict[str, object]], None]) -> None:
    base = root / "policy" / "base.yaml"
    data = load_yaml(base.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    mutation(data)
    base.write_text(dump_yaml(data), encoding="utf-8")


# --- strict policy schema and generation ---------------------------------


def test_source_policy_is_valid() -> None:
    assert load_source_policy(REPO_ROOT) == load_compiled_policy()


def test_v04_rule_ids_and_retired_gap_are_preserved_during_cutover() -> None:
    prior = tuple(
        [*(f"RSK{number:03d}" for number in range(1, 13)), "RSK014"]
        + [f"RSK{number:03d}" for number in range(15, 19)]
    )
    assert POLICY.rule_ids[: len(prior)] == prior
    assert POLICY.retired_rule_ids == ("RSK013",)


def test_malformed_policy_yaml_reports_location(tmp_path: Path) -> None:
    root = _policy_checkout(tmp_path)
    (root / "policy" / "base.yaml").write_text("rules: [\n", encoding="utf-8")
    with pytest.raises(PolicyError, match=r":2:1: malformed YAML"):
        load_source_policy(root)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update({"surprise": True}), "unknown keys"),
        (lambda data: data.update({"schema_version": "1"}), "expected an integer"),
        (
            lambda data: data["rules"].append(dict(data["rules"][0])),
            "duplicate rule IDs",
        ),
        (
            lambda data: data["rules"].__setitem__(
                slice(0, 2), list(reversed(data["rules"][:2]))
            ),
            "numerically ordered",
        ),
        (
            lambda data: data["rules"][0].update({"profiles": ["unknown"]}),
            "unknown profiles",
        ),
        (
            lambda data: data["rules"][0]["source"].update({"section": "Missing"}),
            "does not exist",
        ),
        (
            lambda data: data["rules"][0]["check"].update({"kind": "unregistered"}),
            "unregistered check kind",
        ),
    ],
)
def test_invalid_policy_is_rejected(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    root = _policy_checkout(tmp_path)
    _mutate_base(root, mutation)
    with pytest.raises(PolicyError, match=message):
        load_source_policy(root)


def test_generated_policy_artifacts_are_current_and_deterministic() -> None:
    source = load_source_policy(REPO_ROOT)
    expected_json = render_compiled(source)
    assert (REPO_ROOT / "src" / "repo_standard" / "policy" / "compiled.json").read_text(
        encoding="utf-8"
    ) == expected_json
    assert (REPO_ROOT / "docs" / "policy-reference.md").read_text(
        encoding="utf-8"
    ) == render_reference(source)


def test_quality_gates_uses_the_shared_normative_vocabulary() -> None:
    text = (REPO_ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
    assert "This document is part of the normative repository standard." in text
    assert "it is not parsed to derive executable policy." in text
    obsolete_wording = (
        "This is a specification, not guidance",
        "written differently from the rest of `docs/`",
        "are guidance and use plain imperative voice instead",
        "quality-gates is the only specification",
    )
    assert not any(phrase in text for phrase in obsolete_wording)


def test_every_typed_check_kind_has_exactly_one_runtime_handler() -> None:
    assert set(CHECK_SCHEMAS) == set(CHECK_HANDLERS)


def test_rsk003_reuses_the_workflow_quality_commands() -> None:
    rule = POLICY.rule("RSK003")
    assert rule.check.kind == "agents_quality_commands"
    assert CHECK_SCHEMAS["agents_quality_commands"] == (
        {"path", "commands_by_profile"},
        set(),
    )
    assert (
        rule.check.config["commands_by_profile"]
        == POLICY.rule("RSK006").check.config["commands_by_profile"]
    )


def test_rsk021_policy_is_workflow_scoped() -> None:
    assert POLICY.rule("RSK021").check.config == {
        "path": ".github/workflows/quality.yml"
    }
    assert CHECK_SCHEMAS["github_workflow_pins"] == ({"path"}, set())


def test_rsk020_policy_defines_exact_effective_permissions() -> None:
    assert POLICY.rule("RSK020").check.config == {
        "path": ".github/workflows/quality.yml",
        "job": "quality",
        "permissions": {"contents": "read"},
    }
    assert CHECK_SCHEMAS["github_workflow_permissions"] == (
        {"path", "job", "permissions"},
        set(),
    )


@pytest.mark.parametrize(
    ("permissions", "message"),
    [
        ("read-all", "expected a mapping with string keys"),
        ({}, "expected a non-empty mapping"),
        ({"contents": "execute"}, "unsupported permission value"),
    ],
)
def test_invalid_rsk020_policy_permissions_are_rejected(
    tmp_path: Path, permissions: object, message: str
) -> None:
    root = _policy_checkout(tmp_path)

    def mutation(data: dict[str, object]) -> None:
        rules = data["rules"]
        assert isinstance(rules, list)
        rule = next(item for item in rules if item["id"] == "RSK020")
        rule["check"]["config"]["permissions"] = permissions

    _mutate_base(root, mutation)
    with pytest.raises(PolicyError, match=message):
        load_source_policy(root)


def test_rsk014_policy_represents_every_required_protection_property() -> None:
    assert POLICY.rule("RSK014").check.config == {
        "branch": "main",
        "required_status_checks": ["quality", "compliance"],
        "minimum_reviews": 0,
        "dismiss_stale_approvals": True,
        "require_up_to_date": True,
        "require_conversation_resolution": True,
        "enforce_admins": True,
    }


def test_rsk022_recommends_one_approving_review() -> None:
    rule = POLICY.rule("RSK022")
    assert rule.level == "recommended"
    assert rule.check.config == {"branch": "main", "minimum_reviews": 1}
    assert CHECK_SCHEMAS["branch_protection_minimum_reviews"] == (
        {"branch", "minimum_reviews"},
        set(),
    )


def test_negative_minimum_review_policy_is_rejected(tmp_path: Path) -> None:
    root = _policy_checkout(tmp_path)

    def mutation(data: dict[str, object]) -> None:
        rules = data["rules"]
        assert isinstance(rules, list)
        rule = next(item for item in rules if item["id"] == "RSK022")
        rule["check"]["config"]["minimum_reviews"] = -1

    _mutate_base(root, mutation)
    with pytest.raises(PolicyError, match="expected a non-negative integer"):
        load_source_policy(root)


def test_standard_package_version_and_source_distribution_inputs_agree() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    assert pyproject["project"]["version"] == POLICY.standard_version
    includes = pyproject["tool"]["uv"]["build-backend"]["source-include"]
    assert "policy/**" in includes
    assert "docs/**" in includes
    assert (REPO_ROOT / "src" / "repo_standard" / "policy" / "compiled.json").is_file()


# --- base rules and actionable findings ----------------------------------


@pytest.mark.parametrize("profile", STARTER_KIT_PROFILES)
def test_minimal_repo_has_no_findings(profile: str, tmp_path: Path) -> None:
    assert check_repo(_minimal_repo(tmp_path, profile), POLICY) == []


@pytest.mark.parametrize(
    ("profile", "incorrect", "expected"),
    [
        ("python-workspace", "uv build --all-packages", "uv build"),
        ("python-single", "uv build", "uv build --all-packages"),
    ],
)
def test_rsk003_rejects_the_other_profiles_build_command(
    tmp_path: Path, profile: str, incorrect: str, expected: str
) -> None:
    root = _minimal_repo(tmp_path, profile)
    path = root / "AGENTS.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f"4. `{incorrect}`", f"4. `{expected}`"
        ),
        encoding="utf-8",
    )
    assert "RSK003" in _rule_ids(check_repo(root, POLICY))


def test_rsk003_rejects_commands_in_the_wrong_order(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "1. `uv sync --locked`\n2. `uv run pre-commit run --all-files`",
        "1. `uv run pre-commit run --all-files`\n2. `uv sync --locked`",
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK003" in _rule_ids(check_repo(root, POLICY))


def test_rsk003_ignores_required_commands_outside_quality_gates(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("4. `uv build`\n\n## Coding Standards", "## Coding Standards")
    text += "\nThe build command is `uv build`.\n"
    path.write_text(text, encoding="utf-8")
    assert "RSK003" in _rule_ids(check_repo(root, POLICY))


def test_rsk003_ignores_unrelated_quality_gate_prose(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8").replace(
        "## Quality Gates\n\n",
        "## Quality Gates\n\nRun these commands from the repository root.\n\n",
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK003" not in _rule_ids(check_repo(root, POLICY))


def test_rsk026_rejects_a_dial_stated_at_the_wrong_level(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8").replace(
        "**Verbosity:** 2 / 5", "**Verbosity:** 4 / 5"
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK026" in _rule_ids(check_repo(root, POLICY))


def test_rsk026_rejects_dials_stated_out_of_order(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    first, second = (
        f"- **{dial['label']}:** {dial['level']} / {dial['scale']}"
        for dial in POLICY.rule("RSK026").check.config["dials"]
    )
    text = text.replace(f"{first}\n{second}", f"{second}\n{first}")
    path.write_text(text, encoding="utf-8")
    assert "RSK026" in _rule_ids(check_repo(root, POLICY))


def test_rsk026_rejects_a_section_that_states_no_dial(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = re.sub(
        r"^- \*\*[^*]+\*\* \d+ / \d+$",
        "Be brief and be precise.",
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK026" in _rule_ids(check_repo(root, POLICY))


def test_rsk026_ignores_dials_stated_outside_the_section(tmp_path: Path) -> None:
    """The section is the contract; a matching line elsewhere is just prose."""
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8").replace("- **Verbosity:** 2 / 5\n", "", 1)
    path.write_text(f"{text}\n- **Verbosity:** 2 / 5\n", encoding="utf-8")
    assert "RSK026" in _rule_ids(check_repo(root, POLICY))


def test_rsk026_ignores_unrelated_operating_mode_prose(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    section = POLICY.rule("RSK026").check.config["section"]
    text = path.read_text(encoding="utf-8").replace(
        f"## {section}\n\n",
        f"## {section}\n\nEach dial runs from 1 to 5.\n\n",
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK026" not in _rule_ids(check_repo(root, POLICY))


def test_no_hand_maintained_document_restates_the_dial_levels() -> None:
    """`docs/` points at the published levels; only the generator writes them.

    `CHANGELOG.md` is exempt by nature: a release entry records what a release
    did and must not change when policy later does.
    """
    generated = {REPO_ROOT / "docs" / "policy-reference.md"}
    dials = POLICY.rule("RSK026").check.config["dials"]
    for path in sorted((REPO_ROOT / "docs").rglob("*.md")):
        if path in generated:
            continue
        text = path.read_text(encoding="utf-8")
        restated = [
            dial["label"]
            for dial in dials
            if f"{dial['level']} / {dial['scale']}" in text
        ]
        assert not restated, (
            f"{path.name} restates the levels for {restated}; link to "
            "docs/policy-reference.md instead"
        )


def test_rsk026_declares_unique_valid_dials() -> None:
    """The model owns dial values; the rule declares only their structure."""
    rule = POLICY.rule("RSK026")
    assert rule.level == "required"
    dials = rule.check.config["dials"]
    assert dials
    assert len({dial["label"] for dial in dials}) == len(dials)
    assert all(1 <= dial["level"] <= dial["scale"] for dial in dials)


@pytest.mark.parametrize(
    ("relative", "rule_id"),
    [
        ("AGENTS.md", "RSK001"),
        ("README.md", "RSK004"),
        ("uv.lock", "RSK009"),
        ("CHANGELOG.md", "RSK017"),
        ("LICENSE", "RSK018"),
    ],
)
def test_missing_policy_owned_path_reports_rule(
    tmp_path: Path, relative: str, rule_id: str
) -> None:
    root = _minimal_repo(tmp_path)
    (root / relative).unlink()
    assert rule_id in _rule_ids(check_repo(root, POLICY))


def test_finding_contains_actionable_contract_fields(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "README.md").unlink()
    finding = next(f for f in check_repo(root, POLICY) if f.rule_id == "RSK004")
    assert finding.title
    assert finding.level == "required"
    assert finding.severity == "shall"
    assert finding.actual == "missing"
    assert finding.expected == "file"
    assert finding.remediation


def test_non_uv_build_backend_is_a_strict_only_recommendation(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = text.replace(
        'requires = ["uv_build>=0.11.20,<0.12"]',
        'requires = ["hatchling>=1.27"]',
    ).replace('build-backend = "uv_build"', 'build-backend = "hatchling.build"')
    pyproject.write_text(text, encoding="utf-8")

    finding = next(
        finding for finding in check_repo(root, POLICY) if finding.rule_id == "RSK008"
    )
    assert finding.level == "recommended"
    assert finding.severity == "should"
    assert cli.main([str(root)]) == 0
    assert cli.main([str(root), "--strict"]) == 1


# --- GitHub workflow structure, commands, permissions, and pins -----------


def test_github_loader_preserves_on_and_valid_workflow_passes(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    assert not _rule_ids(check_repo(root, POLICY)) & {"RSK006", "RSK020", "RSK021"}


@pytest.mark.parametrize(
    "replacement",
    [
        "# uv sync --locked",
        "echo 'uv sync --locked'",
        "bash -c 'uv sync --locked'",
    ],
)
def test_comments_echo_and_shell_wrappers_do_not_count_as_commands(
    tmp_path: Path, replacement: str
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "run: uv sync --locked", f"run: {replacement}"
        ),
        encoding="utf-8",
    )
    assert "RSK006" in _rule_ids(check_repo(root, POLICY))


def test_unrelated_workflow_fields_do_not_count_as_commands(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    text = path.read_text(encoding="utf-8").replace(
        "      - run: uv build", "      - name: uv build\n        run: echo build"
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK006" in _rule_ids(check_repo(root, POLICY))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda text: text.replace("  pull_request:\n", "  workflow_dispatch:\n"),
        lambda text: text.replace("  quality:\n", "  other:\n"),
        lambda text: text.replace("    steps:\n", "    no_steps: true\n"),
    ],
)
def test_missing_trigger_job_or_steps_reports_rsk006(
    tmp_path: Path, mutation: Callable[[str], str]
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    path.write_text(mutation(path.read_text(encoding="utf-8")), encoding="utf-8")
    assert "RSK006" in _rule_ids(check_repo(root, POLICY))


def test_malformed_workflow_reports_yaml_line(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    path.write_text("name: [\n", encoding="utf-8")
    finding = next(f for f in check_repo(root, POLICY) if f.rule_id == "RSK006")
    assert finding.line == 2
    assert "Could not parse YAML" in finding.message


def test_multiline_complete_command_is_accepted(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    text = path.read_text(encoding="utf-8").replace(
        "      - run: uv sync --locked",
        "      - run: |\n          uv sync \\\n            --locked # reproducible",
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK006" not in _rule_ids(check_repo(root, POLICY))


def test_exact_job_permissions_override_broader_workflow_permissions(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    text = (
        path.read_text(encoding="utf-8")
        .replace(
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: write\n",
        )
        .replace(
            "  quality:\n    runs-on:",
            "  quality:\n    permissions:\n      contents: read\n    runs-on:",
        )
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK020" not in _rule_ids(check_repo(root, POLICY))


@pytest.mark.parametrize(
    ("mutation", "actual"),
    [
        (
            lambda text: text.replace(
                "permissions:\n  contents: read\n", "permissions: read-all\n"
            ),
            "read-all",
        ),
        (
            lambda text: text.replace(
                "  contents: read", "  contents: read\n  issues: read"
            ),
            {"contents": "read", "issues": "read"},
        ),
        (
            lambda text: text.replace("  contents: read", "  contents: write"),
            {"contents": "write"},
        ),
        (
            lambda text: text.replace("permissions:\n  contents: read\n", ""),
            None,
        ),
        (
            lambda text: text.replace(
                "  quality:\n    runs-on:",
                "  quality:\n"
                "    permissions:\n"
                "      contents: read\n"
                "      pull-requests: read\n"
                "    runs-on:",
            ),
            {"contents": "read", "pull-requests": "read"},
        ),
    ],
)
def test_nonminimal_effective_permissions_report_rsk020(
    tmp_path: Path, mutation: Callable[[str], str], actual: object
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    path.write_text(mutation(path.read_text(encoding="utf-8")), encoding="utf-8")
    finding = next(f for f in check_repo(root, POLICY) if f.rule_id == "RSK020")
    assert finding.message == (
        "Quality job permissions do not match the least-privilege policy."
    )
    assert finding.actual == actual
    assert finding.expected == {"contents": "read"}
    assert finding.remediation == (
        "Set the quality job's effective permissions to exactly `contents: read`."
    )


def test_mutable_remote_action_reports_rsk021_at_node_line(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    text = path.read_text(encoding="utf-8").replace(
        "    steps:\n", "    steps:\n      - uses: actions/checkout@v5\n"
    )
    path.write_text(text, encoding="utf-8")
    finding = next(f for f in check_repo(root, POLICY) if f.rule_id == "RSK021")
    assert finding.actual == "actions/checkout@v5"
    assert finding.line is not None


def test_sha_local_and_docker_action_references_are_accepted(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    sha = "a" * 40
    text = path.read_text(encoding="utf-8").replace(
        "    steps:\n",
        "    steps:\n"
        f"      - uses: actions/checkout@{sha}\n"
        "      - uses: ./local-action\n"
        "      - uses: docker://alpine:3.22\n",
    )
    path.write_text(text, encoding="utf-8")
    assert "RSK021" not in _rule_ids(check_repo(root, POLICY))


def test_rsk021_scans_every_job_in_the_quality_workflow(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    sha = "b" * 40
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            "  auxiliary:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: owner/tool@main\n"
        )
    assert "RSK021" in _rule_ids(check_repo(root, POLICY))
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "owner/tool@main", f"owner/tool@{sha}"
        ),
        encoding="utf-8",
    )
    assert "RSK021" not in _rule_ids(check_repo(root, POLICY))


# --- pre-commit structure -------------------------------------------------


def test_comment_text_does_not_count_as_pre_commit_hook(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    hooks = _load_pre_commit(root)
    hooks.pop(0)
    _write_pre_commit(root, hooks)
    with (root / ".pre-commit-config.yaml").open("a", encoding="utf-8") as stream:
        stream.write("# id: check-yaml, entry: uv run check-yaml\n")
    assert "RSK007" in _rule_ids(check_repo(root, POLICY))


@pytest.mark.parametrize(
    ("hook_index", "mutate"),
    [
        (8, lambda hook: hook.update({"id": "wrong-hook"})),
        (8, lambda hook: hook.update({"args": []})),
        (11, lambda hook: hook.update({"pass_filenames": True})),
        (0, lambda hook: hook.update({"types": ["text"]})),
    ],
)
def test_wrong_hook_or_material_fields_report_rsk007(
    tmp_path: Path,
    hook_index: int,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    root = _minimal_repo(tmp_path)
    hooks = _load_pre_commit(root)
    mutate(hooks[hook_index])
    _write_pre_commit(root, hooks)
    assert "RSK007" in _rule_ids(check_repo(root, POLICY))


def test_equivalent_yaml_forms_and_filter_order_are_accepted(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    hooks = _load_pre_commit(root)
    hooks[8]["args"] = "--maxkb=1024"
    hooks[9]["types_or"] = ["pyi", "python"]
    _write_pre_commit(root, hooks)
    assert "RSK007" not in _rule_ids(check_repo(root, POLICY))


# --- operational profiles and RSK019 -------------------------------------


def test_profile_resolution_precedence(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path, "python-single")
    (root / "packages").mkdir()
    assert resolve_profile(root, POLICY) == "python-single"
    assert resolve_profile(root, POLICY, "python-workspace") == "python-workspace"


def test_profile_falls_back_to_detection_when_metadata_missing(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path, "python-workspace")
    (root / "packages").mkdir()
    path = root / "pyproject.toml"
    path.write_text(
        path.read_text(encoding="utf-8").split("[tool.repo-standard]")[0],
        encoding="utf-8",
    )
    assert resolve_profile(root, POLICY) == "python-workspace"
    assert "RSK019" in _rule_ids(check_repo(root, POLICY))


def test_unknown_profile_override_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        resolve_profile(_minimal_repo(tmp_path), POLICY, "unknown")


def test_standard_version_mismatch_reports_rsk019_but_other_checks_run(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "pyproject.toml"
    current = f'standard = "{POLICY.standard_major}"'
    other = f'standard = "{int(POLICY.standard_major) + 1}"'
    path.write_text(
        path.read_text(encoding="utf-8").replace(current, other), encoding="utf-8"
    )
    (root / "README.md").unlink()
    ids = _rule_ids(check_repo(root, POLICY))
    assert {"RSK019", "RSK004"} <= ids


def test_rule_applicability_filters_by_resolved_profile(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path, "python-single")
    (root / "docs" / "adr").rmdir()
    rule = POLICY.rule("RSK012")
    single_excluded = replace(rule, profiles=("python-workspace",))
    filtered = replace(
        POLICY,
        rules=tuple(
            single_excluded if item.id == rule.id else item for item in POLICY.rules
        ),
    )
    assert "RSK012" not in _rule_ids(check_repo(root, filtered))


# --- exceptions, output, command errors, and dogfood ---------------------


def _compliant_branch_protection() -> dict[str, object]:
    return {
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
        },
        "required_status_checks": {
            "contexts": ["quality", "compliance"],
            "strict": True,
        },
        "required_conversation_resolution": {"enabled": True},
        "enforce_admins": {"enabled": True},
    }


def _mock_branch_protection_query(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> None:
    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(
                command, 0, "https://github.com/org/repo.git\n", ""
            )
        assert command[:2] == ["gh", "api"]
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(checks.subprocess, "run", fake_run)


def _compliant_ruleset_rules(
    *, source_type: str = "Repository", source: str = "org/repo"
) -> list[dict[str, Any]]:
    metadata = {
        "ruleset_source_type": source_type,
        "ruleset_source": source,
        "ruleset_id": 42,
    }
    return [
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": True,
                "required_review_thread_resolution": True,
            },
            **metadata,
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": "quality"},
                    {"context": "compliance"},
                ],
            },
            **metadata,
        },
    ]


def _mock_ruleset_queries(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rules: list[dict[str, Any]] | None = None,
    bypass_actors: list[dict[str, Any]] | None = None,
    rules_stdout: str | None = None,
    rules_stderr: str = "",
    rules_returncode: int = 0,
    detail_stdout: str | None = None,
    detail_stderr: str = "",
    detail_returncode: int = 0,
) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(
                command, 0, "https://github.com/org/repo.git\n", ""
            )
        assert command[:2] == ["gh", "api"]
        endpoint = command[-1]
        if endpoint.endswith("/branches/main/protection"):
            return subprocess.CompletedProcess(
                command, 1, "", "gh: Branch not protected (HTTP 404)"
            )
        if "/rules/branches/main" in endpoint:
            stdout = (
                rules_stdout
                if rules_stdout is not None
                else json.dumps([rules if rules is not None else []])
            )
            return subprocess.CompletedProcess(
                command, rules_returncode, stdout, rules_stderr
            )
        assert "/rulesets/42" in endpoint
        stdout = (
            detail_stdout
            if detail_stdout is not None
            else json.dumps(
                {"bypass_actors": bypass_actors if bypass_actors is not None else []}
            )
        )
        return subprocess.CompletedProcess(
            command, detail_returncode, stdout, detail_stderr
        )

    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    return calls


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda response: response.update({"required_pull_request_reviews": None}),
            "main does not require pull requests.",
        ),
        (
            lambda response: response["required_pull_request_reviews"].update(
                {"dismiss_stale_reviews": False}
            ),
            "main does not dismiss stale approvals.",
        ),
        (
            lambda response: response["required_status_checks"].update(
                {"contexts": ["compliance"]}
            ),
            "main omits required status checks: quality.",
        ),
        (
            lambda response: response["required_status_checks"].update(
                {"contexts": ["quality"]}
            ),
            "main omits required status checks: compliance.",
        ),
        (
            lambda response: response["required_status_checks"].update(
                {"strict": False}
            ),
            "main does not require branches to be up to date.",
        ),
        (
            lambda response: response["required_conversation_resolution"].update(
                {"enabled": False}
            ),
            "main does not require conversation resolution.",
        ),
        (
            lambda response: response["enforce_admins"].update({"enabled": False}),
            "main allows administrator bypass.",
        ),
    ],
)
def test_each_required_branch_protection_property_is_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    root = _minimal_repo(tmp_path)
    response = _compliant_branch_protection()
    mutate(response)
    _mock_branch_protection_query(monkeypatch, stdout=json.dumps(response))
    findings = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert [finding.message for finding in findings] == [message]
    assert findings[0].status == "violation"


def test_fully_compliant_branch_protection_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_branch_protection_query(
        monkeypatch, stdout=json.dumps(_compliant_branch_protection())
    )
    rule_ids = _rule_ids(check_repo(root, POLICY, include_platform=True))
    assert "RSK014" not in rule_ids
    assert "RSK022" not in rule_ids


def test_zero_approvals_passes_required_policy_but_reports_recommendation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    response = _compliant_branch_protection()
    reviews = response["required_pull_request_reviews"]
    assert isinstance(reviews, dict)
    reviews["required_approving_review_count"] = 0
    _mock_branch_protection_query(monkeypatch, stdout=json.dumps(response))
    findings = check_repo(root, POLICY, include_platform=True)
    assert not any(finding.rule_id == "RSK014" for finding in findings)
    [finding] = [finding for finding in findings if finding.rule_id == "RSK022"]
    assert finding.level == "recommended"
    assert finding.severity == "should"
    assert finding.status == "violation"
    assert finding.message == "main requires too few approving reviews."


def test_fully_compliant_repository_ruleset_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    calls = _mock_ruleset_queries(monkeypatch, rules=_compliant_ruleset_rules())
    rule_ids = _rule_ids(check_repo(root, POLICY, include_platform=True))
    assert "RSK014" not in rule_ids
    assert "RSK022" not in rule_ids
    assert ["gh", "api", "--paginate", "--slurp"] == calls[2][:4]
    assert calls[3][-1] == "repos/org/repo/rulesets/42"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda rules: rules[0]["parameters"].update(
                {"dismiss_stale_reviews_on_push": False}
            ),
            "main does not dismiss stale approvals.",
        ),
        (
            lambda rules: rules[1]["parameters"].update(
                {"required_status_checks": [{"context": "compliance"}]}
            ),
            "main omits required status checks: quality.",
        ),
        (
            lambda rules: rules[1]["parameters"].update(
                {"required_status_checks": [{"context": "quality"}]}
            ),
            "main omits required status checks: compliance.",
        ),
        (
            lambda rules: rules[1]["parameters"].update(
                {"strict_required_status_checks_policy": False}
            ),
            "main does not require branches to be up to date.",
        ),
        (
            lambda rules: rules[0]["parameters"].update(
                {"required_review_thread_resolution": False}
            ),
            "main does not require conversation resolution.",
        ),
    ],
)
def test_each_required_ruleset_property_is_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[list[dict[str, Any]]], None],
    message: str,
) -> None:
    root = _minimal_repo(tmp_path)
    rules = _compliant_ruleset_rules()
    mutate(rules)
    _mock_ruleset_queries(monkeypatch, rules=rules)
    findings = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert [finding.message for finding in findings] == [message]
    assert findings[0].status == "violation"


def test_zero_approval_ruleset_passes_rsk014_but_reports_rsk022(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    rules = _compliant_ruleset_rules()
    rules[0]["parameters"]["required_approving_review_count"] = 0
    _mock_ruleset_queries(monkeypatch, rules=rules)
    findings = check_repo(root, POLICY, include_platform=True)
    assert not any(finding.rule_id == "RSK014" for finding in findings)
    [finding] = [finding for finding in findings if finding.rule_id == "RSK022"]
    assert finding.level == "recommended"
    assert finding.severity == "should"
    assert finding.message == "main requires too few approving reviews."


def test_ruleset_bypass_actor_reports_admin_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_ruleset_queries(
        monkeypatch,
        rules=_compliant_ruleset_rules(),
        bypass_actors=[
            {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
        ],
    )
    findings = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert [finding.message for finding in findings] == [
        "main allows administrator bypass."
    ]


def test_organization_ruleset_uses_organization_detail_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    calls = _mock_ruleset_queries(
        monkeypatch,
        rules=_compliant_ruleset_rules(source_type="Organization", source="org"),
    )
    assert "RSK014" not in _rule_ids(check_repo(root, POLICY, include_platform=True))
    assert calls[3][-1] == "orgs/org/rulesets/42"


def test_missing_ruleset_bypass_evidence_is_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_ruleset_queries(
        monkeypatch,
        rules=_compliant_ruleset_rules(),
        detail_stdout=json.dumps({}),
    )
    [finding] = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert finding.status == "indeterminate"
    assert finding.message == "Could not obtain ruleset bypass actors."


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "rules_returncode": 1,
                "rules_stderr": "gh: failed to connect to api.github.com",
            },
            "Ruleset query failed",
        ),
        ({"rules_stdout": "{}"}, "Effective rules response was not a paginated list."),
        (
            {
                "detail_returncode": 1,
                "detail_stderr": "gh: Resource not accessible (HTTP 403)",
            },
            "Ruleset detail query failed",
        ),
    ],
)
def test_unavailable_or_malformed_ruleset_evidence_is_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_ruleset_queries(monkeypatch, rules=_compliant_ruleset_rules(), **kwargs)
    [finding] = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert finding.status == "indeterminate"
    assert message in finding.message


def test_malformed_branch_protection_json_is_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_branch_protection_query(monkeypatch, stdout="{")
    [finding] = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert finding.status == "indeterminate"


@pytest.mark.parametrize(
    "stderr",
    [
        "gh: authentication required (HTTP 401)",
        "gh: failed to connect to api.github.com",
        "gh: Resource not accessible by personal access token (HTTP 403)",
    ],
)
def test_branch_protection_auth_and_network_failures_are_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_branch_protection_query(monkeypatch, stderr=stderr, returncode=1)
    [finding] = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert finding.status == "indeterminate"


def test_unsupported_branch_protection_response_is_a_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)
    _mock_branch_protection_query(
        monkeypatch,
        stderr=(
            "gh: Upgrade to GitHub Pro or make this repository public to enable "
            "this feature. (HTTP 403)"
        ),
        returncode=1,
    )
    [finding] = [
        finding
        for finding in check_repo(root, POLICY, include_platform=True)
        if finding.rule_id == "RSK014"
    ]
    assert finding.status == "violation"


def test_only_known_nonempty_ignore_reasons_suppress(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "README.md").unlink()
    path = root / "pyproject.toml"
    with path.open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.repo-check.ignore]\nRSK004 = " "\nRSK999 = "Unknown"\n')
    assert "RSK004" in _rule_ids(check_repo(root, POLICY))
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'RSK004 = " "', 'RSK004 = "Approved reason"'
        ),
        encoding="utf-8",
    )
    assert "RSK004" not in _rule_ids(check_repo(root, POLICY))


def test_json_output_retains_legacy_fields_and_adds_actionable_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _minimal_repo(tmp_path)
    (root / "README.md").unlink()
    assert cli.main([str(root), "--format", "json"]) == 1
    [item] = [
        item
        for item in json.loads(capsys.readouterr().out)
        if item["rule_id"] == "RSK004"
    ]
    assert {"rule_id", "severity", "path", "line", "message"} <= item.keys()
    assert {
        "title",
        "level",
        "actual",
        "expected",
        "remediation",
        "status",
    } <= item.keys()


def test_success_output_uses_positive_brand_color() -> None:
    assert cli._format_text([], color=True) == (
        "\033[38;2;35;209;111mAll checks passed!\033[0m\n"
    )


def test_strict_mode_only_promotes_recommended_findings(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "docs" / "adr").rmdir()
    assert cli.main([str(root)]) == 0
    assert cli.main([str(root), "--strict"]) == 1


def test_unavailable_requested_platform_check_is_command_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _minimal_repo(tmp_path)

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[:3] == ["git", "remote", "get-url"]:
            return subprocess.CompletedProcess(
                command, 0, "https://github.com/org/repo.git\n", ""
            )
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    findings = check_repo(root, POLICY, include_platform=True)
    finding = next(f for f in findings if f.rule_id == "RSK014")
    assert finding.status == "indeterminate"
    assert finding.severity == "platform"


@pytest.mark.parametrize("profile", STARTER_KIT_PROFILES)
def test_generated_repos_pass_repo_check(profile: str, tmp_path: Path) -> None:
    output = tmp_path / "generated"
    bootstrap_repo(
        profile=profile,
        repo_name="generated",
        package_name=None,
        description="Generated repo",
        repo_type="service",
        python_version="3.12",
        author="",
        license_id=None,
        output_dir=output,
        no_lock=True,
        no_install=True,
    )
    (output / "uv.lock").write_text("", encoding="utf-8")
    findings = check_repo(output, POLICY)
    assert [finding for finding in findings if finding.level == "required"] == []


def test_repository_passes_repo_check_strictly() -> None:
    assert check_repo(REPO_ROOT, POLICY) == []


def test_repo_check_console_script_runs_end_to_end(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "repo_standard.compliance.cli", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "RSK001" in result.stdout


def test_pre_commit_manifest_declares_repo_check() -> None:
    [hook] = load_yaml(
        (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    )
    assert hook["id"] == "repo-check"
    assert hook["entry"] == "repo-check"
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True


# --- shapes: one canonical section list per governed file -----------------


def test_every_shape_is_bound_to_the_rule_that_enforces_it() -> None:
    """A shape and its rule must name each other, in both directions."""
    for shape in POLICY.shapes:
        rule = POLICY.rule(shape.rule)
        assert rule.check.kind == shape.kind
        assert rule.check.config["shape"] == shape.id
    shaped = {rule.id for rule in POLICY.rules if "shape" in rule.check.config}
    assert shaped == {shape.rule for shape in POLICY.shapes}


def test_rsk002_uses_the_shared_agents_shape_record() -> None:
    """The AGENTS.md contract names a shape instead of duplicating its sections."""
    shape = _shape("RSK002")
    assert shape.path == "AGENTS.md"
    assert shape.heading_level == 2
    assert shape.required == shape.headings
    assert POLICY.rule("RSK002").level == "required"


@pytest.mark.parametrize("rule_id", ["RSK023", "RSK024", "RSK025"])
def test_shape_rules_are_required_for_v2(
    rule_id: str,
) -> None:
    assert POLICY.rule(rule_id).level == "required"


def test_readme_shape_distinguishes_required_sections() -> None:
    shape = _shape("RSK023")
    assert shape.required
    assert set(shape.required).issubset(shape.headings)


def test_missing_required_section_reports_its_shape_rule(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "README.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("## Usage\n\nDetail.\n\n", ""),
        encoding="utf-8",
    )
    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK023"]
    assert finding.message == "Missing required sections: Usage."


def test_reordered_sections_are_reported_even_when_all_are_present(
    tmp_path: Path,
) -> None:
    """Presence was already checked; order is what the shape adds."""
    root = _minimal_repo(tmp_path)
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    layout = "## Repository Layout\n\nDetail.\n\n"
    text = text.replace(layout, "").replace(
        "## Documentation Rules", f"{layout}## Documentation Rules"
    )
    path.write_text(text, encoding="utf-8")

    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK002"]
    assert finding.message == "Declared sections are out of canonical order."
    assert finding.actual.index("Repository Layout") < finding.actual.index(
        "Documentation Rules"
    )


def test_unlisted_sections_are_legal_anywhere(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Usage", "## Design Notes\n\nDetail.\n\n## Usage")
    text += "\n## Acknowledgements\n\nDetail.\n"
    path.write_text(text, encoding="utf-8")
    assert "RSK023" not in _rule_ids(check_repo(root, POLICY))


def test_optional_sections_may_be_absent_but_not_reordered(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "## At A Glance" not in text
    assert "RSK023" not in _rule_ids(check_repo(root, POLICY))

    path.write_text(
        text.replace("## Development", "## At A Glance\n\nDetail.\n\n## Development"),
        encoding="utf-8",
    )
    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK023"]
    assert finding.message == "Declared sections are out of canonical order."


def test_release_sections_do_not_disturb_the_changelog_shape(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Compatibility Policy\n\nDetail.\n\n## [Unreleased]\n\n"
        "## [1.1.0] - 2026-01-02\n\n### Added\n\n- Detail.\n\n"
        "## [1.0.0] - 2026-01-01\n",
        encoding="utf-8",
    )
    assert "RSK024" not in _rule_ids(check_repo(root, POLICY))


def test_changelog_without_an_unreleased_section_reports_rsk024(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK024"]
    assert finding.message == "Missing required sections: [Unreleased]."


def test_deeper_headings_do_not_satisfy_a_markdown_shape(tmp_path: Path) -> None:
    """Markdown shapes govern level two only, matching RSK002's semantics."""
    root = _minimal_repo(tmp_path)
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("## Install", "### At A Glance\n\nDetail.\n\n## Install"),
        encoding="utf-8",
    )
    assert "RSK023" not in _rule_ids(check_repo(root, POLICY))


def test_out_of_order_pyproject_tables_report_rsk025(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    metadata = "[tool.repo-standard]\nprofile = "
    head, _, tail = text.partition(metadata)
    block, _, rest = tail.partition("\n\n")
    path.write_text(f"{head}{rest}\n{metadata}{block}\n", encoding="utf-8")

    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK025"]
    assert finding.message == "Declared sections are out of canonical order."
    assert finding.actual.index("tool.ruff") < finding.actual.index(
        "tool.repo-standard"
    )


def test_unlisted_pyproject_tables_stay_legal_in_any_position(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "pyproject.toml"
    with path.open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.repo-check.ignore]\nRSK012 = "Documented reason."\n')
    assert "RSK025" not in _rule_ids(check_repo(root, POLICY))


def test_table_headers_inside_multiline_strings_are_not_tables(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    path = root / "pyproject.toml"
    with path.open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.example]\nnote = """\n[project]\n"""\n')
    assert "RSK025" not in _rule_ids(check_repo(root, POLICY))


def test_malformed_pyproject_reports_a_parse_error_not_a_shape_error(
    tmp_path: Path,
) -> None:
    root = _minimal_repo(tmp_path)
    (root / "pyproject.toml").write_text("[project\n", encoding="utf-8")
    [finding] = [f for f in check_repo(root, POLICY) if f.rule_id == "RSK025"]
    assert "Could not parse TOML" in finding.message


def _retype_agents_shape_as_toml(data: dict[str, object]) -> None:
    """Leave RSK002 dispatching to markdown_shape while its shape says TOML."""
    shapes = data["shapes"]
    assert isinstance(shapes, list)
    shapes[0].pop("heading_level")
    shapes[0]["kind"] = "toml_table_order"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["shapes"][0].update({"rule": "RSK999"}),
            "unknown rule",
        ),
        (_retype_agents_shape_as_toml, "not a markdown_shape shape"),
        (
            lambda data: data["shapes"][0]["sections"].append(
                dict(data["shapes"][0]["sections"][0])
            ),
            "duplicate section IDs",
        ),
        (
            lambda data: data["shapes"][0]["sections"][0].update({"level": "advisory"}),
            "unknown section level",
        ),
        (
            lambda data: data["shapes"][1].update({"path": "AGENTS.md"}),
            "two shapes govern the same path",
        ),
    ],
)
def test_invalid_shape_policy_is_rejected(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    root = _policy_checkout(tmp_path)
    path = root / "policy" / "shapes.yaml"
    data = load_yaml(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    mutation(data)
    path.write_text(dump_yaml(data), encoding="utf-8")
    with pytest.raises(PolicyError, match=message):
        load_source_policy(root)


def test_a_rule_naming_an_unknown_shape_is_rejected(tmp_path: Path) -> None:
    root = _policy_checkout(tmp_path)

    def mutation(data: dict[str, object]) -> None:
        rules = data["rules"]
        assert isinstance(rules, list)
        rule = next(item for item in rules if item["id"] == "RSK023")
        rule["check"]["config"]["shape"] = "missing"

    _mutate_base(root, mutation)
    with pytest.raises(PolicyError, match="unknown shape"):
        load_source_policy(root)


def test_generated_policy_reference_carries_every_shape() -> None:
    reference = (REPO_ROOT / "docs" / "policy-reference.md").read_text(encoding="utf-8")
    assert "## File Shapes" in reference
    for shape in POLICY.shapes:
        assert f"### {shape.id}" in reference
        for section in shape.sections:
            assert f"| `{section.id}` | `{section.heading}` |" in reference


def test_repo_standard_defers_shape_lists_to_the_generated_reference() -> None:
    text = (REPO_ROOT / "docs" / "repo-standard.md").read_text(encoding="utf-8")
    assert "policy-reference.md#agents" in text
    assert "policy-reference.md#file-shapes" in text
