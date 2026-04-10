from __future__ import annotations

import unittest

from gnuckle.workflow_loader import ManifestError, _validate_workflow


class WorkflowLoaderTests(unittest.TestCase):
    def test_denied_tools_must_be_subset_of_active_tools(self) -> None:
        raw = {
            "workflow_id": "cb_10_tool_denial",
            "title": "Tool Denial",
            "slice": "core",
            "difficulty": "medium",
            "benchmark_layer": "core",
            "system_prompt": "test",
            "fixture": "benchmark_core/cb_10_tool_denial",
            "event": {
                "event_type": "interactive_request",
                "payload": {"text": "test"},
            },
            "allowed_tools": ["read_file", "finish"],
            "active_tools": ["read_file", "finish"],
            "expected_tools": ["read_file", "finish"],
            "denied_tools": ["write_file"],
            "max_turns": 4,
            "verification": {"required": False, "method": "manual", "command": []},
            "success_rule": {"type": "manual"},
        }
        with self.assertRaises(ManifestError):
            _validate_workflow(raw)


if __name__ == "__main__":
    unittest.main()
