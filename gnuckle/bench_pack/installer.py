"""Install, remove, and verify benchmark packs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from gnuckle import __version__
from gnuckle.bench_pack.manifest import install_manifest, load_manifest_file, verify_installed_manifest
from gnuckle.bench_pack.registry import get_pack_info
from gnuckle.bench_pack.trust import (
    INSTALL_DISCLAIMER,
    TRUSTED_DATASET_HOSTS,
    append_audit_log,
    benchmarks_dir,
    datasets_dir,
    ensure_home_layout,
    read_config,
    set_readonly,
)


class RecoverableInstallError(RuntimeError):
    """Recoverable install problem."""


def _clear_readonly(func, path, _exc_info) -> None:
    os.chmod(path, 0o666)
    func(path)


def _download_bytes(url: str, *, size_limit: int) -> bytes:
    request = Request(url, headers={"User-Agent": f"gnuckle/{__version__}"})
    with urlopen(request, timeout=60) as response:
        final_url = response.geturl()
        final_host = urlsplit(final_url).hostname or ""
        if final_host and final_host != (urlsplit(url).hostname or "") and final_host not in TRUSTED_DATASET_HOSTS:
            raise RecoverableInstallError("redirected to non-trusted host")
        chunks = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > size_limit:
                raise RecoverableInstallError("download exceeded declared size cap")
            chunks.append(chunk)
    return b"".join(chunks)


def _verify_dataset_url(url: str, *, trust_url: bool) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise RecoverableInstallError("dataset URL must use https")
    host = parsed.hostname or ""
    config = read_config()
    extra_trusted = set(config.get("trusted_urls", []))
    if host not in TRUSTED_DATASET_HOSTS and host not in extra_trusted and not trust_url:
        raise RecoverableInstallError(f"dataset host not trusted: {host}")


def _safe_extract_zip(archive_path: Path, target_dir: Path, *, size_limit: int) -> list[Path]:
    extracted_paths = []
    total_size = 0
    target_root = target_dir.resolve()
    with zipfile.ZipFile(archive_path) as zf:
        for info in zf.infolist():
            if info.file_size > size_limit:
                raise RecoverableInstallError("zip entry exceeds declared size cap")
            total_size += info.file_size
            if total_size > size_limit:
                raise RecoverableInstallError("zip extraction exceeds declared size cap")
            name = info.filename
            if any(ch in name for ch in ("\x00", ":")):
                raise RecoverableInstallError("zip entry name contains forbidden characters")
            if name.startswith("/") or name.startswith("\\") or name.startswith("-"):
                raise RecoverableInstallError("zip entry path is unsafe")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RecoverableInstallError("zip symlink entries are not allowed")
            destination = (target_dir / name).resolve()
            if target_root not in destination.parents and destination != target_root:
                raise RecoverableInstallError("zip entry path traversal detected")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith("/"):
                destination.mkdir(parents=True, exist_ok=True)
                continue
            with zf.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted_paths.append(destination)
    return extracted_paths


def _install_dataset(manifest, *, trust_url: bool) -> dict:
    if manifest.dataset is None:
        return {}
    _verify_dataset_url(manifest.dataset.url, trust_url=trust_url)
    ensure_home_layout()
    dataset_root = datasets_dir() / manifest.dataset.id
    if dataset_root.exists():
        return {"dataset_path": str(dataset_root)}
    dataset_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "dataset.tmp"
        try:
            payload = _download_bytes(manifest.dataset.url, size_limit=manifest.dataset.size_bytes_max)
            tmp_path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != manifest.dataset.sha256:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
                raise RecoverableInstallError("dataset SHA256 mismatch")
            if manifest.dataset.archive == "zip":
                extracted = _safe_extract_zip(tmp_path, dataset_root, size_limit=manifest.dataset.size_bytes_max)
                if manifest.dataset.extract:
                    expected = (dataset_root / manifest.dataset.extract).resolve()
                    if expected not in extracted and not expected.exists():
                        raise RecoverableInstallError("expected extracted dataset file missing")
            else:
                target_path = dataset_root / (manifest.dataset.extract or Path(urlsplit(manifest.dataset.url).path).name)
                shutil.copy2(tmp_path, target_path)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(dataset_root, ignore_errors=True)
            raise RecoverableInstallError("dataset archive is invalid") from exc
        except Exception:
            if dataset_root.exists() and not any(dataset_root.iterdir()):
                shutil.rmtree(dataset_root, ignore_errors=True)
            raise
    return {"dataset_path": str(dataset_root)}


def _manifest_preview(manifest, manifest_hash: str) -> str:
    lines = [
        f"Installing benchmark pack: {manifest.id} @ {manifest.version}",
        f"  Author: {manifest.author.name}" + (f" <{manifest.author.contact}>" if manifest.author.contact else ""),
        f"  License: {manifest.license}",
        f"  Binary required: {manifest.binary} (allowlisted)",
    ]
    if manifest.dataset is not None:
        host = urlsplit(manifest.dataset.url).hostname or "unknown"
        trusted = "trusted host" if host in TRUSTED_DATASET_HOSTS else "untrusted host"
        lines.extend([
            f"  Dataset: {manifest.dataset.id}",
            f"    URL: {manifest.dataset.url} ({trusted})",
            f"    Size: <= {manifest.dataset.size_bytes_max} bytes",
            f"    SHA256: {manifest.dataset.sha256}",
        ])
    lines.append(f"  Timeout: {manifest.timeout_seconds}s")
    lines.append(f"  Manifest SHA256: {manifest_hash}")
    lines.append("")
    lines.append(INSTALL_DISCLAIMER.strip())
    return "\n".join(lines)


def install_pack(identifier: str, *, assume_yes: bool = False, trust_url: bool = False,
                 input_func=input) -> dict:
    ensure_home_layout()
    manifest_path = Path(identifier)
    if manifest_path.exists():
        manifest, manifest_text, manifest_hash = load_manifest_file(manifest_path, trust_url=trust_url)
    else:
        entry = get_pack_info(identifier)
        if not entry:
            raise RecoverableInstallError(f"pack not found in local registry: {identifier}")
        manifest_url = entry.get("manifest_url") or entry.get("url")
        if not manifest_url:
            raise RecoverableInstallError(f"registry entry missing manifest URL: {identifier}")
        payload = _download_bytes(manifest_url, size_limit=1_000_000)
        manifest_text = payload.decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_manifest = Path(tmpdir) / f"{identifier}.manifest.yaml"
            temp_manifest.write_text(manifest_text, encoding="utf-8")
            manifest, manifest_text, manifest_hash = load_manifest_file(temp_manifest, trust_url=trust_url)
    preview = _manifest_preview(manifest, manifest_hash)
    if not assume_yes:
        answer = (input_func(preview + "\n\nProceed with install? [y/N]: ") or "").strip().lower()
        if answer != "y":
            return {"installed": False, "cancelled": True, "preview": preview}
    dataset_info = _install_dataset(manifest, trust_url=trust_url)
    manifest_file = install_manifest(manifest, manifest_text, manifest_hash)
    append_audit_log("install", pack_id=manifest.id, manifest_sha256=manifest_hash, details=dataset_info)
    return {"installed": True, "manifest_path": str(manifest_file), "preview": preview}


def remove_pack(pack_id: str) -> dict:
    ensure_home_layout()
    target = benchmarks_dir() / pack_id
    if not target.exists():
        return {"removed": False, "pack_id": pack_id}
    shutil.rmtree(target, onerror=_clear_readonly)
    try:
        lock_file = benchmarks_dir().parent / "benchmarks.lock"
        os.chmod(lock_file, 0o666)
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:
        lock = {}
    lock.pop(pack_id, None)
    lock_file.write_text(json.dumps(lock, indent=2, sort_keys=True), encoding="utf-8")
    set_readonly(lock_file)
    append_audit_log("remove", pack_id=pack_id)
    return {"removed": True, "pack_id": pack_id}


def verify_installed_packs() -> dict:
    ensure_home_layout()
    results = {"ok": [], "tampered": []}
    for pack_dir in sorted(benchmarks_dir().iterdir() if benchmarks_dir().exists() else []):
        if not pack_dir.is_dir():
            continue
        pack_id = pack_dir.name
        try:
            manifest, manifest_hash, _ = verify_installed_manifest(pack_id)
            results["ok"].append({"id": manifest.id, "sha256": manifest_hash})
        except Exception as exc:
            results["tampered"].append({"id": pack_id, "error": str(exc)})
    append_audit_log("verify", details={"ok": len(results["ok"]), "tampered": len(results["tampered"])})
    return results
