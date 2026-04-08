#!/usr/bin/env python3
"""Bump gnuckle version across Python and npm metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "gnuckle" / "__init__.py"
VERSION_FILE = ROOT / "gnuckle" / "version.json"
PYPROJECT_FILE = ROOT / "pyproject.toml"
PACKAGE_FILE = ROOT / "package.json"
PYPROJECT_RE = re.compile(r'(?m)^version = "(?P<version>\d+\.\d+\.\d+)"$')


def read_current_version() -> str:
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str):
        raise SystemExit(f"Could not find version in {VERSION_FILE}")
    return version


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"Unknown bump part: {part}")


def replace_version(text: str, pattern: re.Pattern[str], new_version: str, file_path: Path) -> str:
    updated, count = pattern.subn(lambda m: m.group(0).replace(m.group("version"), new_version), text, count=1)
    if count != 1:
        raise SystemExit(f"Could not update version in {file_path}")
    return updated


def write_versions(new_version: str) -> None:
    VERSION_FILE.write_text(json.dumps({"version": new_version}, indent=2) + "\n", encoding="utf-8")

    pyproject_text = PYPROJECT_FILE.read_text(encoding="utf-8")
    PYPROJECT_FILE.write_text(
        replace_version(pyproject_text, PYPROJECT_RE, new_version, PYPROJECT_FILE),
        encoding="utf-8",
    )

    package_data = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    package_data["version"] = new_version
    PACKAGE_FILE.write_text(json.dumps(package_data, indent=2) + "\n", encoding="utf-8")


def run_git(args: list[str]) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bump_version.py",
        description="Bump gnuckle version across Python and npm metadata.",
    )
    parser.add_argument(
        "target",
        help="one of: major, minor, patch, or an explicit semantic version like 0.2.0",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="create a git commit after updating versions",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="create a git tag v<version> after updating versions",
    )
    args = parser.parse_args()

    current = read_current_version()
    if args.target in {"major", "minor", "patch"}:
        new_version = bump(current, args.target)
    else:
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.target):
            raise SystemExit("Explicit versions must look like X.Y.Z")
        new_version = args.target

    if new_version == current:
        raise SystemExit(f"Version already {current}")

    write_versions(new_version)

    print(f"updated version: {current} -> {new_version}")

    if args.commit:
        run_git(["add", str(VERSION_FILE), str(INIT_FILE), str(PYPROJECT_FILE), str(PACKAGE_FILE)])
        run_git(["commit", "-m", f"chore: bump version to {new_version}"])
        print(f"created commit: chore: bump version to {new_version}")

    if args.tag:
        run_git(["tag", f"v{new_version}"])
        print(f"created tag: v{new_version}")

    print("next:")
    print("  git push origin main")
    if args.tag:
        print("  git push origin --tags")


if __name__ == "__main__":
    main()
