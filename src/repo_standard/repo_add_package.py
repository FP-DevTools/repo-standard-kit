"""Add a package to a Python workspace repository."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add a package project to a Python workspace repository."
    )
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--package-slug")
    parser.add_argument("--package-path")
    parser.add_argument("--description", default="Describe this package.")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_package_name(package_name: str) -> None:
    if not package_name.isidentifier():
        raise ValueError(
            f"--package-name must be a valid Python identifier (got {package_name!r})"
        )


def derive_package_slug(package_name: str) -> str:
    return package_name.replace("_", "-").lower()


def resolve_package_path(
    repo_root: Path, package_slug: str, package_path_arg: str | None
) -> Path:
    if package_path_arg is None:
        return repo_root / "packages" / package_slug
    package_path = (repo_root / package_path_arg).resolve()
    packages_root = (repo_root / "packages").resolve()
    if packages_root not in package_path.parents:
        raise ValueError("Package path must live under packages/.")
    return package_path


def ensure_workspace_root(repo_root: Path) -> None:
    packages_dir = repo_root / "packages"
    if not packages_dir.exists():
        raise ValueError(
            "Current directory is not a bootstrapped Python workspace repo."
        )


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_package(
    *,
    repo_root: Path,
    package_name: str,
    package_slug: str,
    package_path: Path,
    description: str,
) -> Path:
    validate_package_name(package_name)
    ensure_workspace_root(repo_root)
    if package_path.exists():
        raise ValueError(f"Package path already exists: {package_path}")

    write_file(
        package_path / "pyproject.toml",
        (
            "[project]\n"
            f'name = "{package_slug}"\n'
            'version = "0.1.0"\n'
            f'description = "{description}"\n'
            'readme = "README.md"\n'
            'requires-python = ">=3.12"\n'
            "dependencies = []\n\n"
            "[build-system]\n"
            'requires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
        ),
    )
    write_file(
        package_path / "README.md",
        f"# {package_slug}\n\n{description}\n",
    )
    write_file(
        package_path / "src" / package_name / "__init__.py",
        f'"""{package_name} package."""\n',
    )
    write_file(
        package_path / "tests" / "test_smoke.py",
        (
            "import importlib\n\n\n"
            "def test_package_imports() -> None:\n"
            f'    module = importlib.import_module("{package_name}")\n'
            "    assert module.__doc__ is not None\n"
        ),
    )
    return package_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path.cwd()
    package_name = args.package_name
    validate_package_name(package_name)
    package_slug = args.package_slug or derive_package_slug(package_name)
    package_path = resolve_package_path(repo_root, package_slug, args.package_path)

    create_package(
        repo_root=repo_root,
        package_name=package_name,
        package_slug=package_slug,
        package_path=package_path,
        description=args.description,
    )
    print(f"Added package {package_name} at {package_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
