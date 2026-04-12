"""Trust, storage, and audit helpers for benchmark packs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_BINARIES = frozenset({
    "llama-perplexity", "llama-perplexity.exe",
    "llama-bench", "llama-bench.exe",
    "llama-cli", "llama-cli.exe",
    "llama-server", "llama-server.exe",
})

TRUSTED_DATASET_HOSTS = frozenset({
    "huggingface.co",
    "raw.githubusercontent.com",
    "github.com",
    "ggml.ai",
})

ALLOWED_PLACEHOLDERS = frozenset({
    "model_path",
    "dataset_path",
    "logits_in",
    "logits_out",
    "cache_k",
    "cache_v",
    "cache_label",
    "main_gpu",
    "split_mode",
    "tensor_split",
})

INSTALL_DISCLAIMER = (
    "Benchmark packs are community-submitted content. The gnuckle core team reviews\n"
    "contributions to the benchmark-index repository, but review is best-effort and\n"
    "cannot guarantee absence of bugs, vulnerabilities, or malicious behavior.\n"
    "Installation of third-party benchmark packs is at your own risk.\n\n"
    "Gnuckle is not a sandbox. Running gnuckle executes local binaries with your\n"
    "user's privileges. Do not run gnuckle as root, administrator, or inside a\n"
    "production environment. Prefer a dedicated user or container.\n\n"
    "Datasets are downloaded from third-party sources. We verify SHA256 checksums,\n"
    "but dataset content should still be treated as untrusted input.\n\n"
    "Code-plugin benchmarks execute arbitrary Python. Do not install a code-plugin\n"
    "pack unless you trust the author and have read the plugin source.\n\n"
    "No warranty. Gnuckle is provided as-is without warranty of any kind.\n"
)


def gnuckle_home() -> Path:
    override = os.environ.get("GNUCKLE_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gnuckle"


def registry_dir() -> Path:
    return gnuckle_home() / "registry"


def benchmarks_dir() -> Path:
    return gnuckle_home() / "benchmarks"


def datasets_dir() -> Path:
    return gnuckle_home() / "datasets"


def logits_dir() -> Path:
    return gnuckle_home() / "logits"


def config_path() -> Path:
    return gnuckle_home() / "config.json"


def lock_path() -> Path:
    return gnuckle_home() / "benchmarks.lock"


def audit_log_path() -> Path:
    return gnuckle_home() / "audit.log"


def ensure_home_layout() -> None:
    for path in (gnuckle_home(), registry_dir(), benchmarks_dir(), datasets_dir(), logits_dir()):
        path.mkdir(parents=True, exist_ok=True)
    if not config_path().exists():
        config_path().write_text(json.dumps({"trusted_urls": []}, indent=2), encoding="utf-8")
    if not lock_path().exists():
        lock_path().write_text("{}", encoding="utf-8")
    if not audit_log_path().exists():
        audit_log_path().write_text("", encoding="utf-8")


def read_config() -> dict:
    ensure_home_layout()
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except Exception:
        return {"trusted_urls": []}


def write_config(config: dict) -> None:
    ensure_home_layout()
    config_path().write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def set_readonly(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode & 0o555)
    except OSError:
        try:
            os.chmod(path, 0o444)
        except OSError:
            pass


def append_audit_log(action: str, *, pack_id: str | None = None, manifest_sha256: str | None = None,
                     details: dict | None = None) -> None:
    ensure_home_layout()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "pack_id": pack_id,
        "manifest_sha256": manifest_sha256,
        "details": details or {},
    }
    with audit_log_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def sanitized_subprocess_env(source_env: dict | None = None) -> dict:
    source = dict(source_env or os.environ)
    kept = {}
    for key in ("PATH", "HOME", "USERPROFILE", "CUDA_VISIBLE_DEVICES", "LD_LIBRARY_PATH", "TMPDIR"):
        if key in source:
            kept[key] = source[key]
    for key in ("SYSTEMROOT", "WINDIR"):
        if key in source:
            kept[key] = source[key]
    return kept
