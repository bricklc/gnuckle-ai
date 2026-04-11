"""Session benchmark runner for persistent, transcript-style benchmark sessions."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from openai import OpenAI

from gnuckle.benchmark import (
    accumulate_usage,
    ape_print,
    empty_usage,
    estimate_context_token_counts,
    get_hardware_snapshot,
    print_header,
    print_step,
    render_progress,
    update_usage,
    usage_total_tokens,
)
from gnuckle.tool_executor import TOOL_SPECS, tool_definitions


MODEL = "local-model"
BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"
DEFAULT_BENCHMARK_DATE = "2026-04-10"
MAX_NO_RESPONSE_RETRIES = 2


@dataclass
class SessionState:
    files: dict[str, str] = field(default_factory=dict)
    list_items: list[dict] = field(default_factory=list)
    tool_history: list[dict] = field(default_factory=list)
    tool_outputs: list[dict] = field(default_factory=list)


def discover_benchmarks(search_dir: Path | None = None) -> list[dict]:
    """Find all session benchmark files and normalize them into one internal shape."""
    directory = search_dir or BENCHMARKS_DIR
    if not directory.is_dir():
        return []
    results = []
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            normalized = normalize_benchmark_definition(data)
            normalized["_path"] = str(path)
            results.append(normalized)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return results


def load_benchmark(bench_id: str, search_dir: Path | None = None) -> dict:
    """Load a specific benchmark by ID."""
    for bench in discover_benchmarks(search_dir):
        if bench["id"] == bench_id:
            return bench
    raise ValueError(f"benchmark not found: {bench_id}")


def normalize_benchmark_definition(data: dict) -> dict:
    """Accept legacy and v2 session benchmark JSON and return one internal shape."""
    session_block = data.get("session", {})
    meta_block = data.get("meta", {})
    scoring_block = data.get("scoring", {})

    benchmark_type = data.get("type") or session_block.get("type")
    if benchmark_type != "session":
        raise ValueError("not a session benchmark")

    bench_id = meta_block.get("id") or data.get("id")
    if not bench_id:
        raise ValueError("session benchmark missing id")

    tool_manifest = data.get("tool_manifest") or []
    tools = data.get("tools")
    if tools is None:
        tools = [entry["name"] for entry in tool_manifest if entry.get("name")]
    if not tools:
        raise ValueError("session benchmark missing tool manifest")

    system_prompt = session_block.get("system_prompt") or data.get("system_prompt") or ""
    standing_rules = session_block.get("standing_rules") or data.get("standing_rules") or []
    initial_state = session_block.get("initial_state") or {}

    normalized_turns = []
    for index, turn in enumerate(data.get("turns", []), start=1):
        expect = dict(turn.get("expect") or turn.get("expectations") or {})
        response_expect = dict(expect.get("response") or {})
        tool_expect = dict(expect.get("tool_usage") or {})
        session_expect = dict(expect.get("session") or {})

        finish_required = bool(
            session_expect.get("must_finish")
            if "must_finish" in session_expect
            else expect.get("finish_required", False)
        )

        mock_results = turn.get("mock_results")
        if mock_results is None:
            mock_results = _normalize_mock_tool_results(turn.get("mock_tool_results", []))

        normalized_turns.append(
            {
                "id": turn.get("id") or f"t{index:02d}",
                "title": turn.get("title") or turn.get("id") or f"Turn {index}",
                "prompt": turn.get("prompt") or turn.get("user_message") or "",
                "active_tools": turn.get("active_tools") or list(tools),
                "mock_results": mock_results or {},
                "expect": {
                    "tools_called": tool_expect.get("must_call", expect.get("tools_called", [])),
                    "tools_not_called": tool_expect.get("must_not_call", expect.get("tools_not_called", [])),
                    "tool_order": tool_expect.get("ordered_calls", expect.get("tool_order", [])),
                    "finish_required": finish_required,
                    "response_contains": response_expect.get("must_contain", expect.get("response_contains", [])),
                    "response_format": response_expect.get("format", expect.get("response_format")),
                    "expect_refusal": expect.get("expect_refusal", False),
                },
            }
        )

    return {
        "id": bench_id,
        "title": meta_block.get("title") or data.get("title") or bench_id,
        "version": meta_block.get("version") or data.get("version", "1.0"),
        "author": meta_block.get("author") or data.get("author", "unknown"),
        "description": meta_block.get("description") or data.get("description", ""),
        "tags": meta_block.get("tags") or data.get("tags", []),
        "type": "session",
        "system_prompt": system_prompt,
        "standing_rules": standing_rules,
        "tools": list(tools),
        "turns": normalized_turns,
        "session": {
            "mode": session_block.get("mode", "persistent"),
            "carry_state_across_turns": session_block.get("carry_state_across_turns", True),
            "finish_policy": session_block.get("finish_policy", "checkpoint_or_final_only"),
            "initial_state": initial_state,
        },
        "scoring": scoring_block,
    }


def _normalize_mock_tool_results(entries: list[dict]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for entry in entries:
        tool_name = entry.get("tool")
        if not tool_name:
            continue
        result = entry.get("result", {})
        existing = normalized.get(tool_name)
        if existing is None:
            normalized[tool_name] = result
        elif isinstance(existing, list):
            existing.append(result)
        else:
            normalized[tool_name] = [existing, result]
    return normalized


def _score_turn(
    turn_def: dict,
    actual_tool_calls: list[str],
    assistant_text: str,
    hallucinated_tools: list[str],
    *,
    no_response: bool = False,
) -> dict:
    """Score a single turn against its expectations."""
    expect = turn_def.get("expect", {})
    scores = {}

    scores["no_response"] = bool(no_response)
    scores["empty_turn"] = bool(no_response)
    scores["invalid_turn_completion"] = bool(no_response)

    if no_response:
        scores["tool_recall"] = 0.0 if expect.get("tools_called", []) else 1.0
        scores["tool_precision"] = 0.0
        scores["extra_tools"] = []
        scores["missing_tools"] = list(dict.fromkeys(expect.get("tools_called", [])))
        scores["tool_order_correct"] = not bool(expect.get("tool_order", []))
        scores["unwanted_tool_violations"] = []
        scores["hallucinated_tools"] = hallucinated_tools
        scores["content_recall"] = 0.0 if expect.get("response_contains", []) else 1.0
        scores["content_missing"] = list(expect.get("response_contains", []))
        scores["format_correct"] = False
        scores["refusal_detected"] = False if expect.get("expect_refusal") else None
        scores["finish_called"] = False if expect.get("finish_required") else None
        scores["turn_score"] = 0.0
        return scores

    expected_tools = expect.get("tools_called", [])
    if expected_tools:
        called_set = set(actual_tool_calls)
        expected_set = set(expected_tools)
        correct = called_set & expected_set
        extra = called_set - expected_set
        missing = expected_set - called_set
        scores["tool_recall"] = round(len(correct) / max(1, len(expected_set)), 3)
        scores["tool_precision"] = round(len(correct) / max(1, len(called_set)), 3) if called_set else 0.0
        scores["extra_tools"] = sorted(extra)
        scores["missing_tools"] = sorted(missing)
    else:
        scores["tool_recall"] = 1.0
        scores["tool_precision"] = 1.0
        scores["extra_tools"] = []
        scores["missing_tools"] = []

    tool_order = expect.get("tool_order", [])
    if tool_order:
        order_idx = 0
        for tool_name in actual_tool_calls:
            if order_idx < len(tool_order) and tool_name == tool_order[order_idx]:
                order_idx += 1
        scores["tool_order_correct"] = order_idx >= len(tool_order)
    else:
        scores["tool_order_correct"] = True

    not_called = expect.get("tools_not_called", [])
    violations = [tool_name for tool_name in not_called if tool_name in actual_tool_calls]
    scores["unwanted_tool_violations"] = violations
    scores["hallucinated_tools"] = hallucinated_tools

    contains = expect.get("response_contains", [])
    if contains:
        text_lower = assistant_text.lower()
        found = [item for item in contains if item.lower() in text_lower]
        scores["content_recall"] = round(len(found) / len(contains), 3)
        scores["content_missing"] = [item for item in contains if item.lower() not in text_lower]
    else:
        scores["content_recall"] = 1.0
        scores["content_missing"] = []

    if expect.get("response_format") == "bullet_points":
        lines = [line.strip() for line in assistant_text.strip().splitlines() if line.strip()]
        bullet_lines = [line for line in lines if re.match(r"^[-*•]\s", line) or re.match(r"^\d+[.)]\s", line)]
        scores["format_correct"] = len(bullet_lines) >= max(1, len(lines) // 2)
    else:
        scores["format_correct"] = True

    if expect.get("expect_refusal"):
        refusal_phrases = ["cannot", "can't", "don't have", "not available", "no tool", "not possible", "unable"]
        scores["refusal_detected"] = any(phrase in assistant_text.lower() for phrase in refusal_phrases)
    else:
        scores["refusal_detected"] = None

    if expect.get("finish_required"):
        scores["finish_called"] = "finish" in actual_tool_calls
    else:
        scores["finish_called"] = None

    weights = {
        "tool_recall": 0.25,
        "tool_precision": 0.25,
        "tool_order_correct": 0.15,
        "content_recall": 0.15,
        "format_correct": 0.10,
        "no_violations": 0.10,
    }
    no_violations = 1.0 if (not violations and not hallucinated_tools) else 0.0
    composite = (
        weights["tool_recall"] * scores["tool_recall"]
        + weights["tool_precision"] * scores["tool_precision"]
        + weights["tool_order_correct"] * (1.0 if scores["tool_order_correct"] else 0.0)
        + weights["content_recall"] * scores["content_recall"]
        + weights["format_correct"] * (1.0 if scores["format_correct"] else 0.0)
        + weights["no_violations"] * no_violations
    )
    if expect.get("finish_required") and not scores["finish_called"]:
        composite -= 0.15
    scores["turn_score"] = round(max(0.0, composite), 3)
    return scores


class MockToolExecutor:
    """Deterministic session tool executor with persistent mocked world state."""

    def __init__(self, session_state: SessionState, allowed_tools: list[str], mock_results: dict):
        self.state = session_state
        self.allowed_tools = set(allowed_tools)
        self._mocks = {}
        for tool_name, result in (mock_results or {}).items():
            self._mocks[tool_name] = list(result) if isinstance(result, list) else result

    def invoke(self, tool_call_id: str, tool_name: str, arguments: dict) -> dict:
        if tool_name not in self.allowed_tools:
            return self._error_result(tool_call_id, tool_name, "undeclared_tool", f"tool '{tool_name}' is not active for this turn")
        validation_error = self._validate_input(tool_name, arguments)
        if validation_error:
            return self._error_result(tool_call_id, tool_name, "input_validation_error", validation_error)

        mock = self._consume_mock(tool_name)
        try:
            if tool_name == "echo":
                result = {"tool": "echo", "ok": True, "text": str(arguments.get("text", ""))}
            elif tool_name == "read_file":
                path = str(arguments.get("path", ""))
                content = self._read_file(path, mock)
                result = {"tool": "read_file", "ok": True, "path": path, "content": content}
            elif tool_name == "write_file":
                path = str(arguments.get("path", ""))
                content = str(arguments.get("content", ""))
                self.state.files[path] = content
                result = {"tool": "write_file", "ok": True, "path": path, "content_preview": content[:240]}
            elif tool_name == "append_file":
                path = str(arguments.get("path", ""))
                content = str(arguments.get("content", ""))
                self.state.files[path] = self.state.files.get(path, "") + content
                result = {"tool": "append_file", "ok": True, "path": path, "content_preview": content[:240]}
            elif tool_name == "list_files":
                entries = self._list_files(mock)
                result = {"tool": "list_files", "ok": True, "entries": entries, "count": len(entries)}
            elif tool_name == "get_date":
                anchored = self.state.files.get("__benchmark_date__", DEFAULT_BENCHMARK_DATE)
                result = {"tool": "get_date", "ok": True, "iso_date": anchored, "display": anchored}
            elif tool_name == "add_item":
                item = {
                    "id": max((entry["id"] for entry in self.state.list_items), default=0) + 1,
                    "text": str(arguments.get("text", "")),
                }
                self.state.list_items.append(item)
                result = {"tool": "add_item", "ok": True, "item": item, "items": list(self.state.list_items)}
            elif tool_name == "update_item":
                result = self._update_item(arguments)
            elif tool_name == "read_list":
                result = {"tool": "read_list", "ok": True, "items": list(self.state.list_items), "count": len(self.state.list_items)}
            elif tool_name == "finish":
                result = {
                    "tool": "finish",
                    "ok": True,
                    "summary": str(arguments.get("summary", "")),
                    "files_changed": list(arguments.get("files_changed", [])),
                }
            else:
                return self._error_result(tool_call_id, tool_name, "unsupported_tool", f"unsupported tool '{tool_name}'")
        except Exception as exc:
            return self._error_result(tool_call_id, tool_name, "execution_error", str(exc))

        result = self._merge_mock_result(result, mock)
        result.update(
            {
                "tool_call_id": tool_call_id,
                "is_error": False,
                "error_type": None,
                "arguments": arguments,
            }
        )
        self.state.tool_history.append({"tool": tool_name, "arguments": arguments, "ok": True})
        self.state.tool_outputs.append(result)
        return result

    def _consume_mock(self, tool_name: str):
        mock = self._mocks.get(tool_name)
        if isinstance(mock, list):
            if mock:
                return mock.pop(0)
            return None
        return mock

    def _merge_mock_result(self, result: dict, mock: object) -> dict:
        if isinstance(mock, dict):
            merged = dict(result)
            merged.update(mock)
            merged.setdefault("tool", result.get("tool"))
            merged.setdefault("ok", True)
            return merged
        return result

    def _read_file(self, path: str, mock: object) -> str:
        if isinstance(mock, dict) and isinstance(mock.get("output"), str):
            return str(mock["output"])
        if path not in self.state.files:
            raise FileNotFoundError(path)
        return self.state.files[path]

    def _list_files(self, mock: object) -> list[dict]:
        if isinstance(mock, dict) and isinstance(mock.get("output"), str):
            return [
                {"name": line.strip(), "path": line.strip(), "type": "file"}
                for line in str(mock["output"]).splitlines()
                if line.strip()
            ]
        return [
            {"name": Path(path).name, "path": path, "type": "file"}
            for path in sorted(key for key in self.state.files.keys() if not key.startswith("__"))
        ]

    def _update_item(self, arguments: dict) -> dict:
        item_id = arguments.get("item_id")
        old_text = arguments.get("old_text")
        new_text = str(arguments.get("new_text", ""))
        for entry in self.state.list_items:
            if item_id is not None and int(entry["id"]) == int(item_id):
                before_text = entry["text"]
                entry["text"] = new_text
                return {"tool": "update_item", "ok": True, "item": dict(entry), "before_text": before_text, "items": list(self.state.list_items)}
            if old_text is not None and entry["text"] == str(old_text):
                before_text = entry["text"]
                entry["text"] = new_text
                return {"tool": "update_item", "ok": True, "item": dict(entry), "before_text": before_text, "items": list(self.state.list_items)}
        raise KeyError("list item not found")

    def _validate_input(self, tool_name: str, arguments: dict) -> str | None:
        spec = TOOL_SPECS.get(tool_name)
        if spec is None:
            return f"invalid tool: {tool_name}"
        missing = sorted(field for field in spec["required"] if field not in arguments)
        if missing:
            return f"missing required fields: {missing}"
        unexpected = sorted(field for field in arguments if field not in spec["allowed"])
        if unexpected:
            return f"unexpected fields: {unexpected}"
        if tool_name == "update_item" and "item_id" not in arguments and "old_text" not in arguments:
            return "update_item requires item_id or old_text"
        return None

    @staticmethod
    def _error_result(tool_call_id: str, tool_name: str, error_type: str, error: str) -> dict:
        return {
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "ok": False,
            "is_error": True,
            "error_type": error_type,
            "error": error,
        }


def _result_content(result: dict) -> str:
    for key in ("content", "output", "summary", "text", "error"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return json.dumps(result, ensure_ascii=True)


def _append_transcript_entry(
    transcript: list[dict],
    role: str,
    kind: str,
    content: str,
    *,
    turn_id: str,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    status: str | None = None,
) -> None:
    transcript.append(
        {
            "index": len(transcript) + 1,
            "role": role,
            "kind": kind,
            "turn_id": turn_id,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "status": status,
            "content": content,
        }
    )


def _normalize_transcript(records: list[dict]) -> list[dict]:
    normalized = []
    for record in records:
        text = str(record.get("content", "") or "")
        chunks = text.splitlines() if "\n" in text else [text]
        if not chunks:
            chunks = [""]
        for chunk_index, chunk in enumerate(chunks, start=1):
            normalized.append({**record, "chunk_index": chunk_index, "content": chunk})
    return normalized


def _initial_session_state(benchmark: dict) -> SessionState:
    initial_state = benchmark.get("session", {}).get("initial_state", {})
    files = dict(initial_state.get("files", {}))
    list_items = [dict(item) for item in initial_state.get("list_items", [])]
    benchmark_date = str(initial_state.get("benchmark_date", DEFAULT_BENCHMARK_DATE))
    files["__benchmark_date__"] = benchmark_date
    return SessionState(files=files, list_items=list_items)


def run_session_benchmark(
    benchmark: dict,
    base_url: str,
    request_args: dict | None = None,
    output_dir: Path | None = None,
    server_pid: int | None = None,
    context_window: int | None = None,
    observer=None,
    model_name: str | None = None,
    cache_label: str | None = None,
) -> dict:
    """Run a full session benchmark and return the results summary."""
    request_args = request_args or {}
    benchmark = normalize_benchmark_definition(benchmark)
    bench_id = benchmark["id"]
    turns = benchmark["turns"]
    tools = benchmark["tools"]
    system_prompt = benchmark["system_prompt"]
    standing_rules = benchmark.get("standing_rules", [])

    if standing_rules:
        rules_text = "\n".join(f"- {rule}" for rule in standing_rules)
        system_prompt = f"{system_prompt}\n\nStanding rules:\n{rules_text}"

    client = OpenAI(base_url=base_url, api_key="none")
    messages = [{"role": "system", "content": system_prompt}]
    session_state = _initial_session_state(benchmark)
    transcript: list[dict] = []
    tool_defs_by_turn = {turn["id"]: tool_definitions(turn["active_tools"]) for turn in turns}

    session_id = f"{bench_id}_{uuid4().hex[:12]}"
    turn_results = []
    all_tool_calls_flat = []
    initial_hardware = get_hardware_snapshot(server_pid)
    session_start = time.perf_counter()
    total_provider_usage = empty_usage()
    invalid_execution_events: list[dict] = []

    print_header(f"Session Benchmark: {benchmark['title']}")
    print_step(f"id: {bench_id}  turns: {len(turns)}  tools: {len(tools)}")
    print_step(f"rules: {len(standing_rules)}  type: persistent session")
    print()

    if observer is not None:
        observer(
            "episode_start",
            {
                "workflow_id": bench_id,
                "title": benchmark["title"],
                "session_mode": benchmark.get("session", {}).get("mode", "persistent"),
                "model_name": model_name or "unknown model",
                "cache_label": cache_label or "unknown kv",
                "workspace": f"session://{bench_id}",
                "active_tools": tools,
                "max_turns": len(turns),
                "context_window": context_window,
                "user_event": turns[0]["prompt"] if turns else "",
            },
        )

    for turn_idx, turn_def in enumerate(turns):
        turn_num = turn_idx + 1
        turn_id = turn_def["id"]
        turn_title = turn_def.get("title", turn_id)
        prompt = turn_def["prompt"]
        mock_executor = MockToolExecutor(session_state, turn_def["active_tools"], turn_def.get("mock_results", {}))

        render_progress(f"turn {turn_num}/{len(turns)}: {turn_id}", turn_idx, len(turns), done=False)
        print_step(f"turn {turn_num}/{len(turns)}: {turn_title}")

        if observer is not None:
            observer("turn_start", {"turn": turn_num})
            observer("model_request", {"attempt": 1, "prompt": prompt})

        messages.append({"role": "user", "content": prompt})
        _append_transcript_entry(transcript, "user", "prompt", prompt, turn_id=turn_id)

        turn_start = time.perf_counter()
        first_response_ms = None
        total_output_tokens = 0
        actual_tools_called: list[str] = []
        hallucinated_tools: list[str] = []
        tool_round = 0
        max_tool_rounds = 10
        assistant_text = ""
        last_usage = empty_usage()
        turn_provider_usage = empty_usage()
        retry_count = 0
        initial_no_response = False
        no_response = False

        while True:
            call_start = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tool_defs_by_turn[turn_id],
                tool_choice="auto",
                temperature=request_args.get("temperature", 0.6),
                top_p=request_args.get("top_p", 0.95),
                max_tokens=request_args.get("max_tokens", 512),
            )
            call_elapsed_ms = round((time.perf_counter() - call_start) * 1000, 1)
            if first_response_ms is None:
                first_response_ms = call_elapsed_ms

            message_usage = update_usage(empty_usage(), getattr(response, "usage", None))
            last_usage = message_usage
            turn_provider_usage = accumulate_usage(turn_provider_usage, message_usage)
            total_provider_usage = accumulate_usage(total_provider_usage, message_usage)
            total_output_tokens += int((message_usage or {}).get("output_tokens", 0) or 0)

            message = response.choices[0].message
            assistant_text = getattr(message, "content", "") or ""
            raw_tool_calls = [
                {
                    "id": getattr(tool_call, "id", "") or f"tc_{turn_num}_{tool_round}_{index}",
                    "name": tool_call.function.name,
                    "arguments_json": tool_call.function.arguments or "{}",
                }
                for index, tool_call in enumerate(message.tool_calls or [])
            ]

            has_visible_event = bool(assistant_text.strip()) or bool(raw_tool_calls)
            if not has_visible_event:
                if retry_count == 0:
                    initial_no_response = True
                retry_count += 1
                no_response = True
                invalid_execution_events.append(
                    {
                        "turn_id": turn_id,
                        "error": "no_response",
                        "attempt": retry_count,
                    }
                )
                if observer is not None:
                    observer(
                        "no_response",
                        {
                            "turn": turn_num,
                            "attempt": retry_count,
                            "max_retries": MAX_NO_RESPONSE_RETRIES,
                            "retrying": retry_count <= MAX_NO_RESPONSE_RETRIES,
                            "reason": "assistant emitted no text and no tool calls",
                            "latency_ms": call_elapsed_ms,
                            "context_window": context_window,
                        },
                    )
                if retry_count <= MAX_NO_RESPONSE_RETRIES:
                    continue
                _append_transcript_entry(
                    transcript,
                    "assistant",
                    "invalid_turn",
                    "Assistant did not respond.",
                    turn_id=turn_id,
                    status="no_response",
                )
                assistant_text = ""
                break

            no_response = False

            if observer is not None:
                observer(
                    "assistant_action",
                    {
                        "content": assistant_text,
                        "tool_calls": raw_tool_calls,
                        "latency_ms": call_elapsed_ms,
                        "context_window": context_window,
                    },
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_text or "",
                    "tool_calls": [
                        {
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": tool_call["arguments_json"],
                            },
                        }
                        for tool_call in raw_tool_calls
                    ],
                }
            )
            if assistant_text.strip():
                _append_transcript_entry(transcript, "assistant", "message", assistant_text, turn_id=turn_id)

            if not raw_tool_calls:
                break
            tool_round += 1
            if tool_round > max_tool_rounds:
                invalid_execution_events.append({"turn_id": turn_id, "error": "tool_round_limit_reached"})
                break

            for tool_call in raw_tool_calls:
                tool_name = tool_call["name"]
                tool_call_id = tool_call["id"]
                actual_tools_called.append(tool_name)
                all_tool_calls_flat.append(tool_name)

                try:
                    arguments = json.loads(tool_call["arguments_json"] or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                    invalid_execution_events.append(
                        {
                            "turn_id": turn_id,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "error": "invalid_tool_arguments_json",
                        }
                    )

                if observer is not None:
                    observer("tool_call", {"tool_name": tool_name, "tool_call_id": tool_call_id, "arguments": arguments})

                _append_transcript_entry(
                    transcript,
                    "assistant",
                    "tool_use",
                    json.dumps(arguments, ensure_ascii=True),
                    turn_id=turn_id,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                )

                if tool_name not in turn_def["active_tools"]:
                    hallucinated_tools.append(tool_name)

                result = mock_executor.invoke(tool_call_id, tool_name, arguments)
                if result.get("is_error"):
                    invalid_execution_events.append(
                        {
                            "turn_id": turn_id,
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "error": result.get("error_type"),
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result, ensure_ascii=True),
                    }
                )

                _append_transcript_entry(
                    transcript,
                    "user",
                    "tool_result",
                    _result_content(result),
                    turn_id=turn_id,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    status="ok" if result.get("ok") else "error",
                )

                if observer is not None:
                    observer(
                        "tool_result",
                        {
                            "tool_name": tool_name,
                            "tool_call_id": tool_call_id,
                            "ok": bool(result.get("ok")),
                            "result": result,
                        },
                    )

        turn_elapsed_ms = round((time.perf_counter() - turn_start) * 1000, 1)
        context_counts = estimate_context_token_counts(messages, tool_defs_by_turn[turn_id], base_url=base_url)
        context_estimate = int(context_counts["measured"]) if context_counts["measured"] is not None else int(context_counts["heuristic"])
        hardware = get_hardware_snapshot(server_pid)
        scores = _score_turn(
            turn_def,
            actual_tools_called,
            assistant_text,
            hallucinated_tools,
            no_response=no_response,
        )
        tokens_per_second = round(total_output_tokens / max(turn_elapsed_ms / 1000.0, 0.001), 2)
        turn_invalid_events = [event for event in invalid_execution_events if event["turn_id"] == turn_id]
        turn_provider_tokens = usage_total_tokens(turn_provider_usage)
        cumulative_provider_tokens = usage_total_tokens(total_provider_usage)

        turn_result = {
            "turn": turn_num,
            "turn_id": turn_id,
            "title": turn_title,
            "prompt": prompt,
            "active_tools": turn_def["active_tools"],
            "tools_called": actual_tools_called,
            "hallucinated_tools": hallucinated_tools,
            "tool_rounds": tool_round,
            "retry_count": retry_count,
            "initial_no_response": initial_no_response,
            "no_response": no_response,
            "assistant_text": assistant_text[:2000],
            "scores": scores,
            "metrics": {
                "ttft_ms": first_response_ms,
                "turn_elapsed_ms": turn_elapsed_ms,
                "tokens_per_second": tokens_per_second,
                "context_tokens_estimate": context_estimate,
                "context_tokens_heuristic": context_counts["heuristic"],
                "provider_usage_total": turn_provider_tokens,
                "provider_usage_cumulative_total": cumulative_provider_tokens,
                "hardware": hardware,
                "tool_correctness": round(
                    1.0 - (len(scores["extra_tools"]) + len(scores["missing_tools"]) + len(hallucinated_tools))
                    / max(1, len(actual_tools_called) + len(scores["missing_tools"])),
                    3,
                ),
            },
            "invalid_execution_events": turn_invalid_events,
        }
        turn_results.append(turn_result)

        status = "PASS" if scores["turn_score"] >= 0.7 else "FAIL"
        print(
            f"    {status} score={scores['turn_score']}  tools={actual_tools_called}  "
            f"ttft={first_response_ms}ms  ctx~{context_estimate}  tps={tokens_per_second}"
        )
        if observer is not None:
            observer(
                "turn_metrics",
                {
                    "turn": turn_num,
                    "ttft_ms": first_response_ms,
                    "latency_ms": turn_elapsed_ms,
                    "tokens_per_second": tokens_per_second,
                    "context_tokens_estimate": context_estimate,
                    "context_window": context_window,
                    "provider_usage_total": turn_provider_tokens,
                    "provider_usage_cumulative_total": cumulative_provider_tokens,
                    "hardware_usage": hardware,
                },
            )
        if no_response:
            print_step(f"turn failed: empty response after {retry_count} attempts")
            break

    render_progress("session complete", len(turns), len(turns), done=True)

    session_elapsed_s = round(time.perf_counter() - session_start, 2)
    avg_score = round(sum(turn["scores"]["turn_score"] for turn in turn_results) / max(1, len(turn_results)), 3)
    pass_count = sum(1 for turn in turn_results if turn["scores"]["turn_score"] >= 0.7)
    final_hardware = get_hardware_snapshot(server_pid)
    normalized_transcript = _normalize_transcript(transcript)

    summary = {
        "meta": {
            "benchmark_id": bench_id,
            "benchmark_title": benchmark["title"],
            "benchmark_version": benchmark.get("version", "1.0"),
            "author": benchmark.get("author", "unknown"),
            "session_id": session_id,
            "type": "session",
            "total_turns": len(turns),
            "tools_available": tools,
            "standing_rules": standing_rules,
            "timestamp": datetime.now().isoformat(),
        },
        "aggregate": {
            "average_score": avg_score,
            "pass_count": pass_count,
            "fail_count": len(turn_results) - pass_count,
            "pass_rate": round(pass_count / max(1, len(turn_results)), 3),
            "total_tool_calls": len(all_tool_calls_flat),
            "session_elapsed_s": session_elapsed_s,
            "initial_hardware": initial_hardware,
            "final_hardware": final_hardware,
            "provider_usage_total": total_provider_usage,
            "provider_usage_total_tokens": usage_total_tokens(total_provider_usage),
            "invalid_execution_count": len(invalid_execution_events),
            "no_response_turn_count": sum(1 for turn in turn_results if turn.get("no_response")),
        },
        "session": {
            "mode": benchmark.get("session", {}).get("mode", "persistent"),
            "finish_policy": benchmark.get("session", {}).get("finish_policy", "checkpoint_or_final_only"),
            "state": {
                "files": {key: value for key, value in session_state.files.items() if not key.startswith("__")},
                "list_items": session_state.list_items,
                "tool_history": session_state.tool_history,
            },
            "transcript": normalized_transcript,
        },
        "turns": turn_results,
    }

    print()
    print_header("Session Summary")
    print(f"  Score  : {avg_score}  ({pass_count}/{len(turn_results)} passed)")
    print(f"  Tools  : {len(all_tool_calls_flat)} total calls across {len(turns)} turns")
    print(f"  Time   : {session_elapsed_s}s")
    ape_print("done")

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"session_{bench_id}.json"
        out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print_step(f"saved: {out_path}")

    return summary
