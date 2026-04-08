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
    subprocess.run(_resolve_command(command), cwd=PKG_ROOT, check=True)


def _run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _resolve_command(command),
        cwd=PKG_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        raise ValueError("empty command")
    executable = command[0]
    resolved = shutil.which(executable)
    if resolved is None:
        raise FileNotFoundError(f"command not found: {executable}")
    return [resolved, *command[1:]]


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


def _has_command(name: str) -> bool:
    return shutil.which(name) is not None


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


def _remove_generated_dirs() -> None:
    removed: list[str] = []
    for relative in ("gnuckle.egg-info", "node_modules"):
        path = PKG_ROOT / relative
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(relative)

    package_lock = PKG_ROOT / "package-lock.json"
    if package_lock.exists():
        try:
            package_lock.unlink()
            removed.append("package-lock.json")
        except OSError:
            pass

    if removed:
        log(f"cleared generated local state: {', '.join(removed)}")


def _working_tree_dirty() -> bool:
    result = _run_capture(["git", "status", "--porcelain"])
    if result.returncode != 0:
        return False
    return bool(result.stdout.strip())


def _stash_worktree_changes() -> str | None:
    result = _run_capture(
        [
            "git",
            "stash",
            "push",
            "--include-untracked",
            "--message",
            "gnuckle-update-autostash",
            "--",
            ".",
            ":(exclude).gnuckle",
            ":(exclude).gnuckle/**",
        ]
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    output = result.stdout.strip()
    if "No local changes to save" in output:
        return None
    log("stashed local repo changes for update")
    stash_list = _run_capture(["git", "stash", "list"])
    if stash_list.returncode != 0:
        return None
    for line in stash_list.stdout.splitlines():
        if "gnuckle-update-autostash" in line:
            return line.split(":", 1)[0]
    return "stash@{0}"


def _restore_stash(stash_ref: str | None) -> None:
    if not stash_ref:
        return
    result = _run_capture(["git", "stash", "pop", stash_ref])
    if result.returncode == 0:
        log("restored local repo changes after update")
        return
    log("stash pop had conflicts. ape keep stash for manual recovery.")
    log(f"recover with: git stash list / git stash show -p {stash_ref}")


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
    _remove_generated_dirs()

    stash_ref = None
    if _working_tree_dirty():
        try:
            stash_ref = _stash_worktree_changes()
        except subprocess.CalledProcessError as err:
            log("could not stash local repo changes. ape stop here.")
            return err.returncode or 1

    try:
        log("git pull --ff-only")
        _run(["git", "pull", "--ff-only"])
    except (subprocess.CalledProcessError, OSError) as err:
        log("git pull failed. ape stop here so merge weirdness stay visible.")
        return getattr(err, "returncode", 1) or 1

    if _has_command("npm"):
        try:
            log("npm install")
            _run(["npm", "install"])
        except (subprocess.CalledProcessError, OSError) as err:
            log("npm install failed. ape cannot finish update.")
            return getattr(err, "returncode", 1) or 1
    else:
        log("npm not found in this shell. ape skip npm install.")

    try:
        log("python -m pip install -e .")
        _run([*python_cmd, "-m", "pip", "install", "-e", "."])
    except (subprocess.CalledProcessError, OSError) as err:
        log("pip editable install failed. ape cannot finish update.")
        return getattr(err, "returncode", 1) or 1

    _restore_stash(stash_ref)

    print()
    log("update complete. latest banana acquired.")
    print()
    return 0
