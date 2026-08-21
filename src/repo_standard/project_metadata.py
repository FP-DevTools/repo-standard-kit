"""Shared project-metadata validation and parsing helpers."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError


def kit_version() -> str:
    """Return the running `repo-standard-kit` version.

    Installed metadata is the source: a wheel ships no `pyproject.toml`, so
    reading that file is only the fallback for a source checkout that has not
    been installed.
    """
    try:
        return importlib.metadata.version("repo-standard-kit")
    except importlib.metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        return str(
            tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        )


def validate_package_name(package_name: str) -> None:
    """Reject names that cannot become Python package directories."""
    if not package_name.isidentifier():
        raise ValueError(
            f"--package-name must be a valid Python identifier (got {package_name!r})"
        )


def workspace_requires_python(repo_root: Path) -> str:
    """Read the Python requirement declared by a workspace root."""
    path = repo_root / "pyproject.toml"
    try:
        document = tomlkit.parse(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError("Workspace root is missing pyproject.toml.") from error
    except (ParseError, UnicodeDecodeError) as error:
        raise ValueError(
            f"Could not parse workspace pyproject.toml: {error}"
        ) from error

    project = document.get("project")
    if not isinstance(project, dict):
        raise ValueError("Workspace pyproject.toml must contain a [project] table.")
    requires_python = project.get("requires-python")
    if not isinstance(requires_python, str) or not requires_python:
        raise ValueError(
            "Workspace pyproject.toml must declare a non-empty project.requires-python."
        )
    return requires_python
