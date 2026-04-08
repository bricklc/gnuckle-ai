# 07 Focused Session 01: First Agentic Episode

## Purpose

This note defines the next focused implementation session for `gnuckle`.

The goal is to build the first real agentic benchmark path without expanding scope.

This is the smallest feature that turns `gnuckle` from a turn benchmark into a real bounded harness.

## Why This Is Next

This feature comes next because:

- it is the smallest end-to-end runtime slice
- all later agentic work depends on it
- it forces the core data model into place
- it gives the project a real benchmark trace instead of only a design plan

If this loop is not real, later scoring, persistence, and leaderboard work will be decorative.

## Focus Rule

This session should focus on exactly one path:

1. load or create one session
2. load one workflow from the workflow manifest
3. inject one coding event
4. let the model operate inside a bounded tool loop
5. record the full trace
6. emit an explicit episode result

No broader scope should be added during this session unless it is required to make the path runnable.

## Required Tool Surface For This Session

Only these tools should be implemented in this session:

- `read_file`
- `edit_file`
- `run_test`
- `finish`

`search` is deferred unless the first workflow truly requires it.

`spawn_agent` is explicitly out of scope for this session.

## Required Files

This session should create or update:

- `gnuckle/workflows.json`
- `gnuckle/agentic_types.py`
- `gnuckle/workflow_loader.py`
- `gnuckle/session_store.py`
- `gnuckle/tool_executor.py`
- `gnuckle/agentic_runtime.py`

Optional only if required for integration:

- `gnuckle/benchmark.py`
- `gnuckle/profile.py`
- `gnuckle/cli.py`

## Required Runtime Behavior

The first runnable path must:

1. create or load a session object
2. load one workflow definition
3. inject one event into the session
4. build model-visible context
5. request the next action from the model
6. if the model emits a tool call:
   - execute the tool
   - append tool result
   - continue
7. if the model emits `finish`:
   - finalize the episode
   - emit explicit result
8. if turn limit is reached:
   - emit `max_turns`
9. if runtime breaks:
   - emit `harness_error`

## Required Output

The session must produce one structured episode JSON with:

- `episode_id`
- `workflow_id`
- `status`
- `failure_reason`
- `task_completed`
- `verification_passed`
- `turns_used`
- `tool_calls_used`
- `performance`
- `scores`
- `trace`

The trace must contain:

- assistant step
- tool call
- tool result
- final result

## Success Metrics

This focused session is successful only if all of these are true:

1. one workflow runs from event injection to terminal status
2. terminal status is always one of:
   - `completed`
   - `failed`
   - `max_turns`
   - `timeout`
   - `harness_error`
3. the trace is always written
4. tool calls are visible in the trace
5. tool results are visible in the trace
6. explicit final result is visible in the trace
7. episode JSON includes the required outcome and timing fields
8. current `gnuckle benchmark` flow still works

## Explicit Non-Goals

Do not include in this session:

- persistence comparison modes
- leaderboard work
- dashboard redesign
- `spawn_agent`
- large tool families
- browser or automation tooling
- profile editor expansion

These belong to later focused sessions.

## Reference Notes

This session must stay aligned with:

- `docs/05-v1-build-plan.md`
- `docs/06-v1-success-metrics.md`

## Summary

This session should build the first real bounded agentic episode.

If this works, `gnuckle` has crossed the line from planning into implementation.
