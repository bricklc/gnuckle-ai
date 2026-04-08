# GNUCKLE

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/dark.png">
  <source media="(prefers-color-scheme: light)" srcset="assets/readme/light.png">
  <img alt="Gnuckle banner" src="assets/readme/light.png">
</picture>

```
    ██████╗ ███╗   ██╗██╗   ██╗ ██████╗██╗  ██╗██╗     ███████╗
   ██╔════╝ ████╗  ██║██║   ██║██╔════╝██║ ██╔╝██║     ██╔════╝
   ██║  ███╗██╔██╗ ██║██║   ██║██║     █████╔╝ ██║     █████╗
   ██║   ██║██║╚██╗██║██║   ██║██║     ██╔═██╗ ██║     ██╔══╝
   ╚██████╔╝██║ ╚████║╚██████╔╝╚██████╗██║  ██╗███████╗███████╗
    ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝
```

**Agentic AI Benchmark for llama.cpp KV Cache Quantization**

*ape drag knuckle on keyboard. benchmark happen.*

*accidentally GNU, intentionally simian.*

---

## Quick Start

### 1. have things

- Python 3.10+. yes. good.
- `llama-server` built. yes. good.
- `.gguf` model file. yes. good.
- NVIDIA GPU. yes. good.

no have? go get. come back.

### 2. install gnuckle

```bash
pip install gnuckle
```

have gnuckle. yes. good.

### 3. go to folder

go where llama-server and model live.

```bash
cd C:\Users\you\llama.cpp
```

linux ape:

```bash
cd ~/llama.cpp
```

folder have server. folder have model. yes. good.

### 4. run

```bash
gnuckle benchmark
```

gnuckle find server. yes. good.
gnuckle find model. yes. good.
ape pick model. ape press enter.
gnuckle do rest.

### 5. wait

4 passes run. f16, q8_0, q4_0, turbo3. 20 turns each.

ape see phrases. ape see numbers. dis is normal. dis is de way.

### 6. results

```
./benchmark_results/
```

JSON files there. open. look at numbers. numbers good. ape happy.

numbers bad. ape learn. also good.

---

## What dis

gnuckle benchmark [TurboQuant](https://github.com/ggml-org/llama.cpp/discussions/20969) KV cache types on **real agentic tool-calling workloads**.

not synthetic prompts. real tool calls. 20 turns. multi-tool.

| Metric | What | Good? |
|---|---|---|
| **tok/s** | generation speed | high. good. |
| **TTFT** | time to first token | low. good. |
| **VRAM** | memory used | low. good. |
| **Tool accuracy** | JSON calls correct? | 100%. good. |
| **Degradation** | speed drop over turns | flat. good. |

cache types: `f16` -> `q8_0` -> `q4_0` -> `turbo3`

turbo3 claim: 4.4x compression. speed stay flat. gnuckle test if true.

---

## Install

### pip

```bash
pip install gnuckle
```

normal way. yes. good.

### npm

```bash
npm install gnuckle
```

npm package run python program. yes really. no question. dis is de way.

### source

```bash
git clone https://github.com/gnuckle-ai/gnuckle
cd gnuckle
pip install -e .
```

ape build own banana. also good.

---

## Options

```bash
gnuckle benchmark                       # auto-find everything. easy. good.
gnuckle benchmark -m model.gguf         # skip model picker
gnuckle benchmark -m model.gguf -s ./build/bin/llama-server   # skip all prompts
gnuckle benchmark -t 10                 # 10 turns. faster. less data.
gnuckle benchmark -p 9090              # different port
gnuckle benchmark --help               # ape need help. no shame.
gnuckle visualize ./benchmark_results/  # writes turboquant_benchmark_dashboard.html
gnuckle --version                      # gnuckle 0.1.0
```

---

## What ape see

```
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

---

## Output

```
benchmark_f16_20260408_102400.json
benchmark_q8_0_20260408_103200.json
benchmark_q4_0_20260408_104000.json
benchmark_turbo3_20260408_104800.json
```

each file have per-turn: tps, ttft, vram, tool accuracy, context size.

4 files. 4 cache types. compare. done.

---

## How it work

1. gnuckle start `llama-server` with cache type
2. send 20 turns of tool-calling prompts (weather, calendar, search, tasks)
3. measure tok/s, TTFT, VRAM, tool call JSON accuracy
4. kill server
5. next cache type. repeat.
6. save JSON. done.

prompts use real cities: Manila, Tokyo, London, New York, Berlin.

mock tool responses. benchmark measure model speed. not network. clean.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `gnuckle` not found | activate conda/venv. yes. try again. |
| no .gguf found | wrong folder. cd to right folder. |
| server no wake up | check llama-server path. run it manually first. |
| VRAM empty | `nvidia-smi` work? no? fix that first. |
| ape confused | `gnuckle benchmark --help`. read. yes. good. |

---

## TurboQuant

[TurboQuant](https://github.com/ggml-org/llama.cpp/discussions/20969) compress KV cache 4.4x. community say speed stay flat.

gnuckle test this on real agent workloads. tool calls. multi-turn. long context.

turbo3 hold up? run gnuckle. find out.

- [Madreag turbo3-cuda](https://github.com/Madreag/turbo3-cuda)
- [Aaryan-Kapoor CPU fork](https://github.com/Aaryan-Kapoor/llama.cpp/tree/turboquant-tq3_0)

---

## Project structure

```
gnuckle/
  __init__.py        # version
  __main__.py        # python -m gnuckle
  cli.py             # CLI. benchmark. visualize. help.
  benchmark.py       # engine. the banana.
  splash.py          # ASCII art. pretty.
  ape.py             # 50+ loading phrases. important.
bin/
  gnuckle.js         # npm wrapper. javascript is banana peel.
pyproject.toml       # pip install
package.json         # npm install
```

---

## Roadmap

- [x] multi-cache benchmark runner
- [x] auto-detect llama-server and .gguf in cwd
- [x] CLI entry point
- [x] npm distribution
- [x] `gnuckle visualize` charts
- [ ] turbo4 support
- [ ] multi-model comparison
- [ ] community leaderboard

---

## License

MIT. free as in freedom. free as in banana.

---

*by [Gnuckle AI](https://gnuckle.ai)*

*do u kno de way? de way is benchmark.*
