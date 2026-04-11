"""Session benchmark runner — executes community benchmark files as persistent sessions.

A session benchmark is a JSON file that defines:
- One system prompt and tool list
- A deterministic sequence of turns
- Mock tool results for each turn
- Expected tool behavior and scoring criteria per turn

The runner keeps one conversation alive across all turns, measuring
retention, accuracy, and performance degradation as context grows.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from openai import OpenAI

from gnuckle.benchmark import (
    accumulate_usage,
    empty_usage,
    estimate_context_token_counts,
    get_hardware_snapshot,
    print_header,
    print_step,
    render_progress,
    update_usage,
    usage_total_tokens,
    ape_print,
)
from gnuckle.tool_executor import tool_definitions


MODEL = "local-model"
BENCHMARKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks"


# ── BENCHMARK FILE LOADING ──────────────────────────────────────────────────

def discover_benchmarks(search_dir: Path | None = None) -> list[dict]:
    """Find all .json benchmark files in the benchmarks directory."""
    directory = search_dir or BENCHMARKS_DIR
    if not directory.is_dir():
        return []
    results = []
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("type") == "session" and "turns" in data:
                data["_path"] = str(path)
                results.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def load_benchmark(bench_id: str, search_dir: Path | None = None) -> dict:
    """Load a specific benchmark by ID."""
    for bench in discover_benchmarks(search_dir):
        if bench["id"] == bench_id:
            return bench
    raise ValueError(f"benchmark not found: {bench_id}")


# ── MOCK TOOL EXECUTOR ──────────────────────────────────────────────────────

class MockToolExecutor:
    """Returns predetermined results from the benchmark turn definition.

    For deterministic benchmarking, every tool call returns the exact same
    mock output on every run. If a tool is called multiple times in one turn
    and the mock is a list, results are consumed in order.
    """

    def __init__(self, mock_results: dict):
        self._mocks = {}
        for tool_name, result in mock_results.items():
            if isinstance(result, list):
                self._mocks[tool_name] = list(result)  # copy
            else:
                self._mocks[tool_name] = result

    def invoke(self, tool_call_id: str, tool_name: str, arguments: dict) -> dict:
        mock = self._mocks.get(tool_name)
        if mock is None:
            return {
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "ok": False,
                "is_error": True,
                "error_type": "no_mock_defined",
                "error": f"no mock result defined for tool '{tool_name}'",
                "output": "",
            }

        if isinstance(mock, list):
            if mock:
                result = mock.pop(0)
            else:
                result = {"output": f"[mock exhausted for {tool_name}]"}
        else:
            result = mock

        output = result.get("output", "")
        return {
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "ok": True,
            "is_error": False,
            "output": output,
        }


# ── PER-TURN SCORING ────────────────────────────────────────────────────────

def _score_turn(turn_def: dict, actual_tool_calls: list[str], assistant_text: str,
                hallucinated_tools: list[str]) -> dict:
    """Score a single turn against its expectations."""
    expect = turn_def.get("expect", {})
    scores = {}

    # Tool precision: did the model call exactly the expected tools?
    expected_tools = expect.get("tools_called", [])
    if expected_tools:
        called_set = set(actual_tool_calls)
        expected_set = set(expected_tools)
        correct = called_set & expected_set
        extra = called_set - expected_set
        missing = expected_set - called_set
        scores["tool_recall"] = round(len(correct) / max(1, len(expected_set)), 3)
        scores["tool_precision"] = round(len(correct) / max(1, len(called_set)), 3) if called_set else (1.0 if not expected_set else 0.0)
        scores["extra_tools"] = sorted(extra)
        scores["missing_tools"] = sorted(missing)
    else:
        scores["tool_recall"] = 1.0
        scores["tool_precision"] = 1.0
        scores["extra_tools"] = []
        scores["missing_tools"] = []

    # Tool order
    tool_order = expect.get("tool_order", [])
    if tool_order:
        # Check if actual calls follow expected order (allowing extras between)
        order_idx = 0
        for tc in actual_tool_calls:
            if order_idx < len(tool_order) and tc == tool_order[order_idx]:
                order_idx += 1
        scores["tool_order_correct"] = order_idx >= len(tool_order)
    else:
        scores["tool_order_correct"] = True

    # Negative tool check
    not_called = expect.get("tools_not_called", [])
    violations = [t for t in not_called if t in actual_tool_calls]
    scores["unwanted_tool_violations"] = violations

    # Hallucination check
    scores["hallucinated_tools"] = hallucinated_tools

    # Response content check
    contains = expect.get("response_contains", [])
    if contains:
        text_lower = assistant_text.lower()
        found = [c for c in contains if c.lower() in text_lower]
        scores["content_recall"] = round(len(found) / len(contains), 3)
        scores["content_missing"] = [c for c in contains if c.lower() not in text_lower]
    else:
        scores["content_recall"] = 1.0
        scores["content_missing"] = []

    # Bullet point format check
    if expect.get("response_format") == "bullet_points":
        lines = [l.strip() for l in assistant_text.strip().split("\n") if l.strip()]
        bullet_lines = [l for l in lines if re.match(r"^[-*•]\s", l) or re.match(r"^\d+[.)]\s", l)]
        scores["format_correct"] = len(bullet_lines) >= max(1, len(lines) // 2)
    else:
        scores["format_correct"] = True

    # Refusal check
    if expect.get("expect_refusal"):
        refusal_phrases = ["cannot", "can't", "don't have", "not available", "no tool", "not possible", "unable"]
        scores["refusal_detected"] = any(p in assistant_text.lower() for p in refusal_phrases)
    else:
        scores["refusal_detected"] = None

    # Composite turn score
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
    scores["turn_score"] = round(composite, 3)

    return scores


# ── SESSION RUNNER ───────────────────────────────────────────────────────────

def run_session_benchmark(
    benchmark: dict,
    base_url: str,
    request_args: dict | None = None,
    output_dir: Path | None = None,
    server_pid: int | None = None,
    context_window: int | None = None,
    observer=None,
) -> dict:
    """Run a full session benchmark and return the results summary."""
    request_args = request_args or {}
    bench_id = benchmark["id"]
    turns = benchmark["turns"]
    tools = benchmark["tools"]
    system_prompt = benchmark["system_prompt"]
    standing_rules = benchmark.get("standing_rules", [])

    if standing_rules:
        rules_text = "\n".join(f"- {r}" for r in standing_rules)
        system_prompt = f"{system_prompt}\n\nStanding rules:\n{rules_text}"

    client = OpenAI(base_url=base_url, api_key="none")
    messages = [{"role": "system", "content": system_prompt}]
    tool_defs = tool_definitions(tools)

    session_id = f"{bench_id}_{uuid4().hex[:12]}"
    turn_results = []
    all_tool_calls_flat = []
    initial_hardware = get_hardware_snapshot(server_pid)
    session_start = time.perf_counter()

    print_header(f"Session Benchmark: {benchmark['title']}")
    print_step(f"id: {bench_id}  turns: {len(turns)}  tools: {len(tools)}")
    print_step(f"rules: {len(standing_rules)}  type: persistent session")
    print()

    total_provider_usage = empty_usage()

    for turn_idx, turn_def in enumerate(turns):
        turn_num = turn_idx + 1
        turn_id = turn_def["id"]
        turn_title = turn_def.get("title", turn_id)
        prompt = turn_def["prompt"]
        mock_results = turn_def.get("mock_results", {})
        mock_executor = MockToolExecutor(mock_results)

        render_progress(f"turn {turn_num}/{len(turns)}: {turn_id}", turn_idx, len(turns), done=False)
        print_step(f"turn {turn_num}/{len(turns)}: {turn_title}")

        # Send user prompt
        messages.append({"role": "user", "content": prompt})

        # Model call
        turn_start = time.perf_counter()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_defs,
            tool_choice="auto",
            temperature=request_args.get("temperature", 0.6),
            top_p=request_args.get("top_p", 0.95),
            max_tokens=request_args.get("max_tokens", 512),
        )
        first_response_ms = round((time.perf_counter() - turn_start) * 1000, 1)

        message_usage = update_usage(empty_usage(), getattr(response, "usage", None))
        total_provider_usage = accumulate_usage(total_provider_usage, message_usage)

        message = response.choices[0].message
        assistant_text = getattr(message, "content", "") or ""
        raw_tool_calls = [
            {
                "id": getattr(tc, "id", "") or f"tc_{turn_num}_{i}",
                "name": tc.function.name,
                "arguments_json": tc.function.arguments or "{}",
            }
            for i, tc in enumerate(message.tool_calls or [])
        ]

        # Process tool calls in a loop (model may chain multiple rounds)
        actual_tools_called = []
        hallucinated_tools = []
        tool_round = 0
        max_tool_rounds = 10

        while raw_tool_calls and tool_round < max_tool_rounds:
            tool_round += 1

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": assistant_text or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments_json"],
                        },
                    }
                    for tc in raw_tool_calls
                ],
            })

            # Execute each tool call
            for tc in raw_tool_calls:
                tool_name = tc["name"]
                actual_tools_called.append(tool_name)
                all_tool_calls_flat.append(tool_name)

                if tool_name not in tools:
                    hallucinated_tools.append(tool_name)

                arguments = json.loads(tc["arguments_json"] or "{}")
                result = mock_executor.invoke(tc["id"], tool_name, arguments)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

            # Check if model wants to continue (more tool calls or final response)
            followup_start = time.perf_counter()
            followup = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tool_defs,
                tool_choice="auto",
                temperature=request_args.get("temperature", 0.6),
                top_p=request_args.get("top_p", 0.95),
                max_tokens=request_args.get("max_tokens", 512),
            )
            followup_ms = round((time.perf_counter() - followup_start) * 1000, 1)

            followup_usage = update_usage(empty_usage(), getattr(followup, "usage", None))
            total_provider_usage = accumulate_usage(total_provider_usage, followup_usage)

            followup_message = followup.choices[0].message
            assistant_text = getattr(followup_message, "content", "") or ""
            raw_tool_calls = [
                {
                    "id": getattr(tc, "id", "") or f"tc_{turn_num}_r{tool_round}_{i}",
                    "name": tc.function.name,
                    "arguments_json": tc.function.arguments or "{}",
                }
                for i, tc in enumerate(followup_message.tool_calls or [])
            ]

        # Final assistant text appended to messages
        if not raw_tool_calls:
            messages.append({"role": "assistant", "content": assistant_text or ""})

        turn_elapsed_ms = round((time.perf_counter() - turn_start) * 1000, 1)

        # Context estimation
        context_counts = estimate_context_token_counts(messages, tool_defs, base_url=base_url)
        context_estimate = (
            int(context_counts["measured"])
            if context_counts["measured"] is not None
            else int(context_counts["heuristic"])
        )

        # Hardware snapshot
        hardware = get_hardware_snapshot(server_pid)

        # Score this turn
        scores = _score_turn(turn_def, actual_tools_called, assistant_text, hallucinated_tools)

        turn_result = {
            "turn": turn_num,
            "turn_id": turn_id,
            "title": turn_title,
            "tools_called": actual_tools_called,
            "hallucinated_tools": hallucinated_tools,
            "tool_rounds": tool_round,
            "assistant_text": assistant_text[:500],
            "scores": scores,
            "metrics": {
                "ttft_ms": first_response_ms,
                "turn_elapsed_ms": turn_elapsed_ms,
                "context_tokens_estimate": context_estimate,
                "context_tokens_heuristic": context_counts["heuristic"],
                "provider_usage": message_usage,
                "provider_usage_total": usage_total_tokens(message_usage),
                "hardware": hardware,
            },
        }
        turn_results.append(turn_result)

        status = "PASS" if scores["turn_score"] >= 0.7 else "FAIL"
        print(f"    {status} score={scores['turn_score']}  tools={actual_tools_called}  ttft={first_response_ms}ms  ctx≈{context_estimate}")

    render_progress(f"session complete", len(turns), len(turns), done=True)

    # Aggregate session summary
    session_elapsed_s = round(time.perf_counter() - session_start, 2)
    avg_score = round(sum(t["scores"]["turn_score"] for t in turn_results) / max(1, len(turn_results)), 3)
    pass_count = sum(1 for t in turn_results if t["scores"]["turn_score"] >= 0.7)
    final_hardware = get_hardware_snapshot(server_pid)

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
        },
        "turns": turn_results,
    }

    print()
    print_header("Session Summary")
    print(f"  Score  : {avg_score}  ({pass_count}/{len(turn_results)} passed)")
    print(f"  Tools  : {len(all_tool_calls_flat)} total calls across {len(turns)} turns")
    print(f"  Time   : {session_elapsed_s}s")
    ape_print("done")

    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"session_{bench_id}.json"
        out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print_step(f"saved: {out_path}")

    return summary
