"""Policy schema, structural checker, profile, output, and dogfood tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT

from repo_standard.compliance import checks, cli
from repo_standard.compliance.checks import (
    CHECK_HANDLERS,
    Finding,
    check_repo,
    load_policy,
    resolve_profile,
)
from repo_standard.policy import PolicyError, load_compiled_policy, load_source_policy
from repo_standard.policy.compiler import render_compiled, render_reference
from repo_standard.policy.models import CHECK_SCHEMAS
from repo_standard.repo_init import bootstrap_repo

POLICY = load_policy()
STARTER_KIT_PROFILES = POLICY.profile_ids


def _rule_ids(findings: list[Finding]) -> set[str]:
    return {finding.rule_id for finding in findings}


def _write_pre_commit(root: Path, hooks: list[dict[str, object]]) -> None:
    data = {"repos": [{"repo": "local", "hooks": hooks}]}
    (root / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


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


def _minimal_repo(tmp_path: Path, profile: str = "python-single") -> Path:
    root = tmp_path / "compliant-repo"
    root.mkdir()
    headings = POLICY.rule("RSK002").check.config["headings"]
    agents_sections = "\n\n".join(f"## {heading}\n\nDetail." for heading in headings)
    gate_chain = "\n".join(
        f"{index}. `{command}`"
        for index, command in enumerate(POLICY.rule("RSK003").check.config["values"], 1)
    )
    (root / "AGENTS.md").write_text(
        f"# AGENTS.md\n\n{agents_sections}\n\n{gate_chain}\n\nSee repo-standard-kit.\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Repository\n\nSee repo-standard-kit.\n", encoding="utf-8"
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
        "[tool.ruff]\n"
        f"line-length = {POLICY.rule('RSK015').check.config['value']}\n\n"
        "[tool.ruff.lint]\n"
        f"select = {json.dumps(select)}\n\n"
        "[tool.repo-standard]\n"
        f'profile = "{profile}"\n'
        f'standard = "{POLICY.standard_major}"\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("", encoding="utf-8")
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (root / "LICENSE").write_text("Proprietary.\n", encoding="utf-8")
    return root


def _load_pre_commit(root: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(
        (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
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
    data = yaml.safe_load(base.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    mutation(data)
    base.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


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


def test_every_typed_check_kind_has_exactly_one_runtime_handler() -> None:
    assert set(CHECK_SCHEMAS) == set(CHECK_HANDLERS)


def test_rsk021_policy_is_workflow_scoped() -> None:
    assert POLICY.rule("RSK021").check.config == {
        "path": ".github/workflows/quality.yml"
    }
    assert CHECK_SCHEMAS["github_workflow_pins"] == ({"path"}, set())


def test_rsk014_policy_represents_every_required_protection_property() -> None:
    assert POLICY.rule("RSK014").check.config == {
        "branch": "main",
        "required_status_checks": ["quality"],
        "minimum_reviews": 1,
        "dismiss_stale_approvals": True,
        "require_up_to_date": True,
        "require_conversation_resolution": True,
        "enforce_admins": True,
    }


def test_standard_package_version_and_source_distribution_inputs_agree() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    assert pyproject["project"]["version"] == POLICY.standard_version
    includes = pyproject["tool"]["uv"]["build-backend"]["source-include"]
    assert "policy/**" in includes
    assert "docs/**" in includes
    assert (REPO_ROOT / "src" / "repo_standard" / "policy" / "compiled.json").is_file()


# --- base rules and actionable findings ----------------------------------


def test_minimal_repo_has_no_findings(tmp_path: Path) -> None:
    assert check_repo(_minimal_repo(tmp_path), POLICY) == []


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


def test_job_permissions_override_workflow_permissions(tmp_path: Path) -> None:
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


def test_missing_or_write_permissions_report_rsk020(tmp_path: Path) -> None:
    root = _minimal_repo(tmp_path)
    path = root / ".github" / "workflows" / "quality.yml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "  contents: read", "  contents: write"
        ),
        encoding="utf-8",
    )
    finding = next(f for f in check_repo(root, POLICY) if f.rule_id == "RSK020")
    assert finding.line is not None


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
    path.write_text(
        path.read_text(encoding="utf-8").replace('standard = "1"', 'standard = "2"'),
        encoding="utf-8",
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
        "required_status_checks": {"contexts": ["quality"], "strict": True},
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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda response: response.update(
                {"required_pull_request_reviews": None}
            ),
            "main does not require pull request reviews.",
        ),
        (
            lambda response: response["required_pull_request_reviews"].update(
                {"required_approving_review_count": 0}
            ),
            "main requires too few approving reviews.",
        ),
        (
            lambda response: response["required_pull_request_reviews"].update(
                {"dismiss_stale_reviews": False}
            ),
            "main does not dismiss stale approvals.",
        ),
        (
            lambda response: response["required_status_checks"].update(
                {"contexts": []}
            ),
            "main omits required status checks: quality.",
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
    assert "RSK014" not in _rule_ids(
        check_repo(root, POLICY, include_platform=True)
    )


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
        output_dir=output,
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
    [hook] = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    )
    assert hook["id"] == "repo-check"
    assert hook["entry"] == "repo-check"
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True
