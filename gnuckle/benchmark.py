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
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from openai import OpenAI

from gnuckle.ape import ape_print, ape_wait, ape_phrase
from gnuckle.profile import load_profile

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
SERVER_WAIT_S    = 60
WARMUP_WAIT_S    = 120
PRESETS_PATH     = Path(__file__).with_name("llama_presets.json")
DEFAULT_SYSTEM_PROMPT = (
    "You are a function-calling AI assistant. "
    "Always call the appropriate tool(s) before responding. "
    "Return tool calls as valid JSON."
)

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
                return True
            except Exception as exc:
                if not is_server_loading_error(exc):
                    pass
        if not poked and time.time() > deadline - timeout / 2:
            ape_print("loading")
            poked = True
        time.sleep(1)
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
                print("  >> warmup done. model answer received.")
                return True
        except Exception as exc:
            if not announced:
                print("  >> preloading model. wait for first real response...")
                announced = True
            if not is_server_loading_error(exc):
                print(f"  >> warmup retry after startup error: {exc}")
        time.sleep(2)
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

def start_server(server_path: Path, model_path: Path, cache_k: str, cache_v: str, port: int, preset=None):
    preset = preset or select_preset(model_path)
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
    cmd.extend(build_llama_args(preset.get("server_args", {})))
    print_step(f"starting server: cache-k={cache_k} cache-v={cache_v}")
    print_step(f"preset: {preset.get('name', 'default')}")
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
def call_with_metrics(client, messages, port, preset=None):
    preset = preset or load_presets()["default"]
    request_args = preset.get("request_args", {})
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
        temperature=request_args.get("temperature", 0.6),
        top_p=request_args.get("top_p", 0.95),
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
def run_benchmark_pass(cache_label, model_path, output_dir, num_turns, port, preset=None, system_prompt=None):
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
            "sampler_preset": preset.get("name", "default") if preset else "default",
            "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
        },
        "turns": []
    }

    messages = [
        {
            "role": "system",
            "content": system_prompt or DEFAULT_SYSTEM_PROMPT
        }
    ]

    vram_idle = get_vram_mb()
    print_step(f"VRAM idle: {vram_idle} MB")

    for turn_idx in range(num_turns):
        prompt = TURN_PROMPTS[turn_idx % len(TURN_PROMPTS)]
        messages.append({"role": "user", "content": prompt})
        ctx_approx = sum(len(m.get("content", "").split()) for m in messages)

        vram_before = get_vram_mb()
        result      = call_with_metrics(client, messages, port, preset=preset)
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
            "assistant_preview":     result["content"] or "",
            "tool_call_names":       [tc["function"]["name"] for tc in result["tool_calls"]],
            "tool_call_arguments":   [tc["function"]["arguments"] for tc in result["tool_calls"]],
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
                       output_dir=None, num_turns=None, port=None, profile_path=None):
    profile = {}
    if profile_path:
        profile = load_profile(profile_path)

    if profile:
        model_path = model_path or profile.get("model_path")
        server_path = server_path or profile.get("server_path")
        scan_dir = scan_dir or profile.get("scan_dir")
        output_dir = output_dir or profile.get("output_dir")
        num_turns = num_turns if num_turns is not None else profile.get("num_turns")
        port = port if port is not None else profile.get("port")
        profile_preset = profile.get("sampler_preset")
        sampler_overrides = profile.get("sampler")
        cache_labels = profile.get("cache_types")
        system_prompt = profile.get("system_prompt")
    else:
        profile_preset = None
        sampler_overrides = None
        cache_labels = None
        system_prompt = None

    num_turns = num_turns if num_turns is not None else DEFAULT_TURNS
    port = port if port is not None else DEFAULT_PORT
    output_path = Path(output_dir) if output_dir else Path.cwd() / "benchmark_results"

    if model_path:
        model_path = Path(model_path)
    if server_path:
        server_path = Path(server_path)

    if not model_path or not server_path:
        m, s = interactive_setup(scan_dir)
        model_path  = model_path or m
        server_path = server_path or s

    preset = select_preset(model_path, preset_name=profile_preset, sampler_overrides=sampler_overrides)
    cache_configs = get_cache_configs(cache_labels)
    if not cache_configs:
        cache_configs = CACHE_CONFIGS

    print(f"\n  Model  : {model_path.name}")
    print(f"  Server : {server_path}")
    print(f"  Turns  : {num_turns} per cache type")
    print(f"  Runs   : {len(cache_configs)} ({', '.join(c['label'] for c in cache_configs)})")
    print(f"  Output : {output_path}{os.sep}")
    print(f"  Preset : {preset.get('name', 'default')} - {preset.get('description', '')}")
    if system_prompt:
        print(f"  System : custom prompt loaded")
    ape_print("loading")
    print()

    confirm = input("  ape smash Enter to start [y/n]: ").strip().lower()
    if confirm not in ("y", ""):
        print("  ape walk away.")
        sys.exit(0)

    output_files = []
    server_proc  = None

    try:
        for i, cfg in enumerate(cache_configs):
            label   = cfg["label"]
            cache_k = cfg["cache_k"]
            cache_v = cfg["cache_v"]

            print_header(f"Run {i+1}/{len(cache_configs)}: {label}  (cache-k={cache_k} cache-v={cache_v})")

            kill_server(server_proc)
            server_proc = start_server(server_path, model_path, cache_k, cache_v, port, preset=preset)

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

            try:
                out = run_benchmark_pass(label, model_path, output_path, num_turns, port, preset=preset, system_prompt=system_prompt)
                output_files.append(out)
            except Exception as e:
                print(f"  ERROR during benchmark [{label}]: {e}")
                ape_print("error")

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
    print(f"  next step: gnuckle visualize {output_path}{os.sep}")
    print()
