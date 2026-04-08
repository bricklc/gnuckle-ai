"""Shared profile helpers for gnuckle."""

import json
from pathlib import Path


def _resolve_path(value, base_dir: Path):
    if value is None:
        return None
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    return str(p)


def load_profile(profile_path):
    profile_file = Path(profile_path).expanduser().resolve()
    with profile_file.open("r", encoding="utf-8") as f:
        profile = json.load(f)

    base_dir = profile_file.parent
    for key in ("model_path", "server_path", "scan_dir", "output_dir"):
        if key in profile:
            profile[key] = _resolve_path(profile.get(key), base_dir)

    profile["_profile_file"] = str(profile_file)
    return profile
