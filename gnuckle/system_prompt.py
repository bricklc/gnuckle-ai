"""Default system prompt resources for gnuckle benchmark modes."""

from __future__ import annotations

from importlib.resources import files


FALLBACK_SYSTEM_PROMPT = (
    "You are a function-calling AI assistant. "
    "Always call the appropriate tool(s) before responding. "
    "Return tool calls as valid JSON."
)


def approx_token_count(text: str) -> int:
    return max(1, round(len(text) / 4))


def _read_packaged_prompt(path: str) -> str:
    return files("gnuckle").joinpath(path).read_text(encoding="utf-8").strip()


def default_system_prompt_for_mode(benchmark_mode: str) -> tuple[str | None, str]:
    if benchmark_mode == "legacy":
        return _read_packaged_prompt("prompts/legacy_benchmark_system_prompt.txt"), "legacy_constant_v1"
    return None, "workflow_default"
