from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gnuckle.session_runner import normalize_benchmark_definition, run_session_benchmark


def fake_response(content: str = "", tool_calls: list[object] | None = None) -> object:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    usage = {"output_tokens": 5}
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


if __name__ == "__main__":
    unittest.main()
