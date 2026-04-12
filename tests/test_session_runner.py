from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gnuckle.benchmark import update_usage
from gnuckle.session_runner import normalize_benchmark_definition, run_session_benchmark


def fake_response(content: str = "", tool_calls: list[object] | None = None, usage: dict | None = None) -> object:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    usage = usage or {"output_tokens": 5}
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


class SessionRunnerTests(unittest.TestCase):
    def test_update_usage_accepts_openai_style_completion_aliases(self) -> None:
        usage = update_usage(
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
        )
        self.assertEqual(usage["input_tokens"], 12)
        self.assertEqual(usage["output_tokens"], 34)
        self.assertEqual(usage["total_tokens"], 46)

    def test_normalize_v2_turn_shape(self) -> None:
        benchmark = normalize_benchmark_definition(
            {
                "meta": {"id": "bench", "title": "Bench", "version": "2.0"},
                "session": {"type": "session", "system_prompt": "sys", "standing_rules": ["rule"]},
                "tool_manifest": [{"name": "echo"}],
                "turns": [
                    {
                        "id": "t01",
                        "title": "Echo",
                        "user_message": "say hi",
                        "active_tools": ["echo"],
                        "mock_tool_results": [{"tool": "echo", "call_index": 1, "result": {"output": "hi"}}],
                        "expectations": {
                            "tool_usage": {"must_call": ["echo"], "must_not_call": ["finish"]},
                            "response": {"must_contain": ["hi"], "format": "plain_text"},
                            "session": {"must_finish": False},
                        },
                    }
                ],
            }
        )
        self.assertEqual(benchmark["id"], "bench")
        self.assertEqual(benchmark["tools"], ["echo"])
        self.assertEqual(benchmark["turns"][0]["prompt"], "say hi")
        self.assertEqual(benchmark["turns"][0]["mock_results"]["echo"]["output"], "hi")
        self.assertFalse(benchmark["turns"][0]["expect"]["finish_required"])

    def test_run_session_benchmark_keeps_persistent_transcript_and_state(self) -> None:
        benchmark = {
            "meta": {"id": "bench", "title": "Bench", "version": "2.0"},
            "session": {
                "type": "session",
                "system_prompt": "sys",
                "standing_rules": [],
                "initial_state": {
                    "files": {"notes.txt": "alpha"},
                    "benchmark_date": "2026-04-10",
                },
            },
            "tool_manifest": [
                {"name": "read_file"},
                {"name": "write_file"},
                {"name": "finish"},
            ],
            "turns": [
                {
                    "id": "t01",
                    "title": "Write",
                    "user_message": "Write beta to notes.txt.",
                    "active_tools": ["write_file"],
                    "expectations": {"tool_usage": {"must_call": ["write_file"]}, "session": {"must_finish": False}},
                },
                {
                    "id": "t02",
                    "title": "Recall",
                    "user_message": "Read notes.txt back.",
                    "active_tools": ["read_file", "finish"],
                    "expectations": {
                        "tool_usage": {"must_call": ["read_file"]},
                        "response": {"must_contain": ["beta"]},
                        "session": {"must_finish": False},
                    },
                },
            ],
        }

        FakeOpenAI.responses = [
            fake_response(tool_calls=[fake_tool_call("tc1", "write_file", '{"path":"notes.txt","content":"beta"}')]),
            fake_response(content="Wrote beta."),
            fake_response(tool_calls=[fake_tool_call("tc2", "read_file", '{"path":"notes.txt"}')]),
            fake_response(content="notes.txt now says beta."),
        ]

        observer_events = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 64, "heuristic": 64}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1234}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(
                benchmark,
                base_url="http://localhost:8080/v1",
                output_dir=Path(tmp),
                observer=lambda event_type, payload: observer_events.append((event_type, payload)),
            )

        transcript = result["session"]["transcript"]
        kinds = [entry["kind"] for entry in transcript]
        self.assertIn("prompt", kinds)
        self.assertIn("tool_use", kinds)
        self.assertIn("tool_result", kinds)
        self.assertEqual(result["session"]["state"]["files"]["notes.txt"], "beta")
        self.assertEqual(result["turns"][1]["assistant_text"], "notes.txt now says beta.")
        self.assertEqual(result["turns"][0]["metrics"]["provider_usage_total"], 10)
        self.assertEqual(result["turns"][0]["metrics"]["provider_usage_cumulative_total"], 10)
        self.assertEqual(result["turns"][1]["metrics"]["provider_usage_total"], 10)
        self.assertEqual(result["turns"][1]["metrics"]["provider_usage_cumulative_total"], 20)
        self.assertEqual(result["aggregate"]["provider_usage_total_tokens"], 20)
        self.assertTrue(any(event_type == "tool_result" for event_type, _payload in observer_events))

    def test_invalid_tool_stays_in_band_and_counts_as_invalid_execution(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Do the thing.",
                    "active_tools": ["echo"],
                    "expect": {"tools_not_called": ["send_email"], "finish_required": False},
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(tool_calls=[fake_tool_call("tc1", "send_email", '{"to":"team@example.com"}')]),
            fake_response(content="I cannot send email because that tool is unavailable."),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        tool_result_rows = [entry for entry in result["session"]["transcript"] if entry["kind"] == "tool_result"]
        self.assertEqual(len(tool_result_rows), 1)
        self.assertEqual(tool_result_rows[0]["status"], "error")
        self.assertEqual(result["aggregate"]["invalid_execution_count"], 1)

    def test_session_runner_counts_completion_tokens_from_openai_style_usage(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Say hi.",
                    "active_tools": ["echo"],
                    "expect": {"response_contains": ["hi"], "finish_required": False},
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content="hi", usage={"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {key: (total or {}).get(key, 0) + (usage or {}).get(key, 0) for key in ("input_tokens", "output_tokens", "total_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("total_tokens", 0) or ((usage or {}).get("input_tokens", 0) + (usage or {}).get("output_tokens", 0))),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        metrics = result["turns"][0]["metrics"]
        self.assertEqual(metrics["provider_usage_total"], 13)
        self.assertGreaterEqual(metrics["tokens_per_second"], 0.0)

    def test_empty_turn_retries_same_query_before_advancing(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Say hi.",
                    "active_tools": ["echo"],
                    "expect": {"response_contains": ["hi"], "finish_required": False},
                },
                {
                    "id": "t02",
                    "prompt": "Say done.",
                    "active_tools": ["echo"],
                    "expect": {"response_contains": ["done"], "finish_required": False},
                },
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content=""),
            fake_response(content="hi"),
            fake_response(content="done"),
        ]

        observer_events = []
        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(
                benchmark,
                base_url="http://localhost:8080/v1",
                observer=lambda event_type, payload: observer_events.append((event_type, payload)),
            )

        self.assertEqual(len(result["turns"]), 2)
        self.assertEqual(result["turns"][0]["assistant_text"], "hi")
        self.assertEqual(result["turns"][0]["retry_count"], 1)
        self.assertTrue(result["turns"][0]["initial_no_response"])
        self.assertFalse(result["turns"][0]["no_response"])
        self.assertEqual(result["turns"][1]["assistant_text"], "done")
        self.assertTrue(any(event_type == "no_response" for event_type, _payload in observer_events))

    def test_empty_turn_exhaustion_marks_failure_and_stops_session(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Say hi.",
                    "active_tools": ["echo"],
                    "expect": {"response_contains": ["hi"], "finish_required": False},
                },
                {
                    "id": "t02",
                    "prompt": "Say done.",
                    "active_tools": ["echo"],
                    "expect": {"response_contains": ["done"], "finish_required": False},
                },
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content=""),
            fake_response(content=""),
            fake_response(content=""),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        self.assertEqual(len(result["turns"]), 1)
        self.assertTrue(result["turns"][0]["no_response"])
        self.assertEqual(result["turns"][0]["retry_count"], 3)
        self.assertEqual(result["turns"][0]["scores"]["turn_score"], 0.0)
        self.assertEqual(result["aggregate"]["no_response_turn_count"], 1)
        transcript = result["session"]["transcript"]
        self.assertTrue(any(entry["kind"] == "invalid_turn" for entry in transcript))

    def test_semantic_gap_and_format_receipt_are_recorded(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Recall the agenda.",
                    "active_tools": [],
                    "expect": {
                        "response_contains_normalized": ["9am review todo"],
                        "response_format": "bullet_points",
                        "response_format_rules": ["no_headings", "no_tables", "flat_bullets"],
                        "finish_required": False,
                    },
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content="## Today's Agenda\n- **9am** - Review todo"),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        scores = result["turns"][0]["scores"]
        receipt = result["turns"][0]["audit_receipt"]
        self.assertEqual(scores["content_semantic_recall"], 1.0)
        self.assertFalse(scores["format_correct"])
        self.assertTrue(scores["format_indicators"]["used_headings"])
        self.assertIn("format_drift", receipt["flags"])
        self.assertEqual(result["aggregate"]["heading_violation_turn_count"], 1)
        self.assertIn("turn_receipts", result["llm_audit_receipt"])

    def test_must_inspect_turn_marks_unsupported_claims(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["read_file"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "What is in handoff.md?",
                    "active_tools": ["read_file"],
                    "expect": {
                        "tools_called": ["read_file"],
                        "evidence_mode": "must_inspect",
                        "scoring_mode": "strict_grounded",
                        "response_contains": ["Fix login bug"],
                        "finish_required": False,
                    },
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content="- Fix login bug"),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        scores = result["turns"][0]["scores"]
        self.assertEqual(scores["unsupported_claim_count"], 1)
        self.assertIn("Used memory instead of inspecting current state.", scores["score_notes"])

    def test_memory_only_turn_penalizes_tool_use(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["read_file"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Recall from memory.",
                    "active_tools": ["read_file"],
                    "expect": {
                        "tools_called": [],
                        "tools_not_called": ["read_file"],
                        "evidence_mode": "memory_only",
                        "scoring_mode": "semantic_recall",
                        "response_contains": ["8080"],
                        "finish_required": False,
                    },
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(tool_calls=[fake_tool_call("tc1", "read_file", '{"path":"config.json"}')]),
            fake_response(content="- 8080"),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        self.assertEqual(result["aggregate"]["memory_only_tool_violation_turn_count"], 1)
        self.assertIn("Used tools on a memory-only turn.", result["turns"][0]["scores"]["score_notes"])

    def test_failure_branch_retries_same_turn_until_corrected(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["echo"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "What is the current tracker?",
                    "active_tools": [],
                    "max_recovery_tries": 2,
                    "failure_branches": [
                        {
                            "trigger": "content_mismatch",
                            "followup_user_message": "No, I meant the current tracker, not the todo file. Answer directly.",
                            "max_retries": 1,
                            "expect_override": {
                                "response_contains_normalized": ["buy oat milk"],
                                "scoring_mode": "semantic_recall",
                                "evidence_mode": "memory_only",
                            },
                        }
                    ],
                    "expect": {
                        "response_contains_normalized": ["buy oat milk"],
                        "scoring_mode": "semantic_recall",
                        "evidence_mode": "memory_only",
                        "finish_required": False,
                    },
                },
                {
                    "id": "t02",
                    "prompt": "Done?",
                    "active_tools": [],
                    "expect": {"response_contains": ["done"], "finish_required": False},
                },
            ],
        }

        FakeOpenAI.responses = [
            fake_response(content="- Fix login bug"),
            fake_response(content="- buy oat milk"),
            fake_response(content="done"),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        self.assertEqual(len(result["turns"]), 2)
        self.assertEqual(result["turns"][0]["recovery_tries"], 1)
        self.assertTrue(result["turns"][0]["recovery_resolved"])
        self.assertFalse(result["turns"][0]["recovery_loop_exhausted"])
        self.assertEqual(result["turns"][0]["assistant_text"], "- buy oat milk")
        self.assertEqual(result["aggregate"]["recovery_try_count"], 1)
        transcript_kinds = [entry["kind"] for entry in result["session"]["transcript"]]
        self.assertIn("correction_prompt", transcript_kinds)

    def test_finish_turn_scores_visible_summary_before_final_closure(self) -> None:
        benchmark = {
            "id": "bench",
            "title": "Bench",
            "type": "session",
            "system_prompt": "sys",
            "tools": ["finish"],
            "turns": [
                {
                    "id": "t01",
                    "prompt": "Summarize, then finish.",
                    "active_tools": ["finish"],
                    "expect": {
                        "tools_called": ["finish"],
                        "finish_required": True,
                        "response_contains_literal": ["9090", "handoff.md"],
                        "response_format": "bullet_points",
                    },
                }
            ],
        }

        FakeOpenAI.responses = [
            fake_response(
                content="- Config changed to 9090\n- Generated handoff.md",
                tool_calls=[fake_tool_call("tc1", "finish", '{"summary":"done"}')],
            ),
            fake_response(content="done"),
        ]

        with (
            patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
            patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
            patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
            patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
            patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
            patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
            patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
        ):
            result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

        turn = result["turns"][0]
        self.assertEqual(turn["assistant_text"], "done")
        self.assertIn("9090", turn["assistant_visible_text"])
        self.assertIn("handoff.md", turn["assistant_visible_text"])
        self.assertGreaterEqual(turn["scores"]["turn_score"], 0.7)

    def test_attached_context_files_are_loaded_into_rendered_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx_dir = root / "context"
            ctx_dir.mkdir(parents=True, exist_ok=True)
            rules_path = ctx_dir / "HARNESS_RULES.md"
            rules_path.write_text("# Harness Rules\n- current file state matters", encoding="utf-8")

            benchmark = {
                "_path": str(root / "bench.json"),
                "id": "bench",
                "title": "Bench",
                "type": "session",
                "system_prompt": "sys",
                "tools": ["echo"],
                "session": {
                    "type": "session",
                    "context_model": {
                        "base_files": ["context/HARNESS_RULES.md"],
                    },
                },
                "turns": [
                    {
                        "id": "t01",
                        "prompt": "Say hi.",
                        "active_tools": [],
                        "expect": {"response_contains": ["hi"], "finish_required": False},
                    }
                ],
            }

            FakeOpenAI.responses = [
                fake_response(content="hi"),
            ]

            with (
                patch("gnuckle.session_runner.OpenAI", FakeOpenAI),
                patch("gnuckle.session_runner.estimate_context_token_counts", return_value={"measured": 40, "heuristic": 40}),
                patch("gnuckle.session_runner.get_hardware_snapshot", return_value={"vram_peak_mb": 1000}),
                patch("gnuckle.session_runner.empty_usage", return_value={"output_tokens": 0}),
                patch("gnuckle.session_runner.update_usage", side_effect=lambda current, usage: usage or {"output_tokens": 0}),
                patch("gnuckle.session_runner.accumulate_usage", side_effect=lambda total, usage: {"output_tokens": (total or {}).get("output_tokens", 0) + (usage or {}).get("output_tokens", 0)}),
                patch("gnuckle.session_runner.usage_total_tokens", side_effect=lambda usage: (usage or {}).get("output_tokens", 0)),
            ):
                result = run_session_benchmark(benchmark, base_url="http://localhost:8080/v1")

            rendered = result["meta"]["rendered_system_prompt"]
            self.assertIn("Attached Context: HARNESS_RULES.md", rendered)
            self.assertIn("current file state matters", rendered)
            self.assertEqual(result["meta"]["attached_context_document_count"], 1)


if __name__ == "__main__":
    unittest.main()
