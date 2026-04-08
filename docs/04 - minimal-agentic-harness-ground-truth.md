# Minimal Agentic Harness: Technical Ground Truth

## Key Technical Contents

- Runtime purpose and non-goals
- Ground-truth source systems
- Minimal harness architecture
- Working implementation order
- Core execution loop
- Session state model
- Event model
- Tool contract
- Delegation contract
- Verification contract
- Performance model
- Repetition and context-pressure model
- Input schemas
- Output schemas
- Scoring-relevant trace fields
- OpenClaude code excerpts that justify the design

## 1. Purpose

This document defines the technical ground truth for a **minimal agentic harness** intended for benchmarking local models.

The harness is intentionally narrow. It is not meant to reproduce OpenClaude, Hermes Agent, or OpenClaw in full. Its purpose is to create a short but faithful approximation of the runtime conditions that matter when people ask:

- Can this local model operate as an agent instead of a one-shot chatbot?
- Can it survive repeated bounded work inside a persistent session?
- Can it handle realistic tool-using workloads such as coding tasks, message-style tasks, or cron-style tasks?
- At what point does accumulated context cause regression?

This document should be treated as the ground-truth technical behavior for the minimal harness.

The central constraint is practical:

- the harness must be simple enough to implement correctly
- the harness must be close enough to a real agent runtime that benchmark results mean something

This is why OpenClaude is used as the primary grounding reference. The benchmark is not trying to imitate the surface appearance of an agent system. It is trying to preserve the smallest runtime behaviors that make the system actually function.

## 2. Source Systems

This harness definition is grounded in the following systems and materials:

- **OpenClaude**
  - Used as the direct reference for the coding-agent loop, session persistence, tool-driven turns, and optional subagent delegation.
- **Hermes Agent**
  - Used as a reference for continuously running local-agent workflows, memory-backed operation, and recurring/scheduled tasks.
- **OpenClaw**
  - Used as a reference for persistent sessions, gateway-delivered events, isolated sessions, and cron-triggered wakeups.
- **turboquant_plus**
  - Used for its benchmarking mindset: one primary quality metric, with secondary diagnostics such as efficiency and reproducibility.
- **llama.cpp discussion 20969**
  - Used as a methodological reference: benchmark the actual claim, separate model failure from harness failure, and avoid attractive but incorrect conclusions.
- **quant.cpp**
  - Used for the principle of head-to-head comparison under equal operating budgets.

## 3. Technical Objective

The minimal harness must simulate the following agent-runtime contract:

1. A persistent session exists across multiple episodes.
2. The model receives an event into that session.
3. The model can inspect session history and memory.
4. The model can use a bounded tool surface.
5. The model may optionally delegate a bounded subtask.
6. The model must explicitly terminate with success or failure.
7. The system records the full interaction trace for scoring.
8. The system records execution speed and cost-like runtime metrics for every episode.

The objective is not to simulate every product feature. The objective is to simulate the smallest technically valid loop that still behaves like an agent harness.

If a mechanism does not materially affect whether the benchmarked model can operate as an agent, it should be excluded from v1.

The harness must remain simple enough that users can run multiple local models against the same task suite and compare them on a leaderboard.

## 4. Non-Goals

This harness does not attempt to reproduce:

- full OpenClaude worktree management
- background task orchestration
- multi-agent team coordination
- MCP ecosystems
- real Telegram, Slack, or Discord transport
- real container isolation
- production-grade auth or permission systems

Those are useful product features, but they are not required to benchmark minimal agentic capability.

They are also intentionally excluded because every extra moving part increases the chance that the benchmark measures harness complexity instead of model capability.

## 5. Minimal Harness Architecture

The minimal harness contains five technical components.

These are the only required runtime components for v1. A conforming implementation should resist feature expansion unless the addition changes benchmark validity.

### 5.1 Session Store

Stores:

- `session_id`
- `messages`
- `memory_records`
- `episode_count`
- `token_counters`
- `tool_counters`
- `summary_blocks`

### 5.2 Event Injector

Creates benchmark events such as:

- user request
- coding task
- cron wakeup
- Telegram-like inbound message
- follow-up continuation

### 5.3 Agent Runtime

Runs the main decision loop:

- load session
- prepare visible context
- ask model for next action
- run tool or subagent if requested
- append trace
- repeat until `finish` or failure

This is the functional heart of the harness. If this loop is sound, the benchmark works. If this loop is vague, the benchmark becomes decorative rather than operational.

### 5.4 Tool Executor

Executes only the bounded harness tool surface.

### 5.5 Scoring Recorder

Persists:

- raw turn trace
- tool trace
- final result
- verification status
- context-pressure statistics
- performance statistics

## 6. Working Implementation Order

This section is normative for a first implementation.

The goal is a harness that works quickly and predictably, not a harness that models every theoretical feature. A conforming v1 implementation should be buildable in a near one-shot pass by following the steps below in order.

### 6.1 Build Order

1. Implement a persistent `SessionStore`.
2. Implement event injection for a single `interactive_request`.
3. Implement the main runtime loop with `max_turns`.
4. Implement the required tools:
   - `search`
   - `read_file`
   - `edit_file`
   - `run_test`
   - `finish`
5. Emit a structured per-turn trace.
6. Emit a structured final episode result.
7. Add verification recording.
8. Add performance recording.
9. Add repeated-session execution.
10. Add optional `spawn_agent` support only if the previous nine steps already work.

### 6.2 Working Definition

For this benchmark, the harness counts as **working** only if all of the following are true:

- it can run a task from event injection to final result without manual intervention
- it always emits a structured trace
- it always terminates with an explicit result or explicit failure
- tool calls are visible in the trace
- repeated runs can reuse the same session state
- timing data is recorded for every episode

If any of these are missing, the harness is not yet benchmark-valid.

### 6.3 What To Skip In v1

To keep the harness working, a first implementation should explicitly skip:

- background agents
- worktree isolation
- agent teams
- remote execution
- MCP integration
- real chat platform connectors
- non-essential tool families

These may be added later, but they are not required to obtain a valid approximation.

### 6.4 Minimal File Layout

A working minimal implementation can be organized with only these runtime modules:

```text
src/
  harness/
    sessionStore.ts
    eventInjector.ts
    runtimeLoop.ts
    toolExecutor.ts
    verifier.ts
    contextBuilder.ts
    scorer.ts
    types.ts
```

This is not the only valid structure, but it is close to the minimum practical footprint.

### 6.5 First Runnable Milestone

The first runnable milestone is:

1. start an empty session
2. inject one coding-task event
3. let the model call `read_file`, `edit_file`, and `run_test`
4. allow `finish`
5. write the final trace and episode result to disk

If this milestone works reliably, the harness is already useful enough to compare models on bounded coding tasks.

### 6.6 Second Runnable Milestone

The second runnable milestone is:

1. reuse the same session
2. inject a second event
3. preserve prior history in visible or summarized form
4. record whether latency or quality regresses

At that point, the harness can begin to answer the recurring-agent question rather than just the single-episode question.

## 7. Core Execution Loop

The minimal harness loop is:

1. Load the current session state.
2. Inject one benchmark event.
3. Build the visible prompt context from:
   - active event
   - retained session history
   - retrieved memory
   - system instructions
   - tool definitions
4. Ask the model for the next action.
5. If the action is a tool call, execute it and append the result.
6. If the action is a subagent call, run the child loop with a constrained budget and append the result.
7. If the action is `finish`, produce a final episode result.
8. If the turn limit is exceeded, produce a failure result.

The loop must be deterministic at the harness level. Any variation should come from the model, not from runtime ambiguity.

## 8. OpenClaude Grounding

The minimal harness is intentionally derived from the narrowest parts of OpenClaude that define a useful agent loop.

OpenClaude is used here because it already contains a real working coding-agent loop. The benchmark should therefore copy only the parts that are necessary to preserve operational validity:

- session-based execution
- explicit tool mediation
- bounded turn loop
- explicit result or failure
- optional bounded delegation

It should not copy orchestration features that are useful in product form but unnecessary in benchmark form.

### 7.1 Session-Oriented Query Loop

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L209):

```ts
async *submitMessage(
  prompt: string | ContentBlockParam[],
  options?: { uuid?: string; isMeta?: boolean },
): AsyncGenerator<SDKMessage, void, unknown> {
```

This is the key grounding point: a session accepts an input prompt and emits a stream of runtime messages.

The minimal harness should mirror this by treating each benchmark event as input to a stateful message loop rather than a single stateless completion.

### 7.2 Runtime Configuration Includes Tools and Turn Budget

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L213):

```ts
const {
  cwd,
  commands,
  tools,
  mcpClients,
  verbose = false,
  thinkingConfig,
  maxTurns,
} = this.config
```

This grounds two important design facts:

- tool access is part of runtime configuration
- turn limits are part of runtime control

The minimal harness must therefore expose a fixed tool surface and a fixed maximum turn budget for fair comparison.

### 7.3 Messages Are Persistent Runtime State

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L184):

```ts
export class QueryEngine {
  private config: QueryEngineConfig
  private mutableMessages: Message[]
```

This is the direct grounding for persistent session history.

### 7.4 Assistant and Other Messages Are Appended as the Run Progresses

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L761):

```ts
case 'assistant':
  this.mutableMessages.push(message)
  yield* normalizeMessage(message)
  break
```

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L771):

```ts
case 'progress':
  this.mutableMessages.push(message)
```

The harness must therefore preserve the trace as the source of truth, not just the final answer.

### 7.5 Explicit Failure on Turn Exhaustion

From [src/QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L851):

```ts
yield {
  type: 'result',
  subtype: 'error_max_turns',
  duration_ms: Date.now() - startTime,
  is_error: true,
}
```

The minimal harness must explicitly report turn-limit failure. Silent truncation is not allowed.

### 7.6 Optional Delegation Boundary

From [src/tools/AgentTool/AgentTool.tsx](/G:/2026%20Projects/openclaude/src/tools/AgentTool/AgentTool.tsx#L239):

```ts
async call({
  prompt,
  subagent_type,
  description,
  model: modelParam,
  run_in_background,
}: AgentToolInput, toolUseContext, canUseTool, assistantMessage, onProgress?) {
```

This grounds the idea that delegation is a separate runtime action, not just hidden chain-of-thought.

### 7.7 Synchronous Child Execution Is Enough for the Minimal Harness

From [src/tools/AgentTool/AgentTool.tsx](/G:/2026%20Projects/openclaude/src/tools/AgentTool/AgentTool.tsx#L797):

```ts
return runWithAgentContext(syncAgentContext, () => wrapWithCwd(async () => {
  const agentMessages: MessageType[] = [];
```

The minimal harness should only simulate this synchronous path. Background execution, worktrees, and teams are not required for v1.

## 9. Minimal Session State Model

Each session must contain the following fields.

```json
{
  "session_id": "string",
  "messages": [],
  "memory_records": [],
  "summary_blocks": [],
  "episode_count": 0,
  "tool_counters": {
    "total_calls": 0,
    "by_tool": {}
  },
  "token_counters": {
    "input_tokens_est": 0,
    "output_tokens_est": 0,
    "tool_tokens_est": 0
  },
  "context_stats": {
    "history_tokens_visible": 0,
    "memory_tokens_visible": 0,
    "tool_tokens_visible": 0
  }
}
```

### 8.1 `messages`

The ordered runtime trace.

Allowed message kinds:

- `system`
- `event`
- `assistant`
- `tool_use`
- `tool_result`
- `subagent_result`
- `verification_result`
- `result`

### 8.2 `memory_records`

Persistent distilled facts or task-relevant memories retrieved across episodes.

### 8.3 `summary_blocks`

Optional compressed history blocks used when old context is removed from the visible prompt but retained semantically.

## 10. Event Model

Each episode begins with exactly one injected event.

### 9.1 Event Input Schema

```json
{
  "event_id": "string",
  "session_id": "string",
  "event_type": "interactive_request | cron_wakeup | channel_message | continuation",
  "timestamp": "RFC3339 string",
  "payload": {
    "text": "string",
    "metadata": {}
  },
  "task_id": "string",
  "task_variant": "string"
}
```

### 9.2 Event Types

#### `interactive_request`

A direct user or operator request.

#### `cron_wakeup`

A scheduled wakeup. The scheduler is external to the model. The model only receives the wake event and must act on it.

#### `channel_message`

A Telegram-like or Slack-like inbound message, simulated as structured text plus metadata.

#### `continuation`

A follow-up event in an existing ongoing session.

## 11. Tool Contract

The harness must expose a very small tool surface.

### 10.1 Required Tools

- `search`
- `read_file`
- `edit_file`
- `run_test`
- `finish`

### 10.2 Optional Tool

- `spawn_agent`

### 10.3 Tool Input Schema

```json
{
  "tool_name": "string",
  "arguments": {}
}
```

### 10.4 Tool Result Schema

```json
{
  "tool_name": "string",
  "ok": true,
  "output": {},
  "error": null,
  "duration_ms": 0
}
```

### 10.5 Required Properties of Tooling

- deterministic behavior
- stable output shape
- explicit success or failure
- traceability in the session log

The tool surface must remain intentionally small because the benchmark is trying to answer whether the model can operate a harness, not whether the harness can hide difficulty behind many specialized helpers.

## 12. Delegation Contract

Delegation is optional but useful.

The minimal harness should support only one child-agent primitive:

```json
{
  "tool_name": "spawn_agent",
  "arguments": {
    "task": "string",
    "budget_turns": 3
  }
}
```

### 11.1 Child Run Rules

- child runs synchronously
- child runs with the same bounded tool surface
- child has a lower turn limit than the parent
- child returns a structured result, not free-form hidden reasoning

### 11.2 Child Result Schema

```json
{
  "summary": "string",
  "status": "completed | failed",
  "turns_used": 0,
  "tools_used": [],
  "artifact": {}
}
```

This is the smallest meaningful approximation of OpenClaude’s subagent behavior.

If delegation complicates the implementation materially, it may be disabled in a first working release. The harness remains valid without it, as long as the omission is reported clearly in leaderboard metadata.

## 13. Verification Contract

The benchmark must distinguish between:

- claimed completion
- verified completion

For tasks that have an executable verifier, the harness must require the model to use the verifier path before `finish` counts as fully successful.

### 12.1 Verification Result Schema

```json
{
  "verified": true,
  "method": "run_test | output_match | state_check",
  "details": {},
  "timestamp": "RFC3339 string"
}
```

## 14. Performance Model

Performance is a first-class benchmark dimension.

Agentic capability alone is not enough. Local-model users also need to know:

- how long a task takes to complete
- how long each turn takes
- whether latency becomes unacceptable under repeated use
- how much tool usage inflates total wall-clock time
- whether a slower but more capable model is operationally worthwhile

This is especially important in the local-model niche because users routinely compare:

- large but slower models versus smaller faster models
- different quantizations of the same model
- different hardware backends
- different context-management strategies

The benchmark must therefore report performance separately from capability while still tying both to the same trace.

Performance matters here for a practical reason: a harness that technically works but is too slow to operate is not useful to the people comparing local models.

### 13.1 Required Performance Metrics

Each episode must record:

- `wall_clock_ms`
- `time_to_first_action_ms`
- `time_to_finish_ms`
- `avg_turn_latency_ms`
- `max_turn_latency_ms`
- `tool_time_ms_total`
- `model_time_ms_total`
- `verification_time_ms`
- `subagent_time_ms_total`

Each run must also aggregate:

- `episodes_per_hour`
- `successful_episodes_per_hour`
- `median_episode_ms`
- `p95_episode_ms`
- `median_turn_latency_ms`
- `p95_turn_latency_ms`

### 13.2 Required Throughput Context

Every run report must include:

- model identifier
- quantization or precision
- context size setting
- backend/runtime
- hardware summary
- thread or batch settings if relevant

This keeps performance comparisons tied to the actual operating setup rather than vague model labels.

### 13.3 Required Performance Interpretation

Performance must be interpreted in relation to workload class.

Examples:

- A model may be acceptable for nightly cron jobs even if slow.
- The same model may be unacceptable for interactive Telegram-like response tasks.
- A model may succeed on coding tasks but be too slow to be practically useful for leaderboard users.

### 13.4 Required Performance Classifications

Each workload slice should classify the model as:

- `interactive_usable`
- `background_only`
- `slow_but_viable`
- `not_operationally_viable`

This classification must be derived from measured runtime data, not subjective judgment.

### 13.5 Equal-Budget Performance Comparison

Performance comparisons must only be made across runs with the same:

- task suite
- tool surface
- turn budget
- context strategy
- verification rules

Capability and performance should be reported side by side.

The benchmark must not collapse them into a single opaque score.

## 15. Repetition and Context-Pressure Model

This harness must test repeated use, not only first-pass success.

The core problem is that prompts, tool results, and repeated instructions consume context over time. The benchmark must therefore evaluate not only whether a model succeeds once, but whether it remains competent across repeated episodes in the same session.

### 14.1 Required Repetition Modes

- `fresh_session`
  - no prior history
- `full_history`
  - retain the full visible trace
- `summary_history`
  - retain compressed prior context
- `retrieval_history`
  - retain only a short history window plus retrieved memory
- `mixed_workload`
  - alternate task types across repeated episodes

### 14.2 Required Context Measurements

- visible history token estimate
- visible memory token estimate
- visible tool-output token estimate
- total episode count
- turns per episode
- wall-clock time per episode
- wall-clock time per turn

### 14.3 Required Degradation Outputs

- first regression point
- stable zone
- soft regression zone
- failure zone
- latency inflation point

### 14.4 Interpretation

This allows the leaderboard to answer questions such as:

- Can the model repeat cron-like tasks reliably?
- How much context can the model carry before quality drops?
- Does summarization restore performance?
- Is the model only reliable for short-lived episodes?
- Does performance degrade before capability degrades?
- Does context growth make the model operationally too slow even before it starts failing?

## 16. Input Schemas

### 15.1 Benchmark Run Input

```json
{
  "run_id": "string",
  "model_id": "string",
  "runtime_profile": {
    "max_turns": 12,
    "subagent_max_turns": 3,
    "context_strategy": "fresh_session",
    "enable_spawn_agent": true,
    "performance_profile": {
      "hardware": "string",
      "backend": "string",
      "quantization": "string"
    }
  },
  "task_suite": [
    {
      "task_id": "string",
      "events": []
    }
  ]
}
```

### 15.2 Runtime Profile

```json
{
  "max_turns": 12,
  "subagent_max_turns": 3,
  "context_strategy": "fresh_session | full_history | summary_history | retrieval_history | mixed_workload",
  "enable_spawn_agent": true,
  "performance_profile": {
    "hardware": "string",
    "backend": "string",
    "quantization": "string",
    "threads": 0,
    "context_window": 0
  },
  "tool_budget": {
    "max_total_calls": 20
  }
}
```

### 15.3 Task Input

```json
{
  "task_id": "string",
  "task_class": "coding | cron | channel | continuation",
  "initial_files": [],
  "success_condition": {},
  "events": []
}
```

## 17. Output Schemas

### 16.1 Turn Output

```json
{
  "turn_index": 0,
  "action_type": "assistant | tool_use | finish | spawn_agent",
  "action": {},
  "observation": {},
  "timing": {
    "turn_latency_ms": 0,
    "model_latency_ms": 0,
    "tool_latency_ms": 0
  },
  "visible_context_stats": {
    "history_tokens_est": 0,
    "memory_tokens_est": 0,
    "tool_tokens_est": 0
  }
}
```

### 16.2 Episode Result

```json
{
  "episode_id": "string",
  "task_id": "string",
  "status": "completed | failed | max_turns | harness_error",
  "task_completed": true,
  "verification_passed": true,
  "turns_used": 0,
  "tool_calls_used": 0,
  "subagent_calls_used": 0,
  "performance": {
    "wall_clock_ms": 0,
    "time_to_first_action_ms": 0,
    "time_to_finish_ms": 0,
    "avg_turn_latency_ms": 0,
    "max_turn_latency_ms": 0,
    "tool_time_ms_total": 0,
    "model_time_ms_total": 0,
    "verification_time_ms": 0,
    "subagent_time_ms_total": 0
  },
  "failure_reason": null,
  "final_artifact": {},
  "trace": []
}
```

### 16.3 Run Report

```json
{
  "run_id": "string",
  "model_id": "string",
  "episodes": [],
  "aggregate": {
    "success_rate": 0.0,
    "verification_rate": 0.0,
    "avg_turns": 0.0,
    "avg_tool_calls": 0.0,
    "context_regression_point": null,
    "latency_regression_point": null,
    "median_episode_ms": 0,
    "p95_episode_ms": 0,
    "median_turn_latency_ms": 0,
    "p95_turn_latency_ms": 0,
    "episodes_per_hour": 0.0,
    "successful_episodes_per_hour": 0.0
  }
}
```

## 18. Ground-Truth Behavioral Rules

The following rules are normative.

### 17.0 The Harness Must Be Runnable

The benchmark is only valid if the harness can be implemented and run reliably by users comparing local models.

This means:

- required components must be minimal
- required inputs and outputs must be explicit
- task flow must be deterministic at the harness level
- runtime behavior must be inspectable from logs and traces

Any design choice that makes the benchmark harder to run without improving its ability to approximate a real harness should be rejected.

### 17.1 Session Persistence

The harness must preserve session history across episodes unless the benchmark mode explicitly resets the session.

### 17.2 Explicit Tool Mediation

The model must not be credited for capabilities that were performed implicitly by the harness. Any meaningful external action must appear as a tool call or subagent result in the trace.

### 17.3 Explicit Episode Termination

An episode must end only with one of:

- `completed`
- `failed`
- `max_turns`
- `harness_error`

### 17.4 Harness Errors Must Be Separated

If a tool crashes, parser fails, or the harness malfunctions, the run must record `harness_error`, not `model_failed`.

This is directly aligned with the methodological lesson taken from the `llama.cpp` benchmarking discussion: do not attribute infrastructure failure to the model.

### 17.5 Equal-Budget Comparison

Leaderboard comparisons must be made only across runs that share:

- the same task suite
- the same tool surface
- the same turn budget
- the same context strategy
- the same verifier rules

This is aligned with the equal-budget comparison principle highlighted by `quant.cpp`.

### 17.6 Performance Must Be Reported Independently

The run report must preserve capability metrics and performance metrics as separate fields.

The benchmark may provide a derived dashboard view, but it must not discard the raw timing values.

### 17.7 Timeouts Must Be Explicit

If the model exceeds a runtime timeout, the episode result must record:

- timeout status
- elapsed time at timeout
- last successful turn
- last successful tool call

Timeouts must not be collapsed into generic failure.

### 17.8 Prefer Working Approximation Over Feature Completeness

If there is a tradeoff between:

- a smaller harness that clearly works and approximates real agent use
- a larger harness that is more feature-complete but operationally fragile

the smaller working harness is the correct benchmark target.

This is a ground-truth design rule, not a temporary convenience.

## 19. Minimal Reference Pseudocode

```ts
async function runEpisode(session, event, runtime) {
  const episodeStart = Date.now()
  session.messages.push({ type: "event", event })

  for (let turn = 0; turn < runtime.max_turns; turn++) {
    const turnStart = Date.now()
    const visibleContext = buildVisibleContext(session, runtime)

    const action = await modelNextAction({
      messages: visibleContext.messages,
      memory: visibleContext.memory,
      tools: runtime.tools
    })

    if (action.type === "tool_use") {
      const result = await executeTool(action)
      result.timing = { turn_latency_ms: Date.now() - turnStart }
      session.messages.push(action, result)
      continue
    }

    if (action.type === "spawn_agent" && runtime.enable_spawn_agent) {
      const childResult = await runChildAgent(action, runtime.subagent_max_turns)
      session.messages.push(action, {
        type: "subagent_result",
        result: childResult
      })
      continue
    }

    if (action.type === "finish") {
      const verification = await maybeVerify(session)
      const result = finalizeEpisode(session, action, verification)
      result.performance = {
        wall_clock_ms: Date.now() - episodeStart
      }
      session.messages.push({ type: "result", result })
      return result
    }
  }

  const result = {
    status: "max_turns",
    task_completed: false
  }
  session.messages.push({ type: "result", result })
  return result
}
```

## 20. Minimal Technical Recommendation

For v1, the minimal harness should support exactly this stack:

- persistent sessions
- event injection
- short multi-turn loop
- five required tools
- optional synchronous child delegation
- explicit verification
- explicit performance recording
- repeated-episode context-pressure testing
- full structured trace output

That is the smallest technical slice that still gives meaningful evidence about whether a local model can operate in an agentic harness similar in spirit to OpenClaude, Hermes Agent, and OpenClaw.

Anything beyond this should be treated as v2 scope unless it is required to make the approximation operationally valid.

## 21. Nearly One-Shot Build Guide

This section compresses the document into the shortest practical build path.

### 21.1 Step 1: Define the Core Types

Create types for:

- `Session`
- `Event`
- `ToolCall`
- `ToolResult`
- `TurnTrace`
- `EpisodeResult`

Do not start with orchestration features. Start with the data model.

### 21.2 Step 2: Build the Session Store

Implement:

- load session by `session_id`
- append message
- append memory record
- write episode result

Use a simple file-backed or in-memory implementation first.

### 21.3 Step 3: Build the Runtime Loop

Implement exactly this loop:

1. load session
2. append event
3. build visible context
4. ask model for next action
5. if tool call, execute tool and append result
6. if finish, verify and finalize
7. if turn limit reached, emit `max_turns`

Do not add extra branches until this path works.

### 21.4 Step 4: Build the Required Tools

Implement only:

- `search`
- `read_file`
- `edit_file`
- `run_test`
- `finish`

If these five tools work, the harness is already meaningful.

### 21.5 Step 5: Make Trace Output Mandatory

Every turn must write:

- action taken
- observation received
- timing
- visible context stats

If the trace is incomplete, the run is not useful for benchmarking.

### 21.6 Step 6: Add Verification

Require a verification record for tasks that have executable checks.

For coding tasks, this usually means `run_test`.

### 21.7 Step 7: Add Performance Recording

Record:

- wall-clock episode time
- per-turn latency
- tool time
- verification time

This must be added before leaderboard use.

### 21.8 Step 8: Add Repeated Session Runs

Run multiple episodes against the same session and measure:

- success retention
- latency inflation
- context growth
- regression point

This is what turns the harness from a toy into an approximation of real agent use.

### 21.9 Step 9: Add Optional Delegation

Only after the above works, add `spawn_agent` as a small synchronous helper path.

This is optional for v1.

### 21.10 Final Rule

If a proposed feature makes the harness harder to run, harder to inspect, or harder to compare across models without clearly improving the approximation, leave it out.

`WORKING` is the primary requirement.

## 22. Summary

The technical ground truth is:

- the benchmark is a session-based runtime, not a single prompt
- the model must operate through explicit tools
- the harness must preserve trace state across repeated episodes
- optional delegation should be shallow and synchronous
- explicit completion and explicit failure are both required
- verification must be recorded separately from claims of success
- performance must be recorded separately from capability
- context growth must be measured because repeated agent use is a primary failure mode for local models

This is intentionally minimal, but it is sufficient to benchmark whether a local model behaves like an agent under bounded realistic conditions.
