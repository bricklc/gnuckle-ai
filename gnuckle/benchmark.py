"""
Gnuckle Agentic Benchmark — core engine.
ape push token through cache. ape measure how fast.
"""

import json
import time
import subprocess
import sys
import os
import signal
import socket
import copy
import webbrowser
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from collections import deque
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from openai import OpenAI

from gnuckle.ape import ape_print, ape_wait, ape_phrase
from gnuckle.profile import load_profile
from gnuckle.system_prompt import (
    FALLBACK_SYSTEM_PROMPT,
    approx_token_count,
    default_system_prompt_for_mode,
    tokenizer_label,
    tokenizer_token_count,
)

# ── CACHE CONFIGS TO RUN ──────────────────────────────────────────────────────
CACHE_CONFIGS = [
    {"label": "f16",    "cache_k": "f16",    "cache_v": "f16"},
    {"label": "q8_0",   "cache_k": "q8_0",   "cache_v": "q8_0"},
    {"label": "q4_0",   "cache_k": "q4_0",   "cache_v": "q4_0"},
    {"label": "turbo3", "cache_k": "turbo3", "cache_v": "turbo3"},
]

# ── DEFAULTS ─────────────────────────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:{port}/v1"
API_KEY          = "none"
MODEL            = "local-model"
DEFAULT_TURNS    = 20
DEFAULT_PORT     = 8080
DEFAULT_BENCHMARK_MODE = "legacy"
DEFAULT_WORKFLOW_SUITE = "benchmark"
DEFAULT_SESSION_MODE = "fresh_session"
MAX_MALFORMED_TOOL_RETRIES = 1
SERVER_WAIT_S    = 60
WARMUP_WAIT_S    = 120
PRESETS_PATH     = Path(__file__).with_name("llama_presets.json")
DEFAULT_SYSTEM_PROMPT = FALLBACK_SYSTEM_PROMPT

# ── TOOL DEFINITIONS ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time for a given timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone e.g. Asia/Manila"}
                },
                "required": ["timezone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "units":    {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location", "units"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a calendar event",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":    {"type": "string"},
                    "date":     {"type": "string", "description": "ISO 8601 format"},
                    "location": {"type": "string"},
                    "notes":    {"type": "string"}
                },
                "required": ["title", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all current tasks and their status",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "enum": ["all", "pending", "done"]}
                },
                "required": ["filter"]
            }
        }
    }
]

ACTIVE_TOOL_NAMES = [tool["function"]["name"] for tool in TOOLS]

MOCK_RESPONSES = {
    "get_current_time":      '{"time": "2026-04-08T10:24:00+00:00", "timezone": "UTC", "day": "Tuesday"}',
    "get_weather":           '{"location": "Tokyo, JP", "temp_c": 18, "condition": "Partly cloudy", "humidity": 62, "rain_chance": 20}',
    "search_web":            '{"results": [{"title": "Latest tech industry news", "snippet": "New developments in local AI inference 2026...", "url": "https://example.com/1"}, {"title": "Open-source LLM benchmarks", "snippet": "Community-driven performance testing...", "url": "https://example.com/2"}]}',
    "create_calendar_event": '{"status": "created", "event_id": "evt_20260408_001", "confirmation": "Event scheduled successfully"}',
    "list_tasks":            '{"tasks": [{"id": 1, "title": "Finish quarterly report", "status": "pending", "priority": "high"}, {"id": 2, "title": "Deploy staging build", "status": "pending", "priority": "medium"}, {"id": 3, "title": "Update dependencies", "status": "done"}]}'
}

TURN_PROMPTS = [
    "What time is it in Manila and what is the weather there right now?",
    "Search for recent news about AI inference optimization on consumer GPUs.",
    "Based on the weather, should I schedule an outdoor task today? Check my task list first.",
    "Create a calendar event called 'Team Standup' for tomorrow at 9AM in Tokyo.",
    "What is the current weather again and list all my pending tasks?",
    "Search for the best practices for benchmarking large language models locally.",
    "Schedule another event: 'Project Review' for this Friday at 2PM. Also check the time.",
    "List all my tasks and search for open-source LLM quantization news.",
    "What is the weather forecast and should I plan an outdoor meeting today?",
    "Search for GGML format updates in 2026 and get current time in London.",
    "Create an event 'Hardware Delivery' for next Monday morning. Check weather first.",
    "List pending tasks and search for tips on optimizing VRAM usage for local LLMs.",
    "What time is it and what are all my current tasks including completed ones?",
    "Search for news about MoE language models running locally on consumer hardware.",
    "Check the weather and create an event 'Morning Run' at 6AM tomorrow in Central Park, New York.",
    "List all tasks. Search for KV cache quantization accuracy comparisons.",
    "Get current time and weather, then list all pending tasks.",
    "Search for TurboQuant llama.cpp KV cache compression benchmarks.",
    "Create event 'Benchmark Run' for tonight at 9PM in Berlin. Also check current time and weather.",
    "List all tasks, get time, get weather, and search for Gemma 4 local inference performance."
]

LEGACY_EXPECTED_TOOLS = [
    ["get_current_time", "get_weather"],
    ["search_web"],
    ["get_weather", "list_tasks"],
    ["create_calendar_event"],
    ["get_weather", "list_tasks"],
    ["search_web"],
    ["create_calendar_event", "get_current_time"],
    ["list_tasks", "search_web"],
    ["get_weather"],
    ["search_web", "get_current_time"],
    ["create_calendar_event", "get_weather"],
    ["list_tasks", "search_web"],
    ["get_current_time", "list_tasks"],
    ["search_web"],
    ["get_weather", "create_calendar_event"],
    ["list_tasks", "search_web"],
    ["get_current_time", "get_weather", "list_tasks"],
    ["search_web"],
    ["create_calendar_event", "get_current_time", "get_weather"],
    ["list_tasks", "get_current_time", "get_weather", "search_web"],
]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def print_header(text):
    print(f"\n{'='*62}")
    print(f"  {text}")
    print(f"{'='*62}")

def print_step(text):
    print(f"  >> {text}")


def print_info(text):
    print(f"     {text}")


def _is_interactive_terminal() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except Exception:
        return False


def render_progress(label: str, current: int, total: int, width: int = 28, done: bool = False) -> None:
    total = max(1, int(total))
    current = max(0, min(int(current), total))
    filled = round((current / total) * width)
    bar = "#" * filled + "-" * (width - filled)
    percent = round((current / total) * 100)
    end = "\n" if done else "\r"
    print(f"  [{bar}] {percent:>3}%  {label}", end=end, flush=True)


def sanitize_label(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (text or "unknown"))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "unknown"


def _trim_block(text: str, limit: int = 900) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n... [truncated]"


def _terminal_width(default: int = 100) -> int:
    try:
        return max(72, os.get_terminal_size().columns)
    except OSError:
        return default


def _line_block(title: str, body: str, width: int, max_lines: int = 10) -> list[str]:
    heading = f"[ {title} ]"
    border = "-" * width
    lines = [heading, border]
    raw = (body or "").splitlines() or [""]
    trimmed = raw[:max_lines]
    for line in trimmed:
        lines.append(line[:width])
    if len(raw) > max_lines:
        lines.append("... [more]")
    return lines


class HarnessTheaterObserver:
    def __init__(self, show_prompts: str = "summary"):
        self.show_prompts = show_prompts
        self.workflow_id = ""
        self.title = ""
        self.session_mode = "persistent"
        self.workspace = ""
        self.tools = []
        self.max_turns = 0
        self.current_turn = 0
        self.metrics = {"context": "n/a", "vram": "n/a", "latency": "n/a"}
        self.activity = "idle"
        self.audit = deque(maxlen=6)
        self.transcript = deque(maxlen=22)
        self.pending_tools = {}
        self.model_name = "unknown"
        self.cache_label = "n/a"
        self.context_window = None

    def _monitor_header(self) -> str:
        parts = ["[ Monitoring ]"]
        if self.model_name:
            parts.append(f"[ Model {self.model_name} ]")
        if self.cache_label:
            parts.append(f"[ KV {self.cache_label} ]")
        parts.append(f"[ VRAM {self.metrics.get('vram', 'n/a')} ]")
        parts.append(f"[ Ctx {self.metrics.get('context', 'n/a')} ]")
        return " ".join(parts)

    def _add_audit(self, text: str) -> None:
        self.audit.appendleft(text)

    def _push_block(self, block_type: str, title: str, body: str = "", status: str = "", meta: dict | None = None) -> None:
        entry = {
            "type": block_type,
            "title": title,
            "body": (body or "").strip(),
            "status": (status or "").strip(),
            "meta": dict(meta or {}),
        }
        self.transcript.append(entry)
        return entry

    def _wrap_lines(self, text: str, width: int, indent: str = "") -> list[str]:
        text = str(text or "")
        if not text:
            return [indent.rstrip()]
        lines = []
        available = max(16, width - len(indent))
        for raw_line in text.splitlines() or [""]:
            remaining = raw_line.rstrip() or ""
            if not remaining:
                lines.append(indent.rstrip())
                continue
            while len(remaining) > available:
                split_at = remaining.rfind(" ", 0, available)
                if split_at < 1:
                    split_at = available
                lines.append(f"{indent}{remaining[:split_at].rstrip()}")
                remaining = remaining[split_at:].lstrip()
            lines.append(f"{indent}{remaining}")
        return lines

    def _format_tool_block(self, item: dict, width: int) -> list[str]:
        status = item["status"] or item["meta"].get("status", "")
        header = item["title"] + (f" [{status}]" if status else "")
        lines = [header[:width]]
        input_text = item["meta"].get("input", "")
        result_text = item["meta"].get("result", "")
        if input_text:
            lines.extend(self._wrap_lines(f"Input: {input_text}", width, "  "))
        if result_text:
            lines.extend(self._wrap_lines(f"Result: {result_text}", width, "  "))
        if not input_text and not result_text and item["body"]:
            lines.extend(self._wrap_lines(item["body"], width, "  "))
        return lines

    def _render_transcript(self, width: int) -> list[str]:
        lines = ["[ Live Transcript ]", "-" * width]
        for item in self.transcript:
            if item["type"] == "tool":
                lines.extend(self._format_tool_block(item, width))
            else:
                lines.append(item["title"][:width])
                if item["body"]:
                    lines.extend(self._wrap_lines(item["body"], width, "  "))
            lines.append("")
        return lines

    def _format_vram(self, value) -> str:
        if value in (None, "", "n/a"):
            return "n/a"
        try:
            mb = float(value)
        except (TypeError, ValueError):
            return str(value)
        if mb >= 1024:
            return f"{mb / 1024.0:.1f} GB"
        return f"{mb:.0f} MB"

    def _update_metrics(self, payload: dict) -> None:
        payload_context_window = payload.get("context_window")
        if payload_context_window not in (None, ""):
            try:
                self.context_window = int(payload_context_window)
            except (TypeError, ValueError):
                self.context_window = payload_context_window
        context_value = payload.get("context_tokens_estimate")
        if context_value is not None:
            percent = payload.get("context_percent_used")
            if self.context_window:
                if percent is not None:
                    self.metrics["context"] = f"{int(context_value)}/{self.context_window} ({percent:.1f}%)"
                else:
                    self.metrics["context"] = f"{int(context_value)}/{self.context_window}"
            elif percent is not None:
                self.metrics["context"] = f"{int(context_value)} est ({percent:.1f}%)"
            else:
                self.metrics["context"] = f"{int(context_value)} est"
        hardware = payload.get("hardware_usage") or {}
        vram_value = hardware.get("vram_peak_mb", hardware.get("vram_steady_mb"))
        if vram_value is not None:
            self.metrics["vram"] = self._format_vram(vram_value)
        latency_ms = payload.get("latency_ms")
        if latency_ms is not None:
            self.metrics["latency"] = f"{latency_ms} ms"

    def _find_pending_tool(self, tool_call_id: str | None, tool_name: str) -> dict | None:
        if tool_call_id and tool_call_id in self.pending_tools:
            return self.pending_tools[tool_call_id]
        for item in reversed(self.transcript):
            if item["type"] == "tool" and item["meta"].get("tool_name") == tool_name and item["status"] == "running":
                return item
        return None

    def _summarize_tool_result(self, result: dict) -> str:
        for key in ("summary", "content", "output", "text", "error"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return _trim_block(value, 1000)
        return _trim_block(json.dumps(result, ensure_ascii=True), 1000)

    def _render(self) -> None:
        width = _terminal_width()
        try:
            print("\x1b[2J\x1b[H", end="")
        except Exception:
            pass
        if not _is_interactive_terminal():
            os.system("cls" if os.name == "nt" else "clear")
        top = "=" * width
        title = f" Session: {self.title or self.workflow_id} "
        print(top)
        print(title[:width])
        print(f"Mode: {self.session_mode} | Turn: {self.current_turn}/{self.max_turns or '?'} | Workflow: {self.workflow_id}"[:width])
        print(f"Tools: {', '.join(self.tools)}"[:width])
        print(
            f"Context: {self.metrics.get('context', 'n/a')} | VRAM: {self.metrics.get('vram', 'n/a')} | "
            f"Latency: {self.metrics.get('latency', 'n/a')} | Activity: {self.activity}"
        [:width])
        print(top)
        for line in self._render_transcript(width):
            print(line[:width])
        print("-" * width)
        for line in _line_block(self._monitor_header(), "\n".join(self.audit), width, max_lines=6):
            print(line[:width])
        print("=" * width, flush=True)

    def __call__(self, event_type: str, payload: dict) -> None:
        if event_type == "episode_start":
            self.workflow_id = str(payload.get("workflow_id", "unknown"))
            self.title = str(payload.get("title", ""))
            self.session_mode = str(payload.get("session_mode", "persistent"))
            self.workspace = str(payload.get("workspace", ""))
            self.tools = list(payload.get("active_tools", []))
            self.max_turns = int(payload.get("max_turns", 0) or 0)
            self.model_name = str(payload.get("model_name", "unknown"))
            self.cache_label = str(payload.get("cache_label", "n/a"))
            context_window = payload.get("context_window")
            try:
                self.context_window = int(context_window) if context_window is not None else None
            except (TypeError, ValueError):
                self.context_window = context_window
            self.metrics = {"context": "n/a", "vram": "n/a", "latency": "n/a"}
            self.activity = "session ready"
            self.audit.clear()
            self.transcript.clear()
            self.pending_tools.clear()
            if self.show_prompts != "off":
                prompt = _trim_block(str(payload.get("user_event", "")), 2200 if self.show_prompts == "full" else 900)
                self._push_block("user", "User", prompt)
            self._add_audit(f"workspace: {self.workspace}")
            self._render()
            return
        if event_type == "turn_start":
            self.current_turn = int(payload.get("turn", 0) or 0)
            self.activity = "waiting for next user turn"
            self._add_audit(f"turn {self.current_turn} started")
            self._render()
            return
        if event_type == "model_request":
            self.activity = "waiting for model response"
            prompt = str(payload.get("prompt", "")).strip()
            if prompt and self.show_prompts != "off":
                limit = 1800 if self.show_prompts == "full" else 700
                prompt = _trim_block(prompt, limit)
                if not self.transcript or self.transcript[-1].get("body") != prompt:
                    self._push_block("user", "User", prompt)
            self._add_audit(f"model request attempt {payload.get('attempt', '?')}")
            self._render()
            return
        if event_type in {"assistant_action", "plaintext_turn"}:
            self._update_metrics(payload)
            assistant_text = _trim_block(str(payload.get("content", "")), 2800)
            tool_calls = payload.get("tool_calls") or []
            self.activity = "running tools" if tool_calls else "assistant responded"
            if assistant_text.strip():
                self._push_block("assistant", "Assistant", assistant_text)
            self._add_audit(f"assistant replied ({len(tool_calls)} tool calls)")
            self._render()
            return
        if event_type == "no_response":
            self._update_metrics(payload)
            attempt = payload.get("attempt", "?")
            max_retries = payload.get("max_retries", "?")
            retrying = bool(payload.get("retrying"))
            self.activity = "retrying same turn" if retrying else "turn failed: no response"
            body = "Assistant did not respond."
            if retrying:
                body += f" Retrying the same turn ({attempt}/{max_retries})."
            else:
                body += f" Retries exhausted ({attempt}/{max_retries})."
            self._push_block("assistant", "Assistant", body)
            self._add_audit(
                f"no response on attempt {attempt}"
                + ("; retrying" if retrying else "; retries exhausted")
            )
            self._render()
            return
        if event_type == "tool_call":
            tool_name = str(payload.get("tool_name", "tool"))
            tool_call_id = payload.get("tool_call_id")
            arguments = json.dumps(payload.get("arguments", {}), ensure_ascii=True)
            self.activity = f"running {tool_name}"
            block = self._push_block(
                "tool",
                f"Tool: {tool_name}",
                "",
                status="running",
                meta={"tool_name": tool_name, "tool_call_id": tool_call_id, "input": arguments, "result": "Running..."},
            )
            if tool_call_id:
                self.pending_tools[tool_call_id] = block
            self._add_audit(f"tool started: {tool_name}")
            self._render()
            return
        if event_type == "tool_result":
            self._update_metrics(payload)
            result = payload.get("result") or {}
            tool_name = str(payload.get("tool_name", "tool"))
            tool_call_id = payload.get("tool_call_id") or result.get("tool_call_id")
            status = "ok" if payload.get("ok") else "error"
            block = self._find_pending_tool(tool_call_id, tool_name)
            detail = self._summarize_tool_result(result)
            if block is None:
                block = self._push_block(
                    "tool",
                    f"Tool: {tool_name}",
                    "",
                    status=status,
                    meta={"tool_name": tool_name, "tool_call_id": tool_call_id, "input": "", "result": detail},
                )
            else:
                block["status"] = status
                block["meta"]["status"] = status
                block["meta"]["result"] = detail
            self.activity = "waiting for model continuation"
            self._add_audit(f"tool finished: {tool_name} [{status}]")
            self._render()
            return
        if event_type == "tool_retry":
            self.activity = "repairing tool call"
            self._add_audit(f"retry: {payload.get('reason')}")
            self._render()
            return
        if event_type == "repair_prompt":
            self.activity = "repair prompt issued"
            self._add_audit(f"repair: {payload.get('reason')}")
            self._render()
            return
        if event_type == "mid_task_injection":
            self.activity = "received user update"
            self._add_audit("injection delivered")
            self._push_block("user", "User", _trim_block(str(payload.get("content", "")), 900))
            self._render()
            return
        if event_type == "verification":
            self.activity = "verifying"
            self._add_audit(f"verification: {'pass' if payload.get('verification_passed') else 'fail'}")
            self._render()
            return
        if event_type == "turn_metrics":
            self._update_metrics(payload)
            self.activity = "turn complete"
            self._add_audit(
                f"turn metrics: ttft={payload.get('ttft_ms', 'n/a')} ms, "
                f"tps={payload.get('tokens_per_second', 'n/a')}"
            )
            self._render()
            return
        if event_type in {"timeout", "final_result"}:
            self.activity = str(payload.get("status", event_type))
            self._add_audit(f"final: {payload.get('status', event_type)}")
            self._render()
            print()
            return


def make_agentic_observer(show_prompts: str = "summary", style: str = "log"):
    if style == "theater":
        return HarnessTheaterObserver(show_prompts=show_prompts)

    def observer(event_type: str, payload: dict) -> None:
        if event_type == "episode_start":
            print("\n" + "-" * 62)
            print(f"  SIM {payload.get('workflow_id')} :: {payload.get('title')}")
            print(f"  Workspace : {payload.get('workspace')}")
            print(f"  Tools     : {', '.join(payload.get('active_tools', []))}")
            if show_prompts != "off":
                print("  User Event")
                print("  ----------")
                print(_trim_block(str(payload.get("user_event", ""))))
            if show_prompts == "full":
                print("\n  System Prompt")
                print("  -------------")
                print(_trim_block(str(payload.get("system_prompt", "")), limit=2400))
            print("-" * 62)
            return
        if event_type == "turn_start":
            print(f"\n  Turn {payload.get('turn')}")
            return
        if event_type == "model_request":
            if show_prompts == "off":
                return
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                return
            print(f"  Prompt [{payload.get('attempt')}]")
            print("  -----------")
            print(_trim_block(prompt, limit=1200 if show_prompts == "full" else 360))
            return
        if event_type in {"assistant_action", "plaintext_turn"}:
            latency = payload.get("latency_ms")
            context = payload.get("context_tokens_estimate")
            vram = ((payload.get("hardware_usage") or {}).get("vram_peak_mb"))
            meta = []
            if latency is not None:
                meta.append(f"{latency} ms")
            if context is not None:
                meta.append(f"ctx {context}")
            if vram:
                meta.append(f"vram {vram}")
            meta_text = " | ".join(meta)
            print(f"  Assistant{': ' + meta_text if meta_text else ''}")
            print("  ----------")
            print(_trim_block(str(payload.get("content", "")), limit=1400))
            return
        if event_type == "tool_call":
            print(f"  Tool Call  : {payload.get('tool_name')}")
            print(f"  Arguments  : {json.dumps(payload.get('arguments', {}), ensure_ascii=True)}")
            return
        if event_type == "tool_result":
            result = payload.get("result") or {}
            status = "ok" if payload.get("ok") else "error"
            print(f"  Tool Result: {payload.get('tool_name')} [{status}]")
            if payload.get("ok"):
                content = result.get("content")
                summary = result.get("summary")
                shown = summary if summary else json.dumps(content, ensure_ascii=True) if not isinstance(content, str) else content
                if shown:
                    print(_trim_block(str(shown), limit=500))
            else:
                print(_trim_block(str(result.get("error", "tool failed")), limit=500))
            return
        if event_type == "tool_retry":
            print(f"  Retry      : {payload.get('reason')}")
            return
        if event_type == "repair_prompt":
            print(f"  Repair     : {payload.get('reason')}")
            return
        if event_type == "mid_task_injection":
            print("  Injection")
            print("  ---------")
            print(_trim_block(str(payload.get("content", "")), limit=500))
            return
        if event_type == "verification":
            result = payload.get("result") or {}
            print(f"  Verify     : {payload.get('method')} -> {'pass' if payload.get('verification_passed') else 'fail'}")
            if result:
                print(_trim_block(json.dumps(result, ensure_ascii=True), limit=500))
            return
        if event_type == "timeout":
            print("  Timeout    : harness hit workflow timeout")
            return
        if event_type == "final_result":
            print(f"  Final      : {payload.get('status')} ({payload.get('failure_reason') or 'ok'})")
            summary = payload.get("summary")
            if summary:
                print(_trim_block(str(summary), limit=500))
            return
    return observer


def create_run_output_dir(base_output: Path, benchmark_mode: str, model_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_label = sanitize_label(model_path.stem)
    run_dir = base_output / f"{sanitize_label(benchmark_mode)}_{model_label}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def format_elapsed(elapsed_s: float) -> str:
    if elapsed_s < 60:
        return f"{round(elapsed_s, 1)} seconds"
    minutes = int(elapsed_s // 60)
    seconds = round(elapsed_s % 60, 1)
    if seconds == 0:
        return f"{minutes} minutes"
    return f"{minutes} minutes {seconds} seconds"


def prompt_open_visualizer(output_path: Path, elapsed_s: float) -> None:
    from gnuckle.visualize import run_visualize

    out_file = run_visualize(str(output_path))
    if not _is_interactive_terminal():
        print(f"  visualizer banana is saved in {out_file} for viewing later.")
        return

    print()
    choice = input(
        f"  benchmark is complete. it took {format_elapsed(elapsed_s)}. "
        "do you want to open the visualizer now? [y/n]: "
    ).strip().lower()
    if choice in ("y", ""):
        try:
            webbrowser.open(out_file.resolve().as_uri())
            print("  visualizer open in browser. ape look at charts.")
        except Exception:
            print(f"  visualizer banana is saved in {out_file} for viewing later.")
    else:
        print(f"  visualizer banana is saved in {out_file} for viewing later.")


def summarize_exception(exc: Exception) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


def is_retryable_turn_error(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "tool call" in lowered
        or "json" in lowered
        or "parse" in lowered
        or "invalid tool" in lowered
    )


def make_tool_result_message(tool_call_id, name, ok, content, error_type=None, denied=False, arguments=None, retry_errors=None):
    payload = {
        "tool": name,
        "ok": ok,
        "is_error": not ok,
        "error_type": error_type,
        "denied": denied,
    }
    if ok:
        payload["content"] = content
    else:
        payload["error"] = content
    if arguments is not None:
        payload["arguments"] = arguments
    if retry_errors:
        payload["retry_errors"] = list(retry_errors)
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload, ensure_ascii=True),
    }


def detect_gpus():
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore").strip().splitlines()
        gpus = []
        for line in out:
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                index = int(parts[0])
                memory_total_mb = int(parts[2])
            except ValueError:
                continue
            gpus.append(
                {
                    "index": index,
                    "name": parts[1],
                    "memory_total_mb": memory_total_mb,
                }
            )
        return gpus
    except Exception:
        return []


def prompt_split_mode(gpus):
    if len(gpus) <= 1:
        return {
            "split_mode": "none",
            "main_gpu": gpus[0]["index"] if gpus else 0,
            "tensor_split": None,
        }

    print("\n  ape see many GPUs. ape want --split-mode?\n")
    for gpu in gpus:
        print(f"  [{gpu['index']}] {gpu['name']}  ({gpu['memory_total_mb']} MB)")
    print()
    print("  split modes from llama.cpp:")
    print_info("none  : use one GPU only. best when one card can hold the useful workload.")
    print_info("layer : split layers and KV across GPUs. default multi-GPU choice; best first thing to try.")
    print_info("row   : split rows across GPUs. advanced mode; main GPU also handles intermediate results and KV.")
    print()

    options = {"1": "none", "2": "layer", "3": "row"}
    while True:
        print("  [1] none")
        print("  [2] layer")
        print("  [3] row")
        choice = input("  ape pick split mode [1-3]: ").strip()
        split_mode = options.get(choice)
        if split_mode:
            break
        print("  bad banana. pick again.")

    config = {
        "split_mode": split_mode,
        "main_gpu": 0,
        "tensor_split": None,
    }

    if split_mode in {"none", "row"}:
        print()
        print(f"  main GPU matters for split-mode={split_mode}.")
        print_info("none : main GPU is the one GPU used for the model.")
        print_info("row  : main GPU handles intermediate results and KV.")
        while True:
            choice = input("  ape pick main GPU index: ").strip()
            try:
                main_gpu = int(choice)
            except ValueError:
                print("  bad banana. enter a GPU index.")
                continue
            if any(gpu["index"] == main_gpu for gpu in gpus):
                config["main_gpu"] = main_gpu
                break
            print("  ape no see that GPU index.")

    return config


def estimate_context_tokens(messages, tools=None):
    return estimate_context_token_counts(messages, tools)["heuristic"]


def server_root_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    path = parsed.path or ""
    if path.endswith("/v1"):
        path = path[:-3]
    path = path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _post_json(url: str, payload: dict) -> dict | None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def llamacpp_tokenizer_label() -> str:
    return "llama.cpp exact"


def probe_llamacpp_exact(base_url: str | None) -> bool:
    """Probe whether the llama.cpp server supports /tokenize. Returns True only on success."""
    if not base_url:
        return False
    data = _post_json(f"{server_root_url(base_url)}/tokenize", {"content": "probe"})
    return isinstance(data, dict) and isinstance(data.get("tokens"), list)


def llamacpp_text_token_count(base_url: str | None, text: str) -> int | None:
    if not base_url:
        return None
    payload = {"content": text}
    data = _post_json(f"{server_root_url(base_url)}/tokenize", payload)
    tokens = data.get("tokens") if isinstance(data, dict) else None
    return len(tokens) if isinstance(tokens, list) else None


def llamacpp_context_token_count(base_url: str | None, messages: list[dict], tools=None) -> int | None:
    if not base_url:
        return None
    template_payload = {
        "messages": messages,
        "tools": tools or [],
        "add_generation_prompt": True,
    }
    rendered = _post_json(f"{server_root_url(base_url)}/apply-template", template_payload)
    prompt = rendered.get("prompt") if isinstance(rendered, dict) else None
    if not prompt:
        return None
    return llamacpp_text_token_count(base_url, prompt)


def preferred_tokenizer_count(text: str, base_url: str | None = None) -> tuple[int | None, str, int | None, str]:
    measured = llamacpp_text_token_count(base_url, text)
    if measured is not None:
        return measured, llamacpp_tokenizer_label(), measured, llamacpp_tokenizer_label()
    fallback = tokenizer_token_count(text)
    return fallback, tokenizer_label(), measured, llamacpp_tokenizer_label()


def preferred_context_token_count(messages, tools=None, base_url: str | None = None) -> tuple[int | None, str, int | None, str]:
    measured = llamacpp_context_token_count(base_url, messages, tools)
    if measured is not None:
        return measured, llamacpp_tokenizer_label(), measured, llamacpp_tokenizer_label()
    tokenizer_payload = {
        "messages": messages,
        "tools": tools or [],
    }
    fallback = tokenizer_token_count(json.dumps(tokenizer_payload, ensure_ascii=True))
    return fallback, tokenizer_label(), measured, llamacpp_tokenizer_label()


def estimate_context_token_counts(messages, tools=None, base_url: str | None = None):
    total_chars = 0
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += len(json.dumps(content, ensure_ascii=True))
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            total_chars += len(json.dumps(tool_calls, ensure_ascii=True))
    if tools:
        total_chars += len(json.dumps(tools, ensure_ascii=True))
    preferred_count, preferred_label, measured_count, measured_label = preferred_context_token_count(
        messages,
        tools=tools,
        base_url=base_url,
    )
    return {
        "heuristic": max(1, round(total_chars / 4)),
        "tokenizer": preferred_count,
        "tokenizer_label": preferred_label,
        "measured": measured_count,
        "measured_label": measured_label,
    }


def prompt_token_counts(text: str, base_url: str | None = None) -> dict:
    preferred_count, preferred_label, measured_count, measured_label = preferred_tokenizer_count(
        text,
        base_url=base_url,
    )
    return {
        "heuristic": approx_token_count(text),
        "tokenizer": preferred_count,
        "tokenizer_label": preferred_label,
        "measured": measured_count,
        "measured_label": measured_label,
    }


def token_counting_info(exact_available: bool = False) -> dict:
    sample = tokenizer_token_count("banana")
    secondary_method = (
        f"{tokenizer_label()} approximation"
        if sample is not None
        else "tokenizer unavailable"
    )
    info = {
        "status": "measured" if exact_available else "estimated",
        "primary_method": (
            "llama.cpp /apply-template + /tokenize"
            if exact_available
            else secondary_method
        ),
        "measured": bool(exact_available),
        "warning": (
            "Context-pressure metrics are measured with llama.cpp server endpoints."
            if exact_available
            else
            "Context-pressure metrics are estimated until the llama.cpp-backed exact path is available. "
            "Treat CB-6, CB-7, CB-10, and CB-11 context claims as having roughly 15% uncertainty."
        ),
    }
    info["secondary_method"] = secondary_method if exact_available else "char/4 heuristic"
    info["tertiary_method"] = "char/4 heuristic" if exact_available else None
    return info


def empty_usage():
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


def update_usage(usage, part_usage):
    if not part_usage:
        return usage
    data = usage.copy()
    for key in ("input_tokens", "output_tokens", "total_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = getattr(part_usage, key, None)
        if value is None and isinstance(part_usage, dict):
            value = part_usage.get(key)
        if value is None:
            continue
        if key == "input_tokens":
            data[key] = value if value > 0 else data[key]
        else:
            data[key] = value
    return data


def accumulate_usage(total_usage, message_usage):
    data = empty_usage()
    for key in data:
        data[key] = int(total_usage.get(key, 0) or 0) + int(message_usage.get(key, 0) or 0)
    if data["total_tokens"] <= 0:
        data["total_tokens"] = (
            data["input_tokens"]
            + data["cache_creation_input_tokens"]
            + data["cache_read_input_tokens"]
            + data["output_tokens"]
        )
    return data


def usage_total_tokens(usage):
    explicit_total = int(usage.get("total_tokens", 0) or 0)
    if explicit_total > 0:
        return explicit_total
    return (
        int(usage.get("input_tokens", 0) or 0)
        + int(usage.get("cache_creation_input_tokens", 0) or 0)
        + int(usage.get("cache_read_input_tokens", 0) or 0)
        + int(usage.get("output_tokens", 0) or 0)
    )


def summarize_tool_choice(tool_names, expected_tools, wrong_tool_calls, disallowed_tool_calls):
    used = list(tool_names)
    expected = list(expected_tools)
    if not used:
        return "none", "used=none", f"want={','.join(expected) if expected else 'none'}"
    if disallowed_tool_calls:
        status = "bad"
    elif wrong_tool_calls:
        status = "mixed"
    else:
        status = "good"
    used_preview = ",".join(used[:3])
    if len(used) > 3:
        used_preview += ",..."
    expected_preview = ",".join(expected[:3])
    if len(expected) > 3:
        expected_preview += ",..."
    return status, f"used={used_preview}", f"want={expected_preview}"


def get_context_window(preset=None, default_ctx_size=131072):
    server_args = ((preset or {}).get("server_args", {}) or {})
    for key in ("ctx_size", "ctx-size", "context_window"):
        value = server_args.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return int(default_ctx_size)

@lru_cache(maxsize=1)
def load_presets():
    with PRESETS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_sampler_overrides(selected, sampler_overrides):
    if not sampler_overrides:
        return selected

    selected["server_args"].update(sampler_overrides)

    request_updates = {}
    if "temp" in sampler_overrides:
        request_updates["temperature"] = sampler_overrides["temp"]
    if "temperature" in sampler_overrides:
        request_updates["temperature"] = sampler_overrides["temperature"]
    if "top_p" in sampler_overrides:
        request_updates["top_p"] = sampler_overrides["top_p"]

    selected["request_args"].update(request_updates)
    return selected

def select_preset(model_path: Path, preset_name=None, sampler_overrides=None):
    presets = load_presets()
    if preset_name:
        for preset in presets.get("presets", []):
            if preset.get("name") == preset_name:
                selected = copy.deepcopy(preset)
                return merge_sampler_overrides(selected, sampler_overrides)
        if preset_name == presets["default"].get("name"):
            selected = copy.deepcopy(presets["default"])
            return merge_sampler_overrides(selected, sampler_overrides)
    model_name = model_path.name.lower()
    for preset in presets.get("presets", []):
        if any(token in model_name for token in preset.get("match", [])):
            selected = copy.deepcopy(preset)
            return merge_sampler_overrides(selected, sampler_overrides)
    selected = copy.deepcopy(presets["default"])
    return merge_sampler_overrides(selected, sampler_overrides)

def get_cache_configs(cache_labels=None):
    if not cache_labels:
        return CACHE_CONFIGS
    wanted = {label.lower() for label in cache_labels}
    return [cfg for cfg in CACHE_CONFIGS if cfg["label"].lower() in wanted]

def build_llama_args(arg_map):
    args = []
    for key, value in arg_map.items():
        flag = f"--{key.replace('_', '-')}"
        args.extend([flag, str(value)])
    return args


def append_unique_flag(cmd, flag):
    if flag not in cmd:
        cmd.append(flag)

def find_gguf_files(directory: Path):
    """Scan directory and common subdirs for .gguf files."""
    found = list(directory.glob("*.gguf"))
    for sub in ["models", "gguf"]:
        sub_dir = directory / sub
        if sub_dir.is_dir():
            found.extend(sub_dir.glob("*.gguf"))
    return sorted(set(found))

SERVER_NAMES = [
    "llama-server", "llama-server.exe",
    "server", "server.exe",
]
BENCH_NAMES = [
    "llama-bench", "llama-bench.exe",
    "bench", "bench.exe",
]
SERVER_SEARCH_DIRS = [
    ".", "build/bin", "build/bin/Release", "build/bin/Debug",
    "bin", "build",
]

def find_server(base_dir: Path):
    """Auto-detect llama-server binary in cwd and common build dirs."""
    for sub in SERVER_SEARCH_DIRS:
        d = base_dir / sub
        if not d.is_dir():
            continue
        for name in SERVER_NAMES:
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def _search_binary(base_dirs: list[Path], names: list[str]):
    seen = set()
    for base_dir in base_dirs:
        try:
            resolved = str(base_dir.resolve())
        except OSError:
            resolved = str(base_dir)
        if resolved in seen:
            continue
        seen.add(resolved)
        for sub in SERVER_SEARCH_DIRS:
            d = base_dir / sub
            if not d.is_dir():
                continue
            for name in names:
                candidate = d / name
                if candidate.is_file():
                    return candidate
    return None


def find_bench(server_path: Path):
    """Find llama-bench near the selected llama-server binary."""
    roots = [server_path.parent]
    if server_path.parent.parent != server_path.parent:
        roots.append(server_path.parent.parent)
    if server_path.parent.parent.parent != server_path.parent.parent:
        roots.append(server_path.parent.parent.parent)
    return _search_binary(roots, BENCH_NAMES)


def parse_llama_bench_output(output: str) -> dict:
    """Extract prompt and generation throughput from llama-bench text output."""
    import re

    metrics = {
        "prompt_tokens_per_second": None,
        "generation_tokens_per_second": None,
        "prompt_label": None,
        "generation_label": None,
    }
    lines = [line.strip() for line in str(output or "").splitlines() if line.strip()]
    row_re = re.compile(r"\b(?P<label>(?:pp|tg)\d+)\b")
    num_re = re.compile(r"[-+]?\d[\d,]*\.?\d*")

    for line in lines:
        match = row_re.search(line)
        if not match:
            continue
        label = match.group("label")
        numbers = []
        for token in num_re.findall(line):
            try:
                numbers.append(float(token.replace(",", "")))
            except ValueError:
                continue
        if not numbers:
            continue
        rate = numbers[-1]
        if label.startswith("pp") and metrics["prompt_tokens_per_second"] is None:
            metrics["prompt_tokens_per_second"] = rate
            metrics["prompt_label"] = label
        elif label.startswith("tg") and metrics["generation_tokens_per_second"] is None:
            metrics["generation_tokens_per_second"] = rate
            metrics["generation_label"] = label
    return metrics


def collect_llama_bench_metrics(server_path: Path, model_path: Path, cache_k: str, cache_v: str, preset=None, split_config=None) -> dict:
    """Run llama-bench if available and return prompt/gen throughput snapshot."""
    preset = preset or select_preset(model_path)
    split_config = split_config or {}
    bench_path = find_bench(server_path)
    metrics = {
        "available": False,
        "bench_path": str(bench_path) if bench_path else None,
        "prompt_tokens_per_second": None,
        "generation_tokens_per_second": None,
        "prompt_label": None,
        "generation_label": None,
        "raw_output": None,
        "error": None,
    }
    if bench_path is None:
        metrics["error"] = "llama-bench binary not found"
        return metrics

    split_mode = split_config.get("split_mode", "layer")
    main_gpu = split_config.get("main_gpu", 0)
    tensor_split = split_config.get("tensor_split")
    cmd = [
        str(bench_path),
        "-m", str(model_path),
        "-ngl", "99",
        "--split-mode", str(split_mode),
        "--main-gpu", str(main_gpu),
        "--cache-type-k", cache_k,
        "--cache-type-v", cache_v,
        "-p", "512",
        "-n", "128",
        "-r", "1",
    ]
    if tensor_split:
        cmd.extend(["--tensor-split", str(tensor_split)])
    cmd.extend(build_llama_args(preset.get("server_args", {})))

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
    except Exception as exc:
        metrics["error"] = str(exc)
        return metrics

    raw_output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    metrics["raw_output"] = raw_output[:4000]
    if completed.returncode != 0:
        metrics["error"] = f"llama-bench failed with exit code {completed.returncode}"
        return metrics

    parsed = parse_llama_bench_output(raw_output)
    metrics.update(parsed)
    metrics["available"] = bool(
        parsed.get("prompt_tokens_per_second") is not None
        or parsed.get("generation_tokens_per_second") is not None
    )
    if not metrics["available"]:
        metrics["error"] = "unable to parse llama-bench output"
    return metrics

def prompt_gguf_selection(gguf_files):
    print("\n  Available GGUF files (ape see banana pile):\n")
    for i, f in enumerate(gguf_files):
        size_gb = f.stat().st_size / (1024 ** 3)
        print(f"  [{i + 1}] {f.name}  ({size_gb:.2f} GB)")
    print()
    while True:
        try:
            choice = int(input("  ape pick model [number]: ").strip())
            if 1 <= choice <= len(gguf_files):
                return gguf_files[choice - 1]
            print("  bad banana. pick again.")
        except (ValueError, KeyboardInterrupt):
            print("\n  ape leave.")
            sys.exit(0)

def prompt_server_path():
    print("\n  ape need llama-server. where is it?")
    if sys.platform == "win32":
        print("  Example: C:\\Users\\you\\llama.cpp\\build\\bin\\Release\\llama-server.exe\n")
    else:
        print("  Example: /home/user/llama.cpp/build/bin/llama-server\n")
    while True:
        path = input("  llama-server path: ").strip().strip('"')
        p = Path(path)
        if p.exists():
            return p
        print(f"  ape no find: {path}")

def port_open(port, host="localhost"):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def is_server_loading_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "loading model" in text or "503" in text or "unavailable_error" in text

def warmup_messages(system_prompt=None):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append(
        {
            "role": "user",
            "content": "Warm up the model and reply with exactly: READY",
        }
    )
    return messages

def wait_for_server(port, timeout=SERVER_WAIT_S):
    ape_print("server_wait")
    base_url = DEFAULT_BASE_URL.format(port=port)
    client = OpenAI(base_url=base_url, api_key=API_KEY)
    deadline = time.time() + timeout
    poked = False
    while time.time() < deadline:
        if port_open(port):
            try:
                client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    temperature=0,
                )
                ape_print("server_up")
                render_progress("server ready", timeout, timeout, done=True)
                return True
            except Exception as exc:
                if not is_server_loading_error(exc):
                    pass
        if not poked and time.time() > deadline - timeout / 2:
            ape_print("loading")
            poked = True
        elapsed = min(timeout, max(0, round(timeout - (deadline - time.time()))))
        render_progress("waiting for server", elapsed, timeout, done=False)
        time.sleep(1)
    render_progress("server wait timed out", timeout, timeout, done=True)
    return False

def warmup_server(port, preset=None, system_prompt=None, timeout=WARMUP_WAIT_S):
    base_url = DEFAULT_BASE_URL.format(port=port)
    client = OpenAI(base_url=base_url, api_key=API_KEY)
    preset = preset or load_presets()["default"]
    request_args = preset.get("request_args", {})
    deadline = time.time() + timeout
    announced = False

    while time.time() < deadline:
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=warmup_messages(system_prompt=system_prompt),
                max_tokens=8,
                temperature=request_args.get("temperature", 0.6),
                top_p=request_args.get("top_p", 0.95),
            )
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if content or resp.choices:
                render_progress("model warmup complete", timeout, timeout, done=True)
                print("  >> warmup done. model answer received.")
                return True
        except Exception as exc:
            if not announced:
                print("  >> preloading model. wait for first real response...")
                announced = True
            if not is_server_loading_error(exc):
                print(f"  >> warmup retry after startup error: {exc}")
        elapsed = min(timeout, max(0, round(timeout - (deadline - time.time()))))
        render_progress("warming model", elapsed, timeout, done=False)
        time.sleep(2)
    render_progress("warmup timed out", timeout, timeout, done=True)
    return False

def kill_server(proc):
    if proc and proc.poll() is None:
        ape_print("server_kill")
        if sys.platform == "win32":
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(2)

def start_server(server_path: Path, model_path: Path, cache_k: str, cache_v: str, port: int,
                 preset=None, use_jinja=True, split_config=None):
    preset = preset or select_preset(model_path)
    split_config = split_config or {}
    split_mode = split_config.get("split_mode", "layer")
    main_gpu = split_config.get("main_gpu", 0)
    tensor_split = split_config.get("tensor_split")
    cmd = [
        str(server_path),
        "-m",               str(model_path),
        "--host",           "0.0.0.0",
        "--port",           str(port),
        "-ngl",             "99",
        "--split-mode",     str(split_mode),
        "--main-gpu",       str(main_gpu),
        "--ctx-size",       "131072",
        "--cache-type-k",   cache_k,
        "--cache-type-v",   cache_v,
        "--temp",           "0.6",
        "--top-p",          "0.95",
        "--top-k",          "20",
        "--repeat-penalty", "1.1",
    ]
    if tensor_split:
        cmd.extend(["--tensor-split", str(tensor_split)])
    if use_jinja:
        append_unique_flag(cmd, "--jinja")
    cmd.extend(build_llama_args(preset.get("server_args", {})))
    print_step(f"starting server: cache-k={cache_k} cache-v={cache_v}")
    print_step(f"preset: {preset.get('name', 'default')}")
    print_step(f"split-mode: {split_mode} (main-gpu={main_gpu})")
    ape_print("loading")
    kwargs = {}
    if sys.platform != "win32":
        kwargs["preexec_fn"] = os.setsid
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs
    )
    return proc

# ── VRAM ──────────────────────────────────────────────────────────────────────
def get_vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL
        ).decode().strip().split("\n")
        return [int(v.strip()) for v in out if v.strip()]
    except Exception:
        return []


def get_process_ram_mb(pid):
    if not pid:
        return None
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Process -Id {int(pid)} -ErrorAction Stop).WorkingSet64",
                ],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore").strip()
            if not out:
                return None
            return round(int(out) / (1024 * 1024), 1)
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(int(pid))],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore").strip()
        if not out:
            return None
        return round(int(out.splitlines()[-1].strip()) / 1024, 1)
    except Exception:
        return None


def get_hardware_snapshot(server_pid=None):
    vram = get_vram_mb()
    ram_mb = get_process_ram_mb(server_pid)
    return {
        "vram_used_mb": vram,
        "vram_peak_mb": max(vram) if vram else 0,
        "ram_used_mb": ram_mb,
    }

# ── STREAMING CALL ────────────────────────────────────────────────────────────
def call_with_metrics(client, messages, port, preset=None, base_url: str | None = None):
    preset = preset or load_presets()["default"]
    request_args = preset.get("request_args", {})
    context_counts = estimate_context_token_counts(messages, TOOLS, base_url=base_url)
    t_send        = time.perf_counter()
    first_token_t = None
    text_chunks   = 0
    tool_chunks   = 0
    full_content  = ""
    tc_accum      = {}
    current_usage = empty_usage()

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        stream=True,
        stream_options={"include_usage": True},
        temperature=request_args.get("temperature", 0.6),
        top_p=request_args.get("top_p", 0.95),
        max_tokens=512
    )

    for chunk in stream:
        if first_token_t is None:
            first_token_t = time.perf_counter()
        delta = chunk.choices[0].delta if chunk.choices else None
        if getattr(chunk, "usage", None) is not None:
            current_usage = update_usage(current_usage, chunk.usage)
        if not delta:
            continue
        if delta.content:
            full_content += delta.content
            text_chunks  += 1
        if delta.tool_calls:
            for tc in delta.tool_calls:
                saw_tool_delta = False
                idx = tc.index
                if idx not in tc_accum:
                    tc_accum[idx] = {"id": tc.id or "", "function": {"name": "", "arguments": ""}}
                if tc.function:
                    if tc.function.name:
                        tc_accum[idx]["function"]["name"] += tc.function.name
                        saw_tool_delta = True
                    if tc.function.arguments:
                        tc_accum[idx]["function"]["arguments"] += tc.function.arguments
                        saw_tool_delta = True
                if tc.id and not tc_accum[idx]["id"]:
                    saw_tool_delta = True
                if saw_tool_delta:
                    tool_chunks += 1

    t_end   = time.perf_counter()
    ttft    = round((first_token_t - t_send) * 1000, 1) if first_token_t else None
    elapsed = t_end - t_send
    total_chunks = text_chunks + tool_chunks
    tps     = round(total_chunks / elapsed, 2) if elapsed > 0 and total_chunks > 0 else 0.0
    primary_context = (
        int(context_counts["measured"])
        if context_counts["measured"] is not None
        else int(context_counts["heuristic"])
    )

    return {
        "content":    full_content,
        "tool_calls": list(tc_accum.values()),
        "ttft_ms":    ttft,
        "tokens":     total_chunks,
        "text_tokens": text_chunks,
        "tool_call_chunks": tool_chunks,
        "elapsed_s":  round(elapsed, 3),
        "tps":        tps,
        "usage":      current_usage,
        "usage_total_tokens": usage_total_tokens(current_usage),
        "context_tokens_estimate": primary_context,
        "context_tokens_heuristic": context_counts["heuristic"],
        "context_tokens_tokenizer": context_counts["tokenizer"],
        "tokenizer_label": context_counts["tokenizer_label"],
        "context_tokens_measured": context_counts["measured"],
        "measured_label": context_counts["measured_label"],
    }

# ── SINGLE CACHE-TYPE RUN ─────────────────────────────────────────────────────
def run_benchmark_pass(cache_label, model_path, output_dir, num_turns, port, preset=None, system_prompt=None,
                       system_prompt_source="custom_inline", split_config=None, throughput_benchmark=None):
    base_url = DEFAULT_BASE_URL.format(port=port)
    client   = OpenAI(base_url=base_url, api_key=API_KEY)
    exact_available = probe_llamacpp_exact(base_url)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"benchmark_{cache_label}_{ts}.json"
    split_config = split_config or {"split_mode": "layer", "main_gpu": 0, "tensor_split": None}

    prompt_counts = prompt_token_counts(system_prompt or DEFAULT_SYSTEM_PROMPT, base_url=base_url)
    results = {
        "meta": {
            "cache_label": cache_label,
            "model":       model_path.name,
            "num_turns":   num_turns,
            "timestamp":   datetime.now().isoformat(),
            "sampler_preset": preset.get("name", "default") if preset else "default",
            "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
            "system_prompt_source": system_prompt_source,
            "system_prompt_tokens_approx": prompt_counts["heuristic"],
            "system_prompt_tokens_heuristic": prompt_counts["heuristic"],
            "system_prompt_tokens_tokenizer": prompt_counts["tokenizer"],
            "system_prompt_tokens_measured": prompt_counts["measured"],
            "tokenizer_label": prompt_counts["tokenizer_label"],
            "measured_label": prompt_counts["measured_label"],
            "token_counting": token_counting_info(exact_available=exact_available),
            "split_config": split_config,
            "throughput_benchmark": throughput_benchmark or {},
        },
        "turns": [],
        "aggregate": {
            "turn_count": num_turns,
            "error_turns": 0,
            "retry_events": 0,
            "invalid_tool_call_turns": 0,
            "tool_validation_failures": 0,
            "execution_failures": 0,
            "permission_denials": 0,
            "synthetic_tool_results": 0,
            "wrong_tool_calls": 0,
            "unnecessary_tool_calls": 0,
            "disallowed_tool_calls": 0,
            "repeated_bad_tool_calls": 0,
            "tool_selection_precision": 0.0,
            "provider_input_tokens": 0,
            "provider_output_tokens": 0,
            "provider_total_tokens": 0,
            "peak_context_tokens_estimate": 0,
            "peak_context_tokens_heuristic": 0,
            "peak_context_tokens_tokenizer": 0,
            "peak_context_tokens_measured": None,
            "prompt_tokens_per_second_bench": None,
            "generation_tokens_per_second_bench": None,
        },
    }
    if throughput_benchmark:
        results["aggregate"]["prompt_tokens_per_second_bench"] = throughput_benchmark.get("prompt_tokens_per_second")
        results["aggregate"]["generation_tokens_per_second_bench"] = throughput_benchmark.get("generation_tokens_per_second")

    messages = [
        {
            "role": "system",
            "content": system_prompt or DEFAULT_SYSTEM_PROMPT
        }
    ]

    vram_idle = get_vram_mb()
    print_step(f"VRAM idle: {vram_idle} MB")
    prior_tool_signatures = set()

    for turn_idx in range(num_turns):
        prompt = TURN_PROMPTS[turn_idx % len(TURN_PROMPTS)]
        expected_tools = LEGACY_EXPECTED_TOOLS[turn_idx % len(LEGACY_EXPECTED_TOOLS)]
        messages.append({"role": "user", "content": prompt})
        ctx_counts = estimate_context_token_counts(messages, TOOLS, base_url=base_url)
        ctx_approx = int(ctx_counts["measured"]) if ctx_counts["measured"] is not None else ctx_counts["heuristic"]

        result = None
        tool_accuracy = []
        tool_results = []
        turn_error = None
        retry_errors = []
        vram_before = []
        vram_after = []

        for attempt in range(MAX_MALFORMED_TOOL_RETRIES + 1):
            vram_before = get_vram_mb()
            try:
                result = call_with_metrics(client, messages, port, preset=preset, base_url=base_url)
                turn_error = None
            except Exception as exc:
                result = None
                turn_error = summarize_exception(exc)

            vram_after = get_vram_mb()
            tool_accuracy = []
            tool_results = []

            if turn_error is None and result and result["tool_calls"]:
                malformed = False
                for tc in result["tool_calls"]:
                    name = tc["function"]["name"]
                    arguments = None
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        arguments = args
                    except json.JSONDecodeError as e:
                        args = None
                        valid = False
                        error = str(e)
                    else:
                        tool_spec = next(
                            (t for t in TOOLS if t["function"]["name"] == name),
                            None,
                        )
                        if tool_spec is None:
                            valid = False
                            error = f"disallowed tool: {name}"
                        else:
                            required = tool_spec["function"]["parameters"].get("required", [])
                            missing = [r for r in required if r not in args]
                            valid = len(missing) == 0
                            error = f"missing: {missing}" if missing else None

                    signature = None
                    if arguments is not None:
                        signature = f"{name}:{json.dumps(arguments, sort_keys=True, ensure_ascii=True)}"
                    tool_accuracy.append(
                        {
                            "tool": name,
                            "valid": valid,
                            "error": error,
                            "arguments": arguments,
                            "signature": signature,
                        }
                    )
                    if not valid:
                        malformed = True
                    tool_results.append(
                        make_tool_result_message(
                            tool_call_id=tc.get("id", f"tc_{turn_idx}"),
                            name=name,
                            ok=valid,
                            content=MOCK_RESPONSES.get(name, '{"status":"ok"}') if valid else error or "invalid tool call",
                            error_type=None if valid else "input_validation_error",
                            denied=False,
                            arguments=arguments,
                            retry_errors=retry_errors if not valid else None,
                        )
                    )
                if malformed:
                    first_error = next(
                        (entry["error"] for entry in tool_accuracy if not entry["valid"] and entry.get("error")),
                        "invalid tool call",
                    )
                    turn_error = f"invalid tool call: {first_error}"

            if turn_error is None:
                break

            retry_errors.append(turn_error)
            if attempt < MAX_MALFORMED_TOOL_RETRIES and is_retryable_turn_error(turn_error):
                print_step(f"turn {turn_idx + 1:02d} retry after malformed tool call")
                continue
            break

        if result is None:
            choice_status, used_preview, expected_preview = summarize_tool_choice([], expected_tools, 0, 0)
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Tool-call turn failed inside benchmark harness: {turn_error}",
                }
            )
            turn_data = {
                "turn":                  turn_idx + 1,
                "prompt":                prompt,
                "active_tools":          ACTIVE_TOOL_NAMES,
                "expected_tools":        expected_tools,
                "assistant_preview":     "",
                "tool_call_names":       [],
                "tool_call_arguments":   [],
                "ttft_ms":               None,
                "tokens_generated":      0,
                "text_tokens_generated": 0,
                "tool_call_chunks":      0,
                "elapsed_s":             0.0,
                "tps":                   0.0,
                "context_tokens_approx": ctx_approx,
                "context_tokens_estimate": ctx_approx,
                "context_tokens_heuristic": ctx_approx,
                "context_tokens_tokenizer": ctx_counts["tokenizer"],
                "tokenizer_label": ctx_counts["tokenizer_label"],
                "context_tokens_measured": ctx_counts["measured"],
                "measured_label": ctx_counts["measured_label"],
                "provider_usage":        empty_usage(),
                "provider_usage_total_tokens": 0,
                "tool_calls_count":      0,
                "tool_accuracy":         [],
                "tool_accuracy_pct":     None,
                "tool_choice_status":    choice_status,
                "tool_choice_used_preview": used_preview,
                "tool_choice_expected_preview": expected_preview,
                "wrong_tool_calls":      0,
                "unnecessary_tool_calls": 0,
                "disallowed_tool_calls": 0,
                "tool_selection_precision": 0.0,
                "vram_before_mb":        vram_before,
                "vram_after_mb":         vram_after,
                "error":                 turn_error,
                "retry_errors":          retry_errors,
            }
            results["turns"].append(turn_data)
            results["aggregate"]["error_turns"] += 1
            results["aggregate"]["execution_failures"] += 1
            results["aggregate"]["retry_events"] += len(retry_errors)
            results["aggregate"]["peak_context_tokens_estimate"] = max(
                results["aggregate"]["peak_context_tokens_estimate"],
                ctx_approx,
            )
            results["aggregate"]["peak_context_tokens_heuristic"] = max(
                results["aggregate"]["peak_context_tokens_heuristic"],
                ctx_approx,
            )
            if ctx_counts["tokenizer"] is not None:
                results["aggregate"]["peak_context_tokens_tokenizer"] = max(
                    results["aggregate"]["peak_context_tokens_tokenizer"],
                    int(ctx_counts["tokenizer"]),
                )
            if ctx_counts["measured"] is not None:
                prev = results["aggregate"]["peak_context_tokens_measured"]
                results["aggregate"]["peak_context_tokens_measured"] = max(
                    prev if prev is not None else 0,
                    int(ctx_counts["measured"]),
                )
            print(
                f"  Turn {turn_idx + 1:02d} | "
                f"tps=0.0  ttft=n/a  tok=0  tools=0  acc=N/A%  "
                f"choice={choice_status}  "
                f"{used_preview}  {expected_preview}  "
                f"vram={vram_after}  error={turn_error}"
            )
            continue

        if result["tool_calls"]:
            messages.append({
                "role":       "assistant",
                "content":    result["content"] or "",
                "tool_calls": [
                    {
                        "id":       tc.get("id", f"tc_{turn_idx}_{i}"),
                        "type":     "function",
                        "function": tc["function"]
                    }
                    for i, tc in enumerate(result["tool_calls"])
                ]
            })
            messages.extend(tool_results)
        else:
            messages.append({"role": "assistant", "content": result["content"] or ""})

        acc_pct = (
            round(100 * sum(1 for t in tool_accuracy if t["valid"]) / len(tool_accuracy), 1)
            if tool_accuracy else None
        )
        invalid_tool_entries = sum(1 for entry in tool_accuracy if not entry["valid"])
        wrong_tool_calls = sum(
            1
            for entry in tool_accuracy
            if entry["valid"] and entry["tool"] not in expected_tools and entry["tool"] in ACTIVE_TOOL_NAMES
        )
        unnecessary_tool_calls = 0
        repeated_bad_tool_calls = 0
        for entry in tool_accuracy:
            signature = entry.get("signature")
            if not signature:
                continue
            if signature in prior_tool_signatures:
                unnecessary_tool_calls += 1
                if entry["tool"] not in expected_tools or entry["tool"] not in ACTIVE_TOOL_NAMES:
                    repeated_bad_tool_calls += 1
            prior_tool_signatures.add(signature)
        disallowed_tool_calls = sum(
            1
            for entry in tool_accuracy
            if entry["tool"] not in ACTIVE_TOOL_NAMES
        )
        valid_tool_calls = sum(1 for entry in tool_accuracy if entry["valid"])
        selection_denominator = valid_tool_calls + disallowed_tool_calls
        tool_selection_precision = (
            round(
                max(0.0, (selection_denominator - wrong_tool_calls - disallowed_tool_calls) / selection_denominator),
                3,
            )
            if selection_denominator
            else 1.0
        )
        choice_status, used_preview, expected_preview = summarize_tool_choice(
            [tc["function"]["name"] for tc in result["tool_calls"]],
            expected_tools,
            wrong_tool_calls,
            disallowed_tool_calls,
        )
        if invalid_tool_entries:
            results["aggregate"]["invalid_tool_call_turns"] += 1
            results["aggregate"]["tool_validation_failures"] += invalid_tool_entries
            results["aggregate"]["synthetic_tool_results"] += len(result["tool_calls"])
            results["aggregate"]["error_turns"] += 1
            turn_error = next(
                (entry["error"] for entry in tool_accuracy if not entry["valid"] and entry.get("error")),
                "invalid tool call",
            )
        results["aggregate"]["wrong_tool_calls"] += wrong_tool_calls
        results["aggregate"]["unnecessary_tool_calls"] += unnecessary_tool_calls
        results["aggregate"]["disallowed_tool_calls"] += disallowed_tool_calls
        results["aggregate"]["repeated_bad_tool_calls"] += repeated_bad_tool_calls
        results["aggregate"]["retry_events"] += len(retry_errors)
        results["aggregate"]["provider_input_tokens"] += int(result["usage"].get("input_tokens", 0) or 0)
        results["aggregate"]["provider_output_tokens"] += int(result["usage"].get("output_tokens", 0) or 0)
        results["aggregate"]["provider_total_tokens"] += int(result["usage_total_tokens"])
        results["aggregate"]["peak_context_tokens_estimate"] = max(
            results["aggregate"]["peak_context_tokens_estimate"],
            int(result["context_tokens_estimate"]),
        )
        results["aggregate"]["peak_context_tokens_heuristic"] = max(
            results["aggregate"]["peak_context_tokens_heuristic"],
            int(result["context_tokens_heuristic"]),
        )
        if result["context_tokens_tokenizer"] is not None:
            results["aggregate"]["peak_context_tokens_tokenizer"] = max(
                results["aggregate"]["peak_context_tokens_tokenizer"],
                int(result["context_tokens_tokenizer"]),
            )
        if result["context_tokens_measured"] is not None:
            prev = results["aggregate"]["peak_context_tokens_measured"]
            results["aggregate"]["peak_context_tokens_measured"] = max(
                prev if prev is not None else 0,
                int(result["context_tokens_measured"]),
            )

        turn_data = {
            "turn":                  turn_idx + 1,
            "prompt":                prompt,
            "active_tools":          ACTIVE_TOOL_NAMES,
            "expected_tools":        expected_tools,
            "assistant_preview":     result["content"] or "",
            "tool_call_names":       [tc["function"]["name"] for tc in result["tool_calls"]],
            "tool_call_arguments":   [tc["function"]["arguments"] for tc in result["tool_calls"]],
            "ttft_ms":               result["ttft_ms"],
            "tokens_generated":      result["tokens"],
            "text_tokens_generated": result["text_tokens"],
            "tool_call_chunks":      result["tool_call_chunks"],
            "elapsed_s":             result["elapsed_s"],
            "tps":                   result["tps"],
            "context_tokens_approx": ctx_approx,
            "context_tokens_estimate": result["context_tokens_estimate"],
            "context_tokens_heuristic": result["context_tokens_heuristic"],
            "context_tokens_tokenizer": result["context_tokens_tokenizer"],
            "tokenizer_label": result["tokenizer_label"],
            "context_tokens_measured": result["context_tokens_measured"],
            "measured_label": result["measured_label"],
            "provider_usage":        result["usage"],
            "provider_usage_total_tokens": result["usage_total_tokens"],
            "tool_calls_count":      len(result["tool_calls"]),
            "tool_accuracy":         tool_accuracy,
            "tool_accuracy_pct":     acc_pct,
            "tool_choice_status":    choice_status,
            "tool_choice_used_preview": used_preview,
            "tool_choice_expected_preview": expected_preview,
            "wrong_tool_calls":      wrong_tool_calls,
            "unnecessary_tool_calls": unnecessary_tool_calls,
            "disallowed_tool_calls": disallowed_tool_calls,
            "repeated_bad_tool_calls": repeated_bad_tool_calls,
            "tool_selection_precision": tool_selection_precision,
            "vram_before_mb":        vram_before,
            "vram_after_mb":         vram_after,
            "error":                 turn_error,
            "retry_errors":          retry_errors,
        }

        results["turns"].append(turn_data)

        print(
            f"  Turn {turn_idx + 1:02d} | "
            f"tps={result['tps']:.1f}  "
            f"ttft={result['ttft_ms']}ms  "
            f"tok={result['tokens']}  "
            f"tools={len(result['tool_calls'])}  "
            f"acc={acc_pct if acc_pct is not None else 'N/A'}%  "
            f"choice={choice_status}  "
            f"{used_preview}  "
            f"{expected_preview}  "
            f"sel={tool_selection_precision:.2f}  "
            f"vram={vram_after}"
        )

    total_choice_calls = sum(
        max(
            0,
            turn.get("tool_calls_count", 0),
        )
        for turn in results["turns"]
    )
    wrong_or_disallowed = (
        results["aggregate"]["wrong_tool_calls"] + results["aggregate"]["disallowed_tool_calls"]
    )
    results["aggregate"]["tool_selection_precision"] = (
        round(max(0.0, (total_choice_calls - wrong_or_disallowed) / total_choice_calls), 3)
        if total_choice_calls
        else 1.0
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    tps_list = [t["tps"] for t in results["turns"] if t["tps"] > 0]
    if tps_list:
        t1  = tps_list[0]
        tn  = tps_list[-1]
        deg = round(100 * (tn - t1) / t1, 1) if t1 else 0
        print(
            f"\n  [{cache_label}] avg={sum(tps_list)/len(tps_list):.2f}  "
            f"t1={t1:.2f}  t{num_turns}={tn:.2f}  deg={deg:+.1f}%"
        )

    print_step(f"saved: {out_file.name}")
    return out_file

# ── INTERACTIVE SETUP ────────────────────────────────────────────────────────
def interactive_setup(scan_dir=None):
    print_header("ape configure benchmark")

    search_dir = Path(scan_dir) if scan_dir else Path.cwd()
    gguf_files = find_gguf_files(search_dir)

    if not gguf_files:
        print(f"\n  no .gguf found in: {search_dir}")
        choice = input("  ape look elsewhere? [y/n]: ").strip().lower()
        if choice == "y":
            while True:
                scan_path = input("  scan path: ").strip().strip('"')
                p = Path(scan_path)
                if p.is_dir():
                    gguf_files = find_gguf_files(p)
                    if gguf_files:
                        break
                    print("  no banana here either.")
                else:
                    print("  ape no find directory.")
        if not gguf_files:
            print("  no model. ape sad. exiting.")
            sys.exit(0)

    model_path = prompt_gguf_selection(gguf_files)

    # auto-detect server in cwd
    server_path = find_server(search_dir)
    if server_path:
        print(f"\n  ape found server: {server_path}")
        use_it = input("  use this? [y/n]: ").strip().lower()
        if use_it not in ("y", ""):
            server_path = None
    if not server_path:
        server_path = prompt_server_path()

    split_config = prompt_split_mode(detect_gpus())
    return model_path, server_path, split_config


def run_agentic_benchmark_pass(cache_label, model_path, output_dir, port, preset=None,
                               workflow_suite=DEFAULT_WORKFLOW_SUITE, session_mode=DEFAULT_SESSION_MODE,
                               max_turns=None, system_prompt=None, server_pid=None, split_config=None,
                               live_trace: bool = False, trace_prompts: str = "summary",
                               trace_style: str = "theater",
                               selected_workflow_ids=None):
    from gnuckle.agentic_runtime import run_agentic_episode
    from gnuckle.benchmark_scoring import aggregate_workflow_runs, assign_type, finalize_benchmark_summary
    from gnuckle.workflow_loader import load_workflow_suite

    workflows = load_workflow_suite(workflow_suite)
    if selected_workflow_ids is not None:
        workflows = [wf for wf in workflows if wf.workflow_id in selected_workflow_ids]
    if not workflows:
        raise ValueError(f"workflow suite has no workflows: {workflow_suite}")
    observer = make_agentic_observer(show_prompts=trace_prompts, style=trace_style) if live_trace else None

    def run_group(group, label):
        summaries = []
        for wf_index, workflow in enumerate(group, 1):
            run_count = workflow.run_count
            print_step(f"{label} workflow {wf_index}/{len(group)}: {workflow.workflow_id} ({workflow.title})")
            print(f"  Layer  : {workflow.benchmark_layer}" + (f" [{workflow.profile_id}]" if workflow.profile_id else ""))
            print(f"  Scoring: {workflow.scoring_method}  runs: {run_count}  plaintext: {workflow.supports_plaintext_turns}")
            print(f"  Sampler: temp={workflow.sampler_config.get('temperature')} top_p={workflow.sampler_config.get('top_p')} top_k={workflow.sampler_config.get('top_k')} rp={workflow.sampler_config.get('repeat_penalty')}")
            if workflow.mid_task_injections:
                print(f"  Inject : {len(workflow.mid_task_injections)} mid-task injection(s)")
            if workflow.prompt_weight_variant:
                print(f"  Prompt : weight variant {workflow.prompt_weight_variant}")
            if workflow.denied_tools:
                print(f"  Denied : {', '.join(workflow.denied_tools)}")
            print_step(f"session: {session_mode}")

            episodes = []
            for run_num in range(1, run_count + 1):
                render_progress(
                    f"{label} {workflow.workflow_id} run {run_num}/{run_count}",
                    run_num - 1,
                    run_count,
                    done=False,
                )
                if run_count > 1:
                    print_step(f"run {run_num}/{run_count}")
                episode, _workspace_dir = run_agentic_episode(
                    base_url=DEFAULT_BASE_URL.format(port=port),
                    workflow=workflow,
                    output_dir=output_dir,
                    request_args=(preset or {}).get("request_args", {}),
                    session_mode=session_mode,
                    max_turns_override=max_turns,
                    system_prompt_override=system_prompt,
                    server_pid=server_pid,
                    context_window=get_context_window(preset),
                    observer=observer,
                    model_name=model_path.name,
                    cache_label=label,
                )
                print(
                    f"  Episode | status={episode['status']}  "
                    f"success={episode['task_completed']}  "
                    f"verify={episode['verification_passed']}  "
                    f"turns={episode['turns_used']}  "
                    f"tools={episode['tool_calls_used']}  "
                    f"ms={episode['performance']['wall_clock_ms']}"
                )
                episodes.append(episode)
                render_progress(
                    f"{label} {workflow.workflow_id} run {run_num}/{run_count}",
                    run_num,
                    run_count,
                    done=run_num == run_count,
                )
            summary = aggregate_workflow_runs(workflow, episodes)
            summaries.append(summary)
            print(
                f"  Score   | mean={summary['workflow_score_mean']:.3f}  "
                f"std={summary['workflow_score_stddev']:.3f}  runs={summary['run_count']}"
            )
        return summaries

    diagnostics = [workflow for workflow in workflows if workflow.benchmark_layer == "diagnostic"]
    non_diagnostics = [workflow for workflow in workflows if workflow.benchmark_layer != "diagnostic"]

    diagnostic_summaries = run_group(diagnostics, "diagnostic") if diagnostics else []
    benchmark_type = assign_type({item["workflow_id"]: item["workflow_score_mean"] for item in diagnostic_summaries})

    selected = []
    deferred_variants = []
    for workflow in non_diagnostics:
        if workflow.benchmark_layer == "diagnostic_variant":
            deferred_variants.append(workflow)
            continue
        if workflow.benchmark_layer == "core":
            selected.append(workflow)
            continue
        if workflow.benchmark_layer == "profile":
            if benchmark_type == "Type 0":
                continue
            if benchmark_type == "Type 1" and workflow.difficulty.lower() == "hard":
                continue
            selected.append(workflow)

    workflow_summaries = run_group(selected, "benchmark")
    core_summaries = [item for item in workflow_summaries if item["benchmark_layer"] == "core" and item["workflow_id"] != "cb_08_resource_viability"]
    core_score = (sum(item["workflow_score_mean"] for item in core_summaries) / len(core_summaries)) if core_summaries else 0.0
    if benchmark_type == "Type 2" and core_score > 0.85:
        benchmark_type = "Type 3"

    if benchmark_type == "Type 3" and deferred_variants:
        workflow_summaries.extend(run_group(deferred_variants, "stress"))

    summary = finalize_benchmark_summary(
        workflow_summaries=workflow_summaries,
        diagnostics=diagnostic_summaries,
        cache_label=cache_label,
        model_name=model_path.name,
        session_mode=session_mode,
        workflow_suite=workflow_suite,
        runtime_config={
            "split_config": split_config or {"split_mode": "layer", "main_gpu": 0, "tensor_split": None},
            "token_counting": token_counting_info(
                exact_available=probe_llamacpp_exact(DEFAULT_BASE_URL.format(port=port))
            ),
        },
        generated_at=datetime.now().isoformat(),
    )
    out_path = output_dir / f"agentic_{sanitize_label(cache_label)}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print_step(f"saved: {out_path.name}")
    return out_path


def _print_run_banner(benchmark_mode, model_path, server_path, output_path, preset,
                      cache_configs, num_turns, workflow_suite, session_mode, system_prompt,
                      system_prompt_source,
                      use_jinja, split_config=None, base_url=None):
    split_config = split_config or {}
    exact_available = probe_llamacpp_exact(base_url)
    print(f"\n  Mode   : {benchmark_mode}")
    print(f"  Model  : {model_path.name}")
    print(f"  Server : {server_path}")
    if benchmark_mode == "legacy":
        print(f"  Turns  : {num_turns} per cache type")
    else:
        print(f"  Turns  : {num_turns} max agent turns")
        print(f"  Suite  : {workflow_suite}")
        print(f"  Session: {session_mode}")
    print(f"  Runs   : {len(cache_configs)} ({', '.join(c['label'] for c in cache_configs)})")
    print(f"  Output : {output_path}{os.sep}")
    print(f"  Preset : {preset.get('name', 'default')} - {preset.get('description', '')}")
    print(f"  Jinja  : {'on' if use_jinja else 'off'}")
    print(f"  Split  : {split_config.get('split_mode', 'layer')} (main-gpu={split_config.get('main_gpu', 0)})")
    counting = token_counting_info(exact_available=exact_available)
    tertiary = f"; {counting['tertiary_method']}" if counting.get("tertiary_method") else ""
    print(f"  Tokens : {counting['status']} ({counting['primary_method']}; {counting['secondary_method']}{tertiary})")
    if system_prompt:
        prompt_counts = prompt_token_counts(system_prompt, base_url=base_url)
        measured_str = str(prompt_counts["measured"]) if prompt_counts["measured"] is not None else "unavailable"
        print(
            f"  System : {system_prompt_source} "
            f"({prompt_counts['heuristic']} ours · "
            f"{prompt_counts['tokenizer'] if prompt_counts['tokenizer'] is not None else 'unavailable'} {prompt_counts['tokenizer_label']} · "
            f"{measured_str} {prompt_counts['measured_label']})"
        )
    ape_print("loading")
    print()


def _print_profile_card(preset, split_config=None):
    """Display the sampler profile card for user review before benchmark."""
    sa = preset.get("server_args", {})
    ra = preset.get("request_args", {})
    sources = preset.get("source", [])
    notes = preset.get("notes", "")
    sc = split_config or {}

    print("  ┌─────────────────────────────────────────────────┐")
    print(f"  │  Profile Card: {preset.get('name', 'default'):<33}│")
    print(f"  │  {preset.get('description', ''):<48}│")
    print("  ├─────────────────────────────────────────────────┤")
    print(f"  │  server_args                                   │")
    print(f"  │    temp           : {str(sa.get('temp', '—')):<27}│")
    print(f"  │    top_p          : {str(sa.get('top_p', '—')):<27}│")
    print(f"  │    top_k          : {str(sa.get('top_k', '—')):<27}│")
    print(f"  │    repeat_penalty : {str(sa.get('repeat_penalty', '—')):<27}│")
    print(f"  │    repeat_last_n  : {str(sa.get('repeat_last_n', '—')):<27}│")
    print(f"  │    min_p          : {str(sa.get('min_p', '—')):<27}│")
    print("  ├─────────────────────────────────────────────────┤")
    print(f"  │  request_args                                  │")
    print(f"  │    temperature    : {str(ra.get('temperature', '—')):<27}│")
    print(f"  │    top_p          : {str(ra.get('top_p', '—')):<27}│")
    print("  ├─────────────────────────────────────────────────┤")
    print(f"  │  gpu                                           │")
    print(f"  │    main_gpu       : {str(sc.get('main_gpu', 0)):<27}│")
    print(f"  │    split_mode     : {str(sc.get('split_mode', 'layer')):<27}│")
    print("  ├─────────────────────────────────────────────────┤")
    for src in sources[:3]:
        truncated = (src[:45] + "...") if len(src) > 48 else src
        print(f"  │  {truncated:<48}│")
    if notes:
        print("  ├─────────────────────────────────────────────────┤")
        # Wrap notes to fit the card
        words = notes.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 46:
                print(f"  │  {line:<48}│")
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            print(f"  │  {line:<48}│")
    print("  └─────────────────────────────────────────────────┘")
    print()


def _prompt_profile_confirmation(preset, split_config):
    """Show profile card and prompt user to proceed or edit values.

    Returns the (possibly modified) preset and split_config.
    """
    _print_profile_card(preset, split_config)

    if not _is_interactive_terminal():
        return preset, split_config

    while True:
        answer = input("  Proceed without making any changes? (y/n): ").strip().lower()
        if answer in ("y", "yes", ""):
            return preset, split_config
        if answer in ("n", "no"):
            break
        print("  Please enter y or n.")

    print()
    print("  Enter new values (press Enter to keep current):")
    sa = preset.get("server_args", {})
    ra = preset.get("request_args", {})

    edits = [
        ("temp",           sa, float),
        ("top_p",          sa, float),
        ("top_k",          sa, int),
        ("repeat_penalty", sa, float),
        ("repeat_last_n",  sa, int),
        ("min_p",          sa, float),
    ]
    for key, target, cast in edits:
        current = target.get(key, "")
        raw = input(f"    {key:<18} [{current}]: ").strip()
        if raw:
            try:
                target[key] = cast(raw)
            except ValueError:
                print(f"    invalid value, keeping {current}")

    # GPU settings
    current_gpu = split_config.get("main_gpu", 0)
    raw = input(f"    {'main_gpu':<18} [{current_gpu}]: ").strip()
    if raw:
        try:
            split_config["main_gpu"] = int(raw)
        except ValueError:
            print(f"    invalid value, keeping {current_gpu}")

    # Sync request_args with server_args
    ra["temperature"] = sa.get("temp", ra.get("temperature"))
    ra["top_p"] = sa.get("top_p", ra.get("top_p"))

    print()
    _print_profile_card(preset, split_config)
    return preset, split_config


# ── WORKFLOW SELECTION ───────────────────────────────────────────────────────

def _prompt_workflow_selection(workflow_suite):
    """Interactive workflow picker. Returns list of selected workflow IDs or None (= run all)."""
    from gnuckle.workflow_loader import load_workflow_suite

    workflows = load_workflow_suite(workflow_suite)
    if not workflows:
        return None

    # Group by benchmark_layer
    layers = {}
    for wf in workflows:
        layers.setdefault(wf.benchmark_layer, []).append(wf)

    layer_order = ["diagnostic", "core", "profile", "diagnostic_variant"]
    sorted_layers = sorted(layers.keys(), key=lambda l: layer_order.index(l) if l in layer_order else 99)

    # Build flat indexed list
    indexed = []
    for layer in sorted_layers:
        for wf in layers[layer]:
            indexed.append(wf)

    selected = set(range(len(indexed)))  # all selected by default

    def _render_menu():
        print()
        print("  ┌─────────────────────────────────────────────────────────────────────┐")
        print(f"  │  Workflow Selection ({len(selected)}/{len(indexed)} selected)"
              f"{' ' * max(0, 37 - len(str(len(selected))) - len(str(len(indexed))))}│")
        print("  ├─────────────────────────────────────────────────────────────────────┤")
        current_layer = None
        for i, wf in enumerate(indexed):
            if wf.benchmark_layer != current_layer:
                current_layer = wf.benchmark_layer
                print(f"  │  [{current_layer}]"
                      f"{' ' * max(0, 60 - len(current_layer))}│")
            marker = "x" if i in selected else " "
            diff = wf.difficulty[0].upper() if wf.difficulty else " "
            line = f"{i + 1:>3}) [{marker}] {diff} {wf.title}"
            print(f"  │  {line:<66}│")
        print("  └─────────────────────────────────────────────────────────────────────┘")
        print()

    _render_menu()

    print("  Commands: number to toggle, 'all', 'none', layer name (e.g. 'core'),")
    print("           range (e.g. '3-7'), 'go' or Enter to proceed")
    print()

    while True:
        raw = input("  >> ").strip().lower()
        if raw in ("", "go", "g", "y"):
            break

        if raw == "all":
            selected = set(range(len(indexed)))
            _render_menu()
            continue
        if raw == "none":
            selected.clear()
            _render_menu()
            continue

        # Toggle by layer name
        matched_layer = False
        for layer in sorted_layers:
            if raw == layer or raw == layer.replace("_", " ") or raw == layer.replace("_", "-"):
                layer_indices = [i for i, wf in enumerate(indexed) if wf.benchmark_layer == layer]
                if all(i in selected for i in layer_indices):
                    selected -= set(layer_indices)
                else:
                    selected |= set(layer_indices)
                matched_layer = True
                break
        if matched_layer:
            _render_menu()
            continue

        # Range (e.g. "3-7")
        if "-" in raw:
            parts = raw.split("-", 1)
            try:
                start, end = int(parts[0]) - 1, int(parts[1]) - 1
                rng = set(range(start, end + 1)) & set(range(len(indexed)))
                if all(i in selected for i in rng):
                    selected -= rng
                else:
                    selected |= rng
                _render_menu()
                continue
            except ValueError:
                pass

        # Single number or comma-separated
        nums = [n.strip() for n in raw.split(",")]
        toggled = False
        for n in nums:
            try:
                idx = int(n) - 1
                if 0 <= idx < len(indexed):
                    if idx in selected:
                        selected.discard(idx)
                    else:
                        selected.add(idx)
                    toggled = True
            except ValueError:
                pass
        if toggled:
            _render_menu()
        else:
            print("  unrecognized input. try a number, range, layer name, 'all', 'none', or 'go'.")

    if not selected:
        print("  no workflows selected. ape confused. running all.")
        return None

    if len(selected) == len(indexed):
        return None  # all selected, no filter needed

    return [indexed[i].workflow_id for i in sorted(selected)]


def _prompt_session_benchmark_selection() -> list[dict]:
    """Interactive session benchmark picker. Returns list of selected benchmark dicts."""
    from gnuckle.session_runner import discover_benchmarks

    benchmarks = discover_benchmarks()
    if not benchmarks:
        return []

    print()
    print("  ┌─────────────────────────────────────────────────────────────────────┐")
    print(f"  │  Session Benchmarks ({len(benchmarks)} available)"
          f"{' ' * max(0, 43 - len(str(len(benchmarks))))}│")
    print("  ├─────────────────────────────────────────────────────────────────────┤")
    for i, bench in enumerate(benchmarks):
        tags = ", ".join(bench.get("tags", [])[:3])
        turns = len(bench.get("turns", []))
        line = f"{i + 1:>3}) {bench['title']} ({turns}t) [{tags}]"
        print(f"  │  {line:<66}│")
        desc = bench.get("description", "")
        if desc:
            truncated = (desc[:63] + "...") if len(desc) > 66 else desc
            print(f"  │       {truncated:<62}│")
    print("  └─────────────────────────────────────────────────────────────────────┘")
    print()
    print("  Enter numbers to select (comma-separated), 'all', or Enter to skip:")

    raw = input("  >> ").strip().lower()
    if not raw:
        return []
    if raw == "all":
        return benchmarks

    selected = []
    for n in raw.split(","):
        try:
            idx = int(n.strip()) - 1
            if 0 <= idx < len(benchmarks):
                selected.append(benchmarks[idx])
        except ValueError:
            pass
    return selected


# ── FULL BENCHMARK ORCHESTRATOR ──────────────────────────────────────────────
def run_full_benchmark(benchmark_mode=None, model_path=None, server_path=None, scan_dir=None,
                       output_dir=None, num_turns=None, port=None, profile_path=None,
                       workflow_suite=None, session_mode=None, use_jinja=True,
                       live_trace: bool = False, trace_prompts: str = "summary",
                       trace_style: str = "theater",
                       selected_workflow_ids=None, session_bench_ids=None):
    profile = {}
    if profile_path:
        profile = load_profile(profile_path)

    if profile:
        benchmark_mode = benchmark_mode or profile.get("benchmark_mode")
        model_path = model_path or profile.get("model_path")
        server_path = server_path or profile.get("server_path")
        scan_dir = scan_dir or profile.get("scan_dir")
        output_dir = output_dir or profile.get("output_dir")
        num_turns = num_turns if num_turns is not None else profile.get("num_turns")
        port = port if port is not None else profile.get("port")
        workflow_suite = workflow_suite or profile.get("workflow_suite")
        session_mode = session_mode or profile.get("session_mode")
        split_config = profile.get("split_config")
        if profile.get("use_jinja") is not None:
            use_jinja = bool(profile.get("use_jinja"))
        profile_preset = profile.get("sampler_preset")
        sampler_overrides = profile.get("sampler")
        cache_labels = profile.get("cache_types")
        system_prompt = profile.get("system_prompt")
        system_prompt_source = "profile_custom" if system_prompt else None
    else:
        benchmark_mode = benchmark_mode or DEFAULT_BENCHMARK_MODE
        profile_preset = None
        sampler_overrides = None
        cache_labels = None
        system_prompt = None
        system_prompt_source = None
        split_config = None

    benchmark_mode = benchmark_mode or DEFAULT_BENCHMARK_MODE
    workflow_suite = workflow_suite or DEFAULT_WORKFLOW_SUITE
    session_mode = session_mode or DEFAULT_SESSION_MODE
    num_turns = num_turns if num_turns is not None else DEFAULT_TURNS
    port = port if port is not None else DEFAULT_PORT
    base_output_path = Path(output_dir) if output_dir else Path.cwd() / "benchmark_results"

    if model_path:
        model_path = Path(model_path)
    if server_path:
        server_path = Path(server_path)

    if not model_path or not server_path:
        m, s, interactive_split_config = interactive_setup(scan_dir)
        model_path  = model_path or m
        server_path = server_path or s
        split_config = split_config or interactive_split_config

    if split_config is None:
        gpus = detect_gpus()
        if len(gpus) > 1:
            split_config = prompt_split_mode(gpus)

    split_config = split_config or {
        "split_mode": "layer",
        "main_gpu": 0,
        "tensor_split": None,
    }

    output_path = create_run_output_dir(base_output_path, benchmark_mode, model_path)

    preset = select_preset(model_path, preset_name=profile_preset, sampler_overrides=sampler_overrides)
    cache_configs = get_cache_configs(cache_labels)
    if not cache_configs:
        cache_configs = CACHE_CONFIGS
    if not system_prompt:
        system_prompt, system_prompt_source = default_system_prompt_for_mode(benchmark_mode)
    system_prompt_source = system_prompt_source or "custom_inline"

    _print_run_banner(
        benchmark_mode=benchmark_mode,
        model_path=model_path,
        server_path=server_path,
        output_path=output_path,
        preset=preset,
        cache_configs=cache_configs,
        num_turns=num_turns,
        workflow_suite=workflow_suite,
        session_mode=session_mode,
        system_prompt=system_prompt,
        system_prompt_source=system_prompt_source,
        use_jinja=use_jinja,
        split_config=split_config,
        base_url=DEFAULT_BASE_URL.format(port=port),
    )

    if _is_interactive_terminal():
        preset, split_config = _prompt_profile_confirmation(preset, split_config)

    # Workflow selection (agentic mode only)
    if selected_workflow_ids is None and benchmark_mode == "agentic" and _is_interactive_terminal():
        selected_workflow_ids = _prompt_workflow_selection(workflow_suite)

    # Session benchmark selection
    selected_session_benchmarks = []
    if session_bench_ids is not None:
        from gnuckle.session_runner import load_benchmark
        for bid in session_bench_ids:
            selected_session_benchmarks.append(load_benchmark(bid))
    elif benchmark_mode in ("agentic", "session") and _is_interactive_terminal():
        selected_session_benchmarks = _prompt_session_benchmark_selection()

    if benchmark_mode == "session" and not selected_session_benchmarks:
        print("  no session benchmarks selected. nothing to run.")
        return

    output_files = []
    server_proc  = None
    benchmark_started = time.perf_counter()

    try:
        for i, cfg in enumerate(cache_configs):
            label   = cfg["label"]
            cache_k = cfg["cache_k"]
            cache_v = cfg["cache_v"]
            throughput_benchmark = {}

            render_progress(f"cache run {i + 1}/{len(cache_configs)} ({label})", i, len(cache_configs), done=False)
            print_header(f"Run {i+1}/{len(cache_configs)}: {label}  (cache-k={cache_k} cache-v={cache_v})")

            kill_server(server_proc)
            server_proc = start_server(
                server_path,
                model_path,
                cache_k,
                cache_v,
                port,
                preset=preset,
                use_jinja=use_jinja,
                split_config=split_config,
            )

            if not wait_for_server(port):
                print(f"  ERROR: server no wake up for {label}. ape skip.")
                ape_print("error")
                kill_server(server_proc)
                continue

            if not warmup_server(port, preset=preset, system_prompt=system_prompt):
                print(f"  ERROR: model no finish preload for {label}. ape skip.")
                ape_print("error")
                kill_server(server_proc)
                continue

            throughput_benchmark = collect_llama_bench_metrics(
                server_path=server_path,
                model_path=model_path,
                cache_k=cache_k,
                cache_v=cache_v,
                preset=preset,
                split_config=split_config,
            )
            if throughput_benchmark.get("available"):
                print_step(
                    "llama-bench: "
                    f"prompt={throughput_benchmark.get('prompt_tokens_per_second')} t/s "
                    f"gen={throughput_benchmark.get('generation_tokens_per_second')} t/s"
                )
            else:
                print_step(
                    "llama-bench unavailable: "
                    f"{throughput_benchmark.get('error', 'unknown error')}"
                )

            out = None
            try:
                if benchmark_mode == "agentic":
                    out = run_agentic_benchmark_pass(
                        label,
                        model_path,
                        output_path,
                        port,
                        preset=preset,
                        workflow_suite=workflow_suite,
                        session_mode=session_mode,
                        max_turns=num_turns,
                        system_prompt=system_prompt,
                        server_pid=getattr(server_proc, "pid", None),
                        split_config=split_config,
                        live_trace=live_trace,
                        trace_prompts=trace_prompts,
                        trace_style=trace_style,
                        selected_workflow_ids=selected_workflow_ids,
                    )

                    # Run selected session benchmarks after workflow pass
                    if selected_session_benchmarks:
                        from gnuckle.session_runner import run_session_benchmark
                        base_url = DEFAULT_BASE_URL.format(port=port)
                        for bench in selected_session_benchmarks:
                            try:
                                session_observer = make_agentic_observer(
                                    show_prompts=trace_prompts,
                                    style=trace_style,
                                ) if live_trace else None
                                session_out = run_session_benchmark(
                                    bench,
                                    base_url=base_url,
                                    request_args=preset.get("request_args", {}),
                                    output_dir=output_path,
                                    server_pid=getattr(server_proc, "pid", None),
                                    context_window=get_context_window(preset),
                                    observer=session_observer,
                                    model_name=model_path.name,
                                    cache_label=label,
                                )
                                # Save with cache label
                                session_path = output_path / f"session_{bench['id']}_{sanitize_label(label)}.json"
                                session_out["meta"]["cache_label"] = label
                                session_out["meta"]["throughput_benchmark"] = throughput_benchmark
                                session_path.write_text(json.dumps(session_out, indent=2, default=str), encoding="utf-8")
                                print_step(f"session benchmark saved: {session_path.name}")
                            except Exception as se:
                                print(f"  ERROR during session benchmark [{bench['id']}]: {se}")
                                ape_print("error")
                elif benchmark_mode == "session":
                    # Session-only mode — no workflow pass, just session benchmarks
                    from gnuckle.session_runner import run_session_benchmark
                    base_url = DEFAULT_BASE_URL.format(port=port)
                    for bench in selected_session_benchmarks:
                        try:
                            session_observer = make_agentic_observer(
                                show_prompts=trace_prompts,
                                style=trace_style,
                            ) if live_trace else None
                            session_out = run_session_benchmark(
                                bench,
                                base_url=base_url,
                                request_args=preset.get("request_args", {}),
                                output_dir=output_path,
                                server_pid=getattr(server_proc, "pid", None),
                                context_window=get_context_window(preset),
                                observer=session_observer,
                                model_name=model_path.name,
                                cache_label=label,
                            )
                            session_out["meta"]["cache_label"] = label
                            session_out["meta"]["throughput_benchmark"] = throughput_benchmark
                            session_path = output_path / f"session_{bench['id']}_{sanitize_label(label)}.json"
                            session_path.write_text(json.dumps(session_out, indent=2, default=str), encoding="utf-8")
                            out = session_path
                            print_step(f"session benchmark saved: {session_path.name}")
                        except Exception as se:
                            print(f"  ERROR during session benchmark [{bench['id']}]: {se}")
                            ape_print("error")
                else:
                    out = run_benchmark_pass(
                        label,
                        model_path,
                        output_path,
                        num_turns,
                        port,
                        preset=preset,
                        system_prompt=system_prompt,
                        system_prompt_source=system_prompt_source,
                        split_config=split_config,
                        throughput_benchmark=throughput_benchmark,
                    )
                if out is not None:
                    output_files.append(out)
            except Exception as e:
                print(f"  ERROR during benchmark [{label}]: {e}")
                ape_print("error")
            finally:
                render_progress(f"cache run {i + 1}/{len(cache_configs)} ({label})", i + 1, len(cache_configs), done=i + 1 == len(cache_configs))

            kill_server(server_proc)
            server_proc = None

            if i < len(cache_configs) - 1:
                ape_wait(5, "cooldown")

    except KeyboardInterrupt:
        print("\n\n  ape interrupted. ape respect ctrl+c.")
    finally:
        kill_server(server_proc)

    print_header("all runs complete")
    ape_print("completion")
    print()
    for f in output_files:
        print(f"  {f.name}")
    print(f"\n  results in: {output_path}{os.sep}")
    elapsed_s = time.perf_counter() - benchmark_started
    if output_files:
        prompt_open_visualizer(output_path, elapsed_s)
    else:
        if benchmark_mode == "legacy":
            print(f"  next step: gnuckle visualize {output_path}{os.sep}")
        else:
            print("  next step: inspect the agentic run json. ape read trace carefully.")
    print()
