# 24 — Standard Quality Benchmarks: The Bridge Strategy

**Status:** Ideation, ready to phase into a build plan.
**Author:** audit + ideation session, 2026-04-12.
**Supersedes:** nothing. Extends `23-benchmark-json-format-v2.md` and slots quality benchmarks next to the existing throughput (`llama-bench`) and PPL (`llama-perplexity`) wiring.

---

## 1. Why this exists

Gnuckle's unique angle is **agentic + KV-quant behavior**. That is the novel part. The problem is that novel benchmarks are a hard sell to a community that already has its own vocabulary of "trusted" numbers.

If a llama.cpp / ik_llama / Unsloth reader opens our dashboard and sees only `session_score`, `format_obedience`, `literal_vs_semantic_gap` — all of which are *our* terms — they have no anchor. They cannot tell whether gnuckle is serious tooling or a vanity metric dashboard.

If the same reader opens our dashboard and sees **WikiText-2 PPL, KL divergence vs f16, HellaSwag accuracy, and quality tier** *alongside* our agentic metrics, the psychological shift is large:

> "Oh, this tool speaks my language. It reports the standard stack I already use — *and* it has this extra agentic angle I haven't seen before."

That is the bridge. Standard benchmarks act as a trust anchor so the novel agentic metrics get read at all.

We do not need to invent quality benchmarks. We need to **expose the ones `llama-perplexity` already ships with**, and put them in our dashboard next to the agentic data.

---

## 2. The key insight

The `llama-perplexity` binary we already shell out to does far more than raw perplexity. The same binary supports:

| Flag | Benchmark | Community status |
|---|---|---|
| `-f wiki.test.raw` | WikiText-2 perplexity | ✅ everyone reports this |
| `--kl-divergence-base` + `--kl-divergence` | KL divergence vs f16 baseline | ✅ the gold-standard quant comparison in ik_llama, ggml-org, TurboQuant thread |
| `--hellaswag` + dataset | HellaSwag commonsense accuracy | ✅ standard leaderboard metric |
| `--winogrande` + dataset | Winogrande coreference accuracy | ✅ standard |
| `--multiple-choice` | MMLU-style knowledge QA | ✅ standard |

**Every one of these is a shell-out to the same binary we already wired up.** No C++ hooks, no PyTorch, no extra runtime dependencies. Just different flags and different cached datasets.

The only "standard" quality signal this *can't* reach is reconstruction fidelity (cosine similarity / NMSE between original and compressed KV cache), which needs C++ internals access. We explicitly defer that — it is a future-work item, not a blocker.

---

## 3. Comparison to kvtc (the reference point)

`OnlyTerp/kvtc` measures a PyTorch-native KV cache compression algorithm. Their quality benchmarks (`benchmark_perplexity.py`, `benchmark_v4.py`) report:

- WikiText-2 perplexity ← we can match this ✅ (already done)
- Per-sample cross-entropy loss ← subsumed by PPL
- Reconstruction fidelity: cosine similarity, NMSE ← needs C++ hooks, defer
- Per-layer quality tracking ← needs C++ hooks, defer
- Compression/decompression latency (ms) ← we get this more usefully via TTFT + tok/s
- Quality tiers: lossless / excellent / good / usable / degraded ← easy to copy, should do ✅
- 8-prompt calibration text set (code, math, JSON, conversational) ← optional quick sanity probe

What we add *beyond* kvtc's quality set by using `llama-perplexity`'s other modes:

- KL divergence vs f16 (the ik_llama community standard — kvtc doesn't do this)
- HellaSwag, Winogrande, MMLU subsets (standard LLM leaderboard metrics — kvtc doesn't do these either)

So if we implement this plan in full, we end up with a **superset** of kvtc's quality stack on the llama.cpp side, plus our agentic layer on top. That is a credible positioning.

---

## 4. Design principles

1. **Modular.** Every standard benchmark runs as its own independent module, same shape as the existing throughput + PPL wiring in `benchmark.py`. The user picks which ones run via CLI flags, the same way session benchmarks and workflow IDs are already selected.
2. **Degrade gracefully.** If `llama-perplexity` or a dataset is missing, the benchmark emits a clear warning and the run continues. No hard crash. (Fix for current "fail loud" bug — see doc 24 success metrics table below.)
3. **Same save shape.** Every quality benchmark writes into `meta.quality_benchmarks` as a dict keyed by benchmark ID (`wikitext2_ppl`, `kld_vs_f16`, `hellaswag`, ...). This keeps the JSON schema from sprouting new top-level keys every time we add one.
4. **Delta-first reporting.** Every result includes `value`, `baseline_value`, and `delta_vs_baseline`. The baseline is f16 unless overridden. Absolute numbers alone are not useful — `6.43 PPL (+0.8% vs f16)` is.
5. **Quality tier badge.** Derived from KLD delta vs f16, using the same labels kvtc uses: `lossless / excellent / good / usable / degraded`. One cheap, human-readable signal on the dashboard hero card.
6. **Standard datasets, cached on disk.** All datasets live under `~/.gnuckle/datasets/<name>/`. Downloaded on first use with size check. No bundled datasets in the repo.

---

## 5. The benchmark modules

Each module is independent, shells out to `llama-perplexity`, parses output, writes into `meta.quality_benchmarks`.

### 5.1 `wikitext2_ppl` — WikiText-2 perplexity
- **Status:** Already implemented as of v0.3.24. Needs bug fixes (see §8).
- **Binary:** `llama-perplexity -f wiki.test.raw --ctx-size 512`
- **Dataset:** `wikitext-2-raw-v1.zip` from `huggingface.co/datasets/ggml-org/ci`
- **Metric:** final PPL (float)
- **CLI:** `--quality-bench wikitext2_ppl`

### 5.2 `kld_vs_f16` — KL divergence vs f16 baseline
- **Status:** Not yet built. **Highest priority addition.**
- **Binary, two-stage:**
  1. First, on the f16 cache run: `llama-perplexity --kl-divergence-base <out>.dat -f wiki.test.raw` → saves logits file
  2. Then, on every other cache run: `llama-perplexity --kl-divergence --kl-divergence-base <out>.dat -f wiki.test.raw`
- **Dataset:** same WikiText-2, no extra download
- **Metrics:** mean KLD, 99th percentile KLD, top-1 token agreement %, top-5 token agreement %
- **CLI:** `--quality-bench kld_vs_f16`
- **Notes:** requires the f16 run to happen first. The orchestrator already runs cache configs in a fixed order (f16 → q8_0 → q4_0 → turbo3), which is compatible. If the user selects a cache set that excludes f16, this benchmark is skipped with a warning.

### 5.3 `hellaswag` — commonsense reasoning accuracy
- **Binary:** `llama-perplexity --hellaswag -f hellaswag.txt --hellaswag-tasks 400`
- **Dataset:** `hellaswag_val_full.txt` — fetched from the ggml-org CI mirror. Cache under `~/.gnuckle/datasets/hellaswag/`.
- **Metric:** accuracy % over N tasks (400 is the llama.cpp convention; takes ~2 min per cache type on a 4B model)
- **CLI:** `--quality-bench hellaswag`

### 5.4 `winogrande` — coreference reasoning accuracy
- **Binary:** `llama-perplexity --winogrande -f winogrande_val.txt --winogrande-tasks 0` (0 = all)
- **Dataset:** ggml-org CI mirror
- **Metric:** accuracy %
- **CLI:** `--quality-bench winogrande`
- **Priority:** low. Include for completeness but don't block v0.4 on it.

### 5.5 `mmlu_subset` — knowledge QA accuracy
- **Binary:** `llama-perplexity --multiple-choice -f mmlu_subset.txt`
- **Dataset:** ggml-org CI mirror subset
- **Metric:** accuracy %
- **CLI:** `--quality-bench mmlu`
- **Priority:** low. Defer to v0.5.

### 5.6 `quality_tier` — derived badge
- **Not a benchmark run.** A derived label computed from `kld_vs_f16.mean_kld` once that benchmark has data.
- **Thresholds (initial, to be calibrated):**
  - `lossless`: mean KLD < 0.001
  - `excellent`: mean KLD < 0.01
  - `good`: mean KLD < 0.05
  - `usable`: mean KLD < 0.15
  - `degraded`: mean KLD ≥ 0.15
- **Displayed:** dashboard hero card and leaderboard row.

---

## 6. CLI surface

Quality benchmarks are selected via a new `--quality-bench` multi-value flag, mirroring how `--session-bench` and `--workflows` already work:

```
gnuckle benchmark --quality-bench wikitext2_ppl,kld_vs_f16,hellaswag
```

Shortcuts:
- `--quality-bench all` → run every available module
- `--quality-bench standard` → run the Tier-1 set (`wikitext2_ppl,kld_vs_f16`)
- `--quality-bench full` → Tier-1 + Tier-2 (`wikitext2_ppl,kld_vs_f16,hellaswag`)
- `--skip-quality` → run no quality benchmarks (for fast iteration or if binaries are missing)

If `--quality-bench` is not specified, the default is `standard` (PPL + KLD). This is the behavior change that makes gnuckle feel like a "real" benchmark tool by default.

Auto-detection: if `llama-perplexity` binary is not found, the run warns once, skips all quality benchmarks, and continues with speed/agentic data. No `RuntimeError`.

---

## 7. Data shape

All quality benchmark results land in `meta.quality_benchmarks` on every results JSON (agentic, session, legacy — consistent across all modes). This fixes the current bug where agentic mode stores the key in the wrong pocket.

```json
{
  "meta": {
    "cache_label": "turbo3",
    "quality_benchmarks": {
      "wikitext2_ppl": {
        "available": true,
        "value": 6.431,
        "baseline_value": 6.377,
        "delta_vs_baseline": 0.0085,
        "unit": "perplexity",
        "dataset": "wikitext-2-raw-v1"
      },
      "kld_vs_f16": {
        "available": true,
        "mean_kld": 0.0082,
        "p99_kld": 0.041,
        "top1_agreement_pct": 97.8,
        "top5_agreement_pct": 99.6,
        "baseline_cache": "f16",
        "logits_file": "~/.gnuckle/logits/model_f16.dat"
      },
      "hellaswag": {
        "available": true,
        "value": 62.4,
        "baseline_value": 62.8,
        "delta_vs_baseline": -0.0064,
        "unit": "accuracy_pct",
        "tasks": 400
      },
      "quality_tier": "excellent"
    }
  }
}
```

---

## 8. Bugs in the current v0.3.24 PPL implementation (fix before shipping any of the above)

From the audit in this session, three bugs block the bridge plan:

1. **Agentic pass writes `quality_benchmark` to wrong key.** `run_agentic_benchmark_pass` stores it at `summary["quality_benchmark"]`, but `visualize.extract_metrics` reads `meta.quality_benchmark`. PPL is invisible in agentic dashboards. Fix: nest under `meta`.
2. **`build_llama_args` leaks server-only flags into `llama-perplexity`.** Passing `preset["server_args"]` (with `--host`, `--port`, `--parallel`, `--cont-batching`, `--jinja`) to a non-server binary crashes it. Fix: whitelist the small set of args that apply to every llama.cpp tool, or build a perplexity-specific arg map.
3. **"Fail loud" is too loud.** Both `llama-bench` and `llama-perplexity` missing now `raise RuntimeError`, killing the entire run. Fix: warn + continue. Also add the `--skip-quality` CLI flag.

Secondary:
- No checksum on the WikiText-2 zip download. Corrupt cached file = silent permanent failure. Delete on `ZipFile` extraction error.
- Hero card replaced "Total context" with PPL silently — intentional but not documented.

---

## 9. Roadmap (superseded by doc 25)

**The roadmap and success metrics originally in this doc have been superseded by doc `25-benchmark-pack-registry-architecture.md`.**

The platform shift described in doc 25 means the benchmarks listed here (PPL, KLD, HellaSwag, Winogrande, MMLU) are **not** implemented as hardcoded Python modules in `benchmark.py`. Instead, they ship as **seed manifests in the benchmark-index registry repo**, loaded at runtime through the pack runtime described in doc 25.

This doc still stands as the specification for *what* these benchmarks should measure and *why* they matter. Doc 25 covers *how* they get built, shipped, and secured.

For the authoritative version-by-version roadmap and success metrics, see:
- Doc 25 §9 (revised roadmap)
- Doc 25 §10 (per-version success metrics)
- Doc 25 §7 (security audit — read before implementing)

The short version:
- **v0.4.0** — fix the 3 bugs in §8 of this doc (unchanged)
- **v0.5.0** — pack runtime + registry client (declarative only)
- **v0.6.0** — seed the registry with `wikitext2_ppl`, `kld_vs_f16`, `hellaswag`
- **v0.7.0** — `winogrande`, `mmlu_subset`, community PR workflow
- **v0.8.0** — code-plugin escape hatch (gated with explicit trust)
- **v0.9.0** — dashboard bridge layout
- **v1.0.0** — shipping gate

---

## 11. Explicit non-goals

- **Reconstruction fidelity (cosine / NMSE) before v1.0.** Requires C++ internals access. Defer. If someone opens an issue asking for it, revisit.
- **Bundling datasets in the repo.** All datasets are fetched on first use. Keeps the git repo small and avoids licensing questions.
- **Reimplementing `llama-perplexity` in Python.** We are shell-out purists here. If the binary doesn't support it, we don't support it.
- **Matching `kvtc`'s exact numbers.** We're not trying to reproduce their dashboard — we're speaking the shared language so their audience understands ours.

---

## 12. Open questions

- Should KLD report use the `--chunks` flag to speed up on long runs, or always run the full WikiText-2 test set? (Leaning: `--chunks 100` by default, configurable.)
- Should the `standard` default include HellaSwag, or is PPL + KLD sufficient? (Leaning: PPL + KLD only — HellaSwag is a v0.7.0 opt-in until we confirm runtime on big models.)
- Is `~/.gnuckle/logits/` the right place for the f16 baseline logits file, or should it live under the results directory per-run? (Leaning: per-run, so results are self-contained and reproducible — but that means re-running f16 every time, which is slower.)

These are not blockers. Answer during implementation.
