# 05 V1 Build Plan

## Purpose

This note defines the v1 implementation plan for `gnuckle` as a **small, repeatable agentic benchmark harness**.

The normative v1 acceptance target lives in:

- `docs/06-v1-success-metrics.md`

This build plan explains how to get there.

The purpose is not to build a full agent platform.

The purpose is:

- approximate how a local model behaves inside a bounded agent loop
- keep the runtime simple enough to trust and maintain
- let users compare models, quantizations, and cache strategies under equal conditions
- produce leaderboard-friendly outputs with clear traceability

The benchmark should let a user answer:

- which model completes bounded tool-using tasks more reliably
- which model slows down or regresses first as session context grows
- which model is fast enough to be useful, not just capable on paper

## Product Continuity Rules

The v1 build must merge with how `gnuckle` already works today.

This is not a new product with a different tone, different entrypoint, or different setup story.

The following are required:

1. ape voice stays consistent
- CLI copy, prompts, status text, and dashboard labels should still sound like `gnuckle`
- new agentic features should feel like the same tool, not a sterile rewrite

2. easy path stays intact
- interactive model picker stays available when `--model` is omitted
- server picker and auto-detection stay available when `--server` is omitted
- default output behavior stays simple

3. profile flow stays first-class
- existing `--profile` support remains valid
- agentic settings should be loadable from the same profile concept, not from a disconnected config system
- new profile keys should extend the current format instead of replacing it

4. current CLI stays recognizable
- `gnuckle benchmark` remains the main command
- new functionality should come in through flags and modes, not through a second unrelated entrypoint

5. legacy behavior must remain usable
- existing cache benchmarks and current JSON/dashboard flows must still run
- users should not need to relearn the tool just to access the new harness

The plan should therefore treat the current UX as a constraint, not just the current codebase.

## V1 Scope

V1 is intentionally narrow.

It should include:

- persistent session state
- one injected event per episode
- bounded assistant -> tool -> assistant loop
- a very small deterministic tool surface
- explicit `finish` or explicit failure
- structured episode trace
- simple performance metrics
- simple scoring
- simple leaderboard aggregation

It should not include yet:

- full multi-agent orchestration
- remote execution
- browser automation
- large memory systems
- large connector ecosystems
- real chat platform integrations

## V1 Success Definition

V1 counts as working only if all of the following are true:

1. a benchmark run can execute from event injection to explicit result without manual intervention
2. every episode ends as one of:
   - `completed`
   - `failed`
   - `max_turns`
   - `timeout`
   - `harness_error`
3. every episode emits a structured trace
4. tool calls and tool results are visible in the trace
5. timing is recorded per episode
6. repeated episodes can reuse the same session state
7. two models can be compared under the same workflow suite and settings

If any of those are missing, the harness is not benchmark-valid.

The exact locked metrics and reporting requirements are defined in:

- `docs/06-v1-success-metrics.md`

## Product Shape

`gnuckle` should expose two benchmark families:

1. `legacy`
- the current turn-oriented benchmark
- useful for quick smoke tests and existing users

2. `agentic`
- the new bounded workflow benchmark
- the primary future direction

This keeps current functionality alive while building the real harness in parallel.

## UX Contract

The user experience should remain:

- pick a model if none is provided
- pick or auto-detect a server if none is provided
- optionally load a profile
- run benchmark
- get JSON plus static HTML

The new agentic mode must fit inside that flow.

That means the likely user shape is:

- `gnuckle benchmark`
- `gnuckle benchmark --mode agentic`
- `gnuckle benchmark --profile .gnuckle\\profiles\\my-profile.json`

Not:

- a separate benchmark binary
- a separate config universe
- a separate dashboard concept

## Profile Compatibility

The current profile system should become the anchor for runtime configuration.

The existing profile shape already supports path-like settings such as:

- `model_path`
- `server_path`
- `scan_dir`
- `output_dir`

Agentic v1 should extend that same profile family with optional keys like:

```json
{
  "benchmark_mode": "agentic",
  "workflow_suite": "default",
  "session_mode": "fresh_session",
  "max_turns": 10,
  "verification": true
}
```

Rules:

- old profiles must keep working
- new fields must be optional
- the benchmark must still prompt interactively if the profile is partial
- the profile editor should eventually expose agentic settings using the same terminal UX

## Model Selection Contract

The model selector is part of `gnuckle` usability and should remain part of the agentic benchmark.

Required behavior:

- if `--model` is omitted, continue scanning for `.gguf` files
- present the current picker UI
- allow agentic mode to use the selected model without extra setup steps

The workflow suite must be selected separately from the model.

That keeps the mental model clean:

- model picker answers "what model am ape testing?"
- workflow suite answers "what work does ape make model do?"

## Minimal Runtime Contract

Each `agentic` episode must follow this contract:

1. load or create session state
2. inject one event
3. build visible context from:
   - system prompt
   - session history
   - optional summary block
   - current event
   - tool definitions
4. ask model for next action
5. if the model emits a tool call:
   - execute tool
   - append tool result
   - continue
6. if the model emits `finish`:
   - finalize episode
   - optionally verify
   - record explicit result
7. if turn limit or timeout is reached:
   - record explicit failure result

This loop is the core benchmark behavior. Everything else is support code.

## Required V1 Tool Surface

The v1 tool surface should stay small and deterministic.

Required:

- `search`
- `read_file`
- `edit_file`
- `run_test`
- `finish`

Deferred:

- `spawn_agent`

Rationale:

- this tool set is enough to benchmark bounded coding-style agent behavior
- it matches the practical direction in `04 - minimal-agentic-harness-ground-truth.md`
- it avoids building a decorative but unstable tool zoo

## Required V1 Modes

The first two operating modes should be:

1. `fresh_session`
- each episode starts with clean state

2. `full_history`
- each episode reuses the same session trace

`summary_history` can come next once the baseline loop is stable.

## Required V1 Workflow Shape

Add a compact workflow manifest:

- `gnuckle/workflows.json`

Each workflow entry should include:

```json
{
  "workflow_id": "coding_fix_001",
  "title": "Fix a failing assertion",
  "slice": "coding",
  "difficulty": "easy",
  "system_prompt": "string",
  "event": {
    "event_type": "interactive_request",
    "payload": {
      "text": "string"
    }
  },
  "allowed_tools": ["search", "read_file", "edit_file", "run_test", "finish"],
  "max_turns": 10,
  "verification": {
    "required": true,
    "method": "run_test"
  },
  "success_rule": {
    "type": "test_pass"
  }
}
```

V1 workflow count should stay small:

- target: `6` to `12` workflows

That is enough for a leaderboard without making the suite hard to iterate.

## Required V1 Output Shape

### Episode Trace

Each episode JSON should include:

```json
{
  "episode_id": "string",
  "workflow_id": "string",
  "mode": "fresh_session",
  "status": "completed",
  "failure_reason": null,
  "task_completed": true,
  "verification_passed": true,
  "turns_used": 4,
  "tool_calls_used": 3,
  "performance": {
    "wall_clock_ms": 0,
    "time_to_first_action_ms": 0,
    "time_to_finish_ms": 0,
    "avg_turn_latency_ms": 0,
    "max_turn_latency_ms": 0,
    "tool_time_ms_total": 0,
    "model_time_ms_total": 0,
    "verification_time_ms": 0
  },
  "scores": {
    "task_success": 1.0,
    "constraint_obedience": 1.0,
    "verification": 1.0,
    "efficiency": 0.8,
    "episode_score": 0.95
  },
  "trace": []
}
```

### Run Summary

Each suite run should include:

```json
{
  "run_id": "string",
  "benchmark_mode": "agentic",
  "model_id": "string",
  "episodes": [],
  "aggregate": {
    "success_rate": 0.0,
    "verification_rate": 0.0,
    "avg_turns": 0.0,
    "avg_tool_calls": 0.0,
    "median_episode_ms": 0,
    "p95_episode_ms": 0,
    "median_turn_latency_ms": 0,
    "p95_turn_latency_ms": 0,
    "episodes_per_hour": 0.0,
    "successful_episodes_per_hour": 0.0
  }
}
```

## Required V1 Scoring

The scoring must stay interpretable.

Primary:

- `TaskSuccess`

Secondary:

- `ConstraintObedience`
- `Verification`
- `Efficiency`

Suggested v1 formula:

```text
EpisodeScore =
  0.55 * TaskSuccess
  0.20 * ConstraintObedience
  0.15 * Verification
  0.10 * Efficiency
```

Definitions:

- `TaskSuccess`
  - `1.0` if the workflow success condition is met
  - `0.0` otherwise
- `ConstraintObedience`
  - penalize invalid tools, over-budget loops, malformed finish behavior
- `Verification`
  - `1.0` when required verification passed
  - `0.0` when required verification was skipped or failed
- `Efficiency`
  - relative penalty for excessive turns, excessive tool calls, or excessive wall time versus suite thresholds

The benchmark must preserve raw metrics. The score is a summary, not a replacement.

## Required V1 Performance Metrics

Every episode must record:

- `wall_clock_ms`
- `time_to_first_action_ms`
- `time_to_finish_ms`
- `avg_turn_latency_ms`
- `max_turn_latency_ms`
- `tool_time_ms_total`
- `model_time_ms_total`
- `verification_time_ms`

Every run must aggregate:

- `median_episode_ms`
- `p95_episode_ms`
- `median_turn_latency_ms`
- `p95_turn_latency_ms`
- `episodes_per_hour`
- `successful_episodes_per_hour`

These metrics are required because local-model users are comparing both capability and usability.

## Failure Taxonomy

V1 should classify failures explicitly.

Required failure reasons:

- `task_unsolved`
- `verification_failed`
- `verification_missing`
- `max_turns`
- `timeout`
- `invalid_tool_call`
- `malformed_finish`
- `harness_error`

This separation matters because harness failures must not be blamed on the model.

## Required Modules

The first implementation should add these Python modules under `gnuckle/`:

- `agentic_types.py`
  - workflow, event, session, turn, episode, run summary types
- `workflow_loader.py`
  - load and validate `workflows.json`
- `session_store.py`
  - file-backed session load/save
- `agentic_runtime.py`
  - main bounded loop
- `tool_executor.py`
  - deterministic tool execution
- `verifier.py`
  - workflow verification hooks
- `agentic_scorer.py`
  - per-episode and aggregate scoring

Minimal CLI changes:

- `gnuckle benchmark --mode legacy`
- `gnuckle benchmark --mode agentic`
- optional:
  - `--workflow-suite`
  - `--session-mode`

CLI compatibility rules:

- `gnuckle benchmark` without `--mode` should preserve the current default behavior until the agentic mode is mature
- once agentic mode is stable, default behavior may change only if profiles, model selection, and existing quick-run UX still feel familiar
- `visualize` should continue to work on both legacy and agentic outputs

## Phase Plan

### Phase 1. Runner Stabilization

Purpose:

- make current benchmark execution reliable and inspectable

Scope:

- keep warmup before measured turns
- keep split-view dashboard
- fix Windows splash encoding
- auto-open static HTML after visualize

Success metrics:

- zero false-start episodes caused by model-loading race
- `visualize` writes and opens the report on Windows
- turn cards show telemetry and truncated prompt/response previews

### Phase 2. Workflow Foundation

Purpose:

- move from loose prompts to explicit workflow objects

Scope:

- add `gnuckle/workflows.json`
- add workflow loader and validation
- define `6` to `12` workflows
- add workflow-level success rules and verification rules
- define how workflow suite selection fits into current profile and CLI behavior

Success metrics:

- workflow suite loads without manual editing
- invalid workflow files fail fast with clear errors
- one benchmark run can enumerate and execute workflows deterministically
- users can choose a workflow suite without losing the existing easy path

### Phase 3. Core Agentic Runtime

Purpose:

- replace isolated turn scoring with bounded episode scoring

Scope:

- implement session-backed runtime loop
- support `search`, `read_file`, `edit_file`, `run_test`, `finish`
- add explicit stop reasons
- emit structured episode JSON
- keep the current splash, tone, and picker flow coherent in agentic mode

Success metrics:

- one coding workflow can run from event injection to explicit result
- trace always includes assistant action, tool action, tool result, and final result
- no episode exits without a terminal status
- agentic mode feels like current `gnuckle`, not a second tool bolted on top

### Phase 4. Verification and Scoring

Purpose:

- make benchmark results trustworthy and comparable

Scope:

- implement verification hooks
- implement episode score fields
- implement aggregate run summary
- add failure taxonomy rollups

Success metrics:

- workflows with required verification do not count as full success without passing verification
- aggregate summary reports success rate, verification rate, and failure distribution
- two models can be compared with the same suite output schema

### Phase 5. Persistence Comparison

Purpose:

- measure context survival, not just single-episode success

Scope:

- add `fresh_session`
- add `full_history`
- add repeated-episode execution
- record visible context growth and regression points

Success metrics:

- same workflow suite can run in both session modes
- reports show success deltas and latency deltas by episode index
- first regression point can be identified from the output

### Phase 6. Leaderboard Output

Purpose:

- make results usable for head-to-head model comparison

Scope:

- static aggregate HTML
- model comparison tables
- slice summaries
- operational classification:
  - `interactive_usable`
  - `slow_but_viable`
  - `background_only`
  - `not_operationally_viable`

Success metrics:

- one report can compare multiple runs side by side
- users can identify best model by slice and by overall score
- raw metrics remain visible next to derived score

## First Runnable Milestone

The first milestone should stay very small:

1. create one empty session
2. inject one coding event
3. allow:
   - `read_file`
   - `edit_file`
   - `run_test`
   - `finish`
4. record the full trace
5. write explicit episode result

If this milestone works, the harness is already useful enough to compare models on bounded coding tasks.

## Second Runnable Milestone

The second milestone is:

1. reuse the same session
2. inject a second event
3. preserve prior history
4. record success retention and latency inflation

That is the point where `gnuckle` starts answering the repeated-agent question instead of just the single-episode question.

## Acceptance Checklist

Before v1 is called usable, confirm:

- workflow manifest exists and validates
- one episode can run end-to-end
- episode trace is always written
- verification is recorded
- aggregate summary is written
- repeated-session mode works
- dashboard renders both raw metrics and derived scores
- legacy mode still works
- existing profiles still load
- interactive model selection still works
- tone and command flow remain recognizably `gnuckle`

## Summary

The correct v1 is not a giant runtime.

It is:

- small
- explicit
- repeatable
- inspectable
- comparable

If `gnuckle` can run a short bounded agent loop with clear traces, clear metrics, and equal-budget comparison, it is already doing the job it needs to do.
