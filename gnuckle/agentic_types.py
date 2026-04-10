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

VALID_BENCHMARK_LAYERS = {"diagnostic", "core", "profile", "diagnostic_variant"}
VALID_SCORING_METHODS = {"test_pass", "trace_criteria", "ground_truth", "manual"}
VALID_REPORTING_TAGS = {"explicit", "implicit", "decay", "taglish", "diagnostic"}

DEFAULT_SAMPLER_CONFIG: dict[str, Any] = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "repeat_penalty": 1.1,
}


@dataclass(slots=True)
class MidTaskInjection:
    after_turn: int
    text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MidTaskInjection":
        return cls(after_turn=int(data["after_turn"]), text=str(data["text"]))


@dataclass(slots=True)
class ScoringCriterion:
    name: str
    weight: float
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringCriterion":
        return cls(
            name=str(data["name"]),
            weight=float(data["weight"]),
            description=str(data.get("description", "")),
        )


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
    # --- identity ---
    workflow_id: str
    title: str
    slice: str
    difficulty: str

    # --- benchmark classification ---
    benchmark_layer: str  # diagnostic | core | profile | diagnostic_variant
    profile_id: str | None
    workflow_variant_of: str | None

    # --- content ---
    system_prompt: str
    fixture: str
    workspace_fixture: str | None
    ground_truth_path: str | None
    context_noise_fixture: str | None
    event_type: str
    event_text: str
    standing_rules: list[str]

    # --- tools ---
    active_tools: list[str]
    expected_tools: list[str]
    denied_tools: list[str]
    expected_trace_pattern: list[str]

    # --- execution ---
    max_turns: int
    timeout_s: int
    run_count: int
    supports_plaintext_turns: bool
    mid_task_injections: list[MidTaskInjection]
    sampler_config: dict[str, Any]

    # --- scoring ---
    verification: WorkflowVerification
    success_rule: WorkflowSuccessRule
    scoring_method: str  # test_pass | trace_criteria | ground_truth | manual
    scoring_criteria: list[ScoringCriterion]

    # --- reporting ---
    reporting_tags: list[str]
    prompt_weight_variant: str | None
    tool_denial_expectation: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        verification = WorkflowVerification(**data["verification"])
        success_rule = WorkflowSuccessRule(**data["success_rule"])
        event = data["event"]
        payload = event["payload"]

        raw_injections = data.get("mid_task_injections") or []
        injections = [MidTaskInjection.from_dict(inj) for inj in raw_injections]

        raw_criteria = data.get("scoring_criteria") or []
        criteria = [ScoringCriterion.from_dict(sc) for sc in raw_criteria]

        sampler = dict(DEFAULT_SAMPLER_CONFIG)
        sampler.update(data.get("sampler_config") or {})

        return cls(
            workflow_id=data["workflow_id"],
            title=data["title"],
            slice=data["slice"],
            difficulty=data["difficulty"],
            benchmark_layer=data.get("benchmark_layer", "core"),
            profile_id=data.get("profile_id"),
            workflow_variant_of=data.get("workflow_variant_of"),
            system_prompt=data["system_prompt"],
            fixture=data["fixture"],
            workspace_fixture=data.get("workspace_fixture"),
            ground_truth_path=data.get("ground_truth_path"),
            context_noise_fixture=data.get("context_noise_fixture"),
            event_type=event["event_type"],
            event_text=payload["text"],
            standing_rules=list(data.get("standing_rules") or []),
            active_tools=list(data.get("active_tools") or data["allowed_tools"]),
            expected_tools=list(data.get("expected_tools") or data["allowed_tools"]),
            denied_tools=list(data.get("denied_tools") or []),
            expected_trace_pattern=list(data.get("expected_trace_pattern") or []),
            max_turns=int(data["max_turns"]),
            timeout_s=int(data.get("timeout_s", 180)),
            run_count=int(data.get("run_count", 1)),
            supports_plaintext_turns=bool(data.get("supports_plaintext_turns", False)),
            mid_task_injections=injections,
            sampler_config=sampler,
            verification=verification,
            success_rule=success_rule,
            scoring_method=data.get("scoring_method", success_rule.type),
            scoring_criteria=criteria,
            reporting_tags=list(data.get("reporting_tags") or []),
            prompt_weight_variant=data.get("prompt_weight_variant"),
            tool_denial_expectation=data.get("tool_denial_expectation"),
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
