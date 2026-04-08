# 03 Runtime Roadmap

## Purpose

This note translates the larger benchmark spec into a realistic roadmap for `gnuckle`.

The goal is not to build a full Hermes, OpenClaw, or OpenClaude clone.

The goal is:

- create a short but credible approximation of agentic harness behavior
- let users compare local models against each other under the same conditions
- produce leaderboard-friendly outputs
- keep the harness simple enough to maintain

## Product Position

`gnuckle` should be a comparative local benchmark, not a full runtime platform.

That means:

- deterministic fixtures
- small but realistic tool surface
- bounded workflows
- clear stop conditions
- simple persistence modes
- easy repeatability

The benchmark should answer:

- which local model handles bounded agent loops better
- which model survives repeated sessions better
- which model regresses first as context accumulates

It does not need to answer:

- every multi-agent orchestration question
- every runtime integration question
- every production deployment concern

## V1 Principle

V1 should simulate just enough of an agent harness to be useful.

That means:

1. one session
- no true multi-session orchestration yet

2. one event at a time
- user message or scheduled wakeup

3. deterministic tools
- mock but structured

4. bounded loop
- assistant -> tool -> assistant until stop

5. simple persistence modes
- fresh
- full history
- rolling summary

6. leaderboard output
- score models against the same workflow suite

## What V1 Should Include

### 1. Simple Workflow Manifest

Add a workflow definition file.

Likely path:

- `gnuckle/workflows.json`

Each workflow should define:

- `workflow_id`
- `title`
- `slice`
- `difficulty`
- `system_prompt`
- `event`
- `allowed_tools`
- `max_loops`
- `success_rule`
- `verification_required`

This should stay compact.

We do not need the full large manifest from the spec yet.

### 2. Agentic Loop Runner

Replace the current "one turn equals one scored unit" logic with:

1. inject event
2. call model
3. if tool call exists, execute tool
4. append tool result
5. call model again
6. stop when:
   - final answer is present
   - no more tool calls
   - max loops reached
   - timeout

This is the single most important code change.

### 3. Minimal Tool Surface

V1 tool set should be small and deterministic.

Recommended V1 tools:

- `read_inbox`
- `send_notification`
- `search_memory`
- `write_memory`
- `list_files`
- `read_file`
- `run_tests`
- `submit_final`

Optional but not required for V1:

- `edit_file`
- `spawn_helper_session`
- `schedule_job`

The point is to test reasoning and discipline, not to build a giant fixture system immediately.

### 4. Basic Slices

V1 slices should be:

1. `interactive`
- bounded request with tool use

2. `scheduled`
- cron-style wakeup task

3. `memory`
- continue work with stored prior facts

4. `verification`
- task requiring evidence before success

This is enough to produce a meaningful leaderboard.

### 5. Simple Persistence Modes

V1 should support:

- `fresh`
- `full_history`
- `rolling_summary`

Retrieval memory can come next.

This keeps the harness smaller while still testing the degradation story.

### 6. Structured Episode Output

The current JSON should evolve into a smaller version of the spec output.

Required V1 fields:

- `episode_id`
- `workflow_id`
- `mode`
- `status`
- `start_time`
- `end_time`
- `loops`
- `tool_calls`
- `final_result`
- `metrics`
- `scores`

This is enough for later HTML and leaderboard generation.

### 7. Leaderboard Summary

The suite output should include:

- overall success rate
- slice success rate
- persistence success rate
- average loops to completion
- average tool errors
- average TTFT
- average wall time
- average tokens generated
- failure distribution

This should roll up into a simple comparative table.

## What V1 Should Not Include

Do not include yet:

- full multi-session orchestration
- true helper worktrees
- true browser automation
- ask-on-use approvals
- giant environment simulation
- large inbox/channel systems
- every OpenClaude tool concept

Those are useful later, but they will slow down delivery and make the benchmark harder to trust.

## Proposed Roadmap

### Phase 1. Stabilize the Current Runner

Goal:

- stop false starts
- improve result visibility

Tasks:

- keep warmup before timing
- keep split-view HTML
- fix Windows splash encoding
- auto-open dashboard in browser

### Phase 2. Introduce Workflow Objects

Goal:

- move from prompts to workflows

Tasks:

- add `gnuckle/workflows.json`
- add workflow loader
- define 6 to 12 benchmark workflows
- add success rules per workflow

Deliverable:

- `gnuckle benchmark --mode capability`

### Phase 3. Implement the Agentic Loop

Goal:

- score bounded workflows instead of isolated turns

Tasks:

- add loop runner
- add stop reasons
- add finalization rules
- add `submit_final`
- score completion and tool discipline

Deliverable:

- per-episode JSON traces

### Phase 4. Add Persistence Modes

Goal:

- compare fresh vs carry vs summary

Tasks:

- add session state object
- add `fresh`
- add `full_history`
- add `rolling_summary`
- record degradation per episode index

Deliverable:

- `gnuckle benchmark --mode persistence`

### Phase 5. Add Leaderboard Output

Goal:

- let users compare models cleanly

Tasks:

- add aggregate score output
- add slice tables
- add failure taxonomy summary
- add deployment-style recommendation
- add static leaderboard HTML

Deliverable:

- one benchmark suite report per model
- one comparison report across models

## Suggested V1 Scoring

Keep the scoring simple.

Primary:

- `TaskSuccess`

Secondary:

- `ConstraintObedience`
- `Verification`
- `Efficiency`

Suggested V1 formula:

```text
EpisodeScore =
  0.55 * TaskSuccess
  0.20 * ConstraintObedience
  0.15 * Verification
  0.10 * Efficiency
```

For persistence mode:

```text
PersistenceScore =
  0.50 * RepeatedTaskSuccess
  0.30 * StabilityAcrossEpisodes
  0.20 * SummaryRecovery
```

This is simpler than the full spec, which is appropriate for V1.

## Leaderboard Philosophy

The leaderboard should be comparative, not absolute.

Meaning:

- users compare models under the same workflow suite
- users compare cache types or inference stacks under the same workflows
- users compare persistence policies under the same tasks

The output should help users say:

- model A is better for bounded cron tasks
- model B is better for supervised coding loops
- model C falls apart under context growth

That is enough.

## Recommended Next Code Changes

In order:

1. fix the CLI/dashboard polish in the current runner
2. add workflow manifest support
3. add bounded loop execution
4. add simple scoring
5. add persistence modes
6. add leaderboard aggregation

## Summary

`gnuckle` should become a small, serious agentic benchmark harness.

Not a giant runtime.
Not a toy prompt benchmark.

A short approximation is enough if:

- the workflow is real enough
- the scoring is structured
- the runs are repeatable
- the outputs are comparable

That is the right shape for a local-model benchmark and leaderboard tool.
