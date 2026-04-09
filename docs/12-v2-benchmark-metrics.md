# 12 V2 Benchmark Metrics

## Purpose

This note defines the benchmark dimensions, success metrics, and reporting targets for `gnuckle` v2.

It answers:

- what we are measuring
- why it matters
- what must be shown to compare models fairly

## Primary Benchmark Dimensions

### 1. Task Capability

What:

- whether the model completes the assigned bounded task

Why:

- fast but unreliable agents are not useful

Required metrics:

- `task_success_rate`
- `verification_pass_rate`
- `episode_score`

### 2. Tool Choice Quality

What:

- whether the model chooses the correct tool from the visible tool menu

Why:

- real agent workloads are damaged by wrong or unnecessary tool calls

Required metrics:

- `tool_selection_precision`
- `wrong_tool_calls`
- `unnecessary_tool_calls`
- `disallowed_tool_calls`

### 3. Constitution Under Load

What:

- whether the model preserves required behavioral rules from the system prompt as context and tool noise grow

Why:

- agents that finish tasks but lose behavioral discipline are not dependable

Required metrics:

- `constitution_rules_total`
- `constitution_rules_followed`
- `constitution_violations`
- `constitution_adherence_rate`
- `first_constitution_drift_turn`
- `constitution_drift_after_tool_calls`
- `constitution_drift_after_context_percent`

### 4. Prompt and Memory Integrity

What:

- whether the model still remembers the original query, persistent preferences, and loaded memory facts after long sessions

Why:

- local-agent reliability depends on more than immediate task execution

Required metrics:

- `original_query_retention`
- `preference_retention`
- `memory_recall_accuracy`
- `contradiction_rate`
- `integrity_score`

### 5. Runtime Performance

What:

- how long the agent takes to produce results

Why:

- capability without usable speed is not practical

Required metrics:

- `ttft_ms`
- `tokens_per_second`
- `wall_clock_ms`
- `avg_turn_latency_ms`
- `episodes_per_hour`

### 6. Resource Pressure

What:

- how much token budget and hardware budget the run consumes

Why:

- local users need to know whether the model fits and remains stable

Required metrics:

- `provider_input_tokens`
- `provider_output_tokens`
- `provider_total_tokens`
- `context_tokens_estimate`
- `context_window`
- `context_percent_used`
- `vram_peak_mb`
- `vram_steady_mb`
- `ram_peak_mb`

## Integrity Decay Curve

V2 should explicitly measure reliability decay under larger memory loads.

This curve should report:

- `stable_zone`
- `drift_zone`
- `failure_zone`

And the actionable threshold:

- `MRMB`
  - `Maximum Reliable Memory Budget`

Definition:

- the largest injected memory budget where benchmark reliability remains above the configured threshold

## Minimum Reliability Threshold

The default threshold for MRMB should be documentable and visible.

Suggested default:

- `task_success_rate >= 0.90`
- `constitution_adherence_rate >= 0.95`
- `original_query_retention >= 0.90`
- `memory_recall_accuracy >= 0.90`
- `contradiction_rate <= 0.05`

## What The Leaderboard Should Show

The model comparison view must expose:

- model
- cache type
- workflow suite
- task success
- verification
- tool selection precision
- constitution adherence
- integrity score
- MRMB
- TTFT
- wall-clock time
- provider total tokens
- peak context estimate
- VRAM peak

## JSON Visibility Requirements

The JSON output must preserve:

- raw trace
- raw failure counters
- raw score components
- raw token and context fields
- raw VRAM and RAM fields when available

## HTML Visibility Requirements

The HTML output must make visible:

- benchmark outcome
- score components
- tool selection quality
- constitution adherence
- integrity decay signals
- token/context budget
- VRAM/RAM pressure
- trace timeline

## Summary

V2 must not be a vague “agent benchmark”.

It must clearly show:

- can the model do the work?
- can it keep behaving correctly?
- can it keep remembering?
- how expensive is that in context and VRAM?

