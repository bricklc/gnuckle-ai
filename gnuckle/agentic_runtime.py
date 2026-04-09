"""Minimal bounded agentic runtime for the v1 benchmark slice."""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from openai import OpenAI

from gnuckle.agentic_types import FAILURE_REASONS, TERMINAL_STATUSES, Workflow
from gnuckle.session_store import SessionStore
from gnuckle.tool_executor import ToolExecutor, tool_definitions
from gnuckle.benchmark import empty_usage, estimate_context_tokens, update_usage, usage_total_tokens


MODEL = "local-model"
MAX_MALFORMED_TOOL_RETRIES = 1


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _fixture_root(fixture_name: str) -> Path:
    return _package_root() / "fixtures" / fixture_name


def prepare_workspace(workflow: Workflow, output_dir: Path) -> Path:
    source = _fixture_root(workflow.fixture)
    if not source.is_dir():
        raise FileNotFoundError(f"missing workflow fixture: {source}")

    workspace = output_dir / "agentic_workspaces" / f"{workflow.workflow_id}_{uuid4().hex[:8]}"
    shutil.copytree(source, workspace)
    return workspace


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not json serializable: {type(value)!r}")


def _efficiency_score(turns_used: int, max_turns: int, tool_calls_used: int, wall_clock_ms: float, timeout_s: int) -> float:
    turn_penalty = min(0.4, (turns_used / max(1, max_turns)) * 0.4)
    tool_penalty = min(0.3, (tool_calls_used / max(1, max_turns * 2)) * 0.3)
    time_penalty = min(0.3, (wall_clock_ms / max(1.0, timeout_s * 1000)) * 0.3)
    return round(max(0.0, 1.0 - turn_penalty - tool_penalty - time_penalty), 3)


def _constraint_obedience_score(invalid_tool_calls: int, malformed_finish: bool,
                                wrong_tool_calls: int = 0, disallowed_tool_calls: int = 0) -> float:
    penalty = invalid_tool_calls * 0.5
    if malformed_finish:
        penalty += 0.5
    penalty += wrong_tool_calls * 0.15
    penalty += disallowed_tool_calls * 0.35
    return round(max(0.0, 1.0 - penalty), 3)


def _score_episode(task_completed: bool, verification_passed: bool, turns_used: int, max_turns: int,
                   tool_calls_used: int, wall_clock_ms: float, timeout_s: int,
                   invalid_tool_calls: int, malformed_finish: bool,
                   wrong_tool_calls: int = 0, disallowed_tool_calls: int = 0) -> dict:
    task_success = 1.0 if task_completed else 0.0
    verification = 1.0 if verification_passed else 0.0
    constraint_obedience = _constraint_obedience_score(
        invalid_tool_calls,
        malformed_finish,
        wrong_tool_calls=wrong_tool_calls,
        disallowed_tool_calls=disallowed_tool_calls,
    )
    efficiency = _efficiency_score(turns_used, max_turns, tool_calls_used, wall_clock_ms, timeout_s)
    episode_score = round(
        0.55 * task_success
        + 0.20 * constraint_obedience
        + 0.15 * verification
        + 0.10 * efficiency,
        3,
    )
    return {
        "task_success": task_success,
        "constraint_obedience": constraint_obedience,
        "verification": verification,
        "efficiency": efficiency,
        "episode_score": episode_score,
    }


def _normalize_tool_call(tool_call) -> dict:
    return {
        "id": getattr(tool_call, "id", "") or "",
        "name": tool_call.function.name,
        "arguments_json": tool_call.function.arguments or "{}",
    }


def _assistant_message_content(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


def _append_trace(trace: list[dict], entry_type: str, **payload) -> None:
    trace.append({"type": entry_type, **payload})


def _peak_context_tokens_from_trace(trace: list[dict]) -> int:
    peak = 0
    for entry in trace:
        value = entry.get("context_tokens_estimate")
        if isinstance(value, (int, float)):
            peak = max(peak, int(value))
    return peak


def _is_retryable_tool_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return (
        "json" in lowered
        or "tool call" in lowered
        or "invalid tool" in lowered
        or "parse" in lowered
    )


def _tool_message(tool_call_id: str, result: dict) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=True),
    }


def _build_user_event_text(workflow: Workflow, workspace_dir: Path) -> str:
    tool_list = "\n".join(f"- {tool}" for tool in workflow.active_tools)
    return (
        f"{workflow.event_text}\n\n"
        f"Workspace root: {workspace_dir}\n"
        "Active tools:\n"
        f"{tool_list}\n"
        "Rules:\n"
        "- You may only call tools from the active tools list.\n"
        "- Use tools instead of guessing file contents.\n"
        "- Call run_test before finish.\n"
        "- Call finish only when the workspace is ready.\n"
        "- If a tool fails, inspect the tool result and continue.\n"
        "- Keep the final summary concise.\n"
    )


def run_agentic_episode(base_url: str, workflow: Workflow, output_dir: Path, request_args: dict | None = None,
                        session_mode: str = "fresh_session", max_turns_override: int | None = None,
                        system_prompt_override: str | None = None) -> tuple[dict, Path]:
    request_args = request_args or {}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    workspace_dir = prepare_workspace(workflow, output_dir)
    store = SessionStore(output_dir / "agentic_sessions")
    session = store.load_or_create(workflow.workflow_id, session_mode)
    client = OpenAI(base_url=base_url, api_key="none")
    executor = ToolExecutor(workspace_dir, workflow)
    max_turns = max_turns_override or workflow.max_turns
    timeout_s = workflow.timeout_s

    system_prompt = (system_prompt_override or workflow.system_prompt).strip()
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.messages)
    user_event = _build_user_event_text(workflow, workspace_dir)
    messages.append({"role": "user", "content": user_event})

    trace = []
    _append_trace(trace, "event", role="user", event_type=workflow.event_type, content=user_event)

    episode_id = f"{workflow.workflow_id}_{uuid4().hex[:12]}"
    wall_start = time.perf_counter()
    first_action_ms = None
    model_time_ms_total = 0.0
    tool_time_ms_total = 0.0
    verification_time_ms = 0.0
    turn_latencies = []
    total_provider_usage = empty_usage()
    tool_calls_used = 0
    invalid_tool_calls = 0
    retry_events = 0
    malformed_finish_events = 0
    execution_failures = 0
    permission_denials = 0
    synthetic_tool_results = 0
    wrong_tool_calls = 0
    unnecessary_tool_calls = 0
    disallowed_tool_calls = 0
    verification_passed = False
    task_completed = False
    failure_reason = "task_unsolved"
    status = "failed"
    final_summary = ""

    try:
        for turn_index in range(1, max_turns + 1):
            if time.perf_counter() - wall_start > timeout_s:
                status = "timeout"
                failure_reason = "timeout"
                _append_trace(trace, "final_result", status=status, failure_reason=failure_reason)
                break

            assistant_text = ""
            tool_calls = []
            latency_ms = 0.0
            retry_errors = []

            for attempt in range(MAX_MALFORMED_TOOL_RETRIES + 1):
                turn_started = time.perf_counter()
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tool_definitions(workflow.active_tools),
                    tool_choice="auto",
                    temperature=request_args.get("temperature", 0.2),
                    top_p=request_args.get("top_p", 0.9),
                    max_tokens=request_args.get("max_tokens", 512),
                )
                latency_ms = round((time.perf_counter() - turn_started) * 1000, 1)
                turn_latencies.append(latency_ms)
                model_time_ms_total += latency_ms
                if first_action_ms is None:
                    first_action_ms = latency_ms
                message_usage = update_usage(empty_usage(), getattr(response, "usage", None))
                total_provider_usage = update_usage(total_provider_usage, getattr(response, "usage", None))
                context_tokens_estimate = estimate_context_tokens(messages, tool_definitions(workflow.active_tools))

                message = response.choices[0].message
                assistant_text = _assistant_message_content(message)
                tool_calls = [_normalize_tool_call(tc) for tc in (message.tool_calls or [])]
                _append_trace(
                    trace,
                    "assistant_action",
                    turn=turn_index,
                    attempt=attempt + 1,
                    latency_ms=latency_ms,
                    provider_usage=message_usage,
                    provider_usage_total_tokens=usage_total_tokens(message_usage),
                    context_tokens_estimate=context_tokens_estimate,
                    content=assistant_text,
                    tool_calls=tool_calls,
                )

                if not tool_calls:
                    _append_trace(
                        trace,
                        "repair_prompt",
                        turn=turn_index,
                        reason="assistant responded without finish tool",
                    )
                    malformed_finish_events += 1
                    messages.append({"role": "assistant", "content": assistant_text or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": "Previous response did not call an allowed tool or finish. Use the allowed tools and end with finish when ready.",
                        }
                    )
                    tool_calls = []
                    break

                invalid_reason = None
                for tool_call in tool_calls:
                    if tool_call["name"] not in workflow.active_tools:
                        invalid_reason = f"invalid tool call: disallowed tool {tool_call['name']}"
                        break
                    try:
                        json.loads(tool_call["arguments_json"] or "{}")
                    except json.JSONDecodeError as exc:
                        invalid_reason = f"invalid tool call: {exc}"
                        break

                if invalid_reason and attempt < MAX_MALFORMED_TOOL_RETRIES and _is_retryable_tool_error(invalid_reason):
                    invalid_tool_calls += 1
                    retry_events += 1
                    retry_errors.append(invalid_reason)
                    _append_trace(
                        trace,
                        "tool_retry",
                        turn=turn_index,
                        attempt=attempt + 1,
                        reason=invalid_reason,
                    )
                    continue

                if invalid_reason:
                    invalid_tool_calls += 1
                    tool_calls_used += len(tool_calls)
                    synthetic_tool_results += max(1, len(tool_calls))
                    disallowed_tool_calls += sum(1 for tool_call in tool_calls if tool_call["name"] not in workflow.active_tools)
                    messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_text or "",
                            "tool_calls": [
                                {
                                    "id": tool_call["id"] or f"tc_{turn_index}_{index}",
                                    "type": "function",
                                    "function": {
                                        "name": tool_call["name"],
                                        "arguments": tool_call["arguments_json"],
                                    },
                                }
                                for index, tool_call in enumerate(tool_calls)
                            ],
                        }
                    )
                    for index, tool_call in enumerate(tool_calls):
                        tool_error = {
                            "tool": tool_call["name"],
                            "tool_call_id": tool_call["id"] or f"tc_{turn_index}_{index}",
                            "ok": False,
                            "is_error": True,
                            "error_type": "input_validation_error",
                            "error": invalid_reason,
                            "retry_errors": list(retry_errors),
                            "denied": False,
                            "arguments_json": tool_call["arguments_json"],
                        }
                        _append_trace(
                            trace,
                            "tool_result",
                            turn=turn_index,
                            tool_name=tool_call["name"],
                            ok=False,
                            result=tool_error,
                        )
                        messages.append(_tool_message(tool_error["tool_call_id"], tool_error))
                    break

                break

            if not tool_calls:
                continue

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_text or "",
                    "tool_calls": [
                        {
                            "id": tool_call["id"] or f"tc_{turn_index}_{index}",
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                            "arguments": tool_call["arguments_json"],
                            },
                        }
                        for index, tool_call in enumerate(tool_calls)
                    ],
                }
            )

            for tool_call in tool_calls:
                tool_calls_used += 1
                tool_name = tool_call["name"]
                arguments = json.loads(tool_call["arguments_json"] or "{}")
                tool_call_id = tool_call["id"] or f"tc_{turn_index}"

                if tool_name not in workflow.active_tools:
                    disallowed_tool_calls += 1
                elif tool_name not in workflow.expected_tools:
                    wrong_tool_calls += 1
                    unnecessary_tool_calls += 1

                _append_trace(
                    trace,
                    "tool_call",
                    turn=turn_index,
                    tool_name=tool_name,
                    arguments=arguments,
                    expected=tool_name in workflow.expected_tools,
                    active=tool_name in workflow.active_tools,
                )

                result = executor.invoke(tool_call_id, tool_name, arguments)
                if result.get("denied"):
                    permission_denials += 1
                if result.get("error_type") == "execution_error":
                    execution_failures += 1
                if result.get("error_type") == "input_validation_error":
                    invalid_tool_calls += 1
                tool_time_ms_total += result.get("elapsed_ms", 0.0)
                _append_trace(
                    trace,
                    "tool_result",
                    turn=turn_index,
                    tool_name=tool_name,
                    ok=result.get("ok", False),
                    result=result,
                )
                messages.append(_tool_message(tool_call_id, result))

                if not result.get("ok", False):
                    continue

                if tool_name == "finish":
                    final_summary = result.get("summary", "")
                    verification_started = time.perf_counter()
                    verification_result = executor.execute("run_test", {})
                    verification_time_ms = round((time.perf_counter() - verification_started) * 1000, 1)
                    verification_passed = bool(verification_result.get("ok"))
                    _append_trace(
                        trace,
                        "verification",
                        turn=turn_index,
                        method=workflow.verification.method,
                        result=verification_result,
                    )
                    task_completed = verification_passed if workflow.success_rule.type == "test_pass" else True
                    if task_completed:
                        status = "completed"
                        failure_reason = None
                    else:
                        status = "failed"
                        failure_reason = "verification_failed"
                    _append_trace(
                        trace,
                        "final_result",
                        status=status,
                        failure_reason=failure_reason,
                        summary=final_summary,
                        verification_passed=verification_passed,
                    )
                    session.messages = [m for m in messages if m["role"] != "system"]
                    session.episodes_run += 1
                    store.save(session)
                    return _build_episode_result(
                        episode_id=episode_id,
                        workflow=workflow,
                        session_mode=session_mode,
                        status=status,
                        failure_reason=failure_reason,
                        task_completed=task_completed,
                        verification_passed=verification_passed,
                        turns_used=turn_index,
                        tool_calls_used=tool_calls_used,
                        trace=trace,
                        wall_start=wall_start,
                        first_action_ms=first_action_ms,
                        turn_latencies=turn_latencies,
                        tool_time_ms_total=tool_time_ms_total,
                        model_time_ms_total=model_time_ms_total,
                        verification_time_ms=verification_time_ms,
                        total_provider_usage=total_provider_usage,
                        timeout_s=timeout_s,
                        max_turns=max_turns,
                        invalid_tool_calls=invalid_tool_calls,
                        retry_events=retry_events,
                        malformed_finish_events=malformed_finish_events,
                        execution_failures=execution_failures,
                        permission_denials=permission_denials,
                        synthetic_tool_results=synthetic_tool_results,
                        wrong_tool_calls=wrong_tool_calls,
                        unnecessary_tool_calls=unnecessary_tool_calls,
                        disallowed_tool_calls=disallowed_tool_calls,
                        workspace_dir=workspace_dir,
                        final_summary=final_summary,
                    )

        else:
            status = "max_turns"
            failure_reason = "max_turns"
            _append_trace(trace, "final_result", status=status, failure_reason=failure_reason)

    except Exception as exc:  # pragma: no cover
        status = "harness_error"
        failure_reason = "harness_error"
        _append_trace(trace, "final_result", status=status, failure_reason=failure_reason, error=str(exc))

    if status not in TERMINAL_STATUSES:
        status = "harness_error"
        failure_reason = "harness_error"
    if failure_reason is not None and failure_reason not in FAILURE_REASONS:
        failure_reason = "harness_error"

    session.messages = [m for m in messages if m["role"] != "system"]
    session.episodes_run += 1
    store.save(session)
    return _build_episode_result(
        episode_id=episode_id,
        workflow=workflow,
        session_mode=session_mode,
        status=status,
        failure_reason=failure_reason,
        task_completed=task_completed,
        verification_passed=verification_passed,
        turns_used=len(turn_latencies),
        tool_calls_used=tool_calls_used,
        trace=trace,
        wall_start=wall_start,
        first_action_ms=first_action_ms,
        turn_latencies=turn_latencies,
        tool_time_ms_total=tool_time_ms_total,
        model_time_ms_total=model_time_ms_total,
        verification_time_ms=verification_time_ms,
        total_provider_usage=total_provider_usage,
        timeout_s=timeout_s,
        max_turns=max_turns,
        invalid_tool_calls=invalid_tool_calls,
        retry_events=retry_events,
        malformed_finish_events=malformed_finish_events,
        execution_failures=execution_failures,
        permission_denials=permission_denials,
        synthetic_tool_results=synthetic_tool_results,
        wrong_tool_calls=wrong_tool_calls,
        unnecessary_tool_calls=unnecessary_tool_calls,
        disallowed_tool_calls=disallowed_tool_calls,
        workspace_dir=workspace_dir,
        final_summary=final_summary,
    )


def _build_episode_result(episode_id: str, workflow: Workflow, session_mode: str, status: str,
                          failure_reason: str | None, task_completed: bool, verification_passed: bool,
                          turns_used: int, tool_calls_used: int, trace: list[dict], wall_start: float,
                          first_action_ms: float | None, turn_latencies: list[float], tool_time_ms_total: float,
                          model_time_ms_total: float, verification_time_ms: float, total_provider_usage: dict, timeout_s: int,
                          max_turns: int, invalid_tool_calls: int, retry_events: int, malformed_finish_events: int,
                          execution_failures: int, permission_denials: int, synthetic_tool_results: int,
                          wrong_tool_calls: int, unnecessary_tool_calls: int, disallowed_tool_calls: int,
                          workspace_dir: Path, final_summary: str) -> tuple[dict, Path]:
    wall_clock_ms = round((time.perf_counter() - wall_start) * 1000, 1)
    scores = _score_episode(
        task_completed=task_completed,
        verification_passed=verification_passed,
        turns_used=turns_used,
        max_turns=max_turns,
        tool_calls_used=tool_calls_used,
        wall_clock_ms=wall_clock_ms,
        timeout_s=timeout_s,
        invalid_tool_calls=invalid_tool_calls,
        malformed_finish=malformed_finish_events > 0,
        wrong_tool_calls=wrong_tool_calls,
        disallowed_tool_calls=disallowed_tool_calls,
    )
    tool_selection_precision = round(
        max(0.0, (tool_calls_used - wrong_tool_calls - disallowed_tool_calls) / tool_calls_used),
        3,
    ) if tool_calls_used else 1.0
    episode = {
        "episode_id": episode_id,
        "workflow_id": workflow.workflow_id,
        "mode": session_mode,
        "status": status,
        "failure_reason": failure_reason,
        "task_completed": task_completed,
        "verification_passed": verification_passed,
        "turns_used": turns_used,
        "tool_calls_used": tool_calls_used,
        "performance": {
            "wall_clock_ms": wall_clock_ms,
            "time_to_first_action_ms": first_action_ms or 0.0,
            "time_to_finish_ms": wall_clock_ms,
            "avg_turn_latency_ms": round(sum(turn_latencies) / len(turn_latencies), 1) if turn_latencies else 0.0,
            "max_turn_latency_ms": round(max(turn_latencies), 1) if turn_latencies else 0.0,
            "tool_time_ms_total": round(tool_time_ms_total, 1),
            "model_time_ms_total": round(model_time_ms_total, 1),
            "verification_time_ms": round(verification_time_ms, 1),
        },
        "provider_usage": total_provider_usage,
        "provider_usage_total_tokens": usage_total_tokens(total_provider_usage),
        "scores": scores,
        "failure_events": {
            "invalid_tool_calls": invalid_tool_calls,
            "retry_events": retry_events,
            "malformed_finish_events": malformed_finish_events,
            "execution_failures": execution_failures,
            "permission_denials": permission_denials,
            "synthetic_tool_results": synthetic_tool_results,
            "wrong_tool_calls": wrong_tool_calls,
            "unnecessary_tool_calls": unnecessary_tool_calls,
            "disallowed_tool_calls": disallowed_tool_calls,
        },
        "tool_selection": {
            "active_tools": list(workflow.active_tools),
            "expected_tools": list(workflow.expected_tools),
            "wrong_tool_calls": wrong_tool_calls,
            "unnecessary_tool_calls": unnecessary_tool_calls,
            "disallowed_tool_calls": disallowed_tool_calls,
            "tool_selection_precision": tool_selection_precision,
        },
        "trace": trace,
        "workspace_dir": str(workspace_dir),
        "final_summary": final_summary,
    }
    return episode, workspace_dir


def build_agentic_run_summary(workflow: Workflow, episode: dict, model_name: str, cache_label: str,
                              session_mode: str, output_dir: Path, workflow_suite: str = "default") -> tuple[dict, Path]:
    episode_ms = episode["performance"]["wall_clock_ms"]
    turn_latency = episode["performance"]["avg_turn_latency_ms"]
    run_id = f"agentic_{cache_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    aggregate = {
        "success_rate": 1.0 if episode["task_completed"] else 0.0,
        "verification_rate": 1.0 if episode["verification_passed"] else 0.0,
        "avg_turns": float(episode["turns_used"]),
        "avg_tool_calls": float(episode["tool_calls_used"]),
        "median_episode_ms": episode_ms,
        "p95_episode_ms": episode_ms,
        "median_turn_latency_ms": turn_latency,
        "p95_turn_latency_ms": turn_latency,
        "episodes_per_hour": round(3600000 / episode_ms, 3) if episode_ms > 0 else 0.0,
        "successful_episodes_per_hour": round(3600000 / episode_ms, 3) if episode_ms > 0 and episode["task_completed"] else 0.0,
        "failure_distribution": {episode["failure_reason"] or "none": 1},
        "retry_events": int(episode.get("failure_events", {}).get("retry_events", 0)),
        "invalid_tool_calls": int(episode.get("failure_events", {}).get("invalid_tool_calls", 0)),
        "malformed_finish_events": int(episode.get("failure_events", {}).get("malformed_finish_events", 0)),
        "execution_failures": int(episode.get("failure_events", {}).get("execution_failures", 0)),
        "permission_denials": int(episode.get("failure_events", {}).get("permission_denials", 0)),
        "synthetic_tool_results": int(episode.get("failure_events", {}).get("synthetic_tool_results", 0)),
        "wrong_tool_calls": int(episode.get("failure_events", {}).get("wrong_tool_calls", 0)),
        "unnecessary_tool_calls": int(episode.get("failure_events", {}).get("unnecessary_tool_calls", 0)),
        "disallowed_tool_calls": int(episode.get("failure_events", {}).get("disallowed_tool_calls", 0)),
        "tool_selection_precision": float(episode.get("tool_selection", {}).get("tool_selection_precision", 0.0)),
        "provider_input_tokens": int(episode.get("provider_usage", {}).get("input_tokens", 0) or 0),
        "provider_output_tokens": int(episode.get("provider_usage", {}).get("output_tokens", 0) or 0),
        "provider_total_tokens": int(episode.get("provider_usage_total_tokens", 0) or 0),
        "peak_context_tokens_estimate": _peak_context_tokens_from_trace(episode.get("trace", [])),
    }
    summary = {
        "run_id": run_id,
        "benchmark_mode": "agentic",
        "model_id": model_name,
        "cache_label": cache_label,
        "workflow_suite": workflow_suite,
        "session_mode": session_mode,
        "generated_at": datetime.now().isoformat(),
        "episodes": [episode],
        "aggregate": aggregate,
        "workflow": {
            "workflow_id": workflow.workflow_id,
            "title": workflow.title,
            "slice": workflow.slice,
            "difficulty": workflow.difficulty,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")
    return summary, out_path
