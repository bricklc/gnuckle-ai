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
from pathlib import Path
from datetime import datetime
from openai import OpenAI

from gnuckle.ape import ape_print, ape_wait, ape_phrase

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
SERVER_WAIT_S    = 15

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

# ── HELPERS ───────────────────────────────────────────────────────────────────
def print_header(text):
    print(f"\n{'='*62}")
    print(f"  {text}")
    print(f"{'='*62}")

def print_step(text):
    print(f"  >> {text}")

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

def wait_for_server(port, timeout=SERVER_WAIT_S):
    ape_print("server_wait")
    deadline = time.time() + timeout
    poked = False
    while time.time() < deadline:
        if port_open(port):
            ape_print("server_up")
            time.sleep(1.5)
            return True
        if not poked and time.time() > deadline - timeout / 2:
            ape_print("loading")
            poked = True
        time.sleep(1)
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

def start_server(server_path: Path, model_path: Path, cache_k: str, cache_v: str, port: int):
    cmd = [
        str(server_path),
        "-m",               str(model_path),
        "--host",           "0.0.0.0",
        "--port",           str(port),
        "-ngl",             "99",
        "--split-mode",     "layer",
        "--main-gpu",       "0",
        "--ctx-size",       "131072",
        "--cache-type-k",   cache_k,
        "--cache-type-v",   cache_v,
        "--temp",           "0.6",
        "--top-p",          "0.95",
        "--top-k",          "20",
        "--repeat-penalty", "1.1",
    ]
    print_step(f"starting server: cache-k={cache_k} cache-v={cache_v}")
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

# ── STREAMING CALL ────────────────────────────────────────────────────────────
def call_with_metrics(client, messages, port):
    t_send        = time.perf_counter()
    first_token_t = None
    token_count   = 0
    full_content  = ""
    tc_accum      = {}

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        stream=True,
        temperature=0.6,
        top_p=0.95,
        max_tokens=512
    )

    for chunk in stream:
        if first_token_t is None:
            first_token_t = time.perf_counter()
        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            continue
        if delta.content:
            full_content += delta.content
            token_count  += 1
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tc_accum:
                    tc_accum[idx] = {"id": tc.id or "", "function": {"name": "", "arguments": ""}}
                if tc.function:
                    if tc.function.name:
                        tc_accum[idx]["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        tc_accum[idx]["function"]["arguments"] += tc.function.arguments

    t_end   = time.perf_counter()
    ttft    = round((first_token_t - t_send) * 1000, 1) if first_token_t else None
    elapsed = t_end - t_send
    tps     = round(token_count / elapsed, 2) if elapsed > 0 and token_count > 0 else 0.0

    return {
        "content":    full_content,
        "tool_calls": list(tc_accum.values()),
        "ttft_ms":    ttft,
        "tokens":     token_count,
        "elapsed_s":  round(elapsed, 3),
        "tps":        tps
    }

# ── SINGLE CACHE-TYPE RUN ─────────────────────────────────────────────────────
def run_benchmark_pass(cache_label, model_path, output_dir, num_turns, port):
    base_url = DEFAULT_BASE_URL.format(port=port)
    client   = OpenAI(base_url=base_url, api_key=API_KEY)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"benchmark_{cache_label}_{ts}.json"

    results = {
        "meta": {
            "cache_label": cache_label,
            "model":       model_path.name,
            "num_turns":   num_turns,
            "timestamp":   datetime.now().isoformat(),
        },
        "turns": []
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a function-calling AI assistant. "
                "Always call the appropriate tool(s) before responding. "
                "Return tool calls as valid JSON."
            )
        }
    ]

    vram_idle = get_vram_mb()
    print_step(f"VRAM idle: {vram_idle} MB")

    for turn_idx in range(num_turns):
        prompt = TURN_PROMPTS[turn_idx % len(TURN_PROMPTS)]
        messages.append({"role": "user", "content": prompt})
        ctx_approx = sum(len(m.get("content", "").split()) for m in messages)

        vram_before = get_vram_mb()
        result      = call_with_metrics(client, messages, port)
        vram_after  = get_vram_mb()

        tool_accuracy = []
        tool_results  = []

        if result["tool_calls"]:
            for tc in result["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args     = json.loads(tc["function"]["arguments"])
                    required = next(
                        (t["function"]["parameters"].get("required", [])
                         for t in TOOLS if t["function"]["name"] == name), []
                    )
                    missing = [r for r in required if r not in args]
                    valid   = len(missing) == 0
                    error   = f"missing: {missing}" if missing else None
                except json.JSONDecodeError as e:
                    valid = False
                    error = str(e)

                tool_accuracy.append({"tool": name, "valid": valid, "error": error})
                tool_results.append({
                    "role":         "tool",
                    "tool_call_id": tc.get("id", f"tc_{turn_idx}"),
                    "content":      MOCK_RESPONSES.get(name, '{"status":"ok"}')
                })

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

        turn_data = {
            "turn":                  turn_idx + 1,
            "prompt":                prompt,
            "ttft_ms":               result["ttft_ms"],
            "tokens_generated":      result["tokens"],
            "elapsed_s":             result["elapsed_s"],
            "tps":                   result["tps"],
            "context_tokens_approx": ctx_approx,
            "tool_calls_count":      len(result["tool_calls"]),
            "tool_accuracy":         tool_accuracy,
            "tool_accuracy_pct":     acc_pct,
            "vram_before_mb":        vram_before,
            "vram_after_mb":         vram_after,
        }

        results["turns"].append(turn_data)

        print(
            f"  Turn {turn_idx + 1:02d} | "
            f"tps={result['tps']:.1f}  "
            f"ttft={result['ttft_ms']}ms  "
            f"tok={result['tokens']}  "
            f"tools={len(result['tool_calls'])}  "
            f"acc={acc_pct if acc_pct is not None else 'N/A'}%  "
            f"vram={vram_after}"
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

    return model_path, server_path

# ── FULL BENCHMARK ORCHESTRATOR ──────────────────────────────────────────────
def run_full_benchmark(model_path=None, server_path=None, scan_dir=None,
                       output_dir=None, num_turns=DEFAULT_TURNS, port=DEFAULT_PORT):
    output_path = Path(output_dir) if output_dir else Path.cwd() / "benchmark_results"

    if model_path:
        model_path = Path(model_path)
    if server_path:
        server_path = Path(server_path)

    if not model_path or not server_path:
        m, s = interactive_setup(scan_dir)
        model_path  = model_path or m
        server_path = server_path or s

    print(f"\n  Model  : {model_path.name}")
    print(f"  Server : {server_path}")
    print(f"  Turns  : {num_turns} per cache type")
    print(f"  Runs   : {len(CACHE_CONFIGS)} ({', '.join(c['label'] for c in CACHE_CONFIGS)})")
    print(f"  Output : {output_path}{os.sep}")
    ape_print("loading")
    print()

    confirm = input("  ape smash Enter to start [y/n]: ").strip().lower()
    if confirm not in ("y", ""):
        print("  ape walk away.")
        sys.exit(0)

    output_files = []
    server_proc  = None

    try:
        for i, cfg in enumerate(CACHE_CONFIGS):
            label   = cfg["label"]
            cache_k = cfg["cache_k"]
            cache_v = cfg["cache_v"]

            print_header(f"Run {i+1}/{len(CACHE_CONFIGS)}: {label}  (cache-k={cache_k} cache-v={cache_v})")

            kill_server(server_proc)
            server_proc = start_server(server_path, model_path, cache_k, cache_v, port)

            if not wait_for_server(port):
                print(f"  ERROR: server no wake up for {label}. ape skip.")
                ape_print("error")
                kill_server(server_proc)
                continue

            try:
                out = run_benchmark_pass(label, model_path, output_path, num_turns, port)
                output_files.append(out)
            except Exception as e:
                print(f"  ERROR during benchmark [{label}]: {e}")
                ape_print("error")

            kill_server(server_proc)
            server_proc = None

            if i < len(CACHE_CONFIGS) - 1:
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
    print(f"  next step: gnuckle visualize {output_path}{os.sep}")
    print()
