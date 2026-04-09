# Agent Memory

> Add only facts that change how the agent should behave or that are not derivable from code.
> Keep entries short. One sentence per fact when possible.

---

## Project Intent

gnuckle benchmarks local models for **agentic reliability under pressure**, not raw capability.

Two tracks:
- **Legacy** — cache type effect on tok/s, TTFT, VRAM (current focus)
- **Agentic** — bounded harness, tool choice quality, constitutional retention, integrity decay

Output is `Type + Grade` (e.g. `Type 2, B`) — what class of work the model handles, its floor and ceiling.

Context is treated as a scarce budget. Failure is preserved as data, not a kill condition.

---

## Self-Correction Rules

- If a task feels like scope creep, stop and check against the two tracks above.
- Do not remove old docs — superseded notes stay, new numbered file instead.
- If unsure which benchmark track a feature belongs to, ask before building.
- Prefer minimal implementations. Do not add abstractions for one-time use.
- If a memory entry becomes stale or wrong, update or remove it here immediately.

---

## Active Facts

<!-- Add timestamped one-liners here as the project evolves. -->
<!-- Format: `YYYY-MM-DD — fact` -->

2026-04-09 — Primary model target is Nemotron3-Nano-4B; Gemma 4 26B planned next.
2026-04-09 — Correct TurboQuant merge source is TheTom/llama-cpp-turboquant, not Madreag.
2026-04-09 — Safe build target on this machine is RTX 2060 Super first (sm_75, CUDA arch 75).
2026-04-09 — gnuckle entry point may not be on PATH; use `python -m gnuckle` if command missing.
