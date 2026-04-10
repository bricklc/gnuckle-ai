"""Deterministic scoring and benchmark aggregation for workflow suites."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from statistics import mean, pstdev

from gnuckle.agentic_types import Workflow


PROFILE_WEIGHTS = {
    "wf_a_journal_analysis": 0.12,
    "wf_b_note_triage": 0.12,
    "wf_c_daily_agenda": 0.16,
    "wf_c_tl_taglish_agenda": 0.08,
    "wf_d_memory_retention": 0.14,
    "wf_e_commitment_tracking": 0.14,
    "wf_f_scope_boundary": 0.08,
    "wf_g_implicit_format": 0.16,
}

COMPOSITE_WEIGHTS = {"core": 0.4, "profile": 0.6}
CORE_EXCLUDED_FROM_COMPOSITE = {"cb_08_resource_viability"}
MOTIVATIONAL_LANGUAGE = {
    "you got this",
    "keep pushing",
    "stay strong",
    "you can do it",
    "hang in there",
    "keep going",
}


def score_episode(workflow: Workflow, episode: dict) -> dict:
    ground_truth = _load_ground_truth(workflow, episode)
    trace = episode.get("trace", [])
    texts = _collected_texts(episode)
    lower_text = "\n".join(texts).lower()
    successful_tools = _successful_tool_results(trace)
    tool_calls = _tool_calls(trace)
    written_paths = _written_paths(trace)
    written_contents = _written_contents(episode, written_paths)

    scorer = WORKFLOW_SCORERS.get(workflow.workflow_id, _default_score)
    result = scorer(
        workflow=workflow,
        episode=episode,
        ground_truth=ground_truth,
        trace=trace,
        texts=texts,
        lower_text=lower_text,
        successful_tools=successful_tools,
        tool_calls=tool_calls,
        written_paths=written_paths,
        written_contents=written_contents,
    )
    result["workflow_id"] = workflow.workflow_id
    result["benchmark_layer"] = workflow.benchmark_layer
    result["profile_id"] = workflow.profile_id
    result["prompt_weight_variant"] = workflow.prompt_weight_variant
    return result


def aggregate_workflow_runs(workflow: Workflow, episodes: list[dict]) -> dict:
    scored = [score_episode(workflow, episode) for episode in episodes]
    values = [float(item["workflow_score"]) for item in scored]
    derived = _aggregate_derived_metrics(scored)
    return {
        "workflow_id": workflow.workflow_id,
        "title": workflow.title,
        "benchmark_layer": workflow.benchmark_layer,
        "profile_id": workflow.profile_id,
        "workflow_variant_of": workflow.workflow_variant_of,
        "prompt_weight_variant": workflow.prompt_weight_variant,
        "reporting_tags": workflow.reporting_tags,
        "run_count": len(scored),
        "workflow_score_mean": round(mean(values), 3) if values else 0.0,
        "workflow_score_stddev": round(pstdev(values), 3) if len(values) > 1 else 0.0,
        "scores": values,
        "derived_metrics": derived,
        "episodes": scored,
        "usability_flags": _workflow_usability_flags(workflow, scored),
    }


def finalize_benchmark_summary(
    workflow_summaries: list[dict],
    diagnostics: list[dict],
    cache_label: str,
    model_name: str,
    session_mode: str,
    workflow_suite: str,
    runtime_config: dict,
    generated_at: str,
) -> dict:
    by_id = {item["workflow_id"]: item for item in workflow_summaries}
    diagnostic_results = {
        item["workflow_id"]: item["workflow_score_mean"]
        for item in diagnostics
    }
    benchmark_type = assign_type(diagnostic_results)

    core_candidates = [
        item for item in workflow_summaries
        if item["benchmark_layer"] == "core" and item["workflow_id"] not in CORE_EXCLUDED_FROM_COMPOSITE
    ]
    core_score = round(mean(item["workflow_score_mean"] for item in core_candidates), 3) if core_candidates else 0.0

    if benchmark_type == "Type 2" and core_score > 0.85:
        benchmark_type = "Type 3"

    profile_candidates = [
        item for item in workflow_summaries
        if item["benchmark_layer"] == "profile" and item["workflow_id"] in PROFILE_WEIGHTS
    ]
    weighted_profile_total = sum(item["workflow_score_mean"] * PROFILE_WEIGHTS[item["workflow_id"]] for item in profile_candidates)
    profile_score = round(weighted_profile_total, 3) if profile_candidates else None

    if profile_score is None:
        composite = core_score
    else:
        composite = round((core_score * COMPOSITE_WEIGHTS["core"]) + (profile_score * COMPOSITE_WEIGHTS["profile"]), 3)

    grade = grade_for_score(composite)
    derived_metrics = _benchmark_level_metrics(by_id)
    usability_flags = _benchmark_usability_flags(by_id, benchmark_type, grade)
    routing = routing_decision(benchmark_type)

    return {
        "benchmark_mode": "agentic",
        "cache_label": cache_label,
        "model_id": model_name,
        "workflow_suite": workflow_suite,
        "session_mode": session_mode,
        "generated_at": generated_at,
        "runtime_config": runtime_config,
        "diagnostics": diagnostics,
        "workflow_results": workflow_summaries,
        "summary": {
            "type": benchmark_type,
            "grade": grade,
            "core_score": core_score,
            "profile_score": profile_score,
            "composite_score": composite,
            "routing_decision": routing,
            "stress_variants_enabled": benchmark_type == "Type 3",
            "derived_metrics": derived_metrics,
            "usability_flags": usability_flags,
        },
    }


def assign_type(diagnostic_results: dict[str, float]) -> str:
    d1 = diagnostic_results.get("d_1_single_tool_call", 0.0)
    d2 = diagnostic_results.get("d_2_two_tool_sequence", 0.0)
    d3 = diagnostic_results.get("d_3_rule_retention", 0.0)
    if d1 < 1.0:
        return "Type 0"
    if d2 < 1.0 or d3 < 1.0:
        return "Type 1"
    return "Type 2"


def routing_decision(benchmark_type: str) -> str:
    if benchmark_type == "Type 0":
        return "core_only_floor"
    if benchmark_type == "Type 1":
        return "core_plus_easy_profiles"
    if benchmark_type == "Type 2":
        return "core_plus_full_profiles"
    return "core_profiles_and_stress_variants"


def grade_for_score(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.75:
        return "B"
    if score >= 0.60:
        return "C"
    if score >= 0.45:
        return "D"
    return "F"


def _load_ground_truth(workflow: Workflow, episode: dict) -> dict:
    explicit_path = workflow.ground_truth_path
    if explicit_path:
        candidates = [Path(explicit_path)]
    else:
        candidates = [Path(episode.get("workspace_dir", "")) / "_ground_truth.json"]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _collected_texts(episode: dict) -> list[str]:
    texts = []
    if episode.get("final_summary"):
        texts.append(str(episode["final_summary"]))
    for entry in episode.get("trace", []):
        if entry.get("type") in {"assistant_action", "plaintext_turn", "event", "mid_task_injection"}:
            content = entry.get("content")
            if content:
                texts.append(str(content))
    return texts


def _successful_tool_results(trace: list[dict]) -> list[dict]:
    return [
        entry for entry in trace
        if entry.get("type") == "tool_result" and (entry.get("result") or {}).get("ok")
    ]


def _tool_calls(trace: list[dict]) -> list[dict]:
    return [entry for entry in trace if entry.get("type") == "tool_call"]


def _written_paths(trace: list[dict]) -> list[str]:
    paths = []
    for entry in trace:
        if entry.get("type") != "tool_result":
            continue
        result = entry.get("result") or {}
        if result.get("ok") and result.get("tool") in {"write_file", "append_file", "edit_file"} and result.get("path"):
            paths.append(str(result["path"]))
    return paths


def _written_contents(episode: dict, paths: list[str]) -> dict[str, str]:
    workspace = Path(episode.get("workspace_dir", ""))
    contents = {}
    for rel in paths:
        path = workspace / rel
        if path.is_file():
            contents[rel] = path.read_text(encoding="utf-8")
    return contents


def _latest_written_text(written_contents: dict[str, str]) -> str:
    if not written_contents:
        return ""
    return next(reversed(list(written_contents.values())))


def _contains_all(text: str, phrases: list[str]) -> float:
    if not phrases:
        return 1.0
    hits = sum(1 for phrase in phrases if phrase.lower() in text)
    return round(hits / len(phrases), 3)


def _trace_reads(trace: list[dict]) -> list[str]:
    reads = []
    for entry in trace:
        if entry.get("type") != "tool_result":
            continue
        result = entry.get("result") or {}
        if result.get("ok") and result.get("tool") == "read_file":
            reads.append(str(result.get("path", "")))
    return reads


def _trace_tool_names(trace: list[dict]) -> list[str]:
    return [str(entry.get("tool_name")) for entry in trace if entry.get("type") == "tool_call"]


def _final_answer_text(texts: list[str], written_contents: dict[str, str]) -> str:
    if written_contents:
        return _latest_written_text(written_contents)
    return "\n".join(texts)


def _binary(value: bool) -> float:
    return 1.0 if value else 0.0


def _score_with_criteria(criteria: dict[str, float], derived: dict | None = None, evidence: dict | None = None) -> dict:
    total = round(sum(criteria.values()) / max(1, len(criteria)), 3)
    return {
        "workflow_score": total,
        "criteria": criteria,
        "derived_metrics": derived or {},
        "audit_evidence": evidence or {},
    }


def _default_score(**kwargs) -> dict:
    episode = kwargs["episode"]
    return _score_with_criteria(
        {"completion": _binary(bool(episode.get("task_completed")))},
        derived={"status": episode.get("status")},
    )


def _score_d1(**kwargs) -> dict:
    trace = kwargs["trace"]
    tool_calls = _trace_tool_names(trace)
    valid = "echo" in tool_calls
    echo_results = [
        ((entry.get("result") or {}).get("text") or "").lower()
        for entry in trace
        if entry.get("type") == "tool_result" and (entry.get("result") or {}).get("tool") == "echo"
    ]
    arg_match = any(text == "benchmark test" for text in echo_results)
    score = 1.0 if valid and arg_match else 0.5 if valid else 0.0
    return {
        "workflow_score": score,
        "criteria": {"valid_tool_call": score},
        "derived_metrics": {"tool_used": "echo" if valid else None},
        "audit_evidence": {"tool_calls": tool_calls},
    }


def _score_d2(**kwargs) -> dict:
    episode = kwargs["episode"]
    workspace = Path(episode.get("workspace_dir", "")) / ".gnuckle_list_state.json"
    items = json.loads(workspace.read_text(encoding="utf-8")) if workspace.is_file() else []
    final_texts = [item.get("text") for item in items]
    expected = ["diagnostic task updated"]
    score = 1.0 if final_texts == expected else 0.5 if final_texts else 0.0
    return _score_with_criteria(
        {"sequence_success": score},
        derived={"final_items": final_texts},
        evidence={"tool_calls": _trace_tool_names(kwargs["trace"])},
    )


def _score_d3(**kwargs) -> dict:
    text = _final_answer_text(kwargs["texts"], kwargs["written_contents"]).lower()
    bullet_points = any(line.strip().startswith(("-", "*", "•")) for line in text.splitlines() if line.strip())
    return _score_with_criteria(
        {"rule_obeyed": _binary(bullet_points)},
        derived={"bullets_used": bullet_points},
    )


def _score_cb1(**kwargs) -> dict:
    return _score_d1(**kwargs)


def _score_cb2(**kwargs) -> dict:
    precision = float(kwargs["episode"].get("tool_selection", {}).get("tool_selection_precision", 0.0))
    delete_used = "delete_file" in _trace_tool_names(kwargs["trace"])
    score = max(0.0, precision - (0.5 if delete_used else 0.0))
    return _score_with_criteria(
        {"tool_selection_precision": round(score, 3)},
        derived={"tool_selection_precision": precision, "delete_file_used": delete_used},
    )


def _score_cb3(**kwargs) -> dict:
    episode = kwargs["episode"]
    hallucinated = int((episode.get("failure_events") or {}).get("disallowed_tool_calls", 0)) > 0
    graceful = any(word in kwargs["lower_text"] for word in ["cannot", "can't", "no tool", "not available", "draft"])
    workaround = "write_file" in _trace_tool_names(kwargs["trace"])
    score = 1.0 if (not hallucinated and (graceful or workaround)) else 0.5 if not hallucinated else 0.0
    return _score_with_criteria(
        {"refusal_correctness": score},
        derived={"hallucinated_tool": hallucinated, "workaround_used": workaround},
    )


def _score_cb4(**kwargs) -> dict:
    ground_truth = kwargs["ground_truth"]
    workspace = Path(kwargs["episode"].get("workspace_dir", "")) / ".gnuckle_list_state.json"
    items = json.loads(workspace.read_text(encoding="utf-8")) if workspace.is_file() else []
    texts = [item.get("text") for item in items]
    expected = ground_truth.get("expected_final_list", [])
    forbidden = ground_truth.get("forbidden_items", [])
    exact = texts == expected
    forbidden_hit = any(item.lower() in "\n".join(texts).lower() for item in forbidden)
    score = 1.0 if exact and not forbidden_hit else 0.5 if texts else 0.0
    return _score_with_criteria(
        {"final_state": score},
        derived={"final_items": texts},
    )


def _score_rule_retention(answer_text: str, rules: list[str]) -> tuple[float, dict]:
    lines = [line.strip() for line in answer_text.splitlines() if line.strip()]
    bullets_used = bool(lines) and all(line.startswith(("-", "*", "•")) for line in lines[: min(3, len(lines))])
    no_late = not re.search(r"\b(8:([0-5][0-9])|9|10|11|12)\s?(pm|PM)\b", answer_text)
    health_keywords = {"health", "stretch", "rehab", "sleep", "dentist", "exercise"}
    first_content = lines[0].lower() if lines else ""
    health_first = any(word in first_content for word in health_keywords) if lines else False
    no_motivational = not any(phrase in answer_text.lower() for phrase in MOTIVATIONAL_LANGUAGE)
    checks = {
        "Always respond in bullet points.": bullets_used,
        "Never suggest activities after 8pm.": no_late,
        "Health-related items go first in any list.": health_first,
        "Do not include motivational language. Facts only.": no_motivational,
    }
    matched = [checks.get(rule, False) for rule in rules]
    rate = round(sum(1 for flag in matched if flag) / max(1, len(rules)), 3)
    return rate, {
        "bullets_used": bullets_used,
        "no_late_activities": no_late,
        "health_first": health_first,
        "no_motivational_language": no_motivational,
    }


def _score_cb5(**kwargs) -> dict:
    answer = _final_answer_text(kwargs["texts"], kwargs["written_contents"])
    rate, details = _score_rule_retention(answer, kwargs["ground_truth"].get("standing_rules", []))
    return _score_with_criteria({"cul_retention": rate}, derived={"cul_retention_rate": rate, **details})


def _score_cb6(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    answers = gt.get("canonical_questions", {})
    hits = sum(1 for answer in answers.values() if str(answer).lower() in kwargs["lower_text"])
    recall_rate = round(hits / max(1, len(answers)), 3)
    peak_context = int((kwargs["episode"].get("token_usage") or {}).get("context_tokens_measured") or (kwargs["episode"].get("token_usage") or {}).get("context_tokens_heuristic") or 0)
    mrmb = peak_context if recall_rate >= 0.5 else None
    return _score_with_criteria(
        {"memory_recall": recall_rate},
        derived={"memory_recall_rate": recall_rate, "MRMB": mrmb},
    )


def _score_cb7(**kwargs) -> dict:
    facts_rate = _contains_all(kwargs["lower_text"], kwargs["ground_truth"].get("required_summary_facts", []))
    context_percent = (kwargs["episode"].get("token_usage") or {}).get("context_percent_used") or 0
    degradation = round(max(0.0, 1.0 - facts_rate), 3)
    return _score_with_criteria(
        {"required_fact_recall": facts_rate},
        derived={
            "context_degradation_gradient": degradation,
            "context_percent_used": context_percent,
        },
    )


def _score_cb8(**kwargs) -> dict:
    episode = kwargs["episode"]
    performance = episode.get("performance") or {}
    ok = episode.get("status") != "harness_error"
    moderate_latency = float(performance.get("avg_turn_latency_ms", 0)) < 20000
    moderate_vram = int((episode.get("hardware_usage") or {}).get("vram_peak_mb", 0) or 0) < 65536
    score = round((int(ok) + int(moderate_latency) + int(moderate_vram)) / 3, 3)
    return _score_with_criteria(
        {"resource_viability": score},
        derived={"resource_viability": score},
    )


def _score_cb9(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    reads = _trace_reads(kwargs["trace"])
    discovery = any(path.endswith("convention.md") or "example_output" in path for path in reads)
    written_text = _latest_written_text(kwargs["written_contents"]).lower()
    front_matter = written_text.startswith("---")
    title_ok = "\n# " in written_text
    closing_ok = "next:" in written_text
    summary_rate = _contains_all(written_text, gt.get("summary_must_include", []))
    format_score = round((int(front_matter) + int(title_ok) + int(closing_ok)) / 3, 3)
    score = round((0.2 * _binary(discovery)) + (0.4 * format_score) + (0.4 * summary_rate), 3)
    return {
        "workflow_score": score,
        "criteria": {
            "discovery": _binary(discovery),
            "format_compliance": format_score,
            "summary_accuracy": summary_rate,
        },
        "derived_metrics": {"convention_discovery": _binary(discovery)},
        "audit_evidence": {"reads": reads, "written_paths": kwargs["written_paths"]},
    }


def _score_cb10(**kwargs) -> dict:
    failures = kwargs["episode"].get("failure_events") or {}
    graceful = any(word in kwargs["lower_text"] for word in ["cannot", "can't", "denied", "not allowed", "limitation"])
    repeated = int(failures.get("repeated_bad_tool_calls", 0))
    denials = int(failures.get("permission_denials", 0))
    score = 1.0 if denials > 0 and graceful and repeated == 0 else 0.5 if denials > 0 else 0.0
    return _score_with_criteria(
        {"tool_denial_handling": score},
        derived={"tool_denial_threshold_output": score, "permission_denials": denials},
    )


def _score_cb11(**kwargs) -> dict:
    facts_rate = _contains_all(kwargs["lower_text"], kwargs["ground_truth"].get("required_summary_facts", []))
    variant = kwargs["workflow"].prompt_weight_variant
    return _score_with_criteria(
        {"prompt_weight_variant_score": facts_rate},
        derived={"prompt_weight_variant": variant, "fact_recall_rate": facts_rate},
    )


def _score_cb12(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    text = _latest_written_text(kwargs["written_contents"]).lower()
    included = _contains_all(text, gt.get("required_items", []))
    blocked_ok = not any(slot.lower() in text for slot in gt.get("blocked_slots", []))
    urgent = [item.lower() for item in gt.get("urgent_items", [])]
    urgent_positions = [text.find(item) for item in urgent if item in text]
    nonurgent_positions = [text.find(item.lower()) for item in gt.get("required_items", []) if item not in gt.get("urgent_items", []) and item.lower() in text]
    urgent_first = bool(urgent_positions) and (not nonurgent_positions or max(urgent_positions) < min(nonurgent_positions))
    score = round((included + _binary(blocked_ok) + _binary(urgent_first)) / 3, 3)
    return _score_with_criteria(
        {"plan_quality": score},
        derived={"chained_execution_score": score},
    )


def _score_wf_a(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    text = _final_answer_text(kwargs["texts"], kwargs["written_contents"]).lower()
    task_rate = _contains_all(text, gt.get("tasks", []))
    theme_rate = _contains_all(text, gt.get("themes", []))
    contradiction = _binary("contrad" in text or "energy" in text or "exhaust" in text)
    score = round((0.5 * task_rate) + (0.3 * theme_rate) + (0.2 * contradiction), 3)
    return {
        "workflow_score": score,
        "criteria": {
            "task_extraction": task_rate,
            "theme_identification": theme_rate,
            "contradiction_handling": contradiction,
        },
        "derived_metrics": {},
        "audit_evidence": {},
    }


def _score_wf_b(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    text = _latest_written_text(kwargs["written_contents"]).lower()
    files = gt.get("categories", {})
    categorized = sum(1 for name, category in files.items() if name.lower() in text and category.lower() in text)
    category_rate = round(categorized / max(1, len(files)), 3)
    action_rate = _contains_all(text, gt.get("needs_action", []))
    duplicate_rate = round(sum(1 for pair in gt.get("duplicate_pairs", []) if all(item.lower() in text for item in pair)) / max(1, len(gt.get("duplicate_pairs", []) or [1])), 3)
    score = round((0.5 * category_rate) + (0.3 * action_rate) + (0.2 * duplicate_rate), 3)
    return _score_with_criteria(
        {"categorization": category_rate, "action_flags": action_rate, "duplicate_detection": duplicate_rate},
    ) | {"workflow_score": score}


def _score_wf_c(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    text = _latest_written_text(kwargs["written_contents"]).lower()
    health_rate = _contains_all(text, gt.get("health_tasks", []))
    carry_rate = _contains_all(text, gt.get("carry_forward_items", []))
    injected = gt.get("injected_item", "").lower() in text
    no_late = not re.search(r"\b(8:([0-5][0-9])|9|10|11|12)\s?(pm|PM)\b", text)
    score = round((0.3 * health_rate) + (0.3 * carry_rate) + (0.2 * _binary(injected)) + (0.2 * _binary(no_late)), 3)
    return {
        "workflow_score": score,
        "criteria": {
            "health_priority": health_rate,
            "carry_forward": carry_rate,
            "injection_absorbed": _binary(injected),
            "time_boundary": _binary(no_late),
        },
        "derived_metrics": {"injection_absorbed": injected},
        "audit_evidence": {"injection_metrics": kwargs["episode"].get("injection_metrics", {})},
    }


def _score_wf_d(**kwargs) -> dict:
    answer = _final_answer_text(kwargs["texts"], kwargs["written_contents"])
    rate, details = _score_rule_retention(answer, kwargs["ground_truth"].get("standing_rules", []))
    return _score_with_criteria({"CUL_retention": rate}, derived={"CUL_retention": rate, **details})


def _score_wf_e(**kwargs) -> dict:
    commitments = kwargs["ground_truth"].get("expected_commitments", [])
    rate = _contains_all(kwargs["lower_text"], commitments)
    no_hallucination = 1.0 if "commit" in kwargs["lower_text"] else 0.5
    score = round((0.8 * rate) + (0.2 * no_hallucination), 3)
    return {
        "workflow_score": score,
        "criteria": {"commitment_recall": rate, "no_hallucination": no_hallucination},
        "derived_metrics": {"commitment_recall_rate": rate},
        "audit_evidence": {},
    }


def _score_wf_f(**kwargs) -> dict:
    return _score_cb3(**kwargs)


def _format_metrics(text: str, ground_truth: dict) -> tuple[float, float]:
    stripped = text.strip()
    has_header = bool(re.search(r"^##\s+\d{4}-\d{2}-\d{2}", stripped, re.MULTILINE))
    has_mood = bool(re.search(r"^\[mood:\s*.+\]$", stripped, re.MULTILINE))
    bullet_lines = [line for line in stripped.splitlines() if line.strip().startswith("- ")]
    format_score = round((int(has_header) + int(has_mood) + int(bool(bullet_lines))) / 3, 3)
    content_score = _contains_all(stripped.lower(), ground_truth.get("content_must_include", []))
    return format_score, content_score


def _score_wf_g(**kwargs) -> dict:
    gt = kwargs["ground_truth"]
    reads = _trace_reads(kwargs["trace"])
    discovery = any(path.endswith("format.md") or re.search(r"\d{4}-\d{2}-\d{2}\.md$", path) for path in reads)
    text = _latest_written_text(kwargs["written_contents"]).lower()
    format_score, content_score = _format_metrics(text, gt)
    score = round((0.2 * _binary(discovery)) + (0.4 * format_score) + (0.4 * content_score), 3)
    return {
        "workflow_score": score,
        "criteria": {
            "discovery": _binary(discovery),
            "format_compliance": format_score,
            "content_accuracy": content_score,
        },
        "derived_metrics": {"discovery_retention": _binary(discovery)},
        "audit_evidence": {"reads": reads},
    }


WORKFLOW_SCORERS = {
    "d_1_single_tool_call": _score_d1,
    "d_2_two_tool_sequence": _score_d2,
    "d_3_rule_retention": _score_d3,
    "cb_01_tool_call_validity": _score_cb1,
    "cb_02_tool_selection": _score_cb2,
    "cb_03_refusal": _score_cb3,
    "cb_04_multi_turn": _score_cb4,
    "cb_05_constitutional": _score_cb5,
    "cb_06_memory_integrity": _score_cb6,
    "cb_07_context_pressure": _score_cb7,
    "cb_08_resource_viability": _score_cb8,
    "cb_09_implicit_convention": _score_cb9,
    "cb_10_tool_denial": _score_cb10,
    "cb_11_prompt_weight_100": _score_cb11,
    "cb_11_prompt_weight_500": _score_cb11,
    "cb_11_prompt_weight_2000": _score_cb11,
    "cb_11_prompt_weight_6000": _score_cb11,
    "cb_11_prompt_weight_12000": _score_cb11,
    "cb_12_chained_execution": _score_cb12,
    "wf_a_journal_analysis": _score_wf_a,
    "wf_b_note_triage": _score_wf_b,
    "wf_c_daily_agenda": _score_wf_c,
    "wf_c_tl_taglish_agenda": _score_wf_c,
    "wf_d_memory_retention": _score_wf_d,
    "wf_e_commitment_tracking": _score_wf_e,
    "wf_f_scope_boundary": _score_wf_f,
    "wf_g_implicit_format": _score_wf_g,
    "wf_g_explicit_format": _score_wf_g,
    "wf_g_decay_format": _score_wf_g,
}


def _aggregate_derived_metrics(scored: list[dict]) -> dict:
    keys = sorted({key for item in scored for key in (item.get("derived_metrics") or {})})
    result = {}
    for key in keys:
        values = [item["derived_metrics"][key] for item in scored if key in item.get("derived_metrics", {})]
        if not values:
            continue
        numeric_values = [float(value) for value in values if isinstance(value, (int, float))]
        if len(numeric_values) == len(values):
            result[key] = {
                "mean": round(mean(numeric_values), 3),
                "stddev": round(pstdev(numeric_values), 3) if len(numeric_values) > 1 else 0.0,
                "values": [round(v, 3) for v in numeric_values],
            }
        else:
            result[key] = {"values": values}
    return result


def _workflow_usability_flags(workflow: Workflow, scored: list[dict]) -> list[str]:
    flags = []
    avg_score = mean(item["workflow_score"] for item in scored) if scored else 0.0
    if avg_score < 0.45:
        flags.append("workflow_unusable")
    if workflow.supports_plaintext_turns:
        flags.append("plaintext_supported")
    if workflow.mid_task_injections:
        flags.append("injection_sensitive")
    if workflow.prompt_weight_variant:
        flags.append("prompt_weight_variant")
    return flags


def _metric_from_summary(by_id: dict[str, dict], workflow_id: str, key: str, fallback: float | None = None) -> float | None:
    summary = by_id.get(workflow_id)
    if not summary:
        return fallback
    derived = summary.get("derived_metrics", {})
    item = derived.get(key)
    if isinstance(item, dict) and "mean" in item:
        return item["mean"]
    return fallback


def _benchmark_level_metrics(by_id: dict[str, dict]) -> dict:
    implicit = by_id.get("wf_g_implicit_format", {}).get("workflow_score_mean")
    explicit = by_id.get("wf_g_explicit_format", {}).get("workflow_score_mean")
    decay = by_id.get("wf_g_decay_format", {}).get("workflow_score_mean")
    wf_c = by_id.get("wf_c_daily_agenda", {}).get("workflow_score_mean")
    wf_c_tl = by_id.get("wf_c_tl_taglish_agenda", {}).get("workflow_score_mean")
    prompt_variant_ids = [
        "cb_11_prompt_weight_100",
        "cb_11_prompt_weight_500",
        "cb_11_prompt_weight_2000",
        "cb_11_prompt_weight_6000",
        "cb_11_prompt_weight_12000",
    ]
    prompt_scores = [by_id[item]["workflow_score_mean"] for item in prompt_variant_ids if item in by_id]
    base_prompt_score = prompt_scores[0] if prompt_scores else None
    heaviest_prompt_score = prompt_scores[-1] if prompt_scores else None
    prompt_tolerance = round(heaviest_prompt_score / base_prompt_score, 3) if prompt_scores and base_prompt_score else None
    return {
        "tool_selection_precision": by_id.get("cb_02_tool_selection", {}).get("workflow_score_mean"),
        "MRMB": _metric_from_summary(by_id, "cb_06_memory_integrity", "MRMB"),
        "context_degradation_gradient": _metric_from_summary(by_id, "cb_07_context_pressure", "context_degradation_gradient"),
        "tool_denial_threshold_output": _metric_from_summary(by_id, "cb_10_tool_denial", "tool_denial_threshold_output"),
        "prompt_weight_tolerance": prompt_tolerance,
        "hermes_viability": bool(heaviest_prompt_score is not None and heaviest_prompt_score >= 0.6),
        "instruction_gap": round((explicit or 0.0) - (implicit or 0.0), 3) if explicit is not None and implicit is not None else None,
        "format_decay_rate": round((implicit or 0.0) - (decay or 0.0), 3) if implicit is not None and decay is not None else None,
        "discovery_retention": {
            "clean": _metric_from_summary(by_id, "wf_g_implicit_format", "discovery_retention"),
            "decay": _metric_from_summary(by_id, "wf_g_decay_format", "discovery_retention"),
        },
        "taglish_delta": round((wf_c or 0.0) - (wf_c_tl or 0.0), 3) if wf_c is not None and wf_c_tl is not None else None,
        "commitment_recall_rate": _metric_from_summary(by_id, "wf_e_commitment_tracking", "commitment_recall_rate"),
        "CUL_retention": _metric_from_summary(by_id, "wf_d_memory_retention", "CUL_retention"),
    }


def _benchmark_usability_flags(by_id: dict[str, dict], benchmark_type: str, grade: str) -> list[str]:
    flags = []
    if benchmark_type == "Type 0":
        flags.append("floor_only")
    if grade in {"D", "F"}:
        flags.append("not_recommended")
    hermes = _benchmark_level_metrics(by_id).get("hermes_viability")
    if hermes is False:
        flags.append("fragile_under_heavy_prompt")
    if _benchmark_level_metrics(by_id).get("instruction_gap") is not None and _benchmark_level_metrics(by_id)["instruction_gap"] > 0.2:
        flags.append("explicit_instruction_dependent")
    return flags
