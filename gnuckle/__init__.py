"""Gnuckle AI - Agentic AI Benchmark. Accidentally GNU, intentionally simian."""

import json
from importlib.resources import files


def _read_version() -> str:
    data = json.loads(files("gnuckle").joinpath("version.json").read_text(encoding="utf-8"))
    return data["version"]


__version__ = _read_version()
