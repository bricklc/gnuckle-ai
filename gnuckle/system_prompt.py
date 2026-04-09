"""Default system prompt resources for gnuckle benchmark modes."""

from __future__ import annotations

from importlib.resources import files

try:
    import tiktoken
except Exception:  # pragma: no cover - optional dependency at runtime
    tiktoken = None


FALLBACK_SYSTEM_PROMPT = (
    "You are a function-calling AI assistant. "
    "Always call the appropriate tool(s) before responding. "
    "Return tool calls as valid JSON."
)


def approx_token_count(text: str) -> int:
    return max(1, round(len(text) / 4))


def tokenizer_label() -> str:
    return "OpenAI cl100k_base"


def tokenizer_token_count(text: str) -> int | None:
    if not text:
        return 0
    if tiktoken is None:
        return None
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return None


def _read_packaged_prompt(path: str) -> str:
    return files("gnuckle").joinpath(path).read_text(encoding="utf-8").strip()


def default_system_prompt_for_mode(benchmark_mode: str) -> tuple[str | None, str]:
    if benchmark_mode == "legacy":
        return _read_packaged_prompt("prompts/legacy_benchmark_system_prompt.txt"), "legacy_constant_v1"
    return None, "workflow_default"
