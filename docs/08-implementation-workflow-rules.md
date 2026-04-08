# 08 Implementation Workflow Rules

## Purpose

This note defines the final workflow rules for implementing the `gnuckle` v1 agentic benchmark.

These rules exist to keep implementation disciplined against:

- `docs/05-v1-build-plan.md`
- `docs/06-v1-success-metrics.md`
- `docs/07-focused-session-01-first-agentic-episode.md`

This note is not another design proposal.

It is the execution rulebook.

## Rule 1: Build Against The Locked Metrics

Implementation must target the locked metrics in:

- `docs/06-v1-success-metrics.md`

Do not optimize for aesthetic completeness, speculative features, or framework resemblance.

Build only what is needed to satisfy the required:

- outcome metrics
- timing metrics
- trace integrity
- aggregate reporting
- UX continuity

## Rule 2: One Focused Session, One Runtime Win

Each focused session must have exactly one primary runtime goal.

For the current session, that goal is:

- one runnable bounded agentic episode

If a change does not help complete that goal, it should be deferred.

## Rule 3: Preserve Current Gnuckle UX

Every implementation change must preserve:

- `gnuckle benchmark` as the main command
- profile compatibility
- model picker behavior when `--model` is omitted
- server picker or detection when `--server` is omitted
- ape-themed copy and recognizable CLI tone

The new harness must feel like `gnuckle`, not a second tool hidden in the repo.

## Rule 4: Legacy Must Keep Working

The current benchmark path must continue to run while the agentic path is being added.

Required:

- legacy benchmark still executes
- legacy profiles still load
- legacy visualization still works

Breaking legacy behavior for unfinished agentic work is not allowed.

## Rule 5: Add Smallest Valid Slice First

The first implementation slice must be the smallest version that is benchmark-valid.

That means:

- one workflow
- one session
- one event
- bounded tool loop
- explicit result
- structured trace

Do not add:

- multiple slices
- multiple suites
- delegation
- persistence comparison
- leaderboard logic

before the first valid episode exists.

## Rule 6: Prefer Explicit Data Structures Over Cleverness

The runtime should prefer:

- explicit JSON-compatible dicts or typed records
- explicit status values
- explicit failure reasons
- explicit trace entries

Avoid hidden state and implicit behavior.

This benchmark must be easy to inspect after the fact.

## Rule 7: Separate Harness Failure From Model Failure

If the harness fails, record:

- `harness_error`

Do not classify harness bugs as model incapability.

This rule is mandatory because benchmark trust depends on it.

## Rule 8: Every Episode Must Terminate Cleanly

Every episode must end as one of:

- `completed`
- `failed`
- `max_turns`
- `timeout`
- `harness_error`

Silent exits, partial traces, or missing terminal status are implementation failures.

## Rule 9: Trace Is Mandatory

Every runnable episode must emit a trace that shows:

- assistant step
- tool call
- tool result
- final result

If the trace is incomplete, the episode is not benchmark-valid.

## Rule 10: Raw Metrics Stay Visible

The benchmark may compute derived scores, but must keep the raw fields visible.

Do not hide:

- timing
- turns
- tool calls
- failure reason
- verification result

The report can summarize them, but the JSON must preserve them.

## Rule 11: Verification Must Be Explicit

If a workflow requires verification, success must distinguish:

- model claimed success
- verification passed

Do not credit full success without explicit verification when verification is required.

## Rule 12: Build Order Is Fixed

Implementation order should remain:

1. workflow manifest
2. core types
3. workflow loader
4. session store
5. tool executor
6. bounded runtime loop
7. episode result output
8. verification
9. scoring
10. persistence modes
11. leaderboard output

If a later step blocks an earlier step, simplify the later step. Do not expand scope.

## Rule 13: New Docs Must Reduce Ambiguity

Create a new numbered doc only when it does one of these:

- locks a schema
- locks a metric
- locks a focused session target
- records a migration or compatibility contract

Do not create docs for things that should simply be code.

## Rule 14: Success Means Acceptance Gate, Not Personal Satisfaction

The implementation is successful only when it satisfies the acceptance gates in:

- `docs/06-v1-success-metrics.md`
- `docs/07-focused-session-01-first-agentic-episode.md`

Not when it merely feels complete.

## Rule 15: Stop Scope Drift Early

If a task begins expanding into:

- delegation
- memory retrieval systems
- browser tooling
- UI redesign
- large workflow suites

without first completing the active focused session, stop and defer it.

Scope drift is the main risk to delivery.

## Summary

The implementation discipline is:

- preserve current `gnuckle`
- build the smallest valid agentic loop
- record everything explicitly
- keep metrics locked
- defer everything that is not required for the active acceptance gate
