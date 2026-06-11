from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


def collect_relative_files(root: Path) -> set[Path]:
    ignored_dirs = {".ruff_cache", ".pytest_cache", ".mypy_cache", ".ty_cache"}
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and not any(
            part in ignored_dirs or part == "__pycache__" for part in path.parts
        )
        and path.suffix != ".pyc"
    }


def assert_directory_contents_match(source: Path, packaged: Path) -> None:
    source_files = collect_relative_files(source)
    packaged_files = collect_relative_files(packaged)
    assert packaged_files == source_files
    for relative_path in sorted(source_files):
        assert (packaged / relative_path).read_text(encoding="utf-8") == (
            source / relative_path
        ).read_text(encoding="utf-8")


def test_bootstrap_repo_renders_python_single_starter(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "demo-service"

    bootstrap_repo(
        repo_root=repo_root,
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

    assert "__REPO_NAME__" not in agents_text
    assert "demo-service" in pyproject_text
    assert 'importlib.import_module("demo_service")' in smoke_test_text
    assert "## First 10 Minutes" in readme_text
    assert (output_dir / ".github" / "workflows" / "quality.yml").exists()
    assert not (output_dir / ".ruff_cache").exists()
    assert (output_dir / "src" / "demo_service" / "__init__.py").exists()
    assert not (output_dir / "src" / "package_name").exists()


def test_bootstrap_repo_infers_package_name_for_python_single(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "demo-service"

    bootstrap_repo(
        repo_root=repo_root,
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
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "widget-platform"

    bootstrap_repo(
        repo_root=repo_root,
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
    assert "Python workspace" in readme_text
    assert (output_dir / ".github" / "workflows" / "quality.yml").exists()
    assert not (output_dir / ".ruff_cache").exists()
    assert (output_dir / "packages" / ".gitkeep").exists()
    assert not (output_dir / "src").exists()


def test_packaged_starter_kits_match_source_assets() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for profile in ("python-single", "python", "python-workspace"):
        assert_directory_contents_match(
            repo_root / "starter-kits" / profile,
            repo_root / "src" / "repo_standard" / "starter_kits" / profile,
        )


def test_quality_workflow_uses_standard_python_chain() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "quality.yml"
    )
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "uv sync" in workflow_text
    assert "uv run pre-commit run --all-files" in workflow_text
    assert "uv run ruff format --check ." in workflow_text
    assert "uv run ruff check ." in workflow_text
    assert "uv run ty check" in workflow_text
    assert "uv run pytest" in workflow_text


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
