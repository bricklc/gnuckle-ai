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
        "search": {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the workspace for file names or text patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "file name or text pattern to search for"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
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
        elif name == "search":
            result = self._search(arguments["query"])
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

    def invoke(self, tool_call_id: str, name: str, arguments: dict | None) -> dict:
        started = time.perf_counter()
        arguments = arguments or {}

        validation_error = self._validate_input(name, arguments)
        if validation_error:
            return self._error_result(
                tool_call_id=tool_call_id,
                name=name,
                error_type="input_validation_error",
                error=validation_error,
                elapsed_started=started,
                arguments=arguments,
            )

        permission_check = self._check_permission(name, arguments)
        if permission_check is not None:
            return self._error_result(
                tool_call_id=tool_call_id,
                name=name,
                error_type="permission_denied",
                error=permission_check,
                elapsed_started=started,
                arguments=arguments,
                denied=True,
            )

        try:
            result = self.execute(name, arguments)
        except Exception as exc:
            return self._error_result(
                tool_call_id=tool_call_id,
                name=name,
                error_type="execution_error",
                error=str(exc),
                elapsed_started=started,
                arguments=arguments,
            )

        result.update(
            {
                "tool_call_id": tool_call_id,
                "is_error": False,
                "error_type": None,
                "denied": False,
                "arguments": arguments,
            }
        )
        return result

    def _validate_input(self, name: str, arguments: dict) -> str | None:
        specs = {
            "search": {"required": {"query"}, "allowed": {"query"}},
            "read_file": {"required": {"path"}, "allowed": {"path"}},
            "edit_file": {"required": {"path", "content"}, "allowed": {"path", "content"}},
            "run_test": {"required": set(), "allowed": set()},
            "finish": {"required": {"summary"}, "allowed": {"summary", "files_changed"}},
        }
        if name not in specs:
            return f"invalid tool: {name}"

        spec = specs[name]
        missing = sorted(field for field in spec["required"] if field not in arguments)
        if missing:
            return f"missing required fields: {missing}"

        unexpected = sorted(field for field in arguments if field not in spec["allowed"])
        if unexpected:
            return f"unexpected fields: {unexpected}"

        return None

    def _check_permission(self, name: str, arguments: dict) -> str | None:
        if name in {"read_file", "edit_file"} and "path" in arguments:
            try:
                self._resolve_workspace_path(str(arguments["path"]))
            except Exception as exc:
                return str(exc)
        return None

    def _search(self, query: str) -> dict:
        needle = query.lower()
        matches = []
        for path in sorted(self.workspace_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.workspace_dir).as_posix()
            file_hit = needle in rel.lower()
            text_hit = False
            if not file_hit:
                try:
                    content = path.read_text(encoding="utf-8")
                    text_hit = needle in content.lower()
                except Exception:
                    text_hit = False
            if file_hit or text_hit:
                matches.append({"path": rel, "match_type": "file" if file_hit else "content"})
        return {
            "tool": "search",
            "ok": True,
            "query": query,
            "matches": matches[:20],
        }

    def _error_result(self, tool_call_id: str, name: str, error_type: str, error: str,
                      elapsed_started: float, arguments: dict, denied: bool = False) -> dict:
        elapsed_ms = round((time.perf_counter() - elapsed_started) * 1000, 1)
        return {
            "tool": name,
            "tool_call_id": tool_call_id,
            "ok": False,
            "is_error": True,
            "error_type": error_type,
            "error": error,
            "denied": denied,
            "arguments": arguments,
            "elapsed_ms": elapsed_ms,
        }

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
