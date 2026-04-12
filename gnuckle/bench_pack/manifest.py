"""Manifest loading, lockfile handling, and tamper detection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gnuckle.bench_pack.schema import ManifestModel, validate_manifest_dict
from gnuckle.bench_pack.trust import benchmarks_dir, ensure_home_layout, lock_path, set_readonly


class ManifestTamperError(RuntimeError):
    """Raised when an installed manifest no longer matches the lockfile."""


def _reject_duplicate_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key: {key}")
        out[key] = value
    return out


def _parse_scalar(value: str):
    if value in ("null", "~"):
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _next_meaningful(lines: list[str], index: int) -> int:
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped and not stripped.startswith("#"):
            break
        index += 1
    return index


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_mapping_lines(lines: list[str], index: int, indent: int, initial: dict | None = None):
    output = dict(initial or {})
    index = _next_meaningful(lines, index)
    while index < len(lines):
        raw = lines[index]
        current_indent = _indent_of(raw)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"unexpected indentation at line {index + 1}")
        stripped = raw.strip()
        if stripped.startswith("- "):
            break
        if ":" not in stripped:
            raise ValueError(f"expected mapping entry at line {index + 1}")
        key, rest = stripped.split(":", 1)
        key = key.strip()
        if key in output:
            raise ValueError(f"duplicate key: {key}")
        rest = rest.lstrip()
        if rest == ">":
            index += 1
            parts = []
            while index < len(lines):
                child = lines[index]
                child_indent = _indent_of(child)
                if child.strip() and child_indent <= indent:
                    break
                if child.strip():
                    parts.append(child.strip())
                index += 1
            output[key] = " ".join(parts)
            continue
        if rest == "":
            child_index = _next_meaningful(lines, index + 1)
            if child_index >= len(lines) or _indent_of(lines[child_index]) <= indent:
                output[key] = {}
                index = child_index
                continue
            if lines[child_index].strip().startswith("- "):
                value, index = _parse_sequence(lines, child_index, indent + 2)
            else:
                value, index = _parse_mapping_lines(lines, child_index, indent + 2)
            output[key] = value
            continue
        output[key] = _parse_scalar(rest)
        index += 1
        index = _next_meaningful(lines, index)
    return output, index


def _parse_sequence(lines: list[str], index: int, indent: int):
    output = []
    index = _next_meaningful(lines, index)
    while index < len(lines):
        raw = lines[index]
        current_indent = _indent_of(raw)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"unexpected indentation at line {index + 1}")
        stripped = raw.strip()
        if not stripped.startswith("- "):
            break
        item = stripped[2:].lstrip()
        if not item:
            child_index = _next_meaningful(lines, index + 1)
            if child_index >= len(lines) or _indent_of(lines[child_index]) <= indent:
                output.append({})
                index = child_index
                continue
            if lines[child_index].strip().startswith("- "):
                value, index = _parse_sequence(lines, child_index, indent + 2)
            else:
                value, index = _parse_mapping_lines(lines, child_index, indent + 2)
            output.append(value)
            continue
        if ":" in item and not item.startswith(("'", '"', "[")):
            key, rest = item.split(":", 1)
            seed = {key.strip(): _parse_scalar(rest.lstrip()) if rest.strip() else {}}
            value, index = _parse_mapping_lines(lines, index + 1, indent + 2, initial=seed)
            output.append(value)
            continue
        output.append(_parse_scalar(item))
        index += 1
        index = _next_meaningful(lines, index)
    return output, index


def parse_manifest_text(text: str) -> dict:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("manifest is empty")
    if stripped[0] in "{[":
        return json.loads(stripped, object_pairs_hook=_reject_duplicate_pairs)
    lines = text.splitlines()
    parsed, index = _parse_mapping_lines(lines, 0, 0)
    index = _next_meaningful(lines, index)
    if index < len(lines):
        raise ValueError(f"unexpected trailing content at line {index + 1}")
    return parsed


def manifest_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def load_manifest_file(path: Path, *, trust_url: bool = False) -> tuple[ManifestModel, str, str]:
    text = path.read_text(encoding="utf-8")
    data = parse_manifest_text(text)
    manifest = validate_manifest_dict(data, trust_url=trust_url)
    return manifest, text, manifest_sha256(text)


def load_lockfile() -> dict:
    ensure_home_layout()
    try:
        return json.loads(lock_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_lockfile(data: dict) -> None:
    ensure_home_layout()
    lock_path().write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    set_readonly(lock_path())


def install_manifest(manifest: ManifestModel, manifest_text: str, manifest_hash: str) -> Path:
    ensure_home_layout()
    target_dir = benchmarks_dir() / manifest.id
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.yaml"
    sha_path = target_dir / "manifest.sha256"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    sha_path.write_text(manifest_hash + "\n", encoding="utf-8")
    set_readonly(manifest_path)
    set_readonly(sha_path)

    lock = load_lockfile()
    lock[manifest.id] = {
        "version": manifest.version,
        "manifest_sha256": manifest_hash,
    }
    save_lockfile(lock)
    return manifest_path


def verify_installed_manifest(pack_id: str) -> tuple[ManifestModel, str, Path]:
    ensure_home_layout()
    manifest_path = benchmarks_dir() / pack_id / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"pack is not installed: {pack_id}")
    manifest, text, current_hash = load_manifest_file(manifest_path, trust_url=True)
    lock = load_lockfile()
    expected_hash = ((lock.get(pack_id) or {}).get("manifest_sha256") or "").strip()
    if not expected_hash or expected_hash != current_hash:
        raise ManifestTamperError(f"manifest tamper detected for {pack_id}")
    return manifest, current_hash, manifest_path
