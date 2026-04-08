"""Explicit types for the v1 agentic benchmark runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "max_turns", "timeout", "harness_error"}
FAILURE_REASONS = {
    "task_unsolved",
    "verification_failed",
    "verification_missing",
    "max_turns",
    "timeout",
    "invalid_tool_call",
    "malformed_finish",
    "harness_error",
}


@dataclass(slots=True)
class WorkflowVerification:
    required: bool
    method: str
    command: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowSuccessRule:
    type: str


@dataclass(slots=True)
class Workflow:
    workflow_id: str
    title: str
    slice: str
    difficulty: str
    system_prompt: str
    fixture: str
    event_type: str
    event_text: str
    active_tools: list[str]
    expected_tools: list[str]
    max_turns: int
    timeout_s: int
    verification: WorkflowVerification
    success_rule: WorkflowSuccessRule

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        verification = WorkflowVerification(**data["verification"])
        success_rule = WorkflowSuccessRule(**data["success_rule"])
        event = data["event"]
        payload = event["payload"]
        return cls(
            workflow_id=data["workflow_id"],
            title=data["title"],
            slice=data["slice"],
            difficulty=data["difficulty"],
            system_prompt=data["system_prompt"],
            fixture=data["fixture"],
            event_type=event["event_type"],
            event_text=payload["text"],
            active_tools=list(data.get("active_tools") or data["allowed_tools"]),
            expected_tools=list(data.get("expected_tools") or data["allowed_tools"]),
            max_turns=int(data["max_turns"]),
            timeout_s=int(data.get("timeout_s", 180)),
            verification=verification,
            success_rule=success_rule,
        )


@dataclass(slots=True)
class SessionState:
    session_id: str
    workflow_id: str
    session_mode: str
    messages: list[dict[str, Any]]
    episodes_run: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "session_mode": self.session_mode,
            "messages": self.messages,
            "episodes_run": self.episodes_run,
        }
