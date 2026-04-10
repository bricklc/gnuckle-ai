"""Deterministic bounded tools for the benchmark runtime."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from gnuckle.agentic_types import Workflow


DEFAULT_BENCHMARK_DATE = "2026-04-10"
LIST_STATE_FILE = ".gnuckle_list_state.json"

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "echo": {
        "description": "Repeat the provided text exactly.",
        "required": {"text"},
        "allowed": {"text"},
        "properties": {
            "text": {"type": "string", "description": "text to repeat back verbatim"},
        },
    },
    "list_files": {
        "description": "List files and directories inside the benchmark workspace.",
        "required": set(),
        "allowed": {"path"},
        "properties": {
            "path": {"type": "string", "description": "optional relative directory path inside the workspace"},
        },
    },
    "read_file": {
        "description": "Read a text file from the benchmark workspace.",
        "required": {"path"},
        "allowed": {"path"},
        "properties": {
            "path": {"type": "string", "description": "relative file path inside the workspace"},
        },
    },
    "write_file": {
        "description": "Create or overwrite a text file in the benchmark workspace.",
        "required": {"path", "content"},
        "allowed": {"path", "content"},
        "properties": {
            "path": {"type": "string", "description": "relative file path inside the workspace"},
            "content": {"type": "string", "description": "full file contents to persist"},
        },
    },
    "append_file": {
        "description": "Append text to a file in the benchmark workspace.",
        "required": {"path", "content"},
        "allowed": {"path", "content"},
        "properties": {
            "path": {"type": "string", "description": "relative file path inside the workspace"},
            "content": {"type": "string", "description": "text to append"},
        },
    },
    "finish": {
        "description": "Finish the task once the workspace is in the correct final state.",
        "required": {"summary"},
        "allowed": {"summary", "files_changed"},
        "properties": {
            "summary": {"type": "string", "description": "short summary of the completed work"},
            "files_changed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "relative file paths changed during the task",
            },
        },
    },
    "get_date": {
        "description": "Return the benchmark's anchored current date and day of week.",
        "required": set(),
        "allowed": set(),
        "properties": {},
    },
    "add_item": {
        "description": "Add an item to the bounded benchmark list state.",
        "required": {"text"},
        "allowed": {"text"},
        "properties": {
            "text": {"type": "string", "description": "item text to add to the list"},
        },
    },
    "update_item": {
        "description": "Update an existing benchmark list item by id or prior text.",
        "required": {"new_text"},
        "allowed": {"item_id", "old_text", "new_text"},
        "properties": {
            "item_id": {"type": "integer", "description": "numeric id of the item to update"},
            "old_text": {"type": "string", "description": "current text of the item to replace"},
            "new_text": {"type": "string", "description": "replacement text"},
        },
    },
    "read_list": {
        "description": "Return the current bounded benchmark list state.",
        "required": set(),
        "allowed": set(),
        "properties": {},
    },
    # Legacy coding-only tools kept for backward compatibility with the existing workflow.
    "search": {
        "description": "Search the workspace for file names or text patterns.",
        "required": {"query"},
        "allowed": {"query"},
        "properties": {
            "query": {"type": "string", "description": "file name or text pattern to search for"},
        },
    },
    "edit_file": {
        "description": "Replace an entire text file in the benchmark workspace.",
        "required": {"path", "content"},
        "allowed": {"path", "content"},
        "properties": {
            "path": {"type": "string", "description": "relative file path inside the workspace"},
            "content": {"type": "string", "description": "full new file contents"},
        },
    },
    "run_test": {
        "description": "Run the workflow verification test command inside the workspace.",
        "required": set(),
        "allowed": set(),
        "properties": {},
    },
}


def tool_definitions(allowed_tools: list[str]) -> list[dict]:
    definitions = []
    for name in allowed_tools:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            continue
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": {
                        "type": "object",
                        "properties": spec["properties"],
                        "required": sorted(spec["required"]),
                        "additionalProperties": False,
                    },
                },
            }
        )
    return definitions


class ToolExecutor:
    def __init__(self, workspace_dir: Path, workflow: Workflow):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workflow = workflow

    def execute(self, name: str, arguments: dict) -> dict:
        started = time.perf_counter()
        handlers = {
            "echo": lambda args: self._echo(str(args["text"])),
            "list_files": lambda args: self._list_files(str(args.get("path", ""))),
            "read_file": lambda args: self._read_file(str(args["path"])),
            "write_file": lambda args: self._write_file(str(args["path"]), str(args["content"])),
            "append_file": lambda args: self._append_file(str(args["path"]), str(args["content"])),
            "finish": self._finish,
            "get_date": lambda args: self._get_date(),
            "add_item": lambda args: self._add_item(str(args["text"])),
            "update_item": lambda args: self._update_item(
                new_text=str(args["new_text"]),
                item_id=args.get("item_id"),
                old_text=args.get("old_text"),
            ),
            "read_list": lambda args: self._read_list(),
            "search": lambda args: self._search(str(args["query"])),
            "edit_file": lambda args: self._write_file(str(args["path"]), str(args["content"]), tool_name="edit_file"),
            "run_test": lambda args: self._run_test(),
        }
        if name not in handlers:
            raise ValueError(f"invalid tool: {name}")
        result = handlers[name](arguments)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        result["elapsed_ms"] = elapsed_ms
        return result

    def invoke(self, tool_call_id: str, name: str, arguments: dict | None) -> dict:
        started = time.perf_counter()
        arguments = arguments or {}

        permission_check = self._check_permission(name, arguments)
        if permission_check is not None:
            return self._error_result(
                tool_call_id=tool_call_id,
                name=name,
                error_type="permission_denied",
                error=permission_check["message"],
                elapsed_started=started,
                arguments=arguments,
                denied=True,
                denial_reason=permission_check["reason"],
            )

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
                "denial_reason": None,
                "arguments": arguments,
            }
        )
        return result

    def _validate_input(self, name: str, arguments: dict) -> str | None:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            return f"invalid tool: {name}"

        missing = sorted(field for field in spec["required"] if field not in arguments)
        if missing:
            return f"missing required fields: {missing}"

        unexpected = sorted(field for field in arguments if field not in spec["allowed"])
        if unexpected:
            return f"unexpected fields: {unexpected}"

        if name == "update_item" and "item_id" not in arguments and "old_text" not in arguments:
            return "update_item requires item_id or old_text"

        return None

    def _check_permission(self, name: str, arguments: dict) -> dict[str, str] | None:
        if name not in self.workflow.active_tools:
            return {
                "reason": "undeclared_tool",
                "message": f"tool '{name}' is not active for workflow '{self.workflow.workflow_id}'",
            }

        if name in self.workflow.denied_tools:
            return {
                "reason": "workflow_denied_tool",
                "message": f"tool '{name}' is denied by workflow policy",
            }

        if name in {"read_file", "write_file", "append_file", "edit_file", "list_files"} and "path" in arguments:
            try:
                self._resolve_workspace_path(str(arguments["path"]))
            except Exception as exc:
                return {
                    "reason": "path_denied",
                    "message": str(exc),
                }
        return None

    def _echo(self, text: str) -> dict:
        return {
            "tool": "echo",
            "ok": True,
            "text": text,
        }

    def _list_files(self, relative_path: str = "") -> dict:
        target = self._resolve_workspace_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(relative_path or ".")
        if not target.is_dir():
            raise NotADirectoryError(relative_path or ".")

        entries = []
        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            rel = child.relative_to(self.workspace_dir).as_posix()
            entries.append(
                {
                    "name": child.name,
                    "path": rel,
                    "type": "file" if child.is_file() else "directory",
                }
            )

        return {
            "tool": "list_files",
            "ok": True,
            "path": relative_path or ".",
            "entries": entries,
            "count": len(entries),
        }

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

    def _error_result(
        self,
        tool_call_id: str,
        name: str,
        error_type: str,
        error: str,
        elapsed_started: float,
        arguments: dict,
        denied: bool = False,
        denial_reason: str | None = None,
    ) -> dict:
        elapsed_ms = round((time.perf_counter() - elapsed_started) * 1000, 1)
        return {
            "tool": name,
            "tool_call_id": tool_call_id,
            "ok": False,
            "is_error": True,
            "error_type": error_type,
            "error": error,
            "denied": denied,
            "denial_reason": denial_reason,
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

    def _write_file(self, relative_path: str, content: str, tool_name: str = "write_file") -> dict:
        path = self._resolve_workspace_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        before_exists = path.exists()
        before_content = path.read_text(encoding="utf-8") if before_exists else ""
        path.write_text(content, encoding="utf-8")
        persisted_content = path.read_text(encoding="utf-8")
        return {
            "tool": tool_name,
            "ok": True,
            "path": relative_path,
            "before_exists": before_exists,
            "before_bytes": len(before_content.encode("utf-8")),
            "bytes_written": len(content.encode("utf-8")),
            "after_bytes": len(persisted_content.encode("utf-8")),
            "requested_content_preview": self._preview_text(content),
            "persisted_content_preview": self._preview_text(persisted_content),
            "before_hash": self._text_hash(before_content),
            "after_hash": self._text_hash(persisted_content),
            "write_match": persisted_content == content,
        }

    def _append_file(self, relative_path: str, content: str) -> dict:
        path = self._resolve_workspace_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        before_exists = path.exists()
        before_content = path.read_text(encoding="utf-8") if before_exists else ""
        path.write_text(before_content + content, encoding="utf-8")
        persisted_content = path.read_text(encoding="utf-8")
        return {
            "tool": "append_file",
            "ok": True,
            "path": relative_path,
            "before_exists": before_exists,
            "before_bytes": len(before_content.encode("utf-8")),
            "bytes_appended": len(content.encode("utf-8")),
            "after_bytes": len(persisted_content.encode("utf-8")),
            "requested_content_preview": self._preview_text(content),
            "persisted_content_preview": self._preview_text(persisted_content),
            "before_hash": self._text_hash(before_content),
            "after_hash": self._text_hash(persisted_content),
            "append_match": persisted_content == (before_content + content),
        }

    def _get_date(self) -> dict:
        anchored = os.environ.get("GNUCKLE_BENCHMARK_DATE", DEFAULT_BENCHMARK_DATE)
        benchmark_day = date.fromisoformat(anchored)
        return {
            "tool": "get_date",
            "ok": True,
            "iso_date": benchmark_day.isoformat(),
            "day_of_week": benchmark_day.strftime("%A"),
            "display": benchmark_day.strftime("%A, %Y-%m-%d"),
            "source": "anchored_benchmark_clock",
        }

    def _list_state_path(self) -> Path:
        return self.workspace_dir / LIST_STATE_FILE

    def _load_list_state(self) -> list[dict]:
        path = self._list_state_path()
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_list_state(self, items: list[dict]) -> None:
        path = self._list_state_path()
        path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _add_item(self, text: str) -> dict:
        items = self._load_list_state()
        item = {
            "id": (max((entry["id"] for entry in items), default=0) + 1),
            "text": text,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        items.append(item)
        self._save_list_state(items)
        return {
            "tool": "add_item",
            "ok": True,
            "item": item,
            "items": items,
        }

    def _update_item(self, new_text: str, item_id: Any = None, old_text: Any = None) -> dict:
        items = self._load_list_state()
        match = None
        normalized_id = int(item_id) if item_id is not None else None
        for entry in items:
            if normalized_id is not None and int(entry["id"]) == normalized_id:
                match = entry
                break
            if old_text is not None and entry["text"] == str(old_text):
                match = entry
                break
        if match is None:
            raise KeyError("list item not found")

        before_text = match["text"]
        match["text"] = new_text
        match["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self._save_list_state(items)
        return {
            "tool": "update_item",
            "ok": True,
            "item": match,
            "before_text": before_text,
            "items": items,
        }

    def _read_list(self) -> dict:
        items = self._load_list_state()
        return {
            "tool": "read_list",
            "ok": True,
            "items": items,
            "count": len(items),
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

    @staticmethod
    def _preview_text(text: str, limit: int = 240) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def tool_result_preview(result: dict) -> str:
    text = json.dumps(result, ensure_ascii=True)
    if len(text) <= 240:
        return text
    return text[:237] + "..."
