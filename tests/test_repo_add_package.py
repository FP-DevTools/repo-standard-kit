from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from repo_standard.bootstrap_defaults import DEFAULT_UV_BUILD_REQUIREMENT
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
        '[project]\nname = "workspace"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
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
    pyproject = tomllib.loads(
        (package_path / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert pyproject["project"]["requires-python"] == ">=3.12"
    assert pyproject["build-system"]["requires"] == [DEFAULT_UV_BUILD_REQUIREMENT]
    assert pyproject["build-system"]["build-backend"] == "uv_build"
    assert pyproject["tool"]["uv"]["build-backend"]["module-name"] == "widget_api"


def test_validate_package_name_rejects_invalid_identifier() -> None:
    with pytest.raises(ValueError, match="valid Python identifier"):
        validate_package_name("widget-api")


def test_derive_package_slug_uses_kebab_case() -> None:
    assert derive_package_slug("widget_api") == "widget-api"


def test_package_uses_workspace_python_requirement_and_safe_toml_strings(
    tmp_path: Path,
) -> None:
    repo_root = bootstrap_workspace_root(tmp_path)
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "workspace"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    package_path = repo_root / "packages" / "quoted-package"

    create_package(
        repo_root=repo_root,
        package_name="quoted_package",
        package_slug="quoted-package",
        package_path=package_path,
        description='A "quoted" package\nwith Unicode: é.',
    )

    pyproject = tomllib.loads(
        (package_path / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert pyproject["project"]["description"] == 'A "quoted" package\nwith Unicode: é.'
    assert pyproject["project"]["requires-python"] == ">=3.13"


def test_missing_workspace_python_requirement_is_rejected(tmp_path: Path) -> None:
    repo_root = bootstrap_workspace_root(tmp_path)
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "workspace"\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="project.requires-python"):
        create_package(
            repo_root=repo_root,
            package_name="widget_api",
            package_slug="widget-api",
            package_path=repo_root / "packages" / "widget-api",
            description="Widget API package.",
        )


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
