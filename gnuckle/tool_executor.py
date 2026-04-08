"""Deterministic local tools for the v1 agentic benchmark."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from gnuckle.agentic_types import Workflow


def tool_definitions(allowed_tools: list[str]) -> list[dict]:
    specs = {
        "read_file": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file from the benchmark workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "relative file path inside the workspace"}
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        "edit_file": {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Replace an entire text file in the benchmark workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "relative file path inside the workspace"},
                        "content": {"type": "string", "description": "full new file contents"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        "run_test": {
            "type": "function",
            "function": {
                "name": "run_test",
                "description": "Run the workflow verification test command inside the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
        "finish": {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Finish the task once the workspace is in the correct final state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "short summary of the completed work"},
                        "files_changed": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "relative file paths changed during the task",
                        },
                    },
                    "required": ["summary"],
                    "additionalProperties": False,
                },
            },
        },
    }
    return [specs[name] for name in allowed_tools if name in specs]


class ToolExecutor:
    def __init__(self, workspace_dir: Path, workflow: Workflow):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workflow = workflow

    def execute(self, name: str, arguments: dict) -> dict:
        started = time.perf_counter()
        if name == "read_file":
            result = self._read_file(arguments["path"])
        elif name == "edit_file":
            result = self._edit_file(arguments["path"], arguments["content"])
        elif name == "run_test":
            result = self._run_test()
        elif name == "finish":
            result = self._finish(arguments)
        else:
            raise ValueError(f"invalid tool: {name}")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        result["elapsed_ms"] = elapsed_ms
        return result

    def _resolve_workspace_path(self, relative_path: str) -> Path:
        candidate = (self.workspace_dir / relative_path).resolve()
        if not str(candidate).startswith(str(self.workspace_dir)):
            raise ValueError("path escapes benchmark workspace")
        return candidate

    def _read_file(self, relative_path: str) -> dict:
        path = self._resolve_workspace_path(relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        content = path.read_text(encoding="utf-8")
        return {
            "tool": "read_file",
            "ok": True,
            "path": relative_path,
            "content": content,
        }

    def _edit_file(self, relative_path: str, content: str) -> dict:
        path = self._resolve_workspace_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "tool": "edit_file",
            "ok": True,
            "path": relative_path,
            "bytes_written": len(content.encode("utf-8")),
        }

    def _run_test(self) -> dict:
        command = self.workflow.verification.command or [sys.executable, "-m", "unittest", "-q"]
        completed = subprocess.run(
            command,
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        return {
            "tool": "run_test",
            "ok": completed.returncode == 0,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def _finish(self, arguments: dict) -> dict:
        return {
            "tool": "finish",
            "ok": True,
            "summary": arguments.get("summary", ""),
            "files_changed": list(arguments.get("files_changed", [])),
        }


def tool_result_preview(result: dict) -> str:
    text = json.dumps(result, ensure_ascii=True)
    if len(text) <= 240:
        return text
    return text[:237] + "..."
