from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gnuckle.agentic_types import Workflow, WorkflowSuccessRule, WorkflowVerification
from gnuckle.tool_executor import ToolExecutor, tool_definitions


def make_workflow(
    active_tools: list[str],
    denied_tools: list[str] | None = None,
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
        denied_tools=list(denied_tools or []),
        expected_trace_pattern=[],
        max_turns=4,
        timeout_s=30,
        run_count=1,
        supports_plaintext_turns=False,
        mid_task_injections=[],
        sampler_config={},
        verification=WorkflowVerification(required=False, method="manual", command=[]),
        success_rule=WorkflowSuccessRule(type="manual"),
        scoring_method="manual",
        scoring_criteria=[],
        reporting_tags=[],
        prompt_weight_variant=None,
        tool_denial_expectation=None,
    )


class ToolExecutorTests(unittest.TestCase):
    def test_tool_definitions_include_phase3_surface(self) -> None:
        names = [
            spec["function"]["name"]
            for spec in tool_definitions(["echo", "list_files", "read_file", "write_file", "append_file", "finish"])
        ]
        self.assertEqual(names, ["echo", "list_files", "read_file", "write_file", "append_file", "finish"])

    def test_write_append_and_list_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            executor = ToolExecutor(workspace, make_workflow(["list_files", "write_file", "append_file", "read_file"]))

            written = executor.invoke("tc1", "write_file", {"path": "notes/output.txt", "content": "alpha"})
            self.assertTrue(written["ok"])

            appended = executor.invoke("tc2", "append_file", {"path": "notes/output.txt", "content": "\nbeta"})
            self.assertTrue(appended["ok"])

            listed = executor.invoke("tc3", "list_files", {"path": "notes"})
            self.assertTrue(listed["ok"])
            self.assertEqual([entry["name"] for entry in listed["entries"]], ["output.txt"])

            read_back = executor.invoke("tc4", "read_file", {"path": "notes/output.txt"})
            self.assertEqual(read_back["content"], "alpha\nbeta")

    def test_get_date_is_anchored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), make_workflow(["get_date"]))
            result = executor.invoke("tc1", "get_date", {})
            self.assertTrue(result["ok"])
            self.assertEqual(result["iso_date"], "2026-04-10")
            self.assertEqual(result["day_of_week"], "Friday")

    def test_denied_tool_is_distinct_from_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), make_workflow(["write_file"], denied_tools=["write_file"]))
            denied = executor.invoke("tc1", "write_file", {"path": "blocked.txt", "content": "x"})
            self.assertFalse(denied["ok"])
            self.assertEqual(denied["error_type"], "permission_denied")
            self.assertEqual(denied["denial_reason"], "workflow_denied_tool")
            self.assertTrue(denied["denied"])

    def test_undeclared_tool_is_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), make_workflow(["read_file"]))
            denied = executor.invoke("tc1", "write_file", {"path": "blocked.txt", "content": "x"})
            self.assertFalse(denied["ok"])
            self.assertEqual(denied["error_type"], "permission_denied")
            self.assertEqual(denied["denial_reason"], "undeclared_tool")

    def test_update_item_by_old_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), make_workflow(["add_item", "update_item", "read_list"]))
            added = executor.invoke("tc1", "add_item", {"text": "milk"})
            self.assertTrue(added["ok"])

            updated = executor.invoke("tc2", "update_item", {"old_text": "milk", "new_text": "2 liters of fresh milk"})
            self.assertTrue(updated["ok"])

            current = executor.invoke("tc3", "read_list", {})
            self.assertEqual(current["count"], 1)
            self.assertEqual(current["items"][0]["text"], "2 liters of fresh milk")

    def test_invalid_arguments_remain_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ToolExecutor(Path(tmp), make_workflow(["write_file"]))
            invalid = executor.invoke("tc1", "write_file", {"path": "notes.txt"})
            self.assertFalse(invalid["ok"])
            self.assertEqual(invalid["error_type"], "input_validation_error")
            self.assertFalse(invalid["denied"])


if __name__ == "__main__":
    unittest.main()
