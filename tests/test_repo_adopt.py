"""Regression coverage for conflict-aware existing-repository adoption."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import tomlkit
from conftest import REPO_ROOT, dump_yaml, load_yaml

from repo_standard.compliance.checks import Finding, check_repo, load_policy
from repo_standard.policy.models import LEVEL_ORDER
from repo_standard.project_metadata import kit_version
from repo_standard.repo_adopt import (
    ADOPTED_LICENSE_NOTICE,
    ADOPTION_UNLICENSED_NOTICE,
    AdoptionError,
    AdoptionPlan,
    CommandError,
    _merge_agents,
    _merge_pyproject,
    _merge_readme,
    _print_summary,
    _project_values,
    _read_starter,
    _run,
    apply_plan,
    main,
    plan_adoption,
)


def _write_minimal_repo(root: Path, profile: str) -> None:
    root.mkdir()
    build = (
        "\n[build-system]\n"
        'requires = ["uv_build>=0.11.20,<0.12"]\n'
        'build-backend = "uv_build"\n'
        if profile == "python-single"
        else ""
    )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "existing-project"\n'
        'version = "0.1.0"\n'
        'description = "Keep this project behavior."\n'
        'requires-python = ">=3.12"\n'
        'dependencies = ["httpx>=0.28"] # keep dependency comment\n'
        f"{build}",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Existing Project\n\nKeep this project-specific guide.\n", encoding="utf-8"
    )
    (root / "AGENTS.md").write_text(
        "# Local Instructions\n\nKeep this project-owned preamble.\n",
        encoding="utf-8",
    )
    if profile == "python-workspace":
        (root / "packages").mkdir()


def _accept_recommended_ruff_families(root: Path) -> None:
    """Select the families adoption leaves to the maintainer.

    Adoption only repairs `required` rules, so a repository it has finished
    with still carries the recommended ones. A test that needs a repository
    with no findings at all makes that choice itself.
    """
    path = root / "pyproject.toml"
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    select = document["tool"]["ruff"]["lint"]["select"]
    for family in load_policy().rule("RSK016").check.config["values"]:
        if family not in select:
            select.append(family)
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("profile", ["python-single", "python-workspace"])
def test_adoption_reaches_zero_required_findings_and_is_idempotent(
    tmp_path: Path, profile: str
) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, profile)
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "quality.yml").write_text(
        "# keep workflow comment\n"
        "name: Existing CI\n"
        "on: [push]\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    services:\n"
        "      redis:\n"
        "        image: redis:7\n"
        "    steps:\n"
        "      - name: Project-specific preparation\n"
        "        run: echo keep-me\n",
        encoding="utf-8",
    )
    (root / ".pre-commit-config.yaml").write_text(
        "# keep hook comment\n"
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: custom-project-hook\n"
        "        name: custom project hook\n"
        "        entry: echo keep-me\n"
        "        language: system\n",
        encoding="utf-8",
    )

    plan = plan_adoption(root, profile)
    apply_plan(plan)

    findings = check_repo(root, load_policy(), profile=profile)
    assert not [finding for finding in findings if finding.level == "required"]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "Keep this project-owned preamble." in agents
    assert "\n\n## Coding Standards" in agents
    assert "Keep this project-specific guide." in (root / "README.md").read_text(
        encoding="utf-8"
    )
    workflow = load_yaml(
        (root / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    )
    assert workflow["jobs"]["quality"]["services"]["redis"]["image"] == "redis:7"
    assert any(
        step.get("run") == "echo keep-me"
        for step in workflow["jobs"]["quality"]["steps"]
    )
    hooks = load_yaml((root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert hooks["repos"][0]["hooks"][0]["id"] == "custom-project-hook"
    assert "# keep hook comment" in (root / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "# keep workflow comment" in (
        root / ".github" / "workflows" / "quality.yml"
    ).read_text(encoding="utf-8")
    compliance = load_yaml(
        (root / ".github" / "workflows" / "compliance.yml").read_text(encoding="utf-8")
    )
    permissions = compliance["jobs"]["compliance"].get(
        "permissions", compliance.get("permissions")
    )
    assert permissions == {"contents": "read"}
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "httpx>=0.28" in pyproject
    assert "# keep dependency comment" in pyproject

    repeated = plan_adoption(root, profile)
    assert repeated.changes == ()


def test_missing_gitignore_is_added_never_merged(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")

    apply_plan(plan_adoption(root, "python-single"))

    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert ".venv/" in gitignore
    assert "__pycache__/" in gitignore


def test_existing_gitignore_is_left_untouched(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    plan = plan_adoption(root, "python-single")
    apply_plan(plan)

    assert ".gitignore" not in {change.path.as_posix() for change in plan.changes}
    assert (root / ".gitignore").read_text(encoding="utf-8") == "node_modules/\n"


def test_dry_run_is_read_only_and_does_not_require_git(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

    assert main([str(root), "--profile", "python-single", "--dry-run"]) == 0

    after = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before


def test_parse_failure_plans_no_partial_writes(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    invalid = root / ".pre-commit-config.yaml"
    invalid.write_text("repos: [\n", encoding="utf-8")
    before = invalid.read_bytes()

    with pytest.raises(AdoptionError, match="could not parse"):
        plan_adoption(root, "python-single")

    assert invalid.read_bytes() == before
    assert not (root / ".github").exists()


def test_existing_documentation_directories_are_not_seeded(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    adr = root / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "0001-existing-decision.md").write_text("# Existing ADR\n", encoding="utf-8")

    plan = plan_adoption(root, "python-single")

    changed = {change.path.as_posix() for change in plan.changes}
    assert "docs/adr/0001-template.md" not in changed
    assert "docs/adr" in plan.unchanged


def test_quality_gates_prose_before_list_stays_in_place(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    (root / "AGENTS.md").write_text(
        "# Local Instructions\n\n"
        "## Quality Gates\n\n"
        "Run from repo root:\n\n"
        "1. `uv sync --locked`\n"
        "2. `uv run pre-commit run --all-files`\n"
        "3. `uv run pytest`\n"
        "4. `uv build`\n\n"
        "The quality job's effective permissions must be exactly `contents: read`.\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "\n\nRun from repo root:\n\n1. `uv sync --locked`" in agents
    assert "4. `uv build`\n\nThe quality job's effective permissions" in agents


def test_non_uv_build_backend_is_preserved_without_conflict(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = text.replace(
        'requires = ["uv_build>=0.11.20,<0.12"]',
        'requires = ["hatchling>=1.27"]',
    ).replace('build-backend = "uv_build"', 'build-backend = "hatchling.build"')
    pyproject.write_text(text, encoding="utf-8")

    plan = plan_adoption(root, "python-single")

    assert plan.conflicts == ()
    assert main([str(root), "--profile", "python-single", "--dry-run"]) == 0
    adopted_pyproject = next(
        change.content
        for change in plan.changes
        if change.path.as_posix() == "pyproject.toml"
    )
    assert 'build-backend = "hatchling.build"' in adopted_pyproject

    apply_plan(plan)
    findings = check_repo(root, load_policy(), profile="python-single")
    backend_finding = next(
        finding for finding in findings if finding.rule_id == "RSK008"
    )
    assert backend_finding.level == "recommended"
    assert not [finding for finding in findings if finding.level == "required"]


def test_fully_compliant_repository_still_gets_a_missing_gitignore(
    tmp_path: Path,
) -> None:
    """No rule checks `.gitignore`, so zero findings must not short-circuit it."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    apply_plan(plan_adoption(root, "python-single"))
    (root / "LICENSE").write_text("Approved license terms.\n", encoding="utf-8")
    _accept_recommended_ruff_families(root)
    assert check_repo(root, load_policy(), profile="python-single") == []
    (root / ".gitignore").unlink()

    plan = plan_adoption(root, "python-single")

    assert {change.path.as_posix() for change in plan.changes} == {".gitignore"}
    apply_plan(plan)
    assert (root / ".gitignore").is_file()


def test_structurally_compliant_repository_is_a_no_op(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    apply_plan(plan_adoption(root, "python-single"))
    (root / "LICENSE").write_text("Approved license terms.\n", encoding="utf-8")
    _accept_recommended_ruff_families(root)

    pre_commit = root / ".pre-commit-config.yaml"
    hooks = load_yaml(pre_commit.read_text(encoding="utf-8"))
    hooks["repos"] = [
        repository
        for repository in hooks["repos"]
        if repository.get("repo") != "https://github.com/FP-DevTools/repo-standard-kit"
    ]
    pre_commit.write_text(dump_yaml(hooks), encoding="utf-8")

    assert check_repo(root, load_policy(), profile="python-single") == []
    plan = plan_adoption(root, "python-single")

    assert plan.changes == ()
    assert plan.conflicts == ()


def _commit_minimal_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(
        ["git", "add", "pyproject.toml", "uv.lock", "README.md", "AGENTS.md"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True
    )


def test_dirty_checkout_is_refused_without_writes(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    _commit_minimal_repo(root)
    (root / "README.md").write_text("dirty\n", encoding="utf-8")

    assert (
        main([str(root), "--profile", "python-single", "--no-lock", "--no-install"])
        == 2
    )
    assert not (root / ".github").exists()


def test_an_unused_exemption_is_reported_without_failing_adoption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    with (root / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.repo-check.ignore]\nRSK005 = "Suppresses nothing."\n')
    _commit_minimal_repo(root)

    result = main(
        [str(root), "--profile", "python-single", "--no-lock", "--no-install"]
    )

    # Adoption writes the RSK005 reference, so the exemption is left dead; it
    # is reported at RSK005's required level and still must not fail the run.
    assert "RSK005" in capsys.readouterr().out
    assert result == 0


def test_apply_cli_leaves_changes_unstaged_and_uncommitted(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    _commit_minimal_repo(root)

    result = main(
        [str(root), "--profile", "python-single", "--no-lock", "--no-install"]
    )

    assert result == 0
    unstaged = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "pyproject.toml" in unstaged
    assert staged == ""


def test_unpinned_custom_quality_action_is_an_explicit_conflict(
    tmp_path: Path,
) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    workflow = root / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "on: pull_request\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: vendor/custom-action@v2\n",
        encoding="utf-8",
    )

    plan = plan_adoption(root, "python-single")

    assert any("vendor/custom-action@v2" in conflict for conflict in plan.conflicts)


def test_unpinned_custom_compliance_action_is_an_explicit_conflict(
    tmp_path: Path,
) -> None:
    """RSK029 puts the compliance workflow under the same pin rule as quality."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    workflow = root / ".github" / "workflows" / "compliance.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "on: pull_request\n"
        "jobs:\n"
        "  compliance:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: vendor/custom-action@v2\n",
        encoding="utf-8",
    )

    plan = plan_adoption(root, "python-single")

    assert any("vendor/custom-action@v2" in conflict for conflict in plan.conflicts)


def test_recognized_older_compliance_step_is_updated_in_place(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    workflow = root / ".github" / "workflows" / "compliance.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: Compliance\n"
        "on: pull_request\n"
        "jobs:\n"
        "  compliance:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Check repository compliance\n"
        "        run: uvx --from old-kit@v1.0.0 repo-check .\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    adopted = load_yaml(workflow.read_text(encoding="utf-8"))
    steps = adopted["jobs"]["compliance"]["steps"]
    compliance_steps = [
        step for step in steps if step.get("name") == "Check repository compliance"
    ]
    assert len(compliance_steps) == 1
    assert f"@v{kit_version()}" in compliance_steps[0]["run"]


def test_a_compliance_job_that_invokes_nothing_gains_the_invocation(
    tmp_path: Path,
) -> None:
    """RSK030 is repairable through the existing merge: no new repair path."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    workflow = root / ".github" / "workflows" / "compliance.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: Compliance\n"
        "on: pull_request\n"
        "jobs:\n"
        "  compliance:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Say nothing\n"
        "        run: echo compliant\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    assert "RSK030" not in {
        finding.rule_id for finding in check_repo(root, load_policy())
    }


def test_interrupted_command_reports_the_exact_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", interrupt)

    with pytest.raises(CommandError, match=r"uv lock.*interrupted") as error:
        _run(["uv", "lock"], tmp_path)

    assert error.value.command == ["uv", "lock"]


def test_run_sets_native_tls_for_child_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def capture(command: list[str], **kwargs: object) -> None:
        captured["command"] = command
        captured.update(kwargs)

    monkeypatch.delenv("UV_NATIVE_TLS", raising=False)
    monkeypatch.setattr(subprocess, "run", capture)

    _run(["uv", "lock"], tmp_path, native_tls=True)

    assert captured["command"] == ["uv", "lock"]
    assert captured["cwd"] == tmp_path
    assert captured["env"]["UV_NATIVE_TLS"] == "true"


def test_native_tls_is_forwarded_to_dependency_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(
        ["git", "add", "pyproject.toml", "uv.lock", "README.md", "AGENTS.md"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    commands: list[tuple[list[str], bool]] = []

    def capture(command: list[str], root: Path, *, native_tls: bool = False) -> None:
        commands.append((command, native_tls))

    monkeypatch.setattr("repo_standard.repo_adopt._run", capture)

    assert main([str(root), "--profile", "python-single", "--native-tls"]) == 0
    assert commands == [(["uv", "lock"], True), (["uv", "sync"], True)]


def test_this_repository_is_its_own_first_adopter() -> None:
    """`repo-adopt .` must plan nothing against the kit that publishes it."""
    plan = plan_adoption(REPO_ROOT, "python-single")

    assert plan.changes == ()
    assert plan.conflicts == ()


def test_self_adoption_is_a_real_no_op_not_a_short_circuit() -> None:
    """Prove the merges agree with the committed files.

    `plan_adoption` returns early when the repository already has no findings,
    so the plan being empty would also be satisfied by merges that disagree
    with what is committed. Run them directly instead.
    """
    path = REPO_ROOT / "pyproject.toml"
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    values = _project_values(REPO_ROOT, document)

    for relative, merge in (("AGENTS.md", _merge_agents), ("README.md", _merge_readme)):
        target = REPO_ROOT / relative
        assert merge(target, "python-single", values) == target.read_text(
            encoding="utf-8"
        ), f"repo-adopt would rewrite {relative}"

    merged, _changed, conflicts = _merge_pyproject(path, document, "python-single")
    assert conflicts == []
    assert merged == path.read_text(encoding="utf-8")


def _h2(text: str) -> list[str]:
    return re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE)


def _is_subsequence(actual: list[str], declared: tuple[str, ...]) -> bool:
    seen = [item for item in actual if item in declared]
    return seen == [item for item in declared if item in seen]


@pytest.mark.parametrize(
    ("document", "rule_id", "last_section"),
    [
        ("AGENTS.md", "RSK002", "Change Control Notes"),
        ("README.md", "RSK023", "License"),
    ],
)
def test_repaired_sections_land_in_shape_order(
    tmp_path: Path, document: str, rule_id: str, last_section: str
) -> None:
    """A missing section must not be appended past the ones that follow it.

    Appending was safe while RSK002 only checked presence. Now that shapes are
    order-enforced, appending would trade a missing-section finding for an
    out-of-order one.
    """
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    (root / document).write_text(
        f"# Existing\n\nKeep this.\n\n## {last_section}\n\nProject-owned prose.\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    policy = load_policy()
    shape = policy.shape(policy.rule(rule_id).check.config["shape"])
    headings = _h2((root / document).read_text(encoding="utf-8"))
    assert headings[-1] == last_section, "the project's own section moved"
    assert _is_subsequence(headings, shape.headings), (
        f"{document} sections are out of canonical order: {headings}"
    )
    assert "Project-owned prose." in (root / document).read_text(encoding="utf-8")


def test_adoption_invents_no_heading_the_shape_does_not_declare(
    tmp_path: Path,
) -> None:
    """The RSK005 reference used to arrive as a `Repository Standards` section."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")

    apply_plan(plan_adoption(root, "python-single"))

    policy = load_policy()
    for document, rule_id in (("AGENTS.md", "RSK002"), ("README.md", "RSK023")):
        text = (root / document).read_text(encoding="utf-8")
        declared = policy.shape(policy.rule(rule_id).check.config["shape"]).headings
        assert "Repository Standards" not in _h2(text)
        assert set(_h2(text)) <= set(declared), (
            f"adoption added headings to {document} that no shape declares"
        )
        assert "repo-standard-kit" in text


def test_adoption_restores_a_drifted_operating_dial(tmp_path: Path) -> None:
    """RSK026 levels are policy's, so adoption overwrites a local edit."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    path = root / "AGENTS.md"
    config = load_policy().rule("RSK026").check.config
    section = config["section"]
    path.write_text(
        f"# Existing\n\n## {section}\n\nHouse style below.\n\n"
        "- **Verbosity:** 5 / 5\n- **Precision, repeatability, determinism:** 1 / 5\n"
        "\nThe rest is ours.\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    text = path.read_text(encoding="utf-8")
    for dial in config["dials"]:
        assert f"- **{dial['label']}:** {dial['level']} / {dial['scale']}" in text
    assert "**Verbosity:** 5 / 5" not in text
    assert "House style below." in text, "surrounding prose must survive"
    assert "The rest is ours." in text
    assert not [f for f in check_repo(root, load_policy()) if f.rule_id == "RSK026"]


def test_new_pyproject_tables_are_placed_in_declared_order(tmp_path: Path) -> None:
    """`[dependency-groups]` used to be appended after `[build-system]`."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8") + '\n[tool.ty.src]\nroot = "src"\n',
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    policy = load_policy()
    shape = policy.shape(policy.rule("RSK025").check.config["shape"])
    tables = re.findall(
        r"^\[\[?\s*([^\]\s]+)\s*\]\]?$",
        pyproject.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert _is_subsequence(tables, shape.headings), f"table order is wrong: {tables}"
    assert tables.index("dependency-groups") < tables.index("build-system")


def test_summary_reports_every_declared_level(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A level policy declares but the summary omits is a silently dropped finding."""
    plan = AdoptionPlan(
        root=tmp_path,
        profile="python-single",
        version="0.0.0",
        changes=(),
        unchanged=(),
        conflicts=(),
        dependency_metadata_changed=False,
    )
    findings = [
        Finding(
            rule_id=f"RSK{index:03d}",
            title="title",
            level=level,
            path="pyproject.toml",
            line=None,
            message=f"{level} message",
            actual=None,
            expected=None,
            remediation="remediate",
        )
        for index, level in enumerate(LEVEL_ORDER, 1)
    ]

    _print_summary(plan, findings)

    output = capsys.readouterr().out
    for level in LEVEL_ORDER:
        assert f"remaining {level} findings: 1" in output
        assert f"{level} message" in output


def test_summary_counts_a_suppressed_finding_apart_from_remaining_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A silenced required rule the summary omits is a silently green adoption."""
    plan = AdoptionPlan(
        root=tmp_path,
        profile="python-single",
        version="0.0.0",
        changes=(),
        unchanged=(),
        conflicts=(),
        dependency_metadata_changed=False,
    )
    findings = [
        Finding(
            rule_id="RSK004",
            title="title",
            level="required",
            path="README.md",
            line=None,
            message=(
                "Required file is missing. Suppressed by "
                "[tool.repo-check.ignore]: Docs live in the wiki."
            ),
            actual=None,
            expected=None,
            remediation="remediate",
            status="suppressed",
        )
    ]

    _print_summary(plan, findings)

    output = capsys.readouterr().out
    assert "remaining required findings: 0" in output
    assert "suppressed by [tool.repo-check.ignore]: 1" in output
    assert "  - RSK004 README.md:" in output


def _starter_pinned_uses(profile: str, relative: str) -> list[str]:
    """Every `uses: <action>@<sha> # <version>` line the starter workflow pins."""
    return [
        line.strip()
        for line in _read_starter(profile, relative).splitlines()
        if line.lstrip().startswith("uses:") and "#" in line
    ]


def test_repinning_carries_the_starters_version_comment_across(
    tmp_path: Path,
) -> None:
    """A stale annotation beside a fresh SHA is what Dependabot reads as current."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    workflow = root / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "on: pull_request\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4 # v4.2.2\n"
        "\n"
        "      - uses: astral-sh/setup-uv@v3\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-single"))

    # ruamel round-trips comments as attached tokens, so assert on the bytes
    # written rather than on the reloaded document.
    written = workflow.read_text(encoding="utf-8")
    pinned = _starter_pinned_uses("python-single", ".github/workflows/quality.yml")
    assert len(pinned) == 2
    for line in pinned:
        assert line in written
    # The annotation the repin invalidated is gone, and the blank line the
    # replaced comment token carried is still where it was.
    assert "v4.2.2" not in written
    assert "\n\n      - uses: astral-sh/setup-uv@" in written


def _v1_compliance_caller(root: Path, uses: str, inputs: str) -> Path:
    """The compliance workflow shape `docs/compliance.md` publishes as supported."""
    workflow = root / ".github" / "workflows" / "compliance.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: Compliance\n"
        "on:\n"
        "  pull_request:\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        f"  compliance:\n    uses: {uses}\n    with:\n{inputs}",
        encoding="utf-8",
    )
    return workflow


def test_a_reusable_workflow_call_is_reconciled_and_never_gains_steps(
    tmp_path: Path,
) -> None:
    """A job declaring both `uses:` and `steps:` is one GitHub refuses to run."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-workspace")
    workflow = _v1_compliance_caller(
        root,
        "FP-DevTools/repo-standard-kit/.github/workflows/compliance.yml@v1.2.0",
        "      standard-ref: v1.2.0\n      strict: true\n",
    )

    plan = plan_adoption(root, "python-workspace")
    apply_plan(plan)

    job = load_yaml(workflow.read_text(encoding="utf-8"))["jobs"]["compliance"]
    assert "steps" not in job
    assert job["uses"] == (
        "FP-DevTools/repo-standard-kit/.github/workflows/"
        f"compliance-reusable.yml@v{kit_version()}"
    )
    assert job["with"] == {"standard-ref": f"v{kit_version()}"}
    assert any("full commit SHA" in conflict for conflict in plan.conflicts)
    assert any("strict" in conflict for conflict in plan.conflicts)


def test_a_reusable_workflow_this_kit_does_not_publish_is_left_alone(
    tmp_path: Path,
) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-workspace")
    uses = "vendor/ci/.github/workflows/compliance.yml@v3"
    workflow = _v1_compliance_caller(root, uses, "      mode: strict\n")

    plan = plan_adoption(root, "python-workspace")
    apply_plan(plan)

    job = load_yaml(workflow.read_text(encoding="utf-8"))["jobs"]["compliance"]
    assert job == {"uses": uses, "with": {"mode": "strict"}}
    assert any(uses in conflict for conflict in plan.conflicts)


def test_hook_args_the_starter_does_not_model_are_kept_and_reported(
    tmp_path: Path,
) -> None:
    """Dropping `--baseline` turned a clean gate into 98 detect-secrets findings."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: detect-secrets\n"
        "        name: detect secrets\n"
        "        entry: uv run detect-secrets-hook\n"
        "        args: ['--baseline', '.secrets.baseline']\n"
        "        language: system\n"
        "        types: [text]\n",
        encoding="utf-8",
    )

    plan = plan_adoption(root, "python-single")
    apply_plan(plan)

    hook = next(
        item
        for repository in load_yaml(
            (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        )["repos"]
        for item in repository.get("hooks", [])
        if item.get("id") == "detect-secrets"
    )
    assert hook["args"] == ["--baseline", ".secrets.baseline"]
    assert any("detect-secrets" in conflict for conflict in plan.conflicts)


def test_a_recommended_lint_family_is_left_to_the_maintainer(tmp_path: Path) -> None:
    """Selecting `PT` unasked turned a clean `ruff check` into seven errors."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")

    apply_plan(plan_adoption(root, "python-single"))

    policy = load_policy()
    document = tomlkit.parse((root / "pyproject.toml").read_text(encoding="utf-8"))
    select = set(document["tool"]["ruff"]["lint"]["select"])
    assert set(policy.rule("RSK010").check.config["required_select"]) <= select
    assert not set(policy.rule("RSK016").check.config["values"]) & select


def test_a_stale_standard_major_adopts_without_an_explicit_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The state every earlier-major adopter is in is what adoption repairs."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    with (root / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write(
            '\n[tool.repo-standard]\nprofile = "python-single"\nstandard = "1"\n'
        )
    _commit_minimal_repo(root)

    assert main([str(root), "--no-lock", "--no-install"]) == 0

    major = load_policy().standard_major
    output = capsys.readouterr().out
    assert "standard '1'" in output
    assert f"standard {major!r}" in output
    document = tomlkit.parse((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert document["tool"]["repo-standard"]["standard"] == major


def test_an_unknown_profile_still_asks_for_an_explicit_one(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    with (root / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.repo-standard]\nprofile = "python-elixir"\n')

    with pytest.raises(AdoptionError, match="python-elixir"):
        plan_adoption(root)


def test_adoption_leaves_pyproject_in_canonical_table_order(tmp_path: Path) -> None:
    """`updated: pyproject.toml` must not also mean `still failing RSK025`."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + '\n[tool.repo-standard]\nprofile = "python-single"\nstandard = "1"\n'
        '\n[tool.ty.src]\nroot = "src"\n'
        "\n[dependency-groups]\ndev = []\n"
        '\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root))

    policy = load_policy()
    shape = policy.shape(policy.rule("RSK025").check.config["shape"])
    tables = re.findall(
        r"^\[\[?\s*([^\]\s]+)\s*\]\]?$",
        pyproject.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert _is_subsequence(tables, shape.headings), f"table order is wrong: {tables}"
    assert not [
        finding
        for finding in check_repo(root, policy, profile="python-single")
        if finding.rule_id == "RSK025"
    ]


def test_an_equivalent_step_is_matched_rather_than_appended_again(
    tmp_path: Path,
) -> None:
    """The starter guards the build; the adopter runs it plainly. One step."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-workspace")
    workflow = root / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "name: CI\n"
        "on: pull_request\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Build packages\n"
        "        run: uv build --all-packages\n",
        encoding="utf-8",
    )

    apply_plan(plan_adoption(root, "python-workspace"))

    steps = load_yaml(workflow.read_text(encoding="utf-8"))["jobs"]["quality"]["steps"]
    names = [step["name"] for step in steps if "name" in step]
    assert len(names) == len(set(names)), f"duplicate step names: {names}"
    assert [step for step in steps if step.get("name") == "Build packages"] == [
        {"name": "Build packages", "run": "uv build --all-packages"}
    ]


def test_an_inserted_readme_section_states_the_gap(tmp_path: Path) -> None:
    """The starter's prose describes a repository `repo-init` has just generated."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-workspace")

    apply_plan(plan_adoption(root, "python-workspace"))

    policy = load_policy()
    readme = (root / "README.md").read_text(encoding="utf-8")
    shape = policy.shape(policy.rule("RSK023").check.config["shape"])
    assert "repo-add-package" not in readme
    assert "Replace this section" not in readme
    # Every required section but `License`, whose body adoption reads off the
    # repository rather than leaving to the maintainer.
    assert readme.count("it has no content yet.") == len(
        [
            section
            for section in shape.sections
            if section.level == "required" and section.id != "license"
        ]
    )
    assert not [
        finding
        for finding in check_repo(root, policy, profile="python-workspace")
        if finding.rule_id == "RSK023"
    ]


@pytest.mark.parametrize(
    ("licensed", "expected"),
    [
        (True, ADOPTED_LICENSE_NOTICE),
        (False, ADOPTION_UNLICENSED_NOTICE),
    ],
)
def test_an_inserted_license_section_states_the_terms(
    tmp_path: Path, licensed: bool, expected: str
) -> None:
    """`License` is the one section adoption can answer from the repository."""
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-workspace")
    if licensed:
        (root / "LICENSE").write_text("Approved license terms.\n", encoding="utf-8")

    apply_plan(plan_adoption(root, "python-workspace"))

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert f"## License\n\n{expected}\n" in readme
    # `repo-init --license` is not a command an existing repository can run.
    assert "rerun `repo-init`" not in readme
