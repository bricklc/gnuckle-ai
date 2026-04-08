# 06 V1 Success Metrics

## Purpose

This note defines the **non-negotiable success metrics** for the `gnuckle` v1 agentic benchmark.

These metrics are the acceptance target for implementation.

They are intentionally separated from the build plan so that:

- implementation details can evolve
- scope can stay controlled
- evaluation criteria do not drift

If a future change wants to alter these metrics, it must do so in a new numbered note instead of silently rewriting the target.

## Lock Rule

For v1, the metrics in this note are normative.

That means:

- they must be present in the implementation
- they must be present in the output schema
- they must be visible in reports
- they must not be removed or redefined during implementation without a new numbered design note

## Core Purpose Metrics

The benchmark exists to answer three questions.

### 1. Can the model complete bounded agentic work?

Required metric:

- `TaskSuccessRate`

Definition:

- fraction of episodes that satisfy the workflow success rule

Required output:

- per-episode `task_completed`
- aggregate `success_rate`

### 2. Can the model complete work correctly, not just claim success?

Required metric:

- `VerificationPassRate`

Definition:

- fraction of episodes with required verification that actually pass verification

Required output:

- per-episode `verification_passed`
- aggregate `verification_rate`

### 3. Is the model operationally usable?

Required metrics:

- `MedianEpisodeMs`
- `P95EpisodeMs`
- `MedianTurnLatencyMs`
- `EpisodesPerHour`
- `SuccessfulEpisodesPerHour`

Definition:

- raw runtime measurements of practical usability under the benchmark suite

Required output:

- per-episode performance block
- aggregate runtime summary

## Required V1 Score Components

The derived score must remain simple and auditable.

V1 requires these score components:

- `TaskSuccess`
- `ConstraintObedience`
- `Verification`
- `Efficiency`

### TaskSuccess

Definition:

- `1.0` if workflow success rule is met
- `0.0` otherwise

### ConstraintObedience

Definition:

- penalizes invalid tool calls
- penalizes malformed finish behavior
- penalizes over-budget or disallowed runtime behavior

### Verification

Definition:

- `1.0` if required verification passed
- `0.0` if required verification failed or was skipped

### Efficiency

Definition:

- bounded penalty for excessive turns
- bounded penalty for excessive tool calls
- bounded penalty for excessive wall-clock time

## Required V1 Formula

The v1 episode score must use this formula:

```text
EpisodeScore =
  0.55 * TaskSuccess
  0.20 * ConstraintObedience
  0.15 * Verification
  0.10 * Efficiency
```

The raw components must remain visible.

The benchmark must not replace the components with only one opaque number.

## Required Per-Episode Metrics

Every episode must record these fields.

### Outcome

- `status`
- `failure_reason`
- `task_completed`
- `verification_passed`
- `turns_used`
- `tool_calls_used`

### Timing

- `wall_clock_ms`
- `time_to_first_action_ms`
- `time_to_finish_ms`
- `avg_turn_latency_ms`
- `max_turn_latency_ms`
- `tool_time_ms_total`
- `model_time_ms_total`
- `verification_time_ms`

### Trace Integrity

- full ordered `trace`
- visible tool calls
- visible tool results
- explicit final result

### Scoring

- `task_success`
- `constraint_obedience`
- `verification`
- `efficiency`
- `episode_score`

## Required Aggregate Metrics

Every run summary must include these fields.

### Capability

- `success_rate`
- `verification_rate`

### Effort and Shape

- `avg_turns`
- `avg_tool_calls`

### Performance

- `median_episode_ms`
- `p95_episode_ms`
- `median_turn_latency_ms`
- `p95_turn_latency_ms`
- `episodes_per_hour`
- `successful_episodes_per_hour`

### Reliability

- failure distribution by `failure_reason`

## Required Persistence Metrics

When repeated-session mode is active, the run must also record:

- `episode_index`
- visible history growth estimate
- success delta versus first episode
- latency delta versus first episode
- first regression point, if present

V1 persistence reporting must support:

- identifying whether the model stays stable across repeated episodes
- identifying whether latency becomes unacceptable before capability collapses

## Required UX Success Metrics

The implementation must preserve the current `gnuckle` usability contract.

These are acceptance metrics, not just design preferences.

Required:

- existing profiles still load without migration
- interactive model picker still works when `--model` is omitted
- server picker or auto-detection still works when `--server` is omitted
- `gnuckle benchmark` remains the main entrypoint
- `gnuckle visualize` still works on benchmark output
- ape-themed copy remains recognizably consistent

## Required Failure Separation

The benchmark must distinguish harness failure from model failure.

Required failure labels:

- `task_unsolved`
- `verification_failed`
- `verification_missing`
- `max_turns`
- `timeout`
- `invalid_tool_call`
- `malformed_finish`
- `harness_error`

Required failure event counters when applicable:

- `invalid_tool_calls`
- `retry_events`
- `malformed_finish_events`
- `execution_failures`
- `permission_denials`
- `synthetic_tool_results`

For tool-using benchmark modes, required tool-choice metrics when applicable:

- `wrong_tool_calls`
- `unnecessary_tool_calls`
- `disallowed_tool_calls`
- `tool_selection_precision`

This is mandatory because infrastructure problems must not be scored as model incapability.

## Required Reporting Visibility

The following must be visible in the generated outputs:

### JSON

- raw episode trace
- raw timing fields
- raw score components
- aggregate metrics

### HTML

- overall score summary
- capability summary
- runtime summary
- failure distribution
- per-episode detail view

The HTML may summarize, but it must not hide the raw meaning of the run.

## Minimal Acceptance Gate

V1 is not done until all of these are true:

1. `TaskSuccessRate` is recorded
2. `VerificationPassRate` is recorded
3. per-episode timing fields are recorded
4. aggregate runtime metrics are recorded
5. explicit failure taxonomy is recorded
6. raw trace is recorded
7. score components are recorded separately from final score
8. current `gnuckle` UX contract still works

If even one of these is missing, v1 is not benchmark-valid.

## Summary

These metrics are the fixed target for `gnuckle` v1.

Implementation may change.
Internal module layout may change.
Prompt text may change.

These metrics may not silently change.
