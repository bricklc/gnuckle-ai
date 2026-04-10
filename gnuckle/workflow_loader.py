"""Load and validate agentic workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path

from gnuckle.agentic_types import (
    DEFAULT_SAMPLER_CONFIG,
    VALID_BENCHMARK_LAYERS,
    VALID_REPORTING_TAGS,
    VALID_SCORING_METHODS,
    Workflow,
)


WORKFLOWS_PATH = Path(__file__).with_name("workflows.json")

REQUIRED_KEYS = {
    "workflow_id",
    "title",
    "slice",
    "difficulty",
    "system_prompt",
    "fixture",
    "event",
    "allowed_tools",
    "max_turns",
    "verification",
    "success_rule",
}


class ManifestError(ValueError):
    """Raised when a workflow manifest is structurally invalid."""


def _err(workflow_id: str, field: str, msg: str) -> ManifestError:
    return ManifestError(f"workflow '{workflow_id}': field '{field}' — {msg}")


def _load_raw_manifest() -> dict:
    with WORKFLOWS_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    try:
        from gnuckle.benchmark_workflows import benchmark_manifest

        extra = benchmark_manifest()
        manifest.setdefault("suites", {}).update(extra.get("suites", {}))
        manifest.setdefault("workflows", []).extend(extra.get("workflows", []))
    except Exception:
        pass
    return manifest


def _validate_workflow(raw: dict) -> None:
    wid = raw.get("workflow_id", "<unknown>")

    # --- required keys ---
    missing = REQUIRED_KEYS.difference(raw)
    if missing:
        raise ManifestError(f"workflow '{wid}' missing keys: {sorted(missing)}")

    # --- event shape ---
    event = raw.get("event", {})
    payload = event.get("payload", {})
    if "event_type" not in event:
        raise _err(wid, "event.event_type", "missing")
    if "text" not in payload:
        raise _err(wid, "event.payload.text", "missing")

    # --- verification ---
    verification = raw.get("verification", {})
    if "required" not in verification:
        raise _err(wid, "verification.required", "missing")
    if "method" not in verification:
        raise _err(wid, "verification.method", "missing")

    # --- success_rule ---
    success_rule = raw.get("success_rule", {})
    if "type" not in success_rule:
        raise _err(wid, "success_rule.type", "missing")

    # --- tools ---
    active_tools = raw.get("active_tools", raw.get("allowed_tools", []))
    expected_tools = raw.get("expected_tools", raw.get("allowed_tools", []))
    denied_tools = raw.get("denied_tools") or []
    if not isinstance(active_tools, list) or not active_tools:
        raise _err(wid, "active_tools", "must be a non-empty list")
    if not isinstance(expected_tools, list) or not expected_tools:
        raise _err(wid, "expected_tools", "must be a non-empty list")
    if not isinstance(denied_tools, list):
        raise _err(wid, "denied_tools", "must be a list when present")
    invalid_denied = sorted(tool for tool in denied_tools if tool not in active_tools)
    if invalid_denied:
        raise _err(wid, "denied_tools", f"must be a subset of active_tools, got {invalid_denied}")

    # --- benchmark_layer ---
    layer = raw.get("benchmark_layer", "core")
    if layer not in VALID_BENCHMARK_LAYERS:
        raise _err(wid, "benchmark_layer", f"must be one of {sorted(VALID_BENCHMARK_LAYERS)}, got '{layer}'")

    # --- profile_id required for profile layer ---
    if layer == "profile" and not raw.get("profile_id"):
        raise _err(wid, "profile_id", "required when benchmark_layer is 'profile'")

    # --- workflow_variant_of required for diagnostic_variant ---
    if layer == "diagnostic_variant" and not raw.get("workflow_variant_of"):
        raise _err(wid, "workflow_variant_of", "required when benchmark_layer is 'diagnostic_variant'")

    # --- scoring_method ---
    scoring_method = raw.get("scoring_method", success_rule.get("type", ""))
    if scoring_method and scoring_method not in VALID_SCORING_METHODS:
        raise _err(wid, "scoring_method", f"must be one of {sorted(VALID_SCORING_METHODS)}, got '{scoring_method}'")

    # --- scoring_criteria weights ---
    criteria = raw.get("scoring_criteria") or []
    if criteria:
        total = sum(c.get("weight", 0) for c in criteria)
        if abs(total - 1.0) > 0.01:
            raise _err(wid, "scoring_criteria", f"weights must sum to 1.0, got {total:.2f}")

    # --- reporting_tags ---
    tags = raw.get("reporting_tags") or []
    for tag in tags:
        if tag not in VALID_REPORTING_TAGS:
            raise _err(wid, "reporting_tags", f"unknown tag '{tag}', must be one of {sorted(VALID_REPORTING_TAGS)}")

    # --- mid_task_injections shape ---
    injections = raw.get("mid_task_injections") or []
    for i, inj in enumerate(injections):
        if "after_turn" not in inj:
            raise _err(wid, f"mid_task_injections[{i}].after_turn", "missing")
        if "text" not in inj:
            raise _err(wid, f"mid_task_injections[{i}].text", "missing")

    # --- run_count ---
    run_count = raw.get("run_count", 1)
    if not isinstance(run_count, int) or run_count < 1:
        raise _err(wid, "run_count", f"must be a positive integer, got {run_count!r}")

    # --- sampler_config ---
    sampler = raw.get("sampler_config")
    if sampler is not None and not isinstance(sampler, dict):
        raise _err(wid, "sampler_config", "must be an object or null")


def resolve_sampler_config(manifest: dict, workflow_raw: dict) -> dict[str, object]:
    """Merge manifest default -> workflow override. Always returns a complete config."""
    base = dict(DEFAULT_SAMPLER_CONFIG)
    base.update(manifest.get("default_sampler_config") or {})
    base.update(workflow_raw.get("sampler_config") or {})
    return base


def load_workflow_suite(suite_name: str = "default") -> list[Workflow]:
    manifest = _load_raw_manifest()
    suites = manifest.get("suites", {})
    workflows = manifest.get("workflows", [])
    if suite_name not in suites:
        raise ManifestError(f"unknown workflow suite: {suite_name}")

    workflow_by_id: dict[str, Workflow] = {}
    for raw in workflows:
        _validate_workflow(raw)
        raw["sampler_config"] = resolve_sampler_config(manifest, raw)
        workflow_by_id[raw["workflow_id"]] = Workflow.from_dict(raw)

    ordered = []
    for workflow_id in suites[suite_name]:
        if workflow_id not in workflow_by_id:
            raise ManifestError(f"suite '{suite_name}' references missing workflow: {workflow_id}")
        ordered.append(workflow_by_id[workflow_id])
    return ordered


def load_all_workflows() -> list[Workflow]:
    """Load and validate every workflow in the manifest, regardless of suite membership."""
    manifest = _load_raw_manifest()
    workflows = manifest.get("workflows", [])
    result = []
    for raw in workflows:
        _validate_workflow(raw)
        raw["sampler_config"] = resolve_sampler_config(manifest, raw)
        result.append(Workflow.from_dict(raw))
    return result


def enumerate_benchmark_workflows(suite_name: str = "default") -> list[dict]:
    """Return a deterministic enumeration of workflows with their metadata for run planning."""
    wfs = load_workflow_suite(suite_name)
    return [
        {
            "workflow_id": wf.workflow_id,
            "title": wf.title,
            "benchmark_layer": wf.benchmark_layer,
            "profile_id": wf.profile_id,
            "scoring_method": wf.scoring_method,
            "run_count": wf.run_count,
            "supports_plaintext_turns": wf.supports_plaintext_turns,
            "injection_count": len(wf.mid_task_injections),
            "sampler_config": wf.sampler_config,
            "denied_tools": wf.denied_tools,
        }
        for wf in wfs
    ]
