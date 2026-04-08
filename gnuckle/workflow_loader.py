"""Load and validate agentic workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path

from gnuckle.agentic_types import Workflow


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


def _load_raw_manifest() -> dict:
    with WORKFLOWS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_workflow(raw: dict) -> None:
    missing = REQUIRED_KEYS.difference(raw)
    if missing:
        raise ValueError(f"workflow {raw.get('workflow_id', '<unknown>')} missing keys: {sorted(missing)}")

    event = raw.get("event", {})
    payload = event.get("payload", {})
    if "event_type" not in event or "text" not in payload:
        raise ValueError(f"workflow {raw['workflow_id']} has invalid event shape")

    verification = raw.get("verification", {})
    if "required" not in verification or "method" not in verification:
        raise ValueError(f"workflow {raw['workflow_id']} has invalid verification block")

    success_rule = raw.get("success_rule", {})
    if "type" not in success_rule:
        raise ValueError(f"workflow {raw['workflow_id']} has invalid success rule")

    active_tools = raw.get("active_tools", raw.get("allowed_tools", []))
    expected_tools = raw.get("expected_tools", raw.get("allowed_tools", []))
    if not isinstance(active_tools, list) or not active_tools:
        raise ValueError(f"workflow {raw['workflow_id']} has invalid active_tools")
    if not isinstance(expected_tools, list) or not expected_tools:
        raise ValueError(f"workflow {raw['workflow_id']} has invalid expected_tools")


def load_workflow_suite(suite_name: str = "default") -> list[Workflow]:
    manifest = _load_raw_manifest()
    suites = manifest.get("suites", {})
    workflows = manifest.get("workflows", [])
    if suite_name not in suites:
        raise ValueError(f"unknown workflow suite: {suite_name}")

    workflow_by_id = {}
    for raw in workflows:
        _validate_workflow(raw)
        workflow_by_id[raw["workflow_id"]] = Workflow.from_dict(raw)

    ordered = []
    for workflow_id in suites[suite_name]:
        if workflow_id not in workflow_by_id:
            raise ValueError(f"suite {suite_name} references missing workflow: {workflow_id}")
        ordered.append(workflow_by_id[workflow_id])
    return ordered
