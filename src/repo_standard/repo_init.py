"""Bootstrap a new repository from a starter kit."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import tomlkit

from repo_standard.bootstrap_defaults import DEFAULT_PYTHON_VERSION
from repo_standard.policy import load_compiled_policy
from repo_standard.project_metadata import validate_package_name

_POLICY = load_compiled_policy()
PLACEHOLDERS: dict[str, str] = dict(_POLICY.rule("RSK011").check.config["placeholders"])

IGNORED_STARTER_ENTRIES = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".ty_cache",
}

# Each selectable licence maps to its shipped text and its SPDX expression.
LICENSE_EXPRESSIONS: dict[str, str] = {
    "proprietary": "LicenseRef-Proprietary",
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
}

LICENSE_NOTICES: dict[str, str] = {
    "proprietary": (
        "Proprietary. All rights reserved. See [`LICENSE`](LICENSE) for the "
        "terms that apply."
    ),
    "mit": "Released under the MIT License. See [`LICENSE`](LICENSE).",
    "apache-2.0": ("Released under the Apache License 2.0. See [`LICENSE`](LICENSE)."),
}

UNLICENSED_NOTICE = (
    "Licence terms have not been selected for this repository yet, so no "
    "`LICENSE` file is present. RSK018 recommends adding one: rerun `repo-init` "
    "with `--license`, or add the terms your organisation has approved before "
    "sharing this repository."
)

_COPYRIGHT_YEAR = "__COPYRIGHT_YEAR__"
_COPYRIGHT_HOLDER = "__COPYRIGHT_HOLDER__"


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
    parser.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION)
    parser.add_argument("--author", default="")
    parser.add_argument(
        "--license",
        choices=sorted(LICENSE_EXPRESSIONS),
        default=None,
        help=(
            "Licence to write as LICENSE and declare in pyproject.toml. "
            "Omitted, no LICENSE is written and README states that terms are "
            "not yet selected."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Target directory. Defaults to the current working directory.",
    )
    parser.add_argument("--no-lock", action="store_true")
    parser.add_argument("--no-install", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


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
        if path == output_dir / "pyproject.toml":
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


def resolve_license_dir() -> Path:
    return Path(__file__).resolve().parent / "licenses"


def license_notice(license_id: str | None) -> str:
    """Return the README License body for the selected licence, if any."""
    return UNLICENSED_NOTICE if license_id is None else LICENSE_NOTICES[license_id]


def render_license(license_id: str, holder: str, year: int) -> str:
    text = (resolve_license_dir() / f"{license_id}.txt").read_text(encoding="utf-8")
    return text.replace(_COPYRIGHT_YEAR, str(year)).replace(_COPYRIGHT_HOLDER, holder)


def write_license(output_dir: Path, license_id: str, holder: str) -> None:
    (output_dir / "LICENSE").write_text(
        render_license(license_id, holder, date.today().year), encoding="utf-8"
    )


def apply_project_metadata(
    output_dir: Path,
    *,
    profile: str,
    repo_name: str,
    package_name: str | None,
    description: str,
    python_version: str,
    author: str,
    license_id: str | None,
) -> None:
    """Complete `[project]` fields that depend on optional bootstrap flags.

    The starter manifest stays parseable while all user-controlled TOML values
    are assigned through tomlkit rather than substituted as raw text.
    """
    path = output_dir / "pyproject.toml"
    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    project = document["project"]
    project["name"] = (
        f"{repo_name}-workspace" if profile == "python-workspace" else repo_name
    )
    project["description"] = description
    project["requires-python"] = f">={python_version}"
    if not author:
        del project["authors"]
    else:
        project["authors"] = [{"name": author}]
    if license_id is not None:
        project["license"] = LICENSE_EXPRESSIONS[license_id]
        project["license-files"] = ["LICENSE"]
    if package_name is not None:
        document["tool"]["uv"]["build-backend"]["module-name"] = package_name
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


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


def run_lock(output_dir: Path) -> None:
    try:
        subprocess.run(["uv", "lock"], cwd=output_dir, check=True)
    except FileNotFoundError:
        print(
            "Skipped uv lock because the executable was not found.",
            file=sys.stderr,
        )
    except subprocess.CalledProcessError as error:
        print(
            f"uv lock failed with exit status {error.returncode}.",
            file=sys.stderr,
        )


def warn_when_lock_file_missing(output_dir: Path) -> None:
    """Name RSK009 when bootstrap produced no lock file, for whatever reason."""
    if (output_dir / "uv.lock").is_file():
        return
    print(
        "No uv.lock was produced, so repo-check reports required finding RSK009. "
        "Run `uv lock` in the new repository before committing.",
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
    license_id: str | None,
    output_dir: Path,
    no_lock: bool,
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
        "license_notice": license_notice(license_id),
    }
    render_text_files(output_dir, values)
    if package_name is not None:
        rename_package_dir(output_dir, package_name)
    if license_id is not None:
        write_license(output_dir, license_id, author or repo_name)
    apply_project_metadata(
        output_dir,
        profile=profile,
        repo_name=repo_name,
        package_name=package_name,
        description=description,
        python_version=python_version,
        author=author,
        license_id=license_id,
    )
    ensure_no_unresolved_placeholders(output_dir)

    if not no_lock:
        run_lock(output_dir)
    if not no_install:
        run_optional_installs(output_dir)
    warn_when_lock_file_missing(output_dir)

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
        license_id=args.license,
        output_dir=output_dir,
        no_lock=args.no_lock,
        no_install=args.no_install,
    )
    print(f"Bootstrapped {repo_name} into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
