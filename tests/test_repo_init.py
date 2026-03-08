from __future__ import annotations

from pathlib import Path

import pytest

from repo_standard.repo_init import (
    bootstrap_repo,
    ensure_no_unresolved_placeholders,
    ensure_output_dir,
    infer_package_name,
    main,
    validate_package_name,
)


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
    assert (output_dir / "packages" / ".gitkeep").exists()
    assert not (output_dir / "src").exists()


def test_validate_package_name_rejects_invalid_identifier() -> None:
    with pytest.raises(ValueError, match="valid Python identifier"):
        validate_package_name("not-valid")


def test_infer_package_name_normalizes_repo_name() -> None:
    assert infer_package_name("widget-api") == "widget_api"


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
            "--repo-name",
            "empty-dir-app",
            "--description",
            "Empty directory bootstrap",
            "--no-install",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "src" / "empty_dir_app" / "__init__.py").exists()
