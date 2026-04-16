from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gnuckle.playground import playground_output_path, pretend_tool_result


class PlaygroundTests(unittest.TestCase):
    def test_pretend_tool_result_marks_mock_payload(self) -> None:
        result = pretend_tool_result("get_weather", {"location": "Manila"})
        self.assertTrue(result["pretend"])
        self.assertEqual(result["tool"], "get_weather")
        self.assertEqual(result["arguments"], {"location": "Manila"})
        self.assertIn("location", result)

    def test_playground_output_path_uses_model_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = playground_output_path(tmpdir, Path("C:/models/demo-model.gguf"))
        self.assertEqual(path.parent, Path(tmpdir))
        self.assertTrue(path.name.startswith("playground_demo-model_"))
        self.assertEqual(path.suffix, ".json")

    def test_pretend_unknown_tool_returns_json_safe_payload(self) -> None:
        result = pretend_tool_result("missing_tool", {"x": 1})
        encoded = json.dumps(result)
        self.assertIn("missing_tool", encoded)
        self.assertTrue(result["pretend"])


if __name__ == "__main__":
    unittest.main()
