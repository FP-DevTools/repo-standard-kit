"""Regression coverage for conflict-aware existing-repository adoption."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from repo_standard.compliance.checks import check_repo, load_policy
from repo_standard.repo_adopt import (
    AdoptionError,
    CommandError,
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
    workflow = yaml.safe_load(
        (root / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    )
    assert workflow["jobs"]["quality"]["services"]["redis"]["image"] == "redis:7"
    assert any(
        step.get("run") == "echo keep-me"
        for step in workflow["jobs"]["quality"]["steps"]
    )
    hooks = yaml.safe_load(
        (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    assert hooks["repos"][0]["hooks"][0]["id"] == "custom-project-hook"
    assert "# keep hook comment" in (root / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "# keep workflow comment" in (
        root / ".github" / "workflows" / "quality.yml"
    ).read_text(encoding="utf-8")
    compliance = yaml.safe_load(
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
    diagrams = root / "docs" / "diagrams"
    adr.mkdir(parents=True)
    diagrams.mkdir(parents=True)
    (adr / "0001-existing-decision.md").write_text("# Existing ADR\n", encoding="utf-8")
    (diagrams / "architecture.puml").write_text(
        "@startuml\n@enduml\n", encoding="utf-8"
    )

    plan = plan_adoption(root, "python-single")

    changed = {change.path.as_posix() for change in plan.changes}
    assert "docs/adr/0001-template.md" not in changed
    assert "docs/diagrams/README.md" not in changed
    assert "docs/adr" in plan.unchanged
    assert "docs/diagrams" in plan.unchanged


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


def test_structurally_compliant_repository_is_a_no_op(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    _write_minimal_repo(root, "python-single")
    apply_plan(plan_adoption(root, "python-single"))
    (root / "LICENSE").write_text("Approved license terms.\n", encoding="utf-8")

    pre_commit = root / ".pre-commit-config.yaml"
    hooks = yaml.safe_load(pre_commit.read_text(encoding="utf-8"))
    hooks["repos"] = [
        repository
        for repository in hooks["repos"]
        if repository.get("repo") != "https://github.com/FP-DevTools/repo-standard-kit"
    ]
    pre_commit.write_text(yaml.safe_dump(hooks, sort_keys=False), encoding="utf-8")

    assert check_repo(root, load_policy(), profile="python-single") == []
    plan = plan_adoption(root, "python-single")

    assert plan.changes == ()
    assert plan.conflicts == ()


def test_dirty_checkout_is_refused_without_writes(tmp_path: Path) -> None:
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
        ["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True
    )
    (root / "README.md").write_text("dirty\n", encoding="utf-8")

    assert (
        main([str(root), "--profile", "python-single", "--no-lock", "--no-install"])
        == 2
    )
    assert not (root / ".github").exists()


def test_apply_cli_leaves_changes_unstaged_and_uncommitted(tmp_path: Path) -> None:
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
        ["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True
    )

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

    adopted = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    steps = adopted["jobs"]["compliance"]["steps"]
    compliance_steps = [
        step for step in steps if step.get("name") == "Check repository compliance"
    ]
    assert len(compliance_steps) == 1
    assert "@v1.2.0" in compliance_steps[0]["run"]


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
