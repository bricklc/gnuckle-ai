# GNUCKLE

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/light.png">
  <img alt="Gnuckle banner" src="assets/readme/light.png">
</picture>

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

**Agentic AI Benchmark for llama.cpp KV Cache Quantization**

have gnuckle, yes, good.
gnuckle benchmarks llama.cpp KV cache behavior on real tool-calling workloads.
have benchmark harness, yes, good. have fork of llama.cpp, no, sad.

made this to benchmark our models with TurboQuant, yes, good.
eventually we hope TurboQuant also works with 1-bit models, yes, good.
have not tied to one fork, yes, good. all apes happy.

This repo merges ideas and references from:

- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant.git)
- [Mintplex-Labs/prism-ml-llama.cpp](https://github.com/Mintplex-Labs/prism-ml-llama.cpp.git)

That merge path reflects the first working setup used by the original author.
If you already have another compatible `llama-server` build, use that instead.

have no vendored llama.cpp here, yes, good.
keep the external source tree you build from synced to the latest upstream [`ggml-org/llama.cpp`](https://github.com/ggml-org/llama.cpp) or to the fork you choose.

---

## Table of Contents

- [Overview](#overview)
- [Dependencies](#dependencies)
- [Quick Start](#quick-start)
- [Shell Completions](#shell-completions)
- [What It Measures](#what-it-measures)
- [Example Output](#example-output)
- [Results](#results)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Upstream References](#upstream-references)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)
- [Help Wanted](#help-wanted)
- [License](#license)

---

## Overview 🐒

- have same benchmark flow across multiple KV cache types, yes, good.
- have token rate, time to first token, VRAM, and tool-call correctness, yes, good.
- have one JSON file per cache type per run, yes, good.
- have static HTML dashboard from saved results, yes, good.

## Dependencies 🌴

- have Python 3.10+, yes, good.
- have compatible `llama-server` binary from a current llama.cpp-based source tree, yes, good.
- have `.gguf` model file, yes, good.
- have CUDA-capable GPU if you are using a CUDA build, yes, good.
- have `pip` for the Python install path, or `npm` for the wrapper package, yes, good.

## Quick Start 🍌

### (🍌) prerequisites

- have Python 3.10+, yes, good.
- have `llama-server` from a current llama.cpp-compatible checkout or fork, yes, good.
- have `.gguf` model file, yes, good.
- have NVIDIA GPU if you are using a CUDA build, yes, good.

no have? go get. come back. no sadness needed.

### (🍌🍌) install

have install choice, yes, good. pick one:

#### pip

```bash
pip install gnuckle
```

have pip install, yes, good. normal way.

#### npm

```bash
npm install gnuckle
```

have npm package, yes, good. it runs the Python CLI through a local venv.

#### source

```bash
git clone https://github.com/bricklc/gnuckle-ai
cd gnuckle
pip install -e .
```

have source install, yes, good. ape build own banana.

### (🍌🍌🍌) choose runtime

have `llama-server` and model, yes, good. go where they live.

```bash
cd C:\Users\you\llama.cpp
```

linux ape:

```bash
cd ~/llama.cpp
```

have other folder, yes, good. skip the folder dance and pass `--server` and `--model` directly.

### (🍌🍌🍌🍌) run

```bash
gnuckle benchmark
```

or, if you want to be explicit:

```bash
gnuckle benchmark -m model.gguf -s ./build/bin/llama-server
```

gnuckle finds server, yes, good.
gnuckle finds model, yes, good.
ape pick model. ape press enter. gnuckle do rest.

### (🍌🍌🍌🍌🍌) wait

have 4 passes, yes, good. f16, q8_0, q4_0, turbo3. 20 turns each.

ape see phrases. ape see numbers. dis is normal. dis is de way.

### (🍌🍌🍌🍌🍌-🍌) results

```bash
./benchmark_results/
```

have JSON files there, yes, good. open. look at numbers. numbers good. ape happy.

numbers bad. ape learn. also good.

## Shell Completions 🧩

have optional completion support, yes, good. it uses `argcomplete`.

```bash
pip install "gnuckle[completion]"
eval "$(register-python-argcomplete gnuckle)"
```

have different shell flow, yes, good. register the `gnuckle` entry point the same way you would for any `argparse` CLI.

## What It Measures 📏

gnuckle benchmarks [TurboQuant](https://github.com/ggml-org/llama.cpp/discussions/20969) KV cache types on **real agentic tool-calling workloads**.

have synthetic prompts? no, sad.
have real tool calls? yes, good.
have 20 turns? yes, good.
have multi-tool? yes, good.

| Metric | What | Good? |
|---|---|---|
| **tok/s** | generation speed | high. good. |
| **TTFT** | time to first token | low. good. |
| **VRAM** | memory used | low. good. |
| **Tool accuracy** | JSON calls correct? | 100%. good. |
| **Degradation** | speed drop over turns | flat. good. |

cache types: `f16` -> `q8_0` -> `q4_0` -> `turbo3`

turbo3 claim: 4.4x compression. speed stay flat.
gnuckle test if true. claim good? benchmark say yes or no.

## Sample Prompts 🧪

have benchmark samples, yes, good. this is the kind of ape work gnuckle sends through the model:

- "What time is it in Manila and what is the weather there right now?"
- "Based on the weather, should I schedule an outdoor task today? Check my task list first."
- "Create a calendar event called 'Team Standup' for tomorrow at 9AM in Tokyo."
- "List all my tasks and search for open-source LLM quantization news."
- "Check the weather and create an event 'Morning Run' at 6AM tomorrow in Central Park, New York."
- "List all tasks, get time, get weather, and search for Gemma 4 local inference performance."

have tools in the mix, yes, good.

```text
get_current_time -> timezone
get_weather -> location, units
search_web -> query
create_calendar_event -> title, date, location, notes
list_tasks -> filter
```

## Example Output 🦍

```text
  >> ape poke server with stick...
  >> connection established. banana pipeline active.
  >> VRAM idle: [288, 7834] MB
  Turn 01 | tps=11.4  ttft=340ms  tok=42  tools=2  acc=100.0%  vram=[290, 8102]
  Turn 02 | tps=10.8  ttft=380ms  tok=38  tools=3  acc=100.0%  vram=[292, 8240]
  ...
  >> consulting Harambe...
  >> dis is de way...
  Turn 20 | tps=9.2   ttft=520ms  tok=45  tools=2  acc=100.0%  vram=[310, 9100]

  [turbo3] avg=10.12  t1=11.40  t20=9.20  deg=-19.3%
  >> saved: benchmark_turbo3_20260408_104800.json
```

## Results 🍌🌴

```text
benchmark_f16_20260408_102400.json
benchmark_q8_0_20260408_103200.json
benchmark_q4_0_20260408_104000.json
benchmark_turbo3_20260408_104800.json
```

have each file per-turn data, yes, good: tps, ttft, vram, tool accuracy, context size.

4 files. 4 cache types. compare. done.

Run:

```bash
gnuckle visualize ./benchmark_results/
```

## How It Works 🔧

1. gnuckle starts `llama-server` with a cache type, yes, good.
2. gnuckle sends 20 turns of tool-calling prompts, yes, good.
3. gnuckle measures tok/s, TTFT, VRAM, and tool-call JSON accuracy, yes, good.
4. gnuckle kills the server, yes, good.
5. next cache type. repeat. yes, good.
6. save JSON. done.

prompts use real cities: Manila, Tokyo, London, New York, Berlin. cities good.

mock tool responses. benchmark measures model speed, not network. clean, yes, good.

## Troubleshooting 🛠️

| Problem | Fix |
|---|---|
| `gnuckle` not found | have conda/venv active, yes, good. or use `python -m gnuckle`. |
| no `.gguf` found | have wrong folder, no, sad. cd to right folder, or pass `--model`. |
| server no wake up | have wrong `llama-server` path, no, sad. run it manually first. |
| VRAM empty | have `nvidia-smi` work? no, sad. fix that first. |
| ape confused | have `gnuckle benchmark --help`, yes, good. read. |

## Upstream References 🌳

- [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- [TheTom/llama-cpp-turboquant](https://github.com/TheTom/llama-cpp-turboquant.git)
- [Mintplex-Labs/prism-ml-llama.cpp](https://github.com/Mintplex-Labs/prism-ml-llama.cpp.git)
- [TurboQuant discussion](https://github.com/ggml-org/llama.cpp/discussions/20969)
- [Madreag turbo3-cuda](https://github.com/Madreag/turbo3-cuda)
- [Aaryan-Kapoor CPU fork](https://github.com/Aaryan-Kapoor/llama.cpp/tree/turboquant-tq3_0)

## Project Structure 🌴

```text
gnuckle/
  __init__.py        # version
  __main__.py        # python -m gnuckle
  cli.py             # CLI. benchmark. visualize. help.
  benchmark.py       # engine. the banana.
  splash.py          # ASCII art. pretty.
  ape.py             # loading phrases. important.
  visualize.py       # HTML dashboard generator
bin/
  gnuckle.js         # npm wrapper. javascript is banana peel.
pyproject.toml       # pip install
package.json         # npm install
README.md            # this file
```

## Roadmap 🍌

- [x] multi-cache benchmark runner
- [x] auto-detect `llama-server` and `.gguf` in cwd
- [x] CLI entry point
- [x] npm distribution
- [x] `gnuckle visualize` charts
- [x] optional shell completion support
- [x] table of contents and badges
- [ ] turbo4 support
- [ ] multi-model comparison
- [ ] community leaderboard

## Help Wanted 🦍

have more advanced developer, yes, good.
if you want to help, please do. ape not sure what ape do. need more apes do work.

good places to help:

- improve upstream sync guidance for llama.cpp forks
- add more shells or better completion docs
- expand benchmark coverage and result visualization
- tighten install and packaging for power users
- review docs and make them less banana, more clear

## License

MIT. free as in freedom. free as in banana.

---

*by [Gnuckle AI](https://github.com/bricklc/gnuckle-ai)*

*do u kno de way? de way is benchmark.*
