"""Parser safety helpers for benchmark pack output."""

from __future__ import annotations

import re

MAX_CAPTURE_BYTES = 1_000_000
NESTED_QUANTIFIER_RE = re.compile(r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)[+*?]")


class ParserValidationError(ValueError):
    """Raised when a parser regex is considered unsafe."""


def truncate_capture(text: str, max_bytes: int = MAX_CAPTURE_BYTES) -> tuple[str, bool]:
    raw = (text or "").encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text or "", False
    return raw[:max_bytes].decode("utf-8", errors="ignore"), True


def validate_regex_pattern(pattern: str) -> str:
    if NESTED_QUANTIFIER_RE.search(pattern or ""):
        raise ParserValidationError("regex rejected: nested quantifier pattern is unsafe")
    re.compile(pattern)
    return pattern


def parse_metrics(parse_block: dict, output_text: str) -> dict:
    truncated, was_truncated = truncate_capture(output_text)
    parsed = {"capture_truncated": was_truncated}
    for metric_name, parser in (parse_block or {}).items():
        compiled = re.compile(parser.pattern)
        matches = compiled.findall(truncated)
        if not matches:
            continue
        last = matches[-1]
        value = last[0] if isinstance(last, tuple) else last
        try:
            parsed[metric_name] = float(value)
        except ValueError:
            parsed[metric_name] = value
    return parsed
