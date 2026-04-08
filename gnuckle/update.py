"""Shared update helper for gnuckle."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from gnuckle import __version__


BANANA = "\U0001F34C"
PKG_ROOT = Path(__file__).resolve().parents[1]


def log(message: str) -> None:
    print(f"  {BANANA} {message}")


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=PKG_ROOT, check=True)


def _find_python() -> list[str] | None:
    candidates = [["python"], ["python3"]]
    if sys.platform.startswith("win"):
        candidates.append(["py", "-3"])

    for candidate in candidates:
        if shutil.which(candidate[0]):
            try:
                subprocess.run(
                    [*candidate, "--version"],
                    cwd=PKG_ROOT,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return candidate
            except subprocess.CalledProcessError:
                continue
    return None


def _tracked_python_caches() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*__pycache__*", "*.pyc"],
        cwd=PKG_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [PKG_ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def _remove_stale_caches() -> None:
    removed = 0
    for file_path in _tracked_python_caches():
        if not file_path.exists():
            continue
        try:
            file_path.unlink()
            removed += 1
        except OSError:
            continue
    if removed:
        log(f"cleared {removed} tracked python cache file(s) before pull")


def run_update() -> int:
    print()
    log(f"gnuckle v{__version__} update activated")
    log(f"updating clone at {PKG_ROOT}")
    log("user profiles in .gnuckle stay untouched")
    print()

    python_cmd = _find_python()
    if not python_cmd:
        log("ape no find python. install python 3.10+ first.")
        return 1

    _remove_stale_caches()

    try:
        log("git pull --ff-only")
        _run(["git", "pull", "--ff-only"])
    except subprocess.CalledProcessError as err:
        log("git pull failed. ape stop here so merge weirdness stay visible.")
        return err.returncode or 1

    try:
        log("npm install")
        _run(["npm", "install"])
    except subprocess.CalledProcessError as err:
        log("npm install failed. ape cannot finish update.")
        return err.returncode or 1

    try:
        log("python -m pip install -e .")
        _run([*python_cmd, "-m", "pip", "install", "-e", "."])
    except subprocess.CalledProcessError as err:
        log("pip editable install failed. ape cannot finish update.")
        return err.returncode or 1

    print()
    log("update complete. latest banana acquired.")
    print()
    return 0
