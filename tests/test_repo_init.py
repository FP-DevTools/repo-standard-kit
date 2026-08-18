from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

import pytest
from conftest import (
    PROSE_WIDTH,
    REPO_ROOT,
    documented_ruff_baseline,
    mandatory_ci_commands,
    prose_offenders,
    required_agents_sections,
    ruff_config_of,
)

from repo_standard.repo_init import (
    bootstrap_repo,
    ensure_git_repository,
    ensure_no_unresolved_placeholders,
    ensure_output_dir,
    infer_package_name,
    infer_repo_name,
    initialize_git_repository,
    main,
    resolve_output_dir,
    run_optional_installs,
    validate_package_name,
    validate_repo_name,
)

IGNORED_ARTIFACT_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
    "__pycache__",
}

MANDATORY_CI_COMMANDS = mandatory_ci_commands()

MANDATORY_PRE_COMMIT_ENTRIES = [
    "uv run check-yaml",
    "uv run check-toml",
    "uv run check-json",
    "uv run trailing-whitespace-fixer",
    "uv run end-of-file-fixer",
    "uv run check-merge-conflict",
    "uv run detect-private-key",
    "uv run detect-secrets-hook",
    "uv run check-added-large-files",
    "uv run ruff check --force-exclude",
    "uv run ruff format --force-exclude",
]


STARTER_KIT_PROFILES = ("python-single", "python-workspace")

STARTER_KIT_ROOT = Path("src") / "repo_standard" / "starter_kits"


def starter_kit_dir(profile: str) -> Path:
    return Path(__file__).resolve().parents[1] / STARTER_KIT_ROOT / profile


def test_bootstrap_repo_renders_python_single_starter(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo-service"

    bootstrap_repo(
        profile="python-single",
        repo_name="demo-service",
        package_name="demo_service",
        description="Demo service",
        repo_type="service",
        python_version="3.12",
        author="",
        output_dir=output_dir,
        no_install=True,
    )

    agents_text = (output_dir / "AGENTS.md").read_text(encoding="utf-8")
    pyproject_text = (output_dir / "pyproject.toml").read_text(encoding="utf-8")
    smoke_test_text = (output_dir / "tests" / "test_smoke.py").read_text(
        encoding="utf-8"
    )
    readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
    workflow_text = (output_dir / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    pre_commit_text = (output_dir / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )

    assert "__REPO_NAME__" not in agents_text
    assert "demo-service" in pyproject_text
    assert 'importlib.import_module("demo_service")' in smoke_test_text
    assert "## First 10 Minutes" in readme_text
    assert (output_dir / ".github" / "workflows" / "quality.yml").exists()
    for command in MANDATORY_CI_COMMANDS:
        assert command in agents_text
        assert command in workflow_text
    for entry in MANDATORY_PRE_COMMIT_ENTRIES:
        assert entry in pre_commit_text
    assert not (output_dir / ".ruff_cache").exists()
    assert (output_dir / "src" / "demo_service" / "__init__.py").exists()
    assert not (output_dir / "src" / "package_name").exists()


def test_bootstrap_repo_infers_package_name_for_python_single(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo-service"

    bootstrap_repo(
        profile="python-single",
        repo_name="demo-service",
        package_name=None,
        description="Demo service",
        repo_type="service",
        python_version="3.12",
        author="",
        output_dir=output_dir,
        no_install=True,
    )

    assert (output_dir / "src" / "demo_service" / "__init__.py").exists()


def test_bootstrap_repo_renders_python_workspace_starter(tmp_path: Path) -> None:
    output_dir = tmp_path / "widget-platform"

    bootstrap_repo(
        profile="python-workspace",
        repo_name="widget-platform",
        package_name=None,
        description="Workspace repo",
        repo_type="service",
        python_version="3.12",
        author="",
        output_dir=output_dir,
        no_install=True,
    )

    readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
    agents_text = (output_dir / "AGENTS.md").read_text(encoding="utf-8")
    workflow_text = (output_dir / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    pre_commit_text = (output_dir / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )

    assert "Python workspace" in readme_text
    assert (output_dir / ".github" / "workflows" / "quality.yml").exists()
    for command in MANDATORY_CI_COMMANDS:
        assert command in agents_text
        assert command in workflow_text
    for entry in MANDATORY_PRE_COMMIT_ENTRIES:
        assert entry in pre_commit_text
    assert not (output_dir / ".ruff_cache").exists()
    assert (output_dir / "packages" / ".gitkeep").exists()
    assert not (output_dir / "src").exists()


def test_pre_commit_configs_use_mandatory_local_uv_managed_hooks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_paths = [
        repo_root / ".pre-commit-config.yaml",
        *(
            starter_kit_dir(profile) / ".pre-commit-config.yaml"
            for profile in STARTER_KIT_PROFILES
        ),
    ]

    for config_path in config_paths:
        text = config_path.read_text(encoding="utf-8")
        assert "repo: local" in text
        for entry in MANDATORY_PRE_COMMIT_ENTRIES:
            assert entry in text
        assert "ruff-pre-commit" not in text


def test_tracked_starter_assets_do_not_contain_cache_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files", STARTER_KIT_ROOT.as_posix()],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked_files = result.stdout.splitlines()
    assert not any(
        any(part in IGNORED_ARTIFACT_PARTS for part in path.split("/"))
        or path.endswith(".pyc")
        for path in tracked_files
    )


def test_built_wheel_contains_clean_packaged_starter_kits(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(tmp_path),
            "--no-create-gitignore",
        ],
        cwd=repo_root,
        check=True,
    )

    wheel_path = next(tmp_path.glob("repo_standard_kit-*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    assert "repo_standard/starter_kits/python-single/AGENTS.md" in names
    assert "repo_standard/starter_kits/python-workspace/AGENTS.md" in names
    assert any(name.endswith(".dist-info/entry_points.txt") for name in names)
    assert not any(
        any(part in IGNORED_ARTIFACT_PARTS for part in name.split("/"))
        or name.endswith(".pyc")
        for name in names
    )


def test_bootstrap_repo_uses_uv_build_backend_for_python_single(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "demo-service"

    bootstrap_repo(
        profile="python-single",
        repo_name="demo-service",
        package_name="demo_service",
        description="Demo service",
        repo_type="service",
        python_version="3.12",
        author="",
        output_dir=output_dir,
        no_install=True,
    )

    pyproject_text = (output_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires = ["uv_build>=0.11.20,<0.12"]' in pyproject_text
    assert 'build-backend = "uv_build"' in pyproject_text
    assert 'module-name = "demo_service"' in pyproject_text


def test_quality_workflows_use_mandatory_ci_gate_set() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow_paths = [
        repo_root / ".github" / "workflows" / "quality.yml",
        *(
            starter_kit_dir(profile) / ".github" / "workflows" / "quality.yml"
            for profile in STARTER_KIT_PROFILES
        ),
    ]

    for workflow_path in workflow_paths:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        for command in MANDATORY_CI_COMMANDS:
            assert command in workflow_text


def test_root_pyproject_uses_uv_build_backend() -> None:
    pyproject_text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'requires = ["uv_build>=0.11.20,<0.12"]' in pyproject_text
    assert 'build-backend = "uv_build"' in pyproject_text
    assert 'module-name = "repo_standard"' in pyproject_text
    assert "source-exclude" in pyproject_text
    assert "[tool.hatch" not in pyproject_text


def test_validate_package_name_rejects_invalid_identifier() -> None:
    with pytest.raises(ValueError, match="valid Python identifier"):
        validate_package_name("not-valid")


def test_infer_package_name_normalizes_repo_name() -> None:
    assert infer_package_name("widget-api") == "widget_api"


def test_infer_repo_name_uses_target_directory_name(tmp_path: Path) -> None:
    assert infer_repo_name(tmp_path / "widget-platform") == "widget-platform"


def test_validate_repo_name_rejects_path_like_values() -> None:
    with pytest.raises(ValueError, match="must be a repository name, not a path"):
        validate_repo_name("foo/bar")


def test_resolve_output_dir_uses_repo_name_when_output_dir_not_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert resolve_output_dir(None, "widget-platform") == tmp_path / "widget-platform"


def test_resolve_output_dir_prefers_explicit_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert resolve_output_dir("custom-target", "widget-platform") == (
        tmp_path / "custom-target"
    )


def test_ensure_git_repository_initializes_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))

    monkeypatch.setattr(subprocess, "run", fake_run)

    ensure_git_repository(tmp_path)

    assert calls == [(["git", "init", "--initial-branch=main"], tmp_path)]
    assert "Initialized a local Git repository on main" in capsys.readouterr().err


def test_initialize_git_repository_falls_back_when_initial_branch_flag_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))
        if command == ["git", "init", "--initial-branch=main"]:
            raise subprocess.CalledProcessError(returncode=129, cmd=command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    initialize_git_repository(tmp_path)

    assert calls == [
        (["git", "init", "--initial-branch=main"], tmp_path),
        (["git", "init"], tmp_path),
        (["git", "branch", "-m", "main"], tmp_path),
    ]


def test_ensure_git_repository_skips_existing_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()

    def fail_run(command: list[str], *, cwd: Path, check: bool) -> None:
        raise AssertionError(f"subprocess.run should not be called: {command}")

    monkeypatch.setattr(subprocess, "run", fail_run)

    ensure_git_repository(tmp_path)


def test_ensure_git_repository_raises_clear_error_when_git_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_git(command: list[str], *, cwd: Path, check: bool) -> None:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", missing_git)

    with pytest.raises(RuntimeError, match="Install Git or rerun with --no-install"):
        ensure_git_repository(tmp_path)


def test_run_optional_installs_initializes_git_before_pre_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_optional_installs(tmp_path)

    assert calls == [
        (["uv", "sync"], tmp_path),
        (["git", "init", "--initial-branch=main"], tmp_path),
        (["uv", "run", "pre-commit", "install"], tmp_path),
    ]
    assert "Initialized a local Git repository on main" in capsys.readouterr().err


def test_run_optional_installs_skips_git_init_inside_existing_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> None:
        assert check is True
        calls.append((command, cwd))

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_optional_installs(tmp_path)

    assert calls == [
        (["uv", "sync"], tmp_path),
        (["uv", "run", "pre-commit", "install"], tmp_path),
    ]


def test_ensure_output_dir_rejects_non_empty_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    (output_dir / "marker.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="not empty"):
        ensure_output_dir(output_dir)


def test_ensure_no_unresolved_placeholders_rejects_leftovers(tmp_path: Path) -> None:
    file_path = tmp_path / "README.md"
    file_path.write_text("leftover __REPO_NAME__", encoding="utf-8")

    with pytest.raises(ValueError, match="Unresolved placeholders remain"):
        ensure_no_unresolved_placeholders(tmp_path)


def test_main_bootstraps_into_current_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--profile",
            "python-single",
            "--no-install",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    inferred_package = tmp_path.name.replace("-", "_")
    assert (tmp_path / "src" / inferred_package / "__init__.py").exists()
    readme_text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Describe this repository." in readme_text


def test_main_infers_repo_name_from_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "inferred-service"

    exit_code = main(
        [
            "--profile",
            "python-single",
            "--output-dir",
            str(output_dir),
            "--no-install",
        ]
    )

    assert exit_code == 0
    readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "# inferred-service" in readme_text
    assert (output_dir / "src" / "inferred_service" / "__init__.py").exists()
    assert "Describe this repository." in readme_text


def test_main_creates_repo_named_directory_when_repo_name_is_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--profile",
            "python-single",
            "--repo-name",
            "demo-service",
            "--no-install",
        ]
    )

    output_dir = tmp_path / "demo-service"
    assert exit_code == 0
    assert (output_dir / "AGENTS.md").exists()
    assert (output_dir / "src" / "demo_service" / "__init__.py").exists()
    readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "# demo-service" in readme_text


def test_main_uses_explicit_output_dir_when_repo_name_is_also_provided(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "custom-target"

    exit_code = main(
        [
            "--profile",
            "python-single",
            "--repo-name",
            "demo-service",
            "--output-dir",
            str(output_dir),
            "--no-install",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "AGENTS.md").exists()
    assert (output_dir / "src" / "demo_service" / "__init__.py").exists()
    readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "# demo-service" in readme_text


def test_main_rejects_path_like_repo_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="must be a repository name, not a path"):
        main(
            [
                "--profile",
                "python-single",
                "--repo-name",
                "foo/bar",
                "--no-install",
            ]
        )


def test_main_infers_workspace_repo_name_from_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_dir = tmp_path / "widget-platform"
    workspace_dir.mkdir()
    monkeypatch.chdir(workspace_dir)

    exit_code = main(
        [
            "--profile",
            "python-workspace",
            "--no-install",
        ]
    )

    assert exit_code == 0
    readme_text = (workspace_dir / "README.md").read_text(encoding="utf-8")
    assert "# widget-platform" in readme_text
    assert (workspace_dir / "packages" / ".gitkeep").exists()
    assert "Describe this repository." in readme_text


def _headings(path: Path) -> list[str]:
    return re.findall(
        r"^##\s+(.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE
    )


@pytest.mark.parametrize(
    "agents_path",
    [
        Path("AGENTS.md"),
        Path("templates/AGENTS.md"),
        *(
            starter_kit_dir(p).relative_to(REPO_ROOT) / "AGENTS.md"
            for p in STARTER_KIT_PROFILES
        ),
    ],
    ids=["repo-root", "template", "starter-single", "starter-workspace"],
)
def test_shipped_agents_files_carry_every_required_section(agents_path: Path) -> None:
    """Every AGENTS.md we ship carries the sections docs/repo-standard.md mandates."""
    headings = _headings(REPO_ROOT / agents_path)
    missing = [s for s in required_agents_sections() if s not in headings]
    assert not missing, f"{agents_path} is missing required sections: {missing}"


@pytest.mark.parametrize("profile", STARTER_KIT_PROFILES)
def test_generated_agents_files_carry_every_required_section(
    profile: str, tmp_path: Path
) -> None:
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
    headings = _headings(output_dir / "AGENTS.md")
    missing = [s for s in required_agents_sections() if s not in headings]
    assert not missing, f"generated {profile} AGENTS.md is missing: {missing}"


def test_gate_chain_is_defined_by_the_normative_document() -> None:
    """The chain must come from docs/quality-gates.md, not a literal in this file."""
    commands = mandatory_ci_commands()
    assert commands[0] == "uv sync --locked", (
        "the chain must start by verifying a reproducible environment"
    )
    assert commands[-1] == "uv build", "the chain must end with build validation"
    assert len(commands) == len(set(commands)), "duplicate gate in the spec"


def test_profiles_neither_add_nor_relax_gates() -> None:
    """Both profiles claim to defer to the spec; hold them to it."""
    for profile in STARTER_KIT_PROFILES:
        text = (REPO_ROOT / "profiles" / f"{profile}.md").read_text(encoding="utf-8")
        assert "docs/quality-gates.md" in text
        restated = [c for c in mandatory_ci_commands() if c in text]
        assert not restated, (
            f"profiles/{profile}.md restates gates instead of deferring: {restated}"
        )


@pytest.mark.parametrize(
    "agents_path",
    [
        Path("AGENTS.md"),
        Path("templates/AGENTS.md"),
        *(
            starter_kit_dir(p).relative_to(REPO_ROOT) / "AGENTS.md"
            for p in STARTER_KIT_PROFILES
        ),
    ],
    ids=["repo-root", "template", "starter-single", "starter-workspace"],
)
def test_shipped_agents_files_state_the_exact_gate_chain(agents_path: Path) -> None:
    """The contract requires exact gate commands in AGENTS.md; hold each copy to it."""
    text = (REPO_ROOT / agents_path).read_text(encoding="utf-8")
    missing = [c for c in mandatory_ci_commands() if c not in text]
    assert not missing, f"{agents_path} omits mandatory gates: {missing}"


def test_readme_template_defers_to_agents_for_the_gate_chain() -> None:
    """The README template's Quality Gates section points at AGENTS.md.

    Onboarding aids elsewhere in the template - the common-commands table, the
    setup steps - may name individual commands. What must not exist is a second
    authoritative copy of the chain competing with the one AGENTS.md carries.
    """
    text = (REPO_ROOT / "templates" / "README.md").read_text(encoding="utf-8")
    heading = "### Quality Gates"
    assert heading in text, "templates/README.md lost its Quality Gates section"
    section = text.split(heading, 1)[1].split("\n### ", 1)[0]

    restated = [c for c in mandatory_ci_commands() if c in section]
    assert not restated, (
        "templates/README.md restates the gate chain instead of deferring to "
        f"AGENTS.md: {restated}"
    )
    assert "AGENTS.md" in section, (
        "the Quality Gates section must point at AGENTS.md for the chain"
    )


def test_quality_gates_sections_are_sequentially_numbered() -> None:
    """Other documents cite this spec by section number; numbering must stay stable."""
    text = (REPO_ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
    numbers = [int(n) for n in re.findall(r"^##\s+(\d+)\.\s", text, re.MULTILINE)]
    assert numbers, "quality-gates.md lost its numbered sections"
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"sections must run 1..N with no gaps or reordering, got {numbers}"
    )


def test_every_cited_spec_section_exists() -> None:
    """A §N reference anywhere in the repo must resolve to a real section."""
    spec = (REPO_ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
    existing = {int(n) for n in re.findall(r"^##\s+(\d+)\.\s", spec, re.MULTILINE)}

    dangling: list[str] = []
    for path in REPO_ROOT.rglob("*.md"):
        if any(part in {".venv", "dist", "node_modules"} for part in path.parts):
            continue
        for cited in re.findall(r"§(\d+)", path.read_text(encoding="utf-8")):
            if int(cited) not in existing:
                dangling.append(f"{path.relative_to(REPO_ROOT)} cites §{cited}")
    assert not dangling, f"dangling spec citations: {dangling}"


def test_version_pin_examples_match_the_package_version() -> None:
    """Docs show a pinned install; the pin must be this version, not a stale one.

    This example has silently gone stale on every release so far. Asserting it
    against pyproject.toml turns "remember to bump the docs" into a gate.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert version_match, "could not read version from pyproject.toml"
    version = version_match.group(1)

    stale: list[str] = []
    for name in ("README.md", "docs/bootstrap-workflow.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for pinned in re.findall(r"repo-standard-kit\.git@v([0-9][^\"\s]*)", text):
            if pinned != version:
                stale.append(f"{name} pins v{pinned}, package is {version}")
    assert not stale, f"stale version-pin examples: {stale}"


@pytest.mark.parametrize(
    "pyproject_path",
    [
        Path("pyproject.toml"),
        *(
            starter_kit_dir(p).relative_to(REPO_ROOT) / "pyproject.toml"
            for p in STARTER_KIT_PROFILES
        ),
    ],
    ids=["repo-root", "starter-single", "starter-workspace"],
)
def test_ruff_config_matches_the_documented_baseline(pyproject_path: Path) -> None:
    """Passing the format gate is not enough; the config behind it must be the same."""
    documented = documented_ruff_baseline()
    actual = ruff_config_of(REPO_ROOT / pyproject_path)

    assert actual.line_length == documented.line_length, (
        f"{pyproject_path} sets line-length {actual.line_length}, "
        f"baseline requires {documented.line_length}"
    )
    missing = set(documented.select) - set(actual.select)
    assert not missing, (
        f"{pyproject_path} drops required rule families: {sorted(missing)}"
    )


def test_markdown_wraps_at_the_documented_prose_width() -> None:
    """The prose width in the formatting baseline applies to the docs we ship."""
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()

    over_long = [
        f"{name}:{line} ({width} cols)"
        for name in tracked
        for line, width in prose_offenders(REPO_ROOT / name)
    ]
    assert not over_long, f"prose exceeds {PROSE_WIDTH} columns: {over_long}"
