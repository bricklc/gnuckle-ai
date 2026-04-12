"""Registry sync and local index lookup."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from gnuckle import __version__
from gnuckle.bench_pack.trust import append_audit_log, ensure_home_layout, registry_dir

DEFAULT_REGISTRY_INDEX_URL = "https://raw.githubusercontent.com/gnuckle-ai/benchmark-index/main/index.json"


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
    save_local_index(entries)
    append_audit_log("registry_update", details={"count": len(entries), "index_url": url})
    return entries


def list_available_packs() -> list[dict]:
    return load_local_index()


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
