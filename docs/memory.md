# Agent Memory

> Add only facts that change how the agent should behave or that are not derivable from code.
> Keep entries short. One sentence per fact when possible.

---

## Project Intent

gnuckle benchmarks local models for **agentic reliability under pressure**, not raw capability.

Two tracks:
- **Legacy** - cache type effect on tok/s, TTFT, VRAM
- **Agentic** - bounded harness, tool choice quality, constitutional retention, integrity decay

Output is `Type + Grade` (for example `Type 2, B`) so the result shows what class of work the model handles, plus its floor and ceiling.

Context is treated as a scarce budget. Failure is preserved as data, not a kill condition.

---

## Self-Correction Rules

- If a task feels like scope creep, stop and check against the two tracks above.
- Do not remove old docs - superseded notes stay, new numbered file instead.
- If unsure which benchmark track a feature belongs to, ask before building.
- Prefer minimal implementations. Do not add abstractions for one-time use.
- If a memory entry becomes stale or wrong, update or remove it here immediately.

---

## Active Facts

<!-- Add timestamped one-liners here as the project evolves. -->
<!-- Format: `YYYY-MM-DD - fact` -->

2026-04-09 - Primary model target is Nemotron3-Nano-4B; Gemma 4 26B is planned next.
2026-04-09 - Correct TurboQuant merge source is TheTom/llama-cpp-turboquant, not Madreag.
2026-04-09 - Safe build target on this machine is RTX 2060 Super first (sm_75, CUDA arch 75), but RTX 5060 Ti also works and is often used.
2026-04-09 - gnuckle entry point may not be on PATH; use `python -m gnuckle` if the command is missing.
2026-04-10 - Exact token counting for local llama.cpp runs should use `POST /apply-template` plus `POST /tokenize`; only fall back to heuristic or `cl100k_base` approximations if that exact path is unavailable.
2026-04-10 - Benchmark output and visualizers should show token counts with explicit labels for house heuristic, OpenAI `cl100k_base`, and exact llama.cpp counts when available.
2026-04-10 - Context-pressure metrics are benchmark-valid as `measured` only when the llama.cpp exact path succeeds; otherwise they must remain labeled `estimated` with uncertainty.
2026-04-10 - `--split-mode` is benchmark-wide runtime configuration for any current or future benchmark mode that launches local `llama-server`.
2026-04-10 - The OpenClaude-inspired benchmark core is: persistent transcript loop, fixed visible tool list, in-band tool failures, verification before success, separate usage versus context accounting, and trace integrity.
2026-04-10 - Ape commit summaries use a fixed structure: short `title`, then ape-voice `body` with `🍌` bullets for concrete changes and short `have X, yes, good.` outcome lines.
2026-04-10 - Common post-update flow is: `git pull --ff-only`, `pip install -e .`, `python -m gnuckle --version`, then run the relevant benchmark or visualizer command.
2026-04-10 - Preferred runtime invocation is `python -m gnuckle ...`, especially after updates, because it avoids stale launcher or PATH issues.
2026-04-10 - Every repo change must include an explicit version bump, synchronized across `gnuckle/version.json`, `pyproject.toml`, and `package.json`.
2026-04-10 - Version bump preference is small forward increments (for example `0.2.8` to `0.2.9`, or `+0.0.1` when requested) rather than reusing an already-used version.
