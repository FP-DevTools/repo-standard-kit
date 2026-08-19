"""Bootstrap a new repository from a starter kit."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from repo_standard.policy import load_compiled_policy

_POLICY = load_compiled_policy()
PLACEHOLDERS: dict[str, str] = dict(_POLICY.rule("RSK011").check.config["placeholders"])

IGNORED_STARTER_ENTRIES = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a new repository from the standard starter kits."
    )
    parser.add_argument("--profile", choices=_POLICY.profile_ids, required=True)
    parser.add_argument("--repo-name")
    parser.add_argument("--package-name")
    parser.add_argument("--description", default="Describe this repository.")
    parser.add_argument(
        "--repo-type",
        choices=["service", "library", "cli"],
        default="library",
    )
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--author", default="")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Target directory. Defaults to the current working directory.",
    )
    parser.add_argument("--no-install", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_package_name(package_name: str) -> None:
    if not package_name.isidentifier():
        raise ValueError(
            f"--package-name must be a valid Python identifier (got {package_name!r})"
        )


def validate_repo_name(repo_name: str) -> None:
    if "/" in repo_name or "\\" in repo_name or repo_name in {".", ".."}:
        raise ValueError(
            f"--repo-name must be a repository name, not a path (got {repo_name!r})"
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


def infer_repo_name(output_dir: Path) -> str:
    repo_name = output_dir.resolve().name
    if not repo_name:
        raise ValueError(
            "Could not infer a repository name from the target directory; "
            "pass --repo-name explicitly."
        )
    return repo_name


def resolve_output_dir(output_dir_arg: str | None, repo_name: str | None) -> Path:
    if output_dir_arg is not None:
        return Path(output_dir_arg).resolve()
    if repo_name is not None:
        validate_repo_name(repo_name)
        return (Path.cwd() / repo_name).resolve()
    return Path.cwd().resolve()


def resolve_starter_dir(profile: str) -> Path:
    return Path(__file__).resolve().parent / "starter_kits" / profile


def copy_starter(starter_dir: Path, output_dir: Path) -> None:
    def ignore_starter_entries(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name in IGNORED_STARTER_ENTRIES or name.endswith(".pyc")
        }

    for item in starter_dir.iterdir():
        if item.name in IGNORED_STARTER_ENTRIES or item.suffix == ".pyc":
            continue
        destination = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, ignore=ignore_starter_entries)
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


def has_git_repository(output_dir: Path) -> bool:
    return (output_dir / ".git").exists()


def initialize_git_repository(output_dir: Path) -> None:
    try:
        subprocess.run(
            ["git", "init", "--initial-branch=main"], cwd=output_dir, check=True
        )
        return
    except FileNotFoundError:
        raise
    except subprocess.CalledProcessError:
        subprocess.run(["git", "init"], cwd=output_dir, check=True)
        subprocess.run(["git", "branch", "-m", "main"], cwd=output_dir, check=True)


def ensure_git_repository(output_dir: Path) -> None:
    if has_git_repository(output_dir):
        return
    try:
        initialize_git_repository(output_dir)
    except FileNotFoundError as error:
        raise RuntimeError(
            "Git is required to install pre-commit hooks automatically. "
            "Install Git or rerun with --no-install."
        ) from error
    print(
        "Initialized a local Git repository on main so pre-commit hooks can be "
        "installed. Add or change the remote later as needed.",
        file=sys.stderr,
    )


def run_optional_installs(output_dir: Path) -> None:
    try:
        subprocess.run(["uv", "sync"], cwd=output_dir, check=True)
    except FileNotFoundError:
        print(
            "Skipped uv sync because the executable was not found.",
            file=sys.stderr,
        )
        return

    ensure_git_repository(output_dir)
    try:
        subprocess.run(
            ["uv", "run", "pre-commit", "install"], cwd=output_dir, check=True
        )
    except FileNotFoundError:
        print(
            "Skipped uv run pre-commit install because the executable was not found.",
            file=sys.stderr,
        )


def bootstrap_repo(
    *,
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
    if profile == "python-single":
        package_name = package_name or infer_package_name(repo_name)
        validate_package_name(package_name)
    elif package_name is not None:
        raise ValueError("--package-name is only valid for python-single repos.")

    starter_dir = resolve_starter_dir(profile)
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
    output_dir = resolve_output_dir(args.output_dir, args.repo_name)
    if args.repo_name is not None:
        validate_repo_name(args.repo_name)
    repo_name = args.repo_name or infer_repo_name(output_dir)

    bootstrap_repo(
        profile=args.profile,
        repo_name=repo_name,
        package_name=args.package_name,
        description=args.description,
        repo_type=args.repo_type,
        python_version=args.python_version,
        author=args.author,
        output_dir=output_dir,
        no_install=args.no_install,
    )
    print(f"Bootstrapped {repo_name} into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
