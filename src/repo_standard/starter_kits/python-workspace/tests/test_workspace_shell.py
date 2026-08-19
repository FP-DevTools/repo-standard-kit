"""Runs even before the first package exists, so the gate chain is green from birth."""

from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def test_packages_directory_exists() -> None:
    assert (ROOT / "packages").is_dir()


def test_workspace_registers_packages_as_members() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    members = data["tool"]["uv"]["workspace"]["members"]
    assert "packages/*" in members
