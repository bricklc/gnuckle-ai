"""Interactive benchmark menu."""

from __future__ import annotations

import copy
import os
import sys
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
    find_gguf_files,
    find_server,
    get_cache_configs,
    load_presets,
    run_full_benchmark,
    select_preset,
)
from gnuckle.profile import list_profiles, load_profile, profiles_dir, save_profile
from gnuckle.splash import print_splash

MENU_WIDTH = 88


def render_banana_loading_bar(current: int, total: int = 5) -> str:
    current = max(0, min(int(current), int(total)))
    return "[" + ("🍌" * current) + ("·" * (total - current)) + "]"


def _fit(text: str, width: int) -> str:
    text = str(text or "")
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _wrap(text: str, width: int) -> list[str]:
    text = str(text or "")
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if len(trial) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
            current = word
            continue
        lines.append(_fit(word, width))
        current = ""
    if current:
        lines.append(current)
    return lines or [""]


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _box(title: str, lines: list[str], footer: str | None = None) -> str:
    inner = MENU_WIDTH - 4
    rendered = [f"┌{'─' * (MENU_WIDTH - 2)}┐", f"│ {title:<{inner}} │", f"├{'─' * (MENU_WIDTH - 2)}┤"]
    for line in lines:
        rendered.append(f"│ {_fit(line, inner):<{inner}} │")
    if footer:
        rendered.append(f"├{'─' * (MENU_WIDTH - 2)}┤")
        for line in _wrap(footer, inner):
            rendered.append(f"│ {line:<{inner}} │")
    rendered.append(f"└{'─' * (MENU_WIDTH - 2)}┘")
    return "\n".join(rendered)


def _render_screen(title: str, body_lines: list[str], summary: str | None = None, footer: str | None = None) -> None:
    _clear_screen()
    if summary:
        print(_box("Interactive Menu", [summary]))
        print()
    print(_box(title, body_lines, footer=footer))


def _read_key() -> str:
    if os.name == "nt":
        import msvcrt

        first = msvcrt.getwch()
        if first in ("\x00", "\xe0"):
            second = msvcrt.getwch()
            return {
                "H": "UP",
                "P": "DOWN",
                "K": "LEFT",
                "M": "RIGHT",
            }.get(second, second)
        if first == "\r":
            return "ENTER"
        if first == " ":
            return "SPACE"
        if first == "\x1b":
            return "ESC"
        return first

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        first = sys.stdin.read(1)
        if first == "\x1b":
            second = sys.stdin.read(1)
            third = sys.stdin.read(1)
            if second == "[":
                return {
                    "A": "UP",
                    "B": "DOWN",
                    "C": "RIGHT",
                    "D": "LEFT",
                }.get(third, "ESC")
            return "ESC"
        if first in ("\r", "\n"):
            return "ENTER"
        if first == " ":
            return "SPACE"
        return first
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _option_lines(
    options: list[dict],
    cursor: int,
    multi: bool = False,
    selected: set[int] | None = None,
) -> list[str]:
    selected = selected or set()
    lines: list[str] = []
    for idx, option in enumerate(options):
        pointer = ">" if idx == cursor else " "
        marker = f"[{'x' if idx in selected else ' '}] " if multi else ""
        lines.append(f"{pointer} {marker}{_fit(option['label'], MENU_WIDTH - 10)}")
        detail = option.get("detail")
        if detail:
            lines.append(f"    {_fit(detail, MENU_WIDTH - 8)}")
    return lines


def _arrow_select(
    title: str,
    options: list[dict],
    summary: str | None = None,
    footer: str | None = None,
    *,
    multi: bool = False,
    selected: set[int] | None = None,
    allow_escape: bool = False,
) -> int | list[int] | None:
    if not options:
        return [] if multi else None

    cursor = 0
    picked = set(selected or ([] if not multi else range(len(options))))

    while True:
        help_text = footer
        if multi:
            help_text = (help_text + " | " if help_text else "") + "↑/↓ move  space toggle  a all  n none  enter accept"
        else:
            help_text = (help_text + " | " if help_text else "") + "↑/↓ move  enter select"
        if allow_escape:
            help_text += "  esc back"

        _render_screen(
            title,
            _option_lines(options, cursor, multi=multi, selected=picked),
            summary=summary,
            footer=help_text,
        )
        key = _read_key()
        if key == "UP":
            cursor = (cursor - 1) % len(options)
        elif key == "DOWN":
            cursor = (cursor + 1) % len(options)
        elif multi and key == "SPACE":
            if cursor in picked:
                picked.remove(cursor)
            else:
                picked.add(cursor)
        elif multi and str(key).lower() == "a":
            picked = set(range(len(options)))
        elif multi and str(key).lower() == "n":
            picked.clear()
        elif key == "ENTER":
            if multi:
                return sorted(picked)
            return cursor
        elif key == "ESC" and allow_escape:
            return None


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


def _pick_model(state: dict) -> Path | None:
    root = Path(state.get("scan_dir") or Path.cwd())
    ggufs = find_gguf_files(root)
    if not ggufs:
        _render_screen("Models", [f"no .gguf files found under {root}"], summary=render_menu_summary(state))
        input("\npress Enter to continue...")
        return None
    options = [{"label": path.name, "detail": str(path)} for path in ggufs]
    choice = _arrow_select("Select Model", options, summary=render_menu_summary(state), allow_escape=True)
    if choice is None:
        return None
    return ggufs[int(choice)]


def _pick_saved_profile(state: dict) -> str | None:
    profiles = list_profiles()
    if not profiles:
        _render_screen("Saved Profiles", ["no saved profiles found."], summary=render_menu_summary(state))
        input("\npress Enter to continue...")
        return None
    options = [{"label": path.stem, "detail": str(path)} for path in profiles]
    choice = _arrow_select("Load Saved Profile", options, summary=render_menu_summary(state), allow_escape=True)
    if choice is None:
        return None
    return str(profiles[int(choice)])


def _pick_sampler_preset(current_model: Path | None, state: dict) -> str | None:
    presets_doc = load_presets()
    options = [presets_doc["default"]] + list(presets_doc.get("presets", []))
    auto_name = select_preset(current_model).get("name") if current_model is not None else None
    rendered = []
    for preset in options:
        label = preset.get("name", "unnamed")
        if auto_name == label:
            label = f"{label} [auto]"
        rendered.append({"label": label, "detail": preset.get("description", "")})
    choice = _arrow_select("Select Sampler Preset", rendered, summary=render_menu_summary(state), allow_escape=True)
    if choice is None:
        return None
    return options[int(choice)].get("name")


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
    _render_screen(
        "Sampler Overrides",
        [
            "blank keeps current value",
            *[f"{key} = {value}" for key, value in current.items()],
        ],
        summary=render_menu_summary(state),
    )
    casts = {
        "temp": float,
        "top_p": float,
        "top_k": int,
        "repeat_penalty": float,
        "repeat_last_n": int,
        "min_p": float,
    }
    for key, cast in casts.items():
        raw = input(f"{key} [{current[key]}]: ").strip()
        if not raw:
            continue
        try:
            sampler[key] = cast(raw)
        except ValueError:
            print(f"invalid {key}, keeping {current[key]}")
            input("press Enter to continue...")


def _pick_benchmark_mode(state: dict) -> str | None:
    options = [
        {"label": "legacy", "detail": "classic cache sweep plus benchmark snapshots"},
        {"label": "agentic", "detail": "workflow + session evaluation stack"},
        {"label": "session", "detail": "session benchmarks only"},
    ]
    choice = _arrow_select("Select Benchmark Mode", options, summary=render_menu_summary(state), allow_escape=True)
    if choice is None:
        return None
    return options[int(choice)]["label"]


def _pick_cache_types(state: dict) -> list[str]:
    options = [{"label": cfg["label"], "detail": f"cache-k={cfg['cache_k']} cache-v={cfg['cache_v']}"} for cfg in get_cache_configs()]
    selected = {
        idx for idx, cfg in enumerate(get_cache_configs()) if cfg["label"] in (state.get("cache_types") or [])
    }
    picks = _arrow_select(
        "Select Cache Quantizations",
        options,
        summary=render_menu_summary(state),
        multi=True,
        selected=selected,
        allow_escape=True,
    )
    if picks is None:
        return state.get("cache_types") or [cfg["label"] for cfg in get_cache_configs()]
    if not picks:
        return [cfg["label"] for cfg in get_cache_configs()]
    return [get_cache_configs()[idx]["label"] for idx in picks]


def _pick_quality_packs(state: dict) -> list[str]:
    installed = [path.name for path in benchmarks_dir().iterdir() if path.is_dir()] if benchmarks_dir().exists() else []
    available = list_available_packs()
    options = installed or [entry.get("id") for entry in available if entry.get("id")]
    options = [option for option in options if option]
    if not options:
        return []
    rendered = [{"label": option, "detail": "quality benchmark pack"} for option in options]
    preselected = set(range(len(options))) if not state.get("quality_bench_ids") else {
        idx for idx, option in enumerate(options) if option in state.get("quality_bench_ids", [])
    }
    picks = _arrow_select(
        "Select Quality Benchmarks",
        rendered,
        summary=render_menu_summary(state),
        multi=True,
        selected=preselected,
        allow_escape=True,
    )
    if picks is None:
        return state.get("quality_bench_ids", [])
    return [options[idx] for idx in picks]


def _pick_workflow_ids(state: dict) -> list[str] | None:
    from gnuckle.workflow_loader import load_workflow_suite

    workflows = load_workflow_suite(state["workflow_suite"])
    if not workflows:
        return None
    options = []
    for workflow in workflows:
        difficulty = workflow.difficulty[0].upper() if workflow.difficulty else "?"
        options.append(
            {
                "label": f"[{workflow.benchmark_layer}] {workflow.title}",
                "detail": f"{difficulty} | {workflow.workflow_id}",
            }
        )
    selected = set(range(len(options)))
    picks = _arrow_select(
        "Select Workflow Benchmarks",
        options,
        summary=render_menu_summary(state),
        multi=True,
        selected=selected,
        allow_escape=True,
    )
    if picks is None or len(picks) == len(options):
        return None
    if not picks:
        return None
    return [workflows[idx].workflow_id for idx in picks]


def _pick_session_bench_ids(state: dict) -> list[str] | None:
    from gnuckle.session_runner import discover_benchmarks

    benchmarks = discover_benchmarks()
    if not benchmarks:
        return None
    options = []
    for bench in benchmarks:
        tags = ", ".join(bench.get("tags", [])[:3]) or "no tags"
        turns = len(bench.get("turns", []))
        options.append(
            {
                "label": f"{bench['title']} ({turns}t)",
                "detail": f"{tags} | {bench.get('id')}",
            }
        )
    selected = set(range(len(options)))
    picks = _arrow_select(
        "Select Session Benchmarks",
        options,
        summary=render_menu_summary(state),
        multi=True,
        selected=selected,
        allow_escape=True,
    )
    if picks is None:
        return state.get("session_bench_ids")
    if not picks:
        return None
    if len(picks) == len(options):
        return None
    return [benchmarks[idx]["id"] for idx in picks]


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
    _render_screen("Save Preferences", ["type a profile name and press Enter"], summary=render_menu_summary(state))
    name = input("profile name: ").strip()
    if not name:
        raise ValueError("profile name cannot be empty")
    target = profiles_dir() / f"{name}.json"
    return save_profile(target, menu_state_to_profile(state))


def _configure_benchmarks(state: dict) -> None:
    picked_mode = _pick_benchmark_mode(state)
    if picked_mode:
        state["mode"] = picked_mode
    state["cache_types"] = _pick_cache_types(state)
    state["quality_bench_ids"] = _pick_quality_packs(state)
    state["skip_quality"] = not bool(state["quality_bench_ids"])
    if state["mode"] == "agentic":
        state["selected_workflow_ids"] = _pick_workflow_ids(state)
        state["session_bench_ids"] = _pick_session_bench_ids(state)
    elif state["mode"] == "session":
        state["selected_workflow_ids"] = None
        state["session_bench_ids"] = _pick_session_bench_ids(state)
    else:
        state["selected_workflow_ids"] = None
        state["session_bench_ids"] = None


def run_interactive_menu() -> None:
    if not _is_interactive_terminal():
        raise SystemExit("interactive menu requires a TTY")
    state = default_menu_state()

    while True:
        options = [
            {"label": "Select model", "detail": Path(state["model_path"]).name if state.get("model_path") else "no model selected"},
            {"label": "Load saved profile", "detail": "apply a saved gnuckle menu profile"},
            {"label": "Select sampler preset", "detail": state.get("sampler_preset") or "auto"},
            {"label": "Edit temps / sampler overrides", "detail": "manual temp, top-p, top-k, repeat penalties"},
            {"label": "Select benchmarks", "detail": f"{state['mode']} | {','.join(state['cache_types'])}"},
            {"label": "Save preferences", "detail": "write current menu state to ~/.gnuckle/profiles"},
            {"label": "Run benchmark", "detail": "launch benchmark with current selection"},
            {"label": "Exit", "detail": "leave menu"},
        ]
        choice = _arrow_select(
            "Interactive Menu",
            options,
            summary=render_menu_summary(state),
            footer="bordered menu mode active",
        )
        if choice == 0:
            model = _pick_model(state)
            if model is not None:
                state["model_path"] = str(model)
                auto_server = _auto_detect_server(model, Path(state["scan_dir"]) if state.get("scan_dir") else None)
                if auto_server is not None:
                    state["server_path"] = str(auto_server)
        elif choice == 1:
            picked = _pick_saved_profile(state)
            if picked:
                state = _apply_profile_to_state(state, load_profile(picked))
        elif choice == 2:
            if not state.get("model_path"):
                _render_screen("Select Sampler Preset", ["pick a model first."], summary=render_menu_summary(state))
                input("\npress Enter to continue...")
                continue
            picked = _pick_sampler_preset(Path(state["model_path"]), state)
            if picked:
                state["sampler_preset"] = picked
        elif choice == 3:
            _edit_sampler_values(state)
        elif choice == 4:
            _configure_benchmarks(state)
        elif choice == 5:
            saved = _save_preferences(state)
            _render_screen("Save Preferences", [f"saved {saved}"], summary=render_menu_summary(state))
            input("\npress Enter to continue...")
        elif choice == 6:
            if not state.get("model_path"):
                _render_screen("Run Benchmark", ["select a model first."], summary=render_menu_summary(state))
                input("\npress Enter to continue...")
                continue
            _clear_screen()
            print_splash()
            run_benchmark_from_menu_state(state)
            return
        else:
            _clear_screen()
            return


def run_benchmark_from_menu_state(state: dict) -> None:
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
        cache_labels=state.get("cache_types"),
        quality_bench_ids=state.get("quality_bench_ids"),
        skip_quality=state.get("skip_quality", False),
    )
