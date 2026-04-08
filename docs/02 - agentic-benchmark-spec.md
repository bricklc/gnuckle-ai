# Agentic Benchmark Specification

## Key Contents

- Purpose and scope of the benchmark
- Referenced systems and why they matter
- Core design principles
- Benchmark object model
- Harness runtime specification
- Input formats
- Output formats
- Task classes and operational slices
- Repetition and context-survivability testing
- Scoring model
- Reporting format
- Safety and simulation boundaries
- Example benchmark artifacts

## 1. Purpose

This document specifies a benchmark for evaluating local AI models in a simulated agentic runtime.

The benchmark is designed to answer practical questions that matter to people running local or offline models in real systems:

- Can the model operate an agent harness, not just answer prompts?
- Can it complete bounded recurring work reliably?
- Can it survive repeated use as transcript, tool traces, and memory accumulate?
- At what point does performance regress?
- Which classes of work can be left unattended, and which require supervision?

The benchmark is intentionally agent-runtime-centric, not chat-centric.

Its goal is to produce evidence about whether a local model can realistically power systems in the style of:

- Hermes Agent
- OpenClaw
- OpenClaude-like coding loops

without requiring the benchmark to reproduce those systems in full.

## 2. Scope

This benchmark evaluates the model as the decision-making component inside a simulated local-first control plane.

It includes:

- multi-turn tool use
- bounded persistent sessions
- scheduled wakeups
- message or channel-style events
- memory retrieval
- optional delegated helper sessions
- verification behavior
- context survivability under repeated runs

It does not attempt to benchmark:

- raw perplexity
- isolated single-turn chat quality
- full production messenger integrations
- full GUI or browser fidelity beyond the simulation contract
- real-world security guarantees of external runtimes

## 3. Why This Benchmark Exists

Many benchmarks for local models focus on static outputs, coding snippets, retrieval, or raw inference metrics. Those are useful diagnostics, but they do not directly answer whether a model can function inside a persistent autonomous or semi-autonomous workflow.

In actual local-agent use, users care about workflows like:

- "Wake up every morning and summarize logs"
- "Reply to a Telegram message with the right context"
- "Investigate a bug in a repo, edit code, run tests, and report back"
- "Resume where you left off yesterday"
- "Handle recurring maintenance tasks without re-priming the model every time"

This benchmark targets that niche directly.

## 4. Referenced Materials

This benchmark is informed by the following systems and discussions.

### 4.1 OpenClaude

Used as a reference for:

- multi-turn coding-agent loops
- agent roles
- background tasks
- worktree isolation
- verification-oriented agent roles
- skills and hooks as runtime-extensible behavior

Repository:

- https://github.com/Gitlawb/openclaude

### 4.2 Hermes Agent

Used as a reference for:

- unattended local automation
- persistent memory
- gateway-style multi-interface operation
- sub-agent and delegation patterns
- sandboxing expectations
- local-first operation with offline or local models

Repository:

- https://github.com/nousresearch-hermes-agent/hermes-agent

### 4.3 OpenClaw

Used as a reference for:

- local-first gateway architecture
- sessions as first-class agents
- cron and scheduled jobs
- multi-channel inbox and message routing
- session-to-session agent coordination
- isolated non-main sessions and workspaces

Repository and docs:

- https://github.com/openclaw/openclaw
- https://docs.openclaw.ai/automation/cron-jobs

### 4.4 turboquant_plus

Used as a reference for benchmarking discipline:

- use of primary vs secondary metrics
- reproducible benchmark entrypoints
- context-scaling analysis
- quality vs efficiency reporting

Repository:

- https://github.com/TheTom/turboquant_plus

### 4.5 llama.cpp discussion 20969

Used as a reference for benchmarking caution:

- incorrect measurement can produce false conclusions
- quality claims must be tied to the right metric
- failed runs and proxy metrics must not be confused with actual system performance

Discussion:

- https://github.com/ggml-org/llama.cpp/discussions/20969

### 4.6 quant.cpp

Used as a reference for:

- head-to-head comparisons under equal budget
- explicit benchmark entrypoints
- reproducibility expectations
- reporting quality tradeoffs separately from systems tradeoffs

Repository:

- https://github.com/quantumaikr/quant.cpp

## 5. Design Principles

The benchmark must obey the following principles.

### 5.1 Approximate Real Use

The benchmark should approximate how people actually use local agents:

- persistent sessions
- recurring tasks
- scheduled wakeups
- mixed workloads
- memory-backed continuation

### 5.2 Simulate the Runtime, Not the Entire Product

The benchmark must simulate the contract of a local agent runtime:

- event delivery
- tool access
- memory lookup
- session state
- permissions
- scheduling

It must not depend on reproducing every feature of Hermes, OpenClaw, or OpenClaude.

### 5.3 Measure Agentic Capability Directly

Primary scoring must focus on:

- successful task completion
- correct tool use
- correct verification behavior
- safe behavior under constraints

Proxy metrics are diagnostic only.

### 5.4 Evaluate Persistence Separately

The benchmark must separately evaluate:

- fresh-session capability
- repeated-use capability
- context survivability
- summary or retrieval recovery

### 5.5 Equal-Budget Comparisons

When comparing models, runs must normalize:

- tool set
- prompt policy
- max turns
- timeout
- memory policy
- context policy
- event format

### 5.6 Auditability

Every scored run must emit enough structured evidence to support post hoc review.

## 6. Benchmark Questions

The benchmark must be able to answer:

1. Can the model complete bounded agentic tasks in a simulated local harness?
2. Which operational slices can it handle reliably?
3. Can it repeat tasks over multiple wakeups or sessions?
4. How much context growth can it tolerate before regressions appear?
5. Does memory retrieval or summarization restore performance?
6. Can it self-verify before declaring completion?
7. Can it follow permissions and isolation rules?
8. Is it suitable for unattended cron-like work, supervised coding work, or neither?

## 7. Object Model

The benchmark defines the following core entities.

### 7.1 Model Under Test

The Model Under Test is the LLM plus its configured inference stack.

Attributes:

- `model_id`
- `provider`
- `quantization`
- `context_window_tokens`
- `max_output_tokens`
- `temperature`
- `top_p`
- `hardware_profile`
- `runtime_profile`

### 7.2 Harness

The Harness is the simulated runtime around the model.

Responsibilities:

- store session state
- deliver events
- expose tools
- persist memory
- enforce permissions
- schedule wakeups
- collect trace data

### 7.3 Session

A Session is a persistent agent thread.

Attributes:

- `session_id`
- `session_type`
- `state`
- `history`
- `memory_refs`
- `permissions`
- `created_at`
- `last_active_at`

### 7.4 Episode

An Episode is one benchmarked activation of a session.

Examples:

- a direct user request
- a cron wakeup
- an inbound Telegram-style message
- a delegated helper invocation

### 7.5 Task

A Task is the ground-truth objective the benchmark expects the session to satisfy.

### 7.6 Event

An Event is the structured stimulus delivered to a session.

### 7.7 Tool

A Tool is a deterministic simulation surface the model may call.

### 7.8 Memory Record

A Memory Record is a persistent fact, summary, or extracted artifact that may later be retrieved into context.

## 8. Harness Runtime Specification

The benchmark harness must simulate a local-first agent runtime with deterministic infrastructure and non-deterministic model behavior.

### 8.1 Runtime Responsibilities

The harness must:

- accept a benchmark manifest
- initialize sessions
- inject system prompt and runtime instructions
- deliver events
- execute tool calls
- persist transcript and memory
- enforce turn and time limits
- compute scores
- emit structured reports

### 8.2 Runtime Components

The harness should include the following logical components.

#### 8.2.1 Gateway

Simulates the local control plane.

Responsibilities:

- receive events
- route events to sessions
- assign metadata
- start episodes

#### 8.2.2 Scheduler

Simulates cron-like wakeups.

Responsibilities:

- persist scheduled jobs
- trigger sessions at the correct time
- attach job metadata
- record execution history

#### 8.2.3 Tool Executor

Executes simulated tools and returns deterministic outputs.

#### 8.2.4 Session Store

Persists:

- transcripts
- metadata
- current state
- pending reminders or jobs
- delegated task state

#### 8.2.5 Memory Store

Persists retrievable artifacts independently of the transcript.

#### 8.2.6 Scoring Engine

Scores:

- task result
- tool discipline
- verification behavior
- persistence and regression

## 9. Input Specification

This section defines benchmark inputs.

## 9.1 Benchmark Manifest

Each benchmark suite must be defined by a manifest file.

Required fields:

```json
{
  "suite_id": "string",
  "suite_name": "string",
  "version": "string",
  "description": "string",
  "model_profiles": [],
  "runtime_profile": {},
  "tasks": [],
  "reporting": {}
}
```

### 9.1.1 `model_profiles`

Each model profile defines the exact inference configuration.

Example:

```json
{
  "model_id": "qwen2.5-coder-7b-instruct-q4",
  "provider": "llama.cpp",
  "quantization": "Q4_K_M",
  "context_window_tokens": 32768,
  "max_output_tokens": 2048,
  "temperature": 0.2,
  "top_p": 0.95,
  "hardware_profile": "1x RTX 4090",
  "runtime_profile": "local-gpu"
}
```

### 9.1.2 `runtime_profile`

Defines harness-wide defaults.

Example:

```json
{
  "max_turns_per_episode": 24,
  "max_wall_time_seconds": 300,
  "memory_policy": "summary_and_retrieval",
  "history_policy": "bounded",
  "verification_required_by_default": true,
  "default_permission_mode": "constrained"
}
```

## 9.2 Task Manifest

Each task must be represented as a structured object.

Required fields:

```json
{
  "task_id": "string",
  "title": "string",
  "slice": "interactive|scheduled|channel|memory|delegation|verification",
  "difficulty": "easy|medium|hard",
  "environment": {},
  "initial_session_state": {},
  "event_sequence": [],
  "success_criteria": {},
  "scoring_weights": {}
}
```

### 9.2.1 `environment`

Defines the simulated world visible to tools.

Possible fields:

- repo files
- message inbox
- logs
- prior reports
- memory records
- scheduler state
- external API fixtures

### 9.2.2 `initial_session_state`

Defines:

- current transcript
- summary state
- current permissions
- current working directory
- active delegated sessions
- per-session config

### 9.2.3 `event_sequence`

Each task can include one or more events.

Event types:

- `user_message`
- `scheduled_wakeup`
- `channel_message`
- `system_alert`
- `delegation_reply`

Example:

```json
[
  {
    "event_id": "ev1",
    "type": "scheduled_wakeup",
    "channel": "cron",
    "payload": {
      "job_name": "daily-log-summary",
      "instruction": "Summarize the last 24h of errors and notify the admin only if severity >= high."
    }
  }
]
```

### 9.2.4 `success_criteria`

Must be machine-evaluable wherever possible.

Possible criteria:

- edited file matches expectation
- tests pass
- notification text includes required facts
- no forbidden tool used
- verification tool was called
- delegated task completed correctly
- state updated correctly

### 9.2.5 `scoring_weights`

Used to weight score components.

Example:

```json
{
  "task_success": 0.5,
  "verification": 0.2,
  "efficiency": 0.1,
  "constraint_obedience": 0.2
}
```

## 9.3 Event Input Format

Every episode begins with a structured event.

Canonical format:

```json
{
  "event_id": "string",
  "session_id": "string",
  "type": "user_message|scheduled_wakeup|channel_message|system_alert|delegation_reply",
  "timestamp": "ISO-8601",
  "source": {
    "surface": "cli|telegram|slack|discord|cron|system|session",
    "sender_id": "string|null",
    "sender_display": "string|null"
  },
  "payload": {},
  "constraints": {},
  "expected_delivery_mode": "foreground|background"
}
```

## 9.4 Tool Input Format

The benchmark harness must expose a structured tool interface.

Each tool invocation has this canonical form:

```json
{
  "tool_name": "string",
  "arguments": {},
  "request_id": "string"
}
```

## 9.5 Memory Retrieval Input Format

When the harness retrieves memory into context, it must do so explicitly.

Canonical format:

```json
{
  "retrieval_id": "string",
  "session_id": "string",
  "query": "string",
  "records": [
    {
      "memory_id": "string",
      "kind": "summary|fact|artifact|preference|task_history",
      "content": "string",
      "score": 0.0
    }
  ]
}
```

## 10. Output Specification

This section defines benchmark outputs.

## 10.1 Episode Trace Output

Each episode must produce a full trace.

Required fields:

```json
{
  "episode_id": "string",
  "task_id": "string",
  "session_id": "string",
  "model_profile": {},
  "status": "completed|failed|timed_out|invalid",
  "start_time": "ISO-8601",
  "end_time": "ISO-8601",
  "turns": [],
  "tool_calls": [],
  "memory_reads": [],
  "memory_writes": [],
  "verification": {},
  "final_result": {},
  "metrics": {},
  "scores": {}
}
```

## 10.2 Turn Output

Each turn must capture:

```json
{
  "turn_index": 1,
  "assistant_output": "string",
  "tool_calls": [],
  "token_usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  },
  "context_snapshot": {
    "estimated_tokens": 0,
    "history_tokens": 0,
    "tool_trace_tokens": 0,
    "retrieved_memory_tokens": 0,
    "system_tokens": 0
  }
}
```

## 10.3 Tool Result Output

Canonical tool result:

```json
{
  "request_id": "string",
  "tool_name": "string",
  "status": "ok|error|denied",
  "result": {},
  "latency_ms": 0,
  "side_effects": []
}
```

## 10.4 Final Result Output

Canonical final result:

```json
{
  "status": "success|failure|partial",
  "summary": "string",
  "artifacts": [],
  "notifications": [],
  "verification_claim": {
    "claimed": true,
    "evidence_present": true
  }
}
```

## 10.5 Suite Report Output

The suite report must include:

```json
{
  "suite_id": "string",
  "model_profile": {},
  "aggregate_scores": {},
  "slice_scores": {},
  "persistence_scores": {},
  "context_survivability": {},
  "task_results": [],
  "regression_findings": [],
  "deployment_recommendation": {}
}
```

## 11. Harness Tool Surface

The benchmark must use a compact but realistic tool set.

Recommended core tools:

- `list_files`
- `search_files`
- `read_file`
- `edit_file`
- `run_tests`
- `run_command_readonly`
- `send_notification`
- `read_inbox`
- `write_memory`
- `search_memory`
- `schedule_job`
- `list_jobs`
- `spawn_helper_session`
- `send_session_message`
- `submit_final`

Optional tools:

- `browser_action`
- `http_request`
- `structured_verify`

### 11.1 Tool Simulation Rule

Every tool must be deterministic for a given task fixture and model-independent.

### 11.2 Permission Rule

Each task defines whether a tool is:

- allowed
- denied
- ask-on-use
- read-only restricted

### 11.3 Isolation Rule

Some tasks may run in:

- `main_session`
- `isolated_helper`
- `readonly_helper`

The benchmark must simulate isolation as a state constraint even if full OS isolation is not implemented.

## 12. Session State Model

The session state is central to realistic agent benchmarking.

Required fields:

```json
{
  "session_id": "string",
  "session_type": "main|helper",
  "history": [],
  "rolling_summary": "string",
  "memory_index_refs": [],
  "pending_jobs": [],
  "pending_messages": [],
  "permissions": {
    "mode": "constrained|readonly|elevated",
    "allowed_tools": [],
    "denied_tools": []
  },
  "working_set": {
    "cwd": "string",
    "open_task_ids": []
  }
}
```

## 13. Operational Slices

The benchmark must produce slice-level scores.

### 13.1 Interactive Bounded Task

Examples:

- code bug fix
- log analysis request
- file investigation

### 13.2 Scheduled Maintenance Task

Examples:

- cron wakeup
- periodic summary
- health check
- inbox cleanup

### 13.3 Channel Response Task

Examples:

- Telegram-like message asking for status
- Slack-like message requiring contextual reply

### 13.4 Memory-Grounded Continuation

Examples:

- continue yesterday's repo investigation
- remember user preference from prior session

### 13.5 Delegated Helper Task

Examples:

- spawn read-only helper for repo exploration
- message another session for status

### 13.6 Verification-Required Task

Examples:

- edit code and run tests
- produce report and verify source data

## 14. Repetition and Context-Survivability Specification

This is a required part of the benchmark.

## 14.1 Purpose

Many local models fail under repeated use not because they cannot solve a task once, but because:

- transcript history grows
- tool traces consume context
- memory injections grow
- recurring tasks accumulate residual state
- the model forgets constraints or prior commitments

The benchmark must measure this directly.

## 14.2 Test Modes

Each benchmark suite must support at least the following modes.

### 14.2.1 Fresh Baseline

Each episode starts with minimal history.

Purpose:

- establish clean capability baseline

### 14.2.2 Full-History Carry

Each episode appends to the transcript, and prior content remains in context until truncated by the model or runtime limit.

Purpose:

- measure raw tolerance to transcript growth

### 14.2.3 Rolling Summary

Older history is replaced by a structured summary while recent turns stay verbatim.

Purpose:

- test whether summarization preserves capability

### 14.2.4 Retrieval Memory

Older history is removed from direct context and replaced by retrieval against stored records.

Purpose:

- test whether explicit memory retrieval restores performance

### 14.2.5 Mixed Workload Persistence

Episodes alternate across task families.

Purpose:

- approximate real agent operation

## 14.3 Required Persistence Metrics

At every episode index and context level, report:

- task success rate
- verification rate
- average turns
- average tool calls
- average total tokens
- failure mode distribution
- hallucinated-memory incidents
- forgotten-constraint incidents
- redundant-work incidents
- re-reading or re-searching inflation

## 14.4 Required Context Metrics

At every turn, estimate and report:

- system prompt tokens
- history tokens
- tool-trace tokens
- retrieved-memory tokens
- current user or event tokens
- available remaining context estimate

## 14.5 Degradation Thresholds

The benchmark must identify the following thresholds.

### 14.5.1 Stable Zone

The largest context load at which success remains within 95 percent of fresh baseline and no major safety regressions appear.

### 14.5.2 Soft Regression Zone

A zone where:

- success begins to drop
- verification weakens
- redundant tool use rises
- context confusion appears

but the model remains operational.

### 14.5.3 Failure Zone

A zone where:

- task success becomes unacceptable
- the model forgets key constraints
- hallucinated memory or repeated confusion becomes common

### 14.5.4 Recovery Effectiveness

The benchmark must quantify how much rolling summary and retrieval memory recover performance relative to full-history carry.

## 14.6 Recurring Cron-Style Evaluation

Cron-like work must be explicitly benchmarked.

Each cron task should test whether the model can:

- wake from persisted state
- interpret the job payload correctly
- perform a bounded workflow
- produce a deterministic output or notification
- avoid redoing irrelevant prior work

Suggested cron job families:

- daily error summary
- stale issue reminder
- repo health report
- inbox digest
- low-risk data cleanup report

## 15. Scoring Model

The benchmark must use a multi-axis scoring system with a clear primary metric.

## 15.1 Primary Score

The primary score is:

- Agentic Task Success

Definition:

Did the model satisfy the task's machine-evaluable success criteria inside the harness?

## 15.2 Secondary Scores

Required secondary scores:

- verification quality
- efficiency
- constraint obedience
- persistence capability
- context survivability

## 15.3 Per-Episode Score

Recommended weighted formula:

```text
EpisodeScore =
  0.50 * TaskSuccess
  0.20 * ConstraintObedience
  0.15 * VerificationScore
  0.10 * EfficiencyScore
  0.05 * MemoryUseScore
```

All components should be normalized to `[0, 1]`.

## 15.4 Persistence Score

Recommended formula:

```text
PersistenceScore =
  0.40 * RepeatedTaskSuccess
  0.20 * ContextRetention
  0.20 * RecoveryEffectiveness
  0.20 * StabilityAcrossEpisodes
```

## 15.5 Efficiency Score

Should reward:

- fewer unnecessary turns
- fewer unnecessary tool calls
- lower redundant searching

Should not penalize legitimate verification steps.

## 15.6 Constraint Obedience Score

Should penalize:

- forbidden tool use attempts
- write attempts in read-only mode
- ignoring channel or scheduler constraints
- unsafe escalation behavior

## 15.7 Verification Score

Should reward:

- performing verification before declaring success
- citing actual tool outputs
- matching verification evidence to the task

Should penalize:

- claiming success without checks
- relying only on code reading where runtime checks are expected

## 15.8 Memory Use Score

Should reward:

- retrieving the right prior facts
- avoiding re-discovery when memory was available

Should penalize:

- hallucinated prior facts
- irrelevant memory retrieval

## 16. Failure Taxonomy

The benchmark must classify failures, not merely count them.

Required failure classes:

- `task_unsolved`
- `timed_out`
- `invalid_finalization`
- `forbidden_action_attempted`
- `verification_missing`
- `hallucinated_state`
- `memory_confusion`
- `context_overflow_regression`
- `delegation_failure`
- `scheduler_misinterpretation`
- `channel_misrouting`

## 17. Deployment Recommendation Output

The benchmark should conclude with a practical deployment recommendation.

Required categories:

- `safe_for_bounded_unattended_jobs`
- `safe_for_supervised_agent_work`
- `safe_for_interactive_only`
- `not_recommended_for_agentic_use`

The recommendation must be slice-specific.

Example:

```json
{
  "overall": "safe_for_supervised_agent_work",
  "interactive_bounded_task": "strong",
  "scheduled_maintenance_task": "moderate",
  "channel_response_task": "moderate",
  "memory_grounded_continuation": "weak",
  "delegated_helper_task": "weak",
  "verification_required_task": "moderate",
  "notes": [
    "Reliable on bounded cron summaries",
    "Degrades sharply after ~40k effective context tokens in full-history mode",
    "Recovery is acceptable with rolling summary plus retrieval memory"
  ]
}
```

## 18. Benchmark Modes

The suite should support at least three benchmark modes.

### 18.1 Capability Mode

Tests fresh-session agentic capability.

### 18.2 Persistence Mode

Tests repeated episodes and context survivability.

### 18.3 Systems Mode

Tests the same suite under different model or runtime budgets:

- quantization
- context window
- summary policy
- retrieval policy

## 19. Safety and Simulation Boundaries

This benchmark simulates operational conditions but does not grant real-world authority.

The harness must ensure:

- no uncontrolled host execution
- all external side effects are simulated or sandboxed
- channel outputs are fixtures or mocks
- scheduler effects are benchmark-local

The benchmark must explicitly separate:

- model failure
- harness failure
- fixture failure

Failed tool fixtures or malformed task environments must not silently count as model failures.

## 20. Minimal Implementation Requirements

A conforming v1 implementation must support:

- task manifest loading
- event delivery
- multi-turn tool loop
- session persistence
- structured trace output
- at least one memory policy
- at least one cron-style task family
- at least one channel-message task family
- at least one verification-required coding task family
- context survivability reporting

## 21. Example Task

### 21.1 Example: Telegram-Style Cron Summary

Input:

```json
{
  "task_id": "cron_telegram_daily_errors_001",
  "title": "Daily error digest to admin",
  "slice": "scheduled",
  "difficulty": "easy",
  "event_sequence": [
    {
      "event_id": "ev1",
      "type": "scheduled_wakeup",
      "channel": "cron",
      "payload": {
        "job_name": "daily_error_digest",
        "instruction": "Summarize the last 24 hours of high-severity errors and send a short Telegram digest to admin."
      }
    }
  ],
  "success_criteria": {
    "must_send_notification": true,
    "notification_channel": "telegram",
    "must_include": ["highest severity", "count", "top source"],
    "must_not_include": ["low severity only incidents"],
    "forbidden_tools": ["edit_file"]
  }
}
```

Expected output shape:

```json
{
  "status": "success",
  "summary": "Prepared and sent a high-severity error digest.",
  "notifications": [
    {
      "channel": "telegram",
      "recipient": "admin",
      "content": "High-severity digest: 3 incidents..."
    }
  ]
}
```

### 21.2 Example: Coding Task with Verification

Input:

```json
{
  "task_id": "code_fix_test_001",
  "title": "Fix failing parser edge case",
  "slice": "verification",
  "difficulty": "medium",
  "event_sequence": [
    {
      "event_id": "ev1",
      "type": "user_message",
      "source": {
        "surface": "cli",
        "sender_id": "user-1",
        "sender_display": "operator"
      },
      "payload": {
        "text": "Fix the parser so empty input returns [] instead of throwing, then verify with tests."
      }
    }
  ],
  "success_criteria": {
    "must_edit_files": ["src/parser.ts"],
    "must_run_tests": true,
    "tests_must_pass": true,
    "must_report_verification_evidence": true
  }
}
```

## 22. Reporting Requirements

Every benchmark report must include:

- benchmark version
- task suite version
- full model or runtime configuration
- slice-level scores
- persistence and context results
- threshold findings
- representative failure samples
- deployment recommendation

Recommended human-readable sections:

- Overview
- Model Profile
- Capability Results
- Persistence Results
- Context Survivability
- Failure Analysis
- Deployment Recommendation

## 23. Interpretation Guidelines

Results should be interpreted conservatively.

### 23.1 High capability, low persistence

Interpretation:

- suitable for fresh interactive work
- not suitable for long-lived agent sessions without strong summarization

### 23.2 Moderate capability, strong persistence on bounded jobs

Interpretation:

- suitable for cron-style maintenance and repeated summaries
- may still be weak for complex coding or delegation

### 23.3 Strong verification but weak delegation

Interpretation:

- good as a supervised single-session agent
- weak for multi-session orchestration

### 23.4 Strong retrieval recovery

Interpretation:

- raw transcript carry is not required for safe deployment
- retrieval-first architectures may be viable

## 24. Non-Goals

This benchmark is not intended to:

- prove AGI-like autonomy
- replace security review
- replace raw-model evals like perplexity or factual QA
- emulate every proprietary agent product

It is intended to provide a practical, structured way to infer:

- what a local model can do inside an agent harness
- how long it can keep doing it
- which workloads are safe to delegate

## 25. Summary

This benchmark treats the local model as the reasoning core of a simulated local-agent runtime.

It uses references from OpenClaude, Hermes Agent, OpenClaw, and local-model benchmarking practice to define a benchmark that measures:

- agentic task success
- recurring-job reliability
- verification behavior
- persistent-session capability
- degradation under growing context
- recovery via summarization and retrieval

The central output is not just a score. It is a deployment-facing inference:

- what the model can do
- how repeatedly it can do it
- under what context pressure it regresses
- which classes of tasks are appropriate for unattended use

