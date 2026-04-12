# 26 — Agentic Benchmark Preservation Through the Pack Migration

**Status:** Design commitment. Non-negotiable for v0.4 → v1.0.
**Author:** preservation commitment, 2026-04-12.
**Related:** doc 24 (standard quality benchmarks), doc 25 (pack runtime + security).

---

## 1. Core commitment

The agentic benchmark stack is the **novel differentiator** of gnuckle. It is the reason the project exists. The standard quality benchmarks from docs 24 and 25 are a **credibility bridge** so the agentic work gets read seriously — they are not a replacement. Throughout the v0.4 → v1.0 pack migration, every piece of the current agentic stack stays running, untouched, and on the critical path.

This doc exists so that when future work tempts anyone to "simplify" by removing the agentic path, we can point at this page and say: no, that is the product, don't delete it.

---

## 2. What stays as-is through v1.0

Zero code changes to any of these files or features during the v0.4 → v1.0 arc, except for bug fixes and integration points with the new `meta.quality_benchmarks` dict:

- `run_agentic_benchmark_pass` in `gnuckle/benchmark.py`
- `gnuckle/agentic_runtime.py` and the workflow episode runner
- `gnuckle/workflow_loader.py` and the workflow JSON suite
- `gnuckle/benchmark_scoring.py` — session score, format obedience, literal-vs-semantic gap, unsupported claims, recovery tries, workflow aggregation
- Session benchmarks: `persistent_tool_stress`, the 40-turn benefit-of-doubt harness, and any others registered in the session bench set
- Reactive user correction loops (commit `663732c`)
- Constitution Under Load / Integrity Decay Curve / MRMB — definitions from doc 13
- The `--mode agentic|session|legacy` CLI flag and its full branch in `cli.py`
- Workflow JSON definitions including the personal-productivity workflows from doc 17
- Live-trace theater mode (`--live-trace`, `--trace-style`)
- Agentic dashboard panels in `visualize.py` — cache leaderboard, per-workflow drilldowns, trace replays

If a v0.x release changes any of these, it is a bug fix or an integration seam, never a rewrite.

---

## 3. How the two layers coexist

Post-v1.0, every benchmark run executes two parallel layers per cache config:

```
cache config (f16 / q8_0 / q4_0 / turbo3)
│
├── Standard quality layer ← NEW, loaded from installed packs
│   ├── wikitext2_ppl
│   ├── kld_vs_f16
│   ├── hellaswag
│   └── (any community packs)
│
└── Agentic behavior layer ← UNCHANGED, current stack
    ├── workflow suite (tool call validity, selection, etc.)
    ├── session benchmarks (persistent stress, benefit-of-doubt)
    ├── scoring (format obedience, semantic gaps, CUL, IDC, MRMB)
    └── live trace
```

Both layers write to the same results JSON:
- Quality → `meta.quality_benchmarks[<id>]` (dict keyed by benchmark ID)
- Agentic → existing `meta`, `turns`, `aggregate`, `workflow_results`, `session_*` shapes

The two layers do not share state beyond the JSON file. Neither can break the other.

---

## 4. Dashboard composition (post-v0.10)

The dashboard after v0.10 renders both layers in a deliberate order:

1. **Standard benchmarks panel** — top of page, above the fold. Familiar vocabulary. PPL, KLD, HellaSwag, quality tier. This is the anchor for a reader who has never seen gnuckle before.
2. **Agentic behavior panel** — below the standard panel. Session score, per-workflow breakdown, integrity decay curves, format obedience, recovery tries, live-trace embeds. This is where the novel contribution lives.

The ordering is intentional: a reader scanning the page sees the familiar stack first, trusts the tool, and then reads the agentic panel with that trust already in place. Without the standard panel, the agentic numbers have nothing to anchor against and get dismissed as vanity metrics.

---

## 5. Why the standard layer helps the agentic layer

A number like `session_score: 0.78` is meaningless without a reference frame. A reader seeing it in isolation has no way to know if 0.78 is good, bad, or randomly generated.

Put `WikiText-2 PPL: 6.43, KLD vs f16: 0.008, HellaSwag: 62.4%` next to that agentic score, computed by the same tool on the same model on the same cache, and everything changes:

- The reader now trusts gnuckle to correctly measure *something*.
- They implicitly transfer that trust to the agentic numbers.
- They start asking "how does session_score relate to these?" instead of "is this tool even real?"

The standard panel exists to earn that trust. The agentic panel is what we do with it.

This is the entire thesis of the bridge strategy in doc 24. Doc 26 exists to make it impossible to forget.

---

## 6. Explicit non-goals through v1.0

- **Do not port agentic benchmarks to the pack runtime during v0.4 → v1.0.** The agentic stack is too complex and too central to put through a platform migration while we are also building the platform. Two migrations at once is how things break. Quality benchmarks migrate first, prove the runtime, and only then does agentic portability become a v1.5+ conversation.
- **Do not unify the two JSON schemas.** Quality lives in `meta.quality_benchmarks`, agentic keeps its existing shape. A unified schema is a v2.0 thought experiment, not a v0.x goal.
- **Do not add a "quality-only mode" that skips agentic.** Users can already select `--skip-quality` going forward, and `--mode legacy` already runs without workflows. A user who wants only quality metrics has enough knobs.
- **Do not remove the `--mode legacy` flag.** Even though it is the simplest path, it is the fallback when the agentic runtime has issues, and it is the path the standard quality layer will first integrate against during v0.4.

---

## 7. What *could* change after v1.0 (not commitments)

These are conversation starters for v1.1+, listed for the record, not plans:

- Agentic workflow suites expressed as manifests so community contributors can PR new workflows without touching gnuckle core.
- Agentic scoring dimensions exposed as configurable in a pack manifest.
- A unified "bench" concept that treats quality and agentic as two kinds of the same underlying pack abstraction.

None of these happen during v0.4 → v1.0. All of them are optional forever if they turn out to be bad ideas.

---

## 8. Short version

The agentic benchmark stack is gnuckle's reason to exist. The pack migration adds a standard quality layer next to it, not on top of it, not instead of it. Both layers run together, write to the same JSON, render in the same dashboard, and strengthen each other. If you are about to delete agentic code during v0.4 → v1.0, stop and re-read this doc.
