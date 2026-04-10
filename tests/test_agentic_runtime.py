from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gnuckle.agentic_types import MidTaskInjection, Workflow, WorkflowSuccessRule, WorkflowVerification
from gnuckle.agentic_runtime import run_agentic_episode
from gnuckle.session_store import SessionStore


def make_workflow(
    active_tools: list[str],
    supports_plaintext_turns: bool = False,
    mid_task_injections: list[MidTaskInjection] | None = None,
) -> Workflow:
    return Workflow(
        workflow_id="test_workflow",
        title="Test Workflow",
        slice="core",
        difficulty="easy",
        benchmark_layer="core",
        profile_id=None,
        workflow_variant_of=None,
        system_prompt="test",
        fixture="fix_greeting",
        workspace_fixture=None,
        ground_truth_path=None,
        context_noise_fixture=None,
        event_type="interactive_request",
        event_text="test",
        standing_rules=[],
        active_tools=active_tools,
        expected_tools=list(active_tools),
        denied_tools=[],
        expected_trace_pattern=[],
        max_turns=4,
        timeout_s=30,
        run_count=1,
        supports_plaintext_turns=supports_plaintext_turns,
        mid_task_injections=list(mid_task_injections or []),
        sampler_config={},
        verification=WorkflowVerification(required=False, method="manual", command=[]),
        success_rule=WorkflowSuccessRule(type="manual"),
        scoring_method="manual",
        scoring_criteria=[],
        reporting_tags=[],
        prompt_weight_variant=None,
        tool_denial_expectation=None,
    )


def fake_response(content: str = "", tool_calls: list[object] | None = None) -> object:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(choices=[choice], usage=usage)


def fake_tool_call(call_id: str, name: str, arguments_json: str) -> object:
    function = SimpleNamespace(name=name, arguments=arguments_json)
    return SimpleNamespace(id=call_id, function=function)


class FakeOpenAI:
    responses: list[object] = []

    def __init__(self, base_url: str, api_key: str):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if not type(self).responses:
            raise AssertionError("no fake responses queued")
        return type(self).responses.pop(0)


class AgenticRuntimeTests(unittest.TestCase):
    def test_plaintext_turns_are_preserved_in_trace_and_session(self) -> None:
        workflow = make_workflow(
            ["finish"],
            supports_plaintext_turns=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            FakeOpenAI.responses = [
                fake_response(content="Need one more thought before I finish."),
                fake_response(tool_calls=[fake_tool_call("tc_finish", "finish", '{"summary":"done"}')]),
            ]
            with (
                patch("gnuckle.agentic_runtime.OpenAI", FakeOpenAI),
                patch("gnuckle.agentic_runtime.estimate_context_token_counts", return_value={
                    "heuristic": 32,
                    "tokenizer": 32,
                    "tokenizer_label": "llama.cpp tokenizer",
                    "measured": 32,
                    "measured_label": "llama.cpp tokenizer",
                }),
            ):
                episode, _workspace = run_agentic_episode(
                    base_url="http://localhost:8080/v1",
                    workflow=workflow,
                    output_dir=output_dir,
                )

            trace_types = [entry["type"] for entry in episode["trace"]]
            self.assertIn("plaintext_turn", trace_types)
            self.assertEqual(episode["failure_events"]["malformed_finish_events"], 0)

            session = SessionStore(output_dir / "agentic_sessions").load(
                next((output_dir / "agentic_sessions").glob("*.json")).stem
            )
            self.assertIsNotNone(session)
            assistant_messages = [msg for msg in session.messages if msg["role"] == "assistant"]
            self.assertTrue(any(msg.get("content") == "Need one more thought before I finish." for msg in assistant_messages))

    def test_mid_task_injection_is_traced_persisted_and_counted(self) -> None:
        workflow = make_workflow(
            ["finish"],
            supports_plaintext_turns=True,
            mid_task_injections=[MidTaskInjection(after_turn=1, text="User update: prioritize groceries before the call.")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            FakeOpenAI.responses = [
                fake_response(content="I am thinking through the schedule."),
                fake_response(tool_calls=[fake_tool_call("tc_finish", "finish", '{"summary":"updated plan ready"}')]),
            ]
            with (
                patch("gnuckle.agentic_runtime.OpenAI", FakeOpenAI),
                patch("gnuckle.agentic_runtime.estimate_context_token_counts", return_value={
                    "heuristic": 40,
                    "tokenizer": 40,
                    "tokenizer_label": "llama.cpp tokenizer",
                    "measured": 40,
                    "measured_label": "llama.cpp tokenizer",
                }),
            ):
                episode, _workspace = run_agentic_episode(
                    base_url="http://localhost:8080/v1",
                    workflow=workflow,
                    output_dir=output_dir,
                )

            injection_entries = [entry for entry in episode["trace"] if entry["type"] == "mid_task_injection"]
            self.assertEqual(len(injection_entries), 1)
            self.assertEqual(injection_entries[0]["turn"], 1)
            self.assertEqual(episode["injection_metrics"]["delivered"], 1)
            self.assertEqual(episode["injection_metrics"]["absorbed"], 1)
            self.assertEqual(episode["injection_metrics"]["absorption_rate"], 1.0)
            self.assertEqual(episode["injection_metrics"]["events"][0]["response_turn"], 2)

            session = SessionStore(output_dir / "agentic_sessions").load(
                next((output_dir / "agentic_sessions").glob("*.json")).stem
            )
            self.assertIsNotNone(session)
            user_messages = [msg for msg in session.messages if msg["role"] == "user"]
            self.assertTrue(
                any(msg.get("content") == "User update: prioritize groceries before the call." for msg in user_messages)
            )


if __name__ == "__main__":
    unittest.main()
