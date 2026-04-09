# Gnuckle Docs Index

Numbered docs live here so the order stays explicit.

- `00-index.md`
  - docs list and ordering rule
- `01-agentic-loop-benchmark.md`
  - first pass on a real agent loop benchmark design
- `02 - agentic-benchmark-spec.md`
  - fuller benchmark specification
- `03-runtime-roadmap.md`
  - practical implementation roadmap for a lighter v1
- `04 - minimal-agentic-harness-ground-truth.md`
  - normative technical behavior for the minimal harness
- `05-v1-build-plan.md`
  - concrete implementation plan, phases, specs, and success metrics
- `06-v1-success-metrics.md`
  - locked v1 acceptance metrics and reporting requirements
- `07-focused-session-01-first-agentic-episode.md`
  - active focused implementation target for the first runnable agentic loop
- `08-implementation-workflow-rules.md`
  - execution rules for building against the locked v1 metrics without scope drift
- `09-focused-session-01-status.md`
  - status note for the first focused implementation slice
- `10-openclaude-failure-handling-grounding.md`
  - minimal failure-handling rules borrowed from the OpenClaude pattern
- `11-v2-agentic-benchmark-plan.md`
  - purpose and scope of the v2 benchmark
- `12-v2-benchmark-metrics.md`
  - benchmark dimensions, leaderboard metrics, and reporting requirements for v2
- `13-integrity-decay-and-cul.md`
  - named definitions for Constitution Under Load, Integrity Decay Curve, and MRMB
- `14-v2-visualizer-and-postrun-flow.md`
  - visualizer requirements and post-run browser prompt contract
- `15-benchmark-system-intent.md`
  - starting hypothesis, intent, and what the benchmark system is really testing for
- `16-openclaude-reference-map.md`
  - canonical source-anchor map for the OpenClaude behaviors grounding the benchmark

- `memory.md`
  - agent memory: project intent, self-correction rules, active facts (append-only, brief)

Rule:
- add new notes as `02-...`, `03-...`, `04-...`
- keep earlier notes even when superseded
- write a new numbered note when the idea materially changes
