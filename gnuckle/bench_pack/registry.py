"""Registry sync and local index lookup."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
from urllib.request import Request, urlopen

from gnuckle import __version__
from gnuckle.bench_pack.manifest import load_manifest_file
from gnuckle.bench_pack.trust import benchmarks_dir
from gnuckle.bench_pack.trust import append_audit_log, ensure_home_layout, registry_dir

def bundled_registry_index_url() -> str:
    bundled = Path(__file__).resolve().parents[2] / "benchmark-index" / "index.json"
    return bundled.as_uri()


DEFAULT_REGISTRY_INDEX_URL = bundled_registry_index_url()


def index_path() -> Path:
    return registry_dir() / "index.json"


def load_local_index() -> list[dict]:
    ensure_home_layout()
    if not index_path().is_file():
        return []
    try:
        data = json.loads(index_path().read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("benchmarks", []))
    return []


def save_local_index(entries: list[dict]) -> None:
    ensure_home_layout()
    index_path().write_text(json.dumps({"benchmarks": entries}, indent=2, sort_keys=True), encoding="utf-8")


def sync_registry(index_url: str | None = None) -> list[dict]:
    ensure_home_layout()
    url = index_url or DEFAULT_REGISTRY_INDEX_URL
    request = Request(url, headers={"User-Agent": f"gnuckle/{__version__}"})
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    entries = data if isinstance(data, list) else list(data.get("benchmarks", []))
    parsed = urlparse(url)
    if parsed.scheme == "file":
        local_path = url2pathname(parsed.path)
        if parsed.netloc:
            local_path = f"//{parsed.netloc}{local_path}"
        index_file = Path(local_path)
        base_dir = index_file.parent
        normalized = []
        for entry in entries:
            item = dict(entry)
            if "manifest_url" not in item:
                manifest_path = item.get("path") or item.get("manifest_path")
                if manifest_path:
                    item["manifest_url"] = (base_dir / manifest_path).resolve().as_uri()
            normalized.append(item)
        entries = normalized
    save_local_index(entries)
    append_audit_log("registry_update", details={"count": len(entries), "index_url": url})
    return entries


def list_available_packs() -> list[dict]:
    return load_local_index()


def list_registry_benchmarks() -> list[dict]:
    ensure_home_layout()
    available = load_local_index()
    installed_root = benchmarks_dir()
    installed_dirs = sorted([path for path in installed_root.iterdir() if path.is_dir()] if installed_root.exists() else [], key=lambda p: p.name)

    installed_meta = {}
    for pack_dir in installed_dirs:
        manifest_path = pack_dir / "manifest.yaml"
        if not manifest_path.is_file():
            installed_meta[pack_dir.name] = {"id": pack_dir.name, "status": "installed"}
            continue
        try:
            manifest, _, _ = load_manifest_file(manifest_path, trust_url=True)
            installed_meta[pack_dir.name] = {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "author": manifest.author.name,
                "downloads": manifest.downloads,
                "homepage": manifest.homepage,
                "description": manifest.description,
                "tags": list(manifest.tags),
                "status": "installed",
            }
        except Exception:
            installed_meta[pack_dir.name] = {"id": pack_dir.name, "status": "installed"}

    merged = []
    seen = set()
    for entry in available:
        pack_id = entry.get("id")
        if not pack_id:
            continue
        item = dict(entry)
        installed = installed_meta.get(pack_id)
        if installed:
            item["installed_version"] = installed.get("version")
            item["status"] = "installed" if installed.get("version") == item.get("version") else "update_available"
        else:
            item["status"] = "available"
        merged.append(item)
        seen.add(pack_id)

    for pack_id, item in installed_meta.items():
        if pack_id in seen:
            continue
        merged.append(item)

    def sort_key(entry: dict):
        status_rank = {"installed": 0, "update_available": 1, "available": 2}.get(entry.get("status"), 9)
        return (status_rank, str(entry.get("name") or entry.get("id") or ""))

    return sorted(merged, key=sort_key)


def get_pack_info(pack_id: str) -> dict | None:
    for entry in load_local_index():
        if entry.get("id") == pack_id:
            return entry
    return None


def search_packs(query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return load_local_index()
    return [
        entry for entry in load_local_index()
        if q in (entry.get("id", "").lower())
        or q in (entry.get("description", "").lower())
        or q in " ".join(entry.get("tags", [])).lower()
    ]
