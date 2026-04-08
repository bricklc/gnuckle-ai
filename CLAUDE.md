# TurboQuant Agentic Benchmark — Project Context

## Owner
Gnuckle AI 
---

## Project Goal
Benchmark llama.cpp KV cache quantization types for real agentic tool-calling workloads.
Expose the effect of TurboQuant (turbo3/turbo4) on:
- Generation speed degradation across long tool-call chains
- Time to first token (TTFT) as context grows
- VRAM consumption at peak context depth
- Tool call JSON formatting accuracy under load

Results feed a visualization script that produces charts comparable to the TurboQuant
community thread: https://github.com/ggml-org/llama.cpp/discussions/20969

---

## Hardware
| Card | VRAM | CUDA Device (llama.cpp) | nvidia-smi GPU |
|---|---|---|---|
| RTX 5060 Ti | 16 GB | 0 (primary) | 1 |
| RTX 2060 Super | 8 GB | 1 | 0 |

CUDA device order is flipped vs nvidia-smi due to PCIe enumeration.
Always use `--main-gpu 0` in llama-server — this targets the 5060 Ti.

---

## Current llama.cpp Fork
`Mintplex-Labs/prism-ml-llama.cpp` — mainline llama.cpp + Prism-ML 1-bit (Bonsai) model support.
Repo: https://github.com/Mintplex-Labs/prism-ml-llama.cpp

TurboQuant CUDA merge target: https://github.com/Madreag/turbo3-cuda
- Tested on sm_120 (5060 Ti matches)
- sm_75 (2060 Super) is untested — may or may not compile cleanly

Merge approach:
```bash
git remote add turbo https://github.com/Madreag/turbo3-cuda
git fetch turbo
git merge turbo/main
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="75;120" -DGGML_CUDA_FORCE_CUBLAS=OFF
cmake --build build -j
```

---

## Model Targets
| Model | Purpose | Status |
|---|---|---|
| Nemotron3-Nano-4B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf | Benchmark baseline (hybrid Mamba-Transformer) | Active |
| Gemma 4 26B-A4B Q4_K_M | Primary target (MoE, 4B active params, 256K context) | Planned |

Notes on Nemotron3:
- Hybrid Mamba-Transformer architecture — `--cache-type-k/v` flags apply only to transformer attention layers, not Mamba state layers
- Max context: 131072 (per model card)
- Recommended sampling: `--temp 0.6 --top-p 0.95`

---

## Baseline llama-server Command
```bash
build\bin\llama-server.exe -m <model.gguf> ^
  --host 0.0.0.0 --port 8080 ^
  -ngl 99 ^
  --split-mode layer ^
  --main-gpu 0 ^
  --ctx-size 131072 ^
  --cache-type-k q4_0 --cache-type-v q4_0 ^
  --temp 0.6 --top-p 0.95 --top-k 20 ^
  --repeat-penalty 1.1
```

---

## Files
| File | Description |
|---|---|
| `benchmark.py` | Main benchmark script — auto GGUF finder, auto server management, 4 cache types |
| `benchmark_results/` | Output directory — one JSON per cache type per run |
| `visualize.py` | NOT YET BUILT — reads all JSONs, produces 5-panel scientific chart |

---

## Benchmark Script — benchmark.py
Fully automated. Runs f16 → q8_0 → q4_0 → turbo3 back to back.

**What it measures per turn:**
- `tps` — tokens per second (generation only)
- `ttft_ms` — time to first token in milliseconds
- `tokens_generated` — output token count
- `elapsed_s` — total wall time
- `context_tokens_approx` — approximate running context size
- `tool_calls_count` — number of tool calls issued
- `tool_accuracy_pct` — % of tool calls with valid JSON and required fields
- `vram_before_mb` / `vram_after_mb` — per-GPU VRAM from nvidia-smi

**Output JSON structure:**
```json
{
  "meta": { "cache_label": "turbo3", "model": "...", "num_turns": 20, "timestamp": "..." },
  "turns": [
    {
      "turn": 1,
      "tps": 11.4,
      "ttft_ms": 340,
      "tokens_generated": 42,
      "elapsed_s": 3.68,
      "context_tokens_approx": 180,
      "tool_calls_count": 2,
      "tool_accuracy_pct": 100.0,
      "vram_before_mb": [288, 7834],
      "vram_after_mb": [290, 8102]
    }
  ]
}
```

**Run:**
```bash
pip install openai
python benchmark.py
```

---

## Visualization — visualize.py (NEXT TASK)
Reads all JSON files in `benchmark_results/`.
Produces a 5-panel scientific chart:
1. Generation speed (tok/s) across 20 turns — all cache types overlaid
2. TTFT (ms) across 20 turns — all cache types overlaid
3. VRAM at peak context — bar chart per cache type
4. tok/s turn 1 vs turn 20 — grouped bar (degradation comparison)
5. Tool call accuracy % across turn ranges — grouped bar

Output: static HTML or PNG. Community-comparable format matching TurboQuant thread tables.

---

## 5 Benchmark Metrics (scientific rationale)
| # | Metric | What TurboQuant exposes |
|---|---|---|
| 1 | Generation speed (tok/s) | turbo3 holds near-baseline despite 4.4x compression |
| 2 | TTFT (ms) | smaller KV cache = faster prefill scan at long context |
| 3 | Context scaling degradation | core TurboQuant claim — speed curve stays flat |
| 4 | VRAM at peak context | 4.4x reduction vs f16 — headroom for larger models |
| 5 | Tool call accuracy | compression must not break coherence under load |

---

## Key References
- TurboQuant discussion: https://github.com/ggml-org/llama.cpp/discussions/20969
- Madreag CUDA fork: https://github.com/Madreag/turbo3-cuda
- Aaryan-Kapoor CPU fork: https://github.com/Aaryan-Kapoor/llama.cpp/tree/turboquant-tq3_0
- Hermes function calling standard: https://github.com/NousResearch/Hermes-Function-Calling
- Unsloth Gemma 4 GGUFs: https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF