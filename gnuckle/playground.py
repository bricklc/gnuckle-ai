"""Interactive model playground for gnuckle."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from gnuckle.benchmark import (
    API_KEY,
    DEFAULT_BASE_URL,
    DEFAULT_PORT,
    MODEL,
    MOCK_RESPONSES,
    TOOLS,
    _is_interactive_terminal,
    ape_print,
    collect_llamacpp_server_metrics,
    estimate_context_token_counts,
    get_cache_configs,
    get_context_window,
    get_hardware_snapshot,
    kill_server,
    make_agentic_observer,
    print_header,
    print_step,
    sanitize_label,
    select_preset,
    start_server,
    empty_usage,
    update_usage,
    usage_total_tokens,
    wait_for_server,
    warmup_server,
)

PLAYGROUND_SYSTEM_PROMPT = (
    "You are in gnuckle playground mode. Chat naturally with the user. "
    "If pretend tools are available and useful, call them. Tool results are simulated, "
    "so never claim external side effects happened outside this local playground."
)


def playground_output_path(output_dir: str | Path | None, model_path: Path) -> Path:
    base = Path(output_dir) if output_dir else Path.cwd() / "playground_results"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base / f"playground_{sanitize_label(model_path.stem)}_{stamp}.json"


def pretend_tool_result(tool_name: str, arguments: dict | None = None) -> dict:
    raw = MOCK_RESPONSES.get(tool_name)
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"content": raw}
    else:
        payload = {"status": "ok", "tool": tool_name}
    payload.setdefault("pretend", True)
    payload.setdefault("tool", tool_name)
    payload.setdefault("arguments", arguments or {})
    return payload


def _stream_chat_completion(client: OpenAI, messages: list[dict], preset: dict, tools_enabled: bool) -> dict:
    request_args = preset.get("request_args", {})
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": request_args.get("temperature", 0.6),
        "top_p": request_args.get("top_p", 0.95),
        "max_tokens": request_args.get("max_tokens", 768),
    }
    if tools_enabled:
        kwargs["tools"] = TOOLS
        kwargs["tool_choice"] = "auto"

    t_send = time.perf_counter()
    first_token_t = None
    text_chunks = 0
    tool_chunks = 0
    content = ""
    tool_calls: dict[int, dict] = {}
    usage = empty_usage()

    for chunk in client.chat.completions.create(**kwargs):
        if getattr(chunk, "usage", None) is not None:
            usage = update_usage(usage, chunk.usage)
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = choices[0].delta
        if first_token_t is None:
            first_token_t = time.perf_counter()
        if getattr(delta, "content", None):
            text_chunks += 1
            content += delta.content
        for tool_delta in getattr(delta, "tool_calls", None) or []:
            idx = int(getattr(tool_delta, "index", 0) or 0)
            item = tool_calls.setdefault(
                idx,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if getattr(tool_delta, "id", None):
                item["id"] += tool_delta.id
            function = getattr(tool_delta, "function", None)
            if function is not None:
                if getattr(function, "name", None):
                    item["function"]["name"] += function.name
                if getattr(function, "arguments", None):
                    item["function"]["arguments"] += function.arguments
            tool_chunks += 1

    elapsed = time.perf_counter() - t_send
    ttft_ms = round((first_token_t - t_send) * 1000, 1) if first_token_t else None
    tokenish_chunks = text_chunks + tool_chunks
    return {
        "content": content,
        "tool_calls": list(tool_calls.values()),
        "ttft_ms": ttft_ms,
        "elapsed_s": round(elapsed, 3),
        "tokens": tokenish_chunks,
        "tps": round(tokenish_chunks / elapsed, 2) if elapsed > 0 and tokenish_chunks else 0.0,
        "usage": usage,
        "usage_total_tokens": usage_total_tokens(usage),
    }


def _context_payload(messages: list[dict], tools_enabled: bool, base_url: str, context_window: int | None) -> dict:
    counts = estimate_context_token_counts(messages, TOOLS if tools_enabled else None, base_url=base_url)
    context_tokens = int(counts["measured"]) if counts.get("measured") is not None else int(counts["heuristic"])
    payload = {
        "context_tokens_estimate": context_tokens,
        "context_tokens_heuristic": counts["heuristic"],
        "context_tokens_tokenizer": counts.get("tokenizer"),
        "tokenizer_label": counts.get("tokenizer_label"),
        "context_tokens_measured": counts.get("measured"),
        "measured_label": counts.get("measured_label"),
        "context_window": context_window,
    }
    if context_window:
        payload["context_percent_used"] = round((context_tokens / max(1, int(context_window))) * 100, 2)
    return payload


def _append_tool_result(messages: list[dict], tool_call: dict, observer, base_metrics: dict) -> dict:
    tool_name = ((tool_call.get("function") or {}).get("name") or "unknown_tool").strip()
    raw_args = (tool_call.get("function") or {}).get("arguments") or "{}"
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        args = {"_raw": raw_args, "_parse_error": True}
    tool_call_id = tool_call.get("id") or f"pretend_{tool_name}"
    observer("tool_call", {"tool_name": tool_name, "tool_call_id": tool_call_id, "arguments": args})
    result = pretend_tool_result(tool_name, args)
    observer(
        "tool_result",
        {
            **base_metrics,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "ok": True,
            "result": result,
        },
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": json.dumps(result, ensure_ascii=True),
        }
    )
    return {"tool_name": tool_name, "arguments": args, "result": result}


def run_playground(
    model_path: str | Path,
    server_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    port: int = DEFAULT_PORT,
    preset: dict | None = None,
    cache_label: str = "f16",
    pretend_tools: bool = False,
    use_jinja: bool = True,
    split_config: dict | None = None,
    observer=None,
) -> Path:
    if not _is_interactive_terminal():
        raise SystemExit("playground requires an interactive TTY")

    model_path = Path(model_path)
    server_path = Path(server_path)
    preset = preset or select_preset(model_path)
    split_config = split_config or {"split_mode": "layer", "main_gpu": 0, "tensor_split": None}
    cache = next((cfg for cfg in get_cache_configs([cache_label]) if cfg["label"] == cache_label), None)
    if cache is None:
        cache = get_cache_configs(["f16"])[0]

    out_path = playground_output_path(output_dir, model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base_url = DEFAULT_BASE_URL.format(port=port)
    context_window = get_context_window(preset)
    observer = observer or make_agentic_observer(show_prompts="summary", style="theater")
    messages: list[dict] = [{"role": "system", "content": PLAYGROUND_SYSTEM_PROMPT}]
    transcript = []
    server_proc = None

    print_header("Gnuckle Playground")
    print_step(f"model: {model_path.name}")
    print_step(f"pretend tools: {'on' if pretend_tools else 'off'}")

    try:
        server_proc = start_server(
            server_path,
            model_path,
            cache["cache_k"],
            cache["cache_v"],
            port,
            preset=preset,
            use_jinja=use_jinja,
            split_config=split_config,
        )
        if not wait_for_server(port):
            raise RuntimeError("server did not become ready")
        if not warmup_server(port, preset=preset, system_prompt=PLAYGROUND_SYSTEM_PROMPT):
            raise RuntimeError("model warmup failed")

        observer(
            "episode_start",
            {
                "workflow_id": "playground",
                "title": "Gnuckle Playground",
                "session_mode": "interactive_chat",
                "workspace": str(out_path.parent),
                "active_tools": [tool["function"]["name"] for tool in TOOLS] if pretend_tools else [],
                "max_turns": 0,
                "model_name": model_path.name,
                "cache_label": cache["label"],
                "context_window": context_window,
                "user_event": "Type messages. Use /exit to finish. Pretend tools are simulated when enabled.",
            },
        )

        client = OpenAI(base_url=base_url, api_key=API_KEY)
        turn = 0
        while True:
            user_text = input("\nape playground > ").strip()
            if user_text.lower() in {"/exit", "/quit", "exit", "quit"}:
                break
            if not user_text:
                continue
            turn += 1
            observer("turn_start", {"turn": turn})
            messages.append({"role": "user", "content": user_text})
            context_payload = _context_payload(messages, pretend_tools, base_url, context_window)
            observer("model_request", {"attempt": 1, "prompt": user_text, **context_payload})

            turn_record = {"turn": turn, "user": user_text, "tool_results": []}
            for continuation in range(4):
                result = _stream_chat_completion(client, messages, preset, pretend_tools)
                metrics_payload = {
                    **_context_payload(messages, pretend_tools, base_url, context_window),
                    "latency_ms": round(result["elapsed_s"] * 1000, 1),
                    "ttft_ms": result["ttft_ms"],
                    "tokens_per_second": result["tps"],
                    "hardware_usage": get_hardware_snapshot(getattr(server_proc, "pid", None)),
                }
                assistant_message = {
                    "role": "assistant",
                    "content": result["content"] or "",
                }
                if result["tool_calls"]:
                    assistant_message["tool_calls"] = result["tool_calls"]
                messages.append(assistant_message)
                observer(
                    "assistant_action",
                    {
                        **metrics_payload,
                        "content": result["content"] or "",
                        "tool_calls": result["tool_calls"],
                    },
                )
                turn_record.setdefault("assistant", "")
                turn_record["assistant"] += result["content"] or ""
                turn_record["metrics"] = metrics_payload
                turn_record["usage_total_tokens"] = result["usage_total_tokens"]
                if not pretend_tools or not result["tool_calls"]:
                    break
                for tool_call in result["tool_calls"]:
                    turn_record["tool_results"].append(
                        _append_tool_result(messages, tool_call, observer, metrics_payload)
                    )
                observer("model_request", {"attempt": continuation + 2, "prompt": "tool results returned", **metrics_payload})
            transcript.append(turn_record)
            observer("turn_metrics", turn_record.get("metrics", {}))

        server_metrics = collect_llamacpp_server_metrics(server_proc)
        payload = {
            "meta": {
                "type": "playground",
                "timestamp": datetime.now().isoformat(),
                "model": model_path.name,
                "cache_label": cache["label"],
                "pretend_tools": pretend_tools,
                "sampler_preset": preset.get("name", "default"),
                "llamacpp_server_metrics": server_metrics,
            },
            "turns": transcript,
        }
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        observer("final_result", {"status": "saved", "output": str(out_path)})
        print_step(f"playground saved: {out_path}")
        return out_path
    finally:
        kill_server(server_proc)
        ape_print("done")
