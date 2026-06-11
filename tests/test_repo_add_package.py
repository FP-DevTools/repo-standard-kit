from __future__ import annotations

from pathlib import Path

import pytest

from repo_standard.repo_add_package import (
    create_package,
    derive_package_slug,
    main,
    resolve_package_path,
    validate_package_name,
)


def bootstrap_workspace_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "workspace"
    (repo_root / "packages").mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname='workspace'\n", encoding="utf-8"
    )
    return repo_root


def test_create_package_creates_workspace_package(tmp_path: Path) -> None:
    repo_root = bootstrap_workspace_root(tmp_path)
    package_path = repo_root / "packages" / "widget-api"

    create_package(
        repo_root=repo_root,
        package_name="widget_api",
        package_slug="widget-api",
        package_path=package_path,
        description="Widget API package.",
    )

    assert (package_path / "pyproject.toml").exists()
    assert (package_path / "src" / "widget_api" / "__init__.py").exists()
    assert (package_path / "tests" / "test_smoke.py").exists()
    pyproject_text = (package_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires = ["uv_build>=0.11.20,<0.12"]' in pyproject_text
    assert 'build-backend = "uv_build"' in pyproject_text
    assert 'module-name = "widget_api"' in pyproject_text


def test_validate_package_name_rejects_invalid_identifier() -> None:
    with pytest.raises(ValueError, match="valid Python identifier"):
        validate_package_name("widget-api")


def test_derive_package_slug_uses_kebab_case() -> None:
    assert derive_package_slug("widget_api") == "widget-api"


def test_resolve_package_path_rejects_non_packages_path(tmp_path: Path) -> None:
    repo_root = bootstrap_workspace_root(tmp_path)

    with pytest.raises(ValueError, match="must live under packages"):
        resolve_package_path(repo_root, "widget-api", "libs/widget-api")


def test_main_adds_package_from_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = bootstrap_workspace_root(tmp_path)
    monkeypatch.chdir(repo_root)

    exit_code = main(
        [
            "--package-name",
            "widget_api",
            "--description",
            "Widget API package.",
        ]
    )

    assert exit_code == 0
    assert (repo_root / "packages" / "widget-api" / "src" / "widget_api").exists()
