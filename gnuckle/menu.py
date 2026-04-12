"""Interactive benchmark menu."""

from __future__ import annotations

import copy
from pathlib import Path

from gnuckle.bench_pack.registry import list_available_packs
from gnuckle.bench_pack.trust import benchmarks_dir
from gnuckle.benchmark import (
    DEFAULT_BENCHMARK_MODE,
    DEFAULT_PORT,
    DEFAULT_SESSION_MODE,
    DEFAULT_TURNS,
    DEFAULT_WORKFLOW_SUITE,
    _is_interactive_terminal,
    _prompt_session_benchmark_selection,
    _prompt_workflow_selection,
    find_bench,
    find_gguf_files,
    find_server,
    get_cache_configs,
    load_presets,
    run_full_benchmark,
    select_preset,
)
from gnuckle.profile import list_profiles, load_profile, profiles_dir, save_profile
from gnuckle.splash import print_splash


def render_banana_loading_bar(current: int, total: int = 5) -> str:
    current = max(0, min(int(current), int(total)))
    return "[" + ("🍌" * current) + ("·" * (total - current)) + "]"


def _prompt_choice(prompt: str, max_value: int, allow_blank: bool = False) -> int | None:
    while True:
        raw = input(prompt).strip()
        if not raw and allow_blank:
            return None
        try:
            value = int(raw)
        except ValueError:
            print("  enter a number.")
            continue
        if 1 <= value <= max_value:
            return value
        print("  out of range.")


def _auto_detect_server(model_path: Path | None, scan_dir: Path | None) -> Path | None:
    roots = []
    if model_path is not None:
        roots.append(model_path.parent)
    if scan_dir is not None:
        roots.append(scan_dir)
    roots.append(Path.cwd())
    seen = set()
    for root in roots:
        if root is None:
            continue
        resolved = str(root.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        found = find_server(root)
        if found:
            return found
    return None


def _pick_model(scan_dir: Path | None = None) -> Path | None:
    root = Path(scan_dir or Path.cwd())
    ggufs = find_gguf_files(root)
    if not ggufs:
        print(f"  no .gguf files found under {root}")
        return None
    print()
    print("  Models")
    for idx, path in enumerate(ggufs, start=1):
        print(f"  {idx:>2}. {path.name}")
    choice = _prompt_choice("  pick model: ", len(ggufs))
    return ggufs[(choice or 1) - 1]


def _pick_saved_profile() -> str | None:
    profiles = list_profiles()
    if not profiles:
        print("  no saved profiles found.")
        return None
    print()
    print("  Saved profiles")
    for idx, path in enumerate(profiles, start=1):
        print(f"  {idx:>2}. {path.stem}")
    choice = _prompt_choice("  pick profile: ", len(profiles), allow_blank=True)
    if choice is None:
        return None
    return str(profiles[choice - 1])


def _pick_sampler_preset(current_model: Path | None) -> str | None:
    presets_doc = load_presets()
    options = [presets_doc["default"]] + list(presets_doc.get("presets", []))
    print()
    print("  Sampler presets")
    for idx, preset in enumerate(options, start=1):
        marker = ""
        if current_model is not None and select_preset(current_model).get("name") == preset.get("name"):
            marker = " (auto)"
        print(f"  {idx:>2}. {preset.get('name')}{marker} - {preset.get('description', '')}")
    choice = _prompt_choice("  pick preset: ", len(options))
    return options[(choice or 1) - 1].get("name")


def _edit_sampler_values(state: dict) -> None:
    sampler = state.setdefault("sampler", {})
    current = {
        "temp": sampler.get("temp", 0.6),
        "top_p": sampler.get("top_p", 0.95),
        "top_k": sampler.get("top_k", 20),
        "repeat_penalty": sampler.get("repeat_penalty", 1.1),
        "repeat_last_n": sampler.get("repeat_last_n", 64),
        "min_p": sampler.get("min_p", 0.0),
    }
    print()
    print("  Sampler overrides (blank keeps current)")
    casts = {
        "temp": float,
        "top_p": float,
        "top_k": int,
        "repeat_penalty": float,
        "repeat_last_n": int,
        "min_p": float,
    }
    for key, cast in casts.items():
        raw = input(f"  {key} [{current[key]}]: ").strip()
        if not raw:
            continue
        try:
            sampler[key] = cast(raw)
        except ValueError:
            print(f"  invalid {key}, keeping {current[key]}")


def _pick_benchmark_mode() -> str:
    options = ["legacy", "agentic", "session"]
    print()
    print("  Benchmark mode")
    for idx, mode in enumerate(options, start=1):
        print(f"  {idx:>2}. {mode}")
    choice = _prompt_choice("  pick mode: ", len(options))
    return options[(choice or 1) - 1]


def _pick_cache_types() -> list[str]:
    options = ["f16", "q8_0", "q4_0", "turbo3"]
    selected = set(range(len(options)))
    while True:
        print()
        print("  Cache types")
        for idx, label in enumerate(options, start=1):
            marker = "x" if (idx - 1) in selected else " "
            print(f"  {idx:>2}. [{marker}] {label}")
        raw = input("  toggle numbers, 'all', 'done': ").strip().lower()
        if raw in {"done", ""}:
            break
        if raw == "all":
            selected = set(range(len(options)))
            continue
        for part in raw.split(","):
            try:
                idx = int(part.strip()) - 1
            except ValueError:
                continue
            if 0 <= idx < len(options):
                if idx in selected:
                    selected.remove(idx)
                else:
                    selected.add(idx)
        if not selected:
            selected = set(range(len(options)))
    return [options[idx] for idx in sorted(selected)]


def _pick_quality_packs() -> list[str]:
    installed = [path.name for path in benchmarks_dir().iterdir() if path.is_dir()] if benchmarks_dir().exists() else []
    available = list_available_packs()
    options = installed or [entry.get("id") for entry in available if entry.get("id")]
    options = [option for option in options if option]
    if not options:
        print("  no quality packs available yet.")
        return []
    selected = set(range(len(options)))
    while True:
        print()
        print("  Quality benchmarks")
        for idx, label in enumerate(options, start=1):
            marker = "x" if (idx - 1) in selected else " "
            print(f"  {idx:>2}. [{marker}] {label}")
        raw = input("  toggle numbers, 'none', 'done': ").strip().lower()
        if raw in {"done", ""}:
            break
        if raw == "none":
            selected.clear()
            break
        for part in raw.split(","):
            try:
                idx = int(part.strip()) - 1
            except ValueError:
                continue
            if 0 <= idx < len(options):
                if idx in selected:
                    selected.remove(idx)
                else:
                    selected.add(idx)
    return [options[idx] for idx in sorted(selected)]


def menu_state_to_profile(state: dict) -> dict:
    return {
        "benchmark_mode": state.get("mode"),
        "model_path": state.get("model_path"),
        "server_path": state.get("server_path"),
        "scan_dir": state.get("scan_dir"),
        "output_dir": state.get("output_dir"),
        "num_turns": state.get("turns"),
        "port": state.get("port"),
        "workflow_suite": state.get("workflow_suite"),
        "session_mode": state.get("session_mode"),
        "sampler_preset": state.get("sampler_preset"),
        "sampler": state.get("sampler"),
        "cache_types": state.get("cache_types"),
        "split_config": state.get("split_config"),
        "selected_workflow_ids": state.get("selected_workflow_ids"),
        "session_bench_ids": state.get("session_bench_ids"),
        "quality_bench_ids": state.get("quality_bench_ids"),
        "skip_quality": bool(state.get("skip_quality")),
        "use_jinja": bool(state.get("use_jinja", True)),
    }


def _apply_profile_to_state(state: dict, profile: dict) -> dict:
    updated = copy.deepcopy(state)
    updated["mode"] = profile.get("benchmark_mode", updated["mode"])
    updated["model_path"] = profile.get("model_path", updated["model_path"])
    updated["server_path"] = profile.get("server_path", updated["server_path"])
    updated["scan_dir"] = profile.get("scan_dir", updated["scan_dir"])
    updated["output_dir"] = profile.get("output_dir", updated["output_dir"])
    updated["turns"] = profile.get("num_turns", updated["turns"])
    updated["port"] = profile.get("port", updated["port"])
    updated["workflow_suite"] = profile.get("workflow_suite", updated["workflow_suite"])
    updated["session_mode"] = profile.get("session_mode", updated["session_mode"])
    updated["sampler_preset"] = profile.get("sampler_preset", updated["sampler_preset"])
    updated["sampler"] = profile.get("sampler", updated["sampler"])
    updated["cache_types"] = profile.get("cache_types", updated["cache_types"])
    updated["split_config"] = profile.get("split_config", updated["split_config"])
    updated["selected_workflow_ids"] = profile.get("selected_workflow_ids", updated["selected_workflow_ids"])
    updated["session_bench_ids"] = profile.get("session_bench_ids", updated["session_bench_ids"])
    updated["quality_bench_ids"] = profile.get("quality_bench_ids", updated["quality_bench_ids"])
    updated["skip_quality"] = profile.get("skip_quality", updated["skip_quality"])
    updated["use_jinja"] = profile.get("use_jinja", updated["use_jinja"])
    return updated


def default_menu_state() -> dict:
    return {
        "mode": DEFAULT_BENCHMARK_MODE,
        "model_path": None,
        "server_path": None,
        "scan_dir": str(Path.cwd()),
        "output_dir": None,
        "turns": DEFAULT_TURNS,
        "port": DEFAULT_PORT,
        "workflow_suite": DEFAULT_WORKFLOW_SUITE,
        "session_mode": DEFAULT_SESSION_MODE,
        "sampler_preset": None,
        "sampler": {},
        "cache_types": [cfg["label"] for cfg in get_cache_configs()],
        "split_config": {"main_gpu": 0, "split_mode": "layer", "tensor_split": None},
        "selected_workflow_ids": None,
        "session_bench_ids": None,
        "quality_bench_ids": [],
        "skip_quality": False,
        "use_jinja": True,
    }


def render_menu_summary(state: dict) -> str:
    model = Path(state["model_path"]).name if state.get("model_path") else "not selected"
    server = Path(state["server_path"]).name if state.get("server_path") else "auto"
    preset = state.get("sampler_preset") or "auto"
    quality = ",".join(state.get("quality_bench_ids") or []) or ("skip" if state.get("skip_quality") else "auto")
    return (
        f"mode={state['mode']} | model={model} | server={server} | preset={preset} | "
        f"cache={','.join(state['cache_types'])} | quality={quality}"
    )


def _save_preferences(state: dict) -> str:
    name = input("  save profile as: ").strip()
    if not name:
        raise ValueError("profile name cannot be empty")
    target = profiles_dir() / f"{name}.json"
    return save_profile(target, menu_state_to_profile(state))


def run_interactive_menu() -> None:
    if not _is_interactive_terminal():
        raise SystemExit("interactive menu requires a TTY")
    state = default_menu_state()
    while True:
        print()
        print("  Interactive Menu")
        print(f"  {render_menu_summary(state)}")
        print("   1. Select model")
        print("   2. Load saved profile")
        print("   3. Select sampler preset")
        print("   4. Edit temps / sampler overrides")
        print("   5. Select benchmarks")
        print("   6. Save preferences")
        print("   7. Run benchmark")
        print("   8. Exit")
        choice = _prompt_choice("  choose: ", 8)
        if choice == 1:
            model = _pick_model(Path(state["scan_dir"]) if state.get("scan_dir") else None)
            if model is not None:
                state["model_path"] = str(model)
                auto_server = _auto_detect_server(model, Path(state["scan_dir"]) if state.get("scan_dir") else None)
                if auto_server is not None:
                    state["server_path"] = str(auto_server)
        elif choice == 2:
            picked = _pick_saved_profile()
            if picked:
                state = _apply_profile_to_state(state, load_profile(picked))
        elif choice == 3:
            if not state.get("model_path"):
                print("  pick a model first.")
                continue
            state["sampler_preset"] = _pick_sampler_preset(Path(state["model_path"]))
        elif choice == 4:
            _edit_sampler_values(state)
        elif choice == 5:
            state["mode"] = _pick_benchmark_mode()
            state["cache_types"] = _pick_cache_types()
            state["quality_bench_ids"] = _pick_quality_packs()
            state["skip_quality"] = not bool(state["quality_bench_ids"])
            if state["mode"] == "agentic":
                state["selected_workflow_ids"] = _prompt_workflow_selection(state["workflow_suite"])
                session_benches = _prompt_session_benchmark_selection()
                state["session_bench_ids"] = [bench["id"] for bench in session_benches] if session_benches else None
            elif state["mode"] == "session":
                session_benches = _prompt_session_benchmark_selection()
                state["session_bench_ids"] = [bench["id"] for bench in session_benches] if session_benches else None
            else:
                state["selected_workflow_ids"] = None
                state["session_bench_ids"] = None
        elif choice == 6:
            saved = _save_preferences(state)
            print(f"  saved {saved}")
        elif choice == 7:
            if not state.get("model_path"):
                print("  select a model first.")
                continue
            print()
            print_splash()
            run_full_benchmark(
                benchmark_mode=state["mode"],
                model_path=state["model_path"],
                server_path=state.get("server_path"),
                scan_dir=state.get("scan_dir"),
                output_dir=state.get("output_dir"),
                num_turns=state.get("turns"),
                port=state.get("port"),
                workflow_suite=state.get("workflow_suite"),
                session_mode=state.get("session_mode"),
                use_jinja=state.get("use_jinja", True),
                selected_workflow_ids=state.get("selected_workflow_ids"),
                session_bench_ids=state.get("session_bench_ids"),
                quality_bench_ids=state.get("quality_bench_ids"),
                skip_quality=state.get("skip_quality", False),
            )
            return
        else:
            return
