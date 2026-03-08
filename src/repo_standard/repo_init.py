"""Bootstrap a new repository from a starter kit."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE_ALIASES = {
    "python": "python-single",
}

PLACEHOLDERS = {
    "__REPO_NAME__": "repo_name",
    "__PACKAGE_NAME__": "package_name",
    "__DESCRIPTION__": "description",
    "__REPO_TYPE__": "repo_type",
    "__PYTHON_VERSION__": "python_version",
    "__AUTHOR__": "author",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a new repository from the standard starter kits."
    )
    parser.add_argument(
        "--profile",
        choices=["python", "python-single", "python-workspace"],
        required=True,
    )
    parser.add_argument("--repo-name", required=True)
    parser.add_argument("--package-name")
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--repo-type",
        choices=["service", "library", "cli"],
        default="library",
    )
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--author", default="")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Target directory. Defaults to the current working directory.",
    )
    parser.add_argument("--no-install", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def normalize_profile(profile: str) -> str:
    return PROFILE_ALIASES.get(profile, profile)


def validate_package_name(package_name: str) -> None:
    if not package_name.isidentifier():
        raise ValueError(
            f"--package-name must be a valid Python identifier (got {package_name!r})"
        )


def ensure_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(
            f"Output directory {output_dir} already exists and is not empty."
        )
    output_dir.mkdir(parents=True, exist_ok=True)


def infer_package_name(repo_name: str) -> str:
    candidate = repo_name.replace("-", "_").lower()
    if not candidate.isidentifier():
        raise ValueError(
            "Could not infer a valid package name from --repo-name; "
            "pass --package-name explicitly."
        )
    return candidate


def resolve_starter_dir(profile: str, repo_root: Path | None = None) -> Path:
    profile = normalize_profile(profile)
    if repo_root is not None:
        candidate = repo_root / "starter-kits" / profile
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent / "starter_kits" / profile


def copy_starter(starter_dir: Path, output_dir: Path) -> None:
    for item in starter_dir.iterdir():
        destination = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def render_text_files(output_dir: Path, values: dict[str, str]) -> None:
    for path in output_dir.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for placeholder, key in PLACEHOLDERS.items():
            text = text.replace(placeholder, values[key])
        path.write_text(text, encoding="utf-8")


def ensure_no_unresolved_placeholders(output_dir: Path) -> None:
    unresolved: list[str] = []
    placeholder_tokens = tuple(PLACEHOLDERS)
    for path in output_dir.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        matches = [token for token in placeholder_tokens if token in text]
        if matches:
            unresolved.append(f"{path.relative_to(output_dir)}: {', '.join(matches)}")
    if unresolved:
        details = "; ".join(unresolved)
        raise ValueError(f"Unresolved placeholders remain after bootstrap: {details}")


def rename_package_dir(output_dir: Path, package_name: str) -> None:
    source_dir = output_dir / "src" / "package_name"
    if source_dir.exists():
        source_dir.rename(output_dir / "src" / package_name)


def update_python_version(output_dir: Path, python_version: str) -> None:
    pyproject_path = output_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return
    text = pyproject_path.read_text(encoding="utf-8")
    text = text.replace(
        'requires-python = ">=3.12"',
        f'requires-python = ">={python_version}"',
    )
    pyproject_path.write_text(text, encoding="utf-8")


def run_optional_installs(output_dir: Path) -> None:
    commands = [
        ["uv", "sync"],
        ["uv", "run", "pre-commit", "install"],
    ]
    for command in commands:
        try:
            subprocess.run(command, cwd=output_dir, check=True)
        except FileNotFoundError:
            print(
                f"Skipped {' '.join(command)} because the executable was not found.",
                file=sys.stderr,
            )
            return


def bootstrap_repo(
    *,
    repo_root: Path,
    profile: str,
    repo_name: str,
    package_name: str | None,
    description: str,
    repo_type: str,
    python_version: str,
    author: str,
    output_dir: Path,
    no_install: bool,
) -> Path:
    profile = normalize_profile(profile)
    if profile == "python-single":
        package_name = package_name or infer_package_name(repo_name)
        validate_package_name(package_name)
    elif package_name is not None:
        raise ValueError("--package-name is only valid for python-single repos.")

    starter_dir = resolve_starter_dir(profile, repo_root)
    ensure_output_dir(output_dir)
    copy_starter(starter_dir, output_dir)

    values = {
        "repo_name": repo_name,
        "package_name": package_name or "",
        "description": description,
        "repo_type": repo_type,
        "python_version": python_version,
        "author": author,
    }
    render_text_files(output_dir, values)
    if package_name is not None:
        rename_package_dir(output_dir, package_name)
    update_python_version(output_dir, python_version)
    ensure_no_unresolved_placeholders(output_dir)

    if not no_install:
        run_optional_installs(output_dir)

    return output_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output_dir).resolve()

    bootstrap_repo(
        repo_root=repo_root,
        profile=args.profile,
        repo_name=args.repo_name,
        package_name=args.package_name,
        description=args.description,
        repo_type=args.repo_type,
        python_version=args.python_version,
        author=args.author,
        output_dir=output_dir,
        no_install=args.no_install,
    )
    print(f"Bootstrapped {args.repo_name} into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
