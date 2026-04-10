# 19 Benchmark Workflow Implementation Plan

## Purpose

This note is the implementation control document for the benchmark system defined in:

- `docs/18-benchmark-workflow-spec.md`

It exists to turn the spec into a build sequence that is:

- executable
- auditable
- easy to check off during development
- hard to quietly dilute

This is not a restatement of the benchmark philosophy.

This is the primary development reference for building `18`.

If `18` defines what the benchmark is, this note defines:

- what must be built first
- what artifacts must exist
- what "done" means for each part
- what must be visible in output before the implementation can be called valid

## How To Use This Document

Use this note in three ways:

1. as the phase order for implementation
2. as the acceptance checklist during development
3. as the release gate before calling the benchmark complete

The rule is simple:

- do not mark a phase complete because the code "basically works"
- mark it complete only when its success metrics and output requirements are satisfied

## Lock Rule

For the `18` implementation, the requirements in this note are normative.

That means:

- every listed benchmark surface must be implemented or explicitly deferred here
- every required metric must appear in runtime output
- every required workflow asset must be versioned in the repo
- every checklist item must be satisfiable from code, fixtures, and generated outputs

If scope changes materially, the change should happen in a new numbered doc instead of silently drifting this one.

## Spec Sync Note

The checked-in `docs/18-benchmark-workflow-spec.md` currently stops at `CB-9`.

This implementation plan also reserves `CB-10`, `CB-11`, and `CB-12` based on the approved post-`19` review delta:

- `CB-10` Tool Denial Detection
- `CB-11` Prompt Weight Tolerance
- `CB-12` Chained Plan-and-Execute

Until `18` is updated in-repo, treat those three Core items as implementation-plan requirements that must be synced back into the normative spec.

---

## Success Definition

The `18` implementation is complete only when all of the following are true:

1. the Core battery `CB-1` through `CB-12` runs end-to-end from the CLI
2. the `life-mgmt` profile `WF-A` through `WF-G` runs end-to-end from the CLI
3. `WF-C-tl`, `WF-G-explicit`, and `WF-G-decay` run as diagnostics with separate reporting
4. the harness supports plain-text assistant turns without forcing a tool call
5. the harness supports mid-task user injection at deterministic turn indices
6. all benchmark workspaces are pre-authored, fixed, and versioned
7. every workflow with deterministic scoring has a `_ground_truth.json`
8. benchmark runs execute at least `3` times per workflow and report mean plus standard deviation
9. sampler settings are locked or explicitly overridden and always reported
10. per-workflow traces, scores, integrity metrics, resource metrics, and model metadata are written to JSON
11. the visualizer shows the new benchmark dimensions clearly enough to compare runs
12. a completed run can produce `Type X, Grade Y` plus the supporting score breakdown, usability flags, and prompt-weight outputs

If even one of those is missing, `18` is not complete.

---

## Implementation Principles

These principles constrain the build:

- extend the current `gnuckle` runtime instead of creating a second disconnected benchmark system
- preserve current CLI continuity through `gnuckle/cli.py`, `gnuckle/benchmark.py`, and `gnuckle/visualize.py`
- keep benchmark content deterministic by storing fixtures in-repo under `gnuckle/fixtures/`
- keep workflow definitions loadable from `gnuckle/workflows.json` or a closely related manifest format
- preserve raw metrics and traces alongside any composite score
- treat harness failures separately from model failures

## Phase 0 Prerequisite: Token Counting Honesty

Before any context-sensitive benchmark result is treated as benchmark-valid, the run output must declare whether token counting is:

- `measured`
- `estimated`

For `gnuckle`, that declaration is normative because the following workflows depend directly on context pressure, prompt weight, and memory load:

- `CB-6` Memory Integrity Curve
- `CB-7` Context Pressure Gradient
- `CB-10` Tool Denial Detection
- `CB-11` Prompt Weight Tolerance

### Required Output Flag

Every benchmark run must emit a machine-readable token-counting mode such as:

- `token_counting: measured (llama.cpp tokenizer)`
- `token_counting: estimated (char/4 heuristic)`
- `token_counting: estimated (OpenAI cl100k_base approximation)`

### Current Rule

When the benchmark is running through local `llama.cpp` server routes and can successfully render the active transcript through:

- `POST /apply-template`
- `POST /tokenize`

then context-sensitive reporting should be treated as `measured`.

If either step is unavailable or fails, the harness must fall back to `estimated`.

That means:

- context fill percentage is measured only when the exact llama.cpp path succeeds
- prompt-weight totals are measured only when tokenized through llama.cpp
- memory-load claims are approximate under fallback paths
- any `MRMB` or decay boundary derived from fallback counts carries uncertainty

### Required Warning

If token counting is `estimated`, the benchmark output and visualizer must show a warning that context-pressure metrics carry uncertainty.

For now, the minimum accepted warning is:

- context-sensitive benchmark metrics have roughly `15%` uncertainty until llama.cpp tokenizer integration exists

This warning must remain visible in runtime output and saved visualizer output.

## Current Starting Point

The repo already contains a usable baseline for the earlier coding workflow system:

- `gnuckle/agentic_runtime.py`
- `gnuckle/agentic_types.py`
- `gnuckle/session_store.py`
- `gnuckle/tool_executor.py`
- `gnuckle/workflow_loader.py`
- `gnuckle/workflows.json`
- `gnuckle/visualize.py`

That existing runtime should be evolved, not bypassed.

The largest gaps relative to `18` are:

- benchmark content breadth
- deterministic multi-workflow fixtures and ground truth
- profile-level orchestration
- diagnostic tiering
- plain-text assistant turn support
- mid-task user injection
- explicit/implicit comparison reporting
- integrity and decay reporting beyond the original coding slice

---

## Deliverable Map

The implementation has eleven deliverable groups:

1. benchmark schema and runtime foundation
2. deterministic fixtures and ground truth validation
3. required tool-surface support
4. plain-text assistant turn handling
5. mid-task user injection support
6. tier diagnostic and benchmark routing
7. Core battery implementation
8. `life-mgmt` profile implementation
9. scoring, classification, and benchmark outputs
10. reporting and visualizer completion
11. validation, regression coverage, and release readiness

Each group below includes:

- scope
- required artifacts
- dependencies
- success metrics
- a grocery-list checklist

---

## Phase 1 - Benchmark Schema And Runtime Foundation

### Goal

Upgrade the current agentic runtime from a single coding benchmark slice into a workflow system that can express:

- Core workflows
- profile workflows
- diagnostic workflows
- workflow variants
- deterministic injections
- workflow-specific scoring rules

### Required Artifacts

- workflow manifest schema extended in `gnuckle/workflows.json` or split into multiple versioned manifests
- type definitions updated in `gnuckle/agentic_types.py`
- loader validation updated in `gnuckle/workflow_loader.py`
- runtime orchestration updated in `gnuckle/agentic_runtime.py`
- benchmark entrypoint and run summary flow updated in `gnuckle/benchmark.py`

### Required Schema Capabilities

The workflow system must be able to represent:

- `benchmark_layer`: `diagnostic`, `core`, `profile`, `diagnostic_variant`
- `profile_id`
- `workflow_variant_of`
- `workspace_fixture`
- `ground_truth_path`
- `allowed_tools`
- `active_tools`
- `expected_trace_pattern`
- `standing_rules`
- `scoring_criteria`
- `mid_task_injections`
- `supports_plaintext_turns`
- `context_noise_fixture`
- `reporting_tags`
- `scoring_method`
- `run_count`
- `sampler_config`
- `prompt_weight_variant`
- `tool_denial_expectation`

### Success Metrics

- the loader rejects invalid workflow manifests with a clear error that identifies the broken workflow id and field
- a run can enumerate all declared benchmark workflows deterministically
- a workflow can declare zero, one, or many injection events
- a workflow can declare that plain-text assistant turns are allowed
- a workflow can declare a scoring method without hard-coding that method in only one legacy path
- the benchmark can enforce a default sampler config and report any override
- the benchmark records the workflow run count rather than implicitly assuming one pass

### Checklist

- [ ] Extend workflow manifest shape to support Core, Profile, Diagnostic, and Variant workflows
- [ ] Add validation for required fields and invalid combinations
- [ ] Make fixture paths and ground-truth paths first-class workflow fields
- [ ] Add workflow tags for `explicit`, `implicit`, `decay`, `taglish`, and `diagnostic`
- [ ] Add workflow fields for `scoring_method`, `run_count`, `sampler_config`, and prompt-weight variants
- [ ] Ensure run summaries preserve workflow layer and profile metadata
- [ ] Define the benchmark default sampler config (`temperature`, `top_p`, `top_k`, `repeat_penalty`)
- [ ] Ensure sampler config is always written to run output even when overridden
- [ ] Verify invalid manifests fail fast before model execution begins

---

## Phase 2 - Deterministic Fixtures And Ground Truth Validation

### Goal

Create the benchmark data layer required by `18`.

This phase is mandatory because the benchmark is not valid without fixed content.

### Required Artifact Layout

Add versioned benchmark content under `gnuckle/fixtures/` using a structure that cleanly separates workflows.

Minimum expected layout:

```text
gnuckle/fixtures/
  benchmark_core/
  benchmark_life_mgmt/
  benchmark_shared/
```

Each workflow fixture directory should contain:

- workspace files used by the model
- optional noise files used for decay or load tests
- `_ground_truth.json`
- optional `README.md` describing authoring intent

Prompt-weight workflows and variants must also include pre-authored filler blocks at the benchmarked sizes:

- `100` tokens
- `500` tokens
- `2K` tokens
- `6K` tokens
- `12K` tokens

The highest-weight filler must structurally resemble a realistic heavy system prompt, including:

- an `AGENTS.md`-style block
- a memory block
- a skills index
- 12 or more tool definitions with JSON-schema-like structure

### Required Ground Truth Coverage

Ground truth must exist for every workflow where deterministic scoring depends on known answers, including:

- `CB-4`
- `CB-5`
- `CB-6`
- `CB-7`
- `CB-9`
- `CB-10`
- `CB-11`
- `CB-12`
- `WF-A`
- `WF-B`
- `WF-C`
- `WF-C-tl`
- `WF-D`
- `WF-E`
- `WF-G`
- `WF-G-explicit`
- `WF-G-decay`

### Success Metrics

- every fixture directory is committed to the repo
- every fixture directory is stable across runs
- every required workflow has a `_ground_truth.json`
- fixture files satisfy the authored constraints from `18`
- fixture hashes can be recorded or recomputed for auditability
- prompt-weight filler exists at all required size levels
- fixture and ground-truth validation can run before any model inference starts

### Checklist

- [ ] Create fixture directories for all Core workflows
- [ ] Create fixture directories for all `life-mgmt` workflows
- [ ] Author `_ground_truth.json` for each deterministic workflow
- [ ] Record fixture constraints in a repeatable way so later edits do not silently break scoring assumptions
- [ ] Add a lightweight validator that checks fixture completeness before a benchmark run starts
- [ ] Ensure duplicate, empty-file, contradiction, and recurring-theme edge cases are explicitly present where required
- [ ] Author prompt-weight filler packs at `100`, `500`, `2K`, `6K`, and `12K`
- [ ] Add Hermes-scale structured filler for `CB-11`
- [ ] Validate fixture hashes or equivalent version markers as part of fixture validation

---

## Phase 3 - Required Tool-Surface Support

### Goal

Expand the bounded benchmark tool surface so the runtime can execute the Core battery and `life-mgmt` profile without falling back to legacy coding-only assumptions.

### Required Tool Surface

- `echo`
- `list_files`
- `read_file`
- `write_file`
- `append_file`
- `finish`
- `get_date`
- `add_item`
- `update_item`
- `read_list`

### Success Metrics

- tool surfaces are explicit, bounded, and workflow-selectable
- the executor rejects undeclared tools cleanly
- tool denial behavior is traceable for `CB-10`
- refusal and denial results are preserved as structured trace artifacts

### Checklist

- [ ] Add missing Core-battery tool definitions
- [ ] Add missing `life-mgmt` tool definitions
- [ ] Add bounded list-state tools for `CB-4`
- [ ] Add deterministic `get_date`
- [ ] Add explicit structured denial results for denied tool calls
- [ ] Verify undeclared tool calls are distinguishable from malformed arguments and execution failures

---

## Phase 4 - Plain-Text Assistant Turn Handling

### Goal

Allow workflows such as `WF-E` to contain valid assistant turns that do not call a tool.

### Success Metrics

- workflows can explicitly permit plain-text assistant turns
- the runtime does not misclassify permitted plain-text turns as malformed tool behavior
- plain-text turns remain visible in the trace and contribute to memory/coherence scoring

### Checklist

- [ ] Add workflow-level plain-text turn allowance
- [ ] Update runtime loop to accept permitted non-tool assistant turns
- [ ] Preserve plain-text turns in trace output and session history
- [ ] Add tests covering mixed tool and non-tool conversations

---

## Phase 5 - Mid-Task User Injection Support

### Goal

Support deterministic user interjections during a workflow, especially for `WF-C`.

### Success Metrics

- injections can be scheduled at fixed turn indices or after declared trigger points
- injected turns are visible in raw trace data
- scoring logic can attribute success or failure to whether the injection was absorbed

### Checklist

- [ ] Add injection scheduling to workflow schema
- [ ] Add runtime injection handling
- [ ] Preserve injections in trace output as first-class user events
- [ ] Add scoring hooks for injection absorption
- [ ] Add tests for deterministic injection timing

---

## Phase 6 - Tier Diagnostic And Benchmark Routing

### Goal

Implement the pre-run diagnostic gate that routes the model into the correct benchmark tier.

### Scope

Build the three diagnostic tasks defined in `18`:

- `D-1` single tool call with explicit instruction
- `D-2` two-tool sequence
- `D-3` tool call while obeying one standing rule

Then implement benchmark routing:

- `Type 0` -> floor reporting
- `Type 1` -> Core battery plus easy profile variants
- `Type 2` -> Core battery plus full profiles
- `Type 3` -> upgrade from Type 2 when the Core score exceeds `0.85`

### Required Output

Every benchmark run summary must preserve:

- diagnostic task results
- assigned type
- routing decision
- whether stress variants were enabled

### Success Metrics

- the diagnostic runs before the main suite, not after
- tier assignment is deterministic from the diagnostic results plus Core score rule
- a `Type 0` run still reports meaningful floor data instead of failing uselessly
- the final run summary includes both Type and Grade

### Checklist

- [ ] Implement `D-1`, `D-2`, and `D-3` as first-class workflows
- [ ] Add type-routing logic in the benchmark runner
- [ ] Add explicit reporting for `Type 0`, `Type 1`, `Type 2`, and `Type 3`
- [ ] Ensure `Type 3` is only assigned when the Core score exceeds `0.85`
- [ ] Ensure routing affects which workflows are executed
- [ ] Verify skipped workflows are reported as skipped, not silently absent

---

## Phase 7 - Core Battery Implementation

### Goal

Implement `CB-1` through `CB-12` as the universal benchmark layer.

### Scope

All eleven Core workflows must be runnable independently and as a battery.

`CB-8` is a measurement pass, not a scored workflow, so Core-score aggregation must exclude it.

They must produce:

- per-workflow scores
- per-workflow traces
- any special metrics required by the workflow

### Core-Specific Success Metrics

#### CB-1 Tool Call Validity

- emits a valid pass/fail score based on structured tool-call correctness

#### CB-2 Tool Selection Precision

- reports `tool_selection_precision`
- reports wrong, unnecessary, and disallowed tool calls

#### CB-3 Refusal Correctness

- distinguishes graceful refusal/workaround from hallucinated-tool failure

#### CB-4 Multi-Turn Coherence

- scores final state against exact expected list state

#### CB-5 Constitutional Retention

- reports `rules_retained / rules_stated`
- preserves the fixed filler-note sequence across all runs

#### CB-6 Memory Integrity Curve

- runs at `N = 5, 10, 15, 20, 25, 30`
- reports pass/fail at each point across repeated runs
- reports `MRMB`
- defines `MRMB` as the highest `N` answered correctly on `3/3` runs

#### CB-7 Context Pressure Gradient

- runs the same task at `Light`, `Medium`, `Heavy`, and `Critical`
- reports the degradation gradient `score_light - score_critical`

#### CB-8 Resource Viability

- records peak VRAM, steady VRAM, TTFT, average latency, wall-clock time, and peak/final context tokens

#### CB-9 Implicit Convention Adherence

- scores discovery, convention compliance, content accuracy, and efficiency separately

#### CB-10 Tool Denial Detection

- measures whether the model detects and adapts to denied tools instead of repeating or hallucinating around them
- reports a `tool_denial_threshold` or equivalent denial-tolerance output

#### CB-11 Prompt Weight Tolerance

- runs against prompt-weight filler at `100`, `500`, `2K`, `6K`, and `12K`
- reports `prompt_weight_tolerance`
- reports a derived `hermes_viability` signal from the heaviest prompt-weight variants

#### CB-12 Chained Plan-and-Execute

- scores discovery, sequence correctness, constraint retention, artifact correctness, and finish discipline separately
- requires all source files read before write
- validates output artifact against `_ground_truth.json` for item coverage, ordering, and constraint compliance
- diagnostic variants (`CB-12-inject`, `CB-12-fail`, `CB-12-delayed`, `CB-12-verify`) run separately with variant-specific pass/fail signals

### Checklist

- [ ] Implement scoring logic for `CB-1` through `CB-12`
- [ ] Ensure Core workflows can run both singly and as a battery
- [ ] Add fixed filler/noise files for `CB-5`, `CB-6`, and `CB-7`
- [ ] Add fixed denial scenarios for `CB-10`
- [ ] Add fixed prompt-weight scenarios for `CB-11`
- [ ] Add `MRMB` calculation for `CB-6`
- [ ] Add degradation-gradient calculation for `CB-7`
- [ ] Add convention discovery scoring for `CB-9`
- [ ] Add denial-threshold scoring for `CB-10`
- [ ] Add prompt-weight tolerance scoring for `CB-11`
- [ ] Add `CB-12` workspace fixtures (`brief.txt`, `inputs.txt`, `schedule.txt`, `constraints.txt`) and `_ground_truth.json`
- [ ] Add `CB-12` scoring logic for discovery, sequence, constraint retention, artifact correctness, and finish discipline
- [ ] Add `CB-12` diagnostic variants (`CB-12-inject`, `CB-12-fail`, `CB-12-delayed`, `CB-12-verify`) as separate runnable workflows
- [ ] Ensure Core score is the unweighted average of scored Core workflows `CB-1` through `CB-12`, excluding `CB-8`
- [ ] Verify Core outputs are stable across repeated runs with the same model/settings
- [ ] Run each Core workflow at least `3` times and report mean plus standard deviation
- [ ] Record hallucination count and step-efficiency ratio in Core outputs where applicable

---

## Phase 8 - Life-Mgmt Profile Implementation

### Goal

Implement the first complete domain profile exactly as specified in `18`.

### Scope

This phase includes:

- `WF-A`
- `WF-B`
- `WF-C`
- `WF-C-tl`
- `WF-D`
- `WF-E`
- `WF-F`
- `WF-G`
- `WF-G-explicit`
- `WF-G-decay`

### Profile-Specific Success Metrics

#### WF-A Journal Analysis

- all five files are read
- exactly four actionable tasks are scoreable
- exactly two recurring themes are scoreable
- the contradiction can be detected deterministically

#### WF-B Note Triage

- all ten files are read
- duplicate and empty-file handling is testable
- standing-rule obedience is scoreable without ambiguity

#### WF-C Daily Agenda Build

- incomplete carry-forward is scoreable
- health-first ordering is scoreable
- late user injection is scoreable
- conflict reporting is scoreable

#### WF-C-tl Taglish Variant

- uses the same ground truth and scoring rules as `WF-C`
- only language presentation changes
- reports `taglish_delta` against `WF-C`

#### WF-D Memory Retention Under Load

- all four standing rules are checked individually
- CUL retention is reported as `rules_retained / 4`

#### WF-E Commitment Tracking

- plain-text turns are supported without fake tool usage
- the expected commitment list is scored with no hallucination and no conflation checks
- reports `commitment_recall_rate` as a top-level workflow metric

#### WF-F Scope Boundary

- distinguishes graceful refusal from silent failure and tool hallucination

#### WF-G Family

- `WF-G` reports implicit-format discovery behavior
- `WF-G-explicit` establishes explicit-format ceiling
- `WF-G-decay` measures discovery and format retention under prior context noise

### Checklist

- [ ] Implement workflow manifests for all `life-mgmt` workflows
- [ ] Author all profile fixtures and ground truth
- [ ] Implement per-workflow scoring logic and required submetrics
- [ ] Weight the profile composite exactly as specified in `18`
- [ ] Ensure `WF-G-explicit` and `WF-G-decay` are excluded from the profile composite
- [ ] Ensure `WF-C-tl` uses the same scoring logic as `WF-C`
- [ ] Report `taglish_delta` for `WF-C-tl` versus `WF-C`
- [ ] Verify `WF-G` family reports `instruction_gap` and `format_decay_rate`
- [ ] Verify `WF-E` can complete with both tool and non-tool assistant turns in the same session
- [ ] Surface `commitment_recall_rate` explicitly for `WF-E`

---

## Phase 9 - Scoring, Classification, And Benchmark Outputs

### Goal

Make benchmark output mathematically aligned with `18` and usable for comparison.

### Required Score Layers

The implementation must report:

- per-workflow raw criterion scores
- per-workflow final score
- Core score
- profile score
- composite score
- diagnostic `instruction_gap`
- diagnostic `format_decay_rate`
- diagnostic `discovery_retention`
- diagnostic `taglish_delta`
- `tool_denial_threshold`
- `prompt_weight_tolerance`
- `hermes_viability`
- aggregate `hallucination_count`
- `commitment_recall_rate`
- `step_efficiency_ratio`
- machine-readable usability flags
- final `Type X, Grade Y`

### Required Math

#### Composite

```text
composite = (core_score x 0.4) + (avg_profile_scores x 0.6)
```

If no profile is selected:

```text
composite = core_score
```

#### Grade

Grade bands must be explicit in code and output.

Use these locked thresholds:

```text
Grade A: composite >= 0.90
Grade B: composite >= 0.75
Grade C: composite >= 0.60
Grade D: composite >= 0.45
Grade F: composite < 0.45
```

#### Usability Flags

The benchmark must emit machine-readable usability flags:

```text
can_act_at_all:          Type > 0
practical_bounded_work:  Type >= 2
survives_long_sessions:  CB-5 >= 0.67 and CB-7 gradient > -0.30
hermes_viable:           CB-11 hermes-full >= 0.50
safe_to_run_autonomous:  hallucination_count == 0 and CB-3 >= 0.80
```

### Success Metrics

- every score shown in reports is derivable from raw stored fields
- profile composites use the exact workflow weights from `18`
- diagnostic variants do not leak into the profile composite
- `Type` and `Grade` are both visible in the final output
- per-workflow scoring aggregates at least `3` runs and reports mean plus standard deviation
- hallucination count, denial threshold, prompt-weight tolerance, and taglish delta are preserved as first-class outputs
- step-efficiency ratio is visible beyond individual workflow criterion math

### Checklist

- [ ] Implement criterion-level scoring for each workflow
- [ ] Implement Core score aggregation
- [ ] Implement `life-mgmt` weighted profile composite
- [ ] Implement composite score math with no-profile fallback
- [ ] Implement instruction-gap reporting for explicit vs implicit variants
- [ ] Implement format-decay reporting for `WF-G` vs `WF-G-decay`
- [ ] Implement `taglish_delta` reporting
- [ ] Implement `tool_denial_threshold`
- [ ] Implement `prompt_weight_tolerance`
- [ ] Implement `hermes_viability`
- [ ] Implement aggregate `hallucination_count`
- [ ] Implement `commitment_recall_rate` as a named workflow output
- [ ] Implement `step_efficiency_ratio`
- [ ] Implement the locked grade thresholds
- [ ] Implement the machine-readable usability flags
- [ ] Aggregate workflow outputs across at least `3` runs with mean and standard deviation
- [ ] Ensure score JSON preserves both raw components and derived scores

---

## Phase 10 - Reporting And Visualizer Completion

### Goal

Make the new benchmark legible in both JSON and HTML outputs.

### Output Tiers

The reporting system must be organized into three output tiers:

#### Tier 1 - Report Card

High-signal summary for fast comparison:

- `Type`
- `Grade`
- Core score
- profile score
- composite score
- usability flags
- resource viability summary
- `MRMB`
- `prompt_weight_tolerance`
- `hermes_viability`

#### Tier 2 - Detailed Scores

Detailed benchmark reasoning:

- per-workflow scores
- criterion-level subscores
- instruction gap
- format decay
- taglish delta
- denial threshold
- hallucination count
- commitment recall rate
- step-efficiency ratio

#### Tier 3 - Artifacts

Full audit surface:

- raw trace
- tool calls
- tool results
- retries
- denials
- repairs
- verification results
- raw metadata
- fixture/version references
- sampler config

### Required JSON Visibility

JSON output must include:

- workflow id
- benchmark layer
- profile id when applicable
- run count
- mean and standard deviation for repeated runs
- trace
- criterion-level scoring
- final workflow score
- Core score
- profile score
- composite score
- diagnostic results
- Type
- Grade
- usability flags
- sampler config
- model metadata
- resource metrics
- integrity metrics
- decay metrics
- tool denial threshold
- prompt weight tolerance
- hermes viability
- taglish delta
- hallucination count
- commitment recall rate
- step-efficiency ratio

### Required HTML Visibility

The visualizer must show:

- final `Type X, Grade Y`
- Tier 1 report-card metrics
- Core battery breakdown
- profile breakdown
- diagnostic breakdown
- instruction-gap metrics
- decay metrics
- taglish delta
- denial threshold
- CUL retention metrics
- MRMB
- prompt-weight tolerance
- Hermes viability
- context-pressure gradient
- resource viability summary
- sampler config and model metadata summary
- per-workflow detail view

### Success Metrics

- a user can read one HTML report and understand why a model got its final Type and Grade
- the report exposes both universal and profile-specific weaknesses
- the report does not collapse diagnostic metrics into a single opaque score

### Checklist

- [ ] Extend run summary schema to include all new benchmark layers
- [ ] Add explicit Tier 1 / Tier 2 / Tier 3 report structure
- [ ] Update HTML visualizer for Core/Profile/Diagnostic sections
- [ ] Show Type and Grade prominently
- [ ] Show `MRMB`, `instruction_gap`, `format_decay_rate`, `taglish_delta`, and CUL retention explicitly
- [ ] Show tool denial threshold, prompt-weight tolerance, and Hermes viability explicitly
- [ ] Show resource viability metrics next to benchmark outcomes
- [ ] Show sampler config and model metadata in the report header or summary
- [ ] Show mean and standard deviation where repeated runs are aggregated
- [ ] Preserve per-workflow traces or trace links from the report

---

## Phase 11 - Validation, Regression, And Release Gate

### Goal

Prove the implementation is stable, deterministic, and ready to serve as the benchmark reference.

### Required Validation Layers

#### Fixture Validation

- benchmark run fails fast if fixture files or `_ground_truth.json` are missing

#### Schema Validation

- benchmark run fails fast if workflow manifests are malformed

#### Determinism Validation

- fixed-sequence workflows use the same injected files and order every run

#### Reporting Validation

- derived scores match raw data
- output contains required fields

#### UX Validation

- current CLI flow still works
- legacy benchmark mode still works
- the new benchmark mode is discoverable and usable

### Success Metrics

- fixture and manifest validation can run without starting model inference
- two runs against the same fixture set produce the same scoring structure
- repeated benchmark runs expose variance rather than silently hiding it
- no required benchmark field is missing from output
- old benchmark behavior is not broken by the new system

### Checklist

- [ ] Add tests for workflow manifest validation
- [ ] Add tests for fixture completeness validation
- [ ] Add tests for composite math and workflow-weight math
- [ ] Add tests for grade thresholds
- [ ] Add tests for `MRMB` 3/3 pass logic
- [ ] Add tests for routing and type assignment
- [ ] Add tests for injection behavior and plain-text turn handling
- [ ] Add tests for explicit/implicit diagnostic reporting
- [ ] Add tests for prompt-weight variants and tool-denial variants
- [ ] Add tests for run-count aggregation and variance reporting
- [ ] Add tests for sampler-config capture and model-metadata capture
- [ ] Run regression checks against existing coding benchmark behavior
- [ ] Verify visualizer still renders old and new run formats or fails clearly with versioning

---

## Canonical Artifact Checklist

The implementation should not be considered complete until all of these artifact classes exist:

- [ ] benchmark workflow manifests
- [ ] Core fixtures
- [ ] `life-mgmt` fixtures
- [ ] prompt-weight filler packs
- [ ] `_ground_truth.json` files
- [ ] fixture validation logic
- [ ] runtime support for plain-text turns
- [ ] runtime support for mid-task injections
- [ ] expanded benchmark tool executor support
- [ ] per-workflow scoring implementations
- [ ] Core/profile/composite aggregation
- [ ] type-routing logic
- [ ] grade-threshold logic
- [ ] run-count aggregation and variance reporting
- [ ] sampler-config capture
- [ ] model-metadata capture
- [ ] usability flags
- [ ] JSON output updates
- [ ] HTML visualizer updates
- [ ] automated tests for the new benchmark paths

---

## Suggested File Touch List

The following files are the confirmed primary surfaces in the current `gnuckle` codebase:

- `gnuckle/agentic_types.py`
- `gnuckle/agentic_runtime.py`
- `gnuckle/tool_executor.py`
- `gnuckle/workflow_loader.py`
- `gnuckle/workflows.json`
- `gnuckle/benchmark.py`
- `gnuckle/visualize.py`
- `gnuckle/session_store.py`
- `gnuckle/fixtures/...`

These are confirmed because the current code already assigns them the relevant responsibilities:

- `gnuckle/agentic_types.py`
  - workflow/session dataclasses and runtime contract fields
- `gnuckle/workflow_loader.py`
  - manifest loading and validation
- `gnuckle/agentic_runtime.py`
  - bounded episode execution, trace emission, verification flow, and per-episode result construction
- `gnuckle/tool_executor.py`
  - explicit tool surface, validation, permission checks, and tool result shaping
- `gnuckle/session_store.py`
  - multi-turn state persistence
- `gnuckle/benchmark.py`
  - suite loading, top-level run orchestration, summary writing, token/resource aggregation helpers, and CLI-facing routing
- `gnuckle/visualize.py`
  - JSON-to-HTML rendering, trace visibility, and benchmark reporting presentation

If the implementation introduces new modules, these are optional additions rather than confirmed existing surfaces:

- `gnuckle/benchmark_scorer.py`
- `gnuckle/benchmark_fixtures.py`
- `gnuckle/benchmark_reports.py`
- `gnuckle/benchmark_validation.py`

These names are suggestions, not mandates.

---

## OpenClaude Reference Map

The following OpenClaude sources are the highest-value implementation references for `18`.

These are not normative dependencies.

They are useful because they show concrete patterns for:

- deterministic workflow orchestration
- bounded tool execution
- plain-text assistant turns
- refusal and tool-rejection handling
- context and token pressure accounting
- trace preservation
- auditable run output

Use them as implementation references when the corresponding `gnuckle` surface is being built.

### Phase 1 - Runtime Foundation

#### A workflow can declare a scoring method without hard-coding one legacy path

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:209`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:213`

#### A run can enumerate and execute workflows deterministically

- `/G:/2026%20Projects/openclaude/src/query.ts:1367`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts:19`

### Phase 6 - Tier Diagnostic And Routing

#### Diagnostic runs before the main suite

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:209`

#### Tier assignment remains auditable from run output

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:629`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:861`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:991`

### Phase 7 - Core Battery

#### CB-1 tool_call_validity

- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:614`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:682`

#### CB-2 tool_selection_precision

- `/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts:91`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:247`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:261`

#### CB-3 refusal_correctness

- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:469`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:995`
- `/G:/2026%20Projects/openclaude/src/components/messages/UserToolResultMessage/UserToolRejectMessage.tsx:21`

#### CB-4 multi_turn_coherence

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:184`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`

#### CB-5 constitutional_retention

- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`

#### CB-6 memory_integrity_curve

- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

#### CB-7 context_pressure_gradient

- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:33`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:72`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

#### CB-8 resource_viability

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:789`
- `/G:/2026%20Projects/openclaude/src/services/api/claude.ts:2924`
- `/G:/2026%20Projects/openclaude/src/services/api/claude.ts:2993`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:46`

#### CB-9 implicit_convention_adherence

- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts:19`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`

#### CB-10 tool_denial_detection

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:247`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:261`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:995`
- `/G:/2026%20Projects/openclaude/src/components/messages/UserToolResultMessage/UserToolRejectMessage.tsx:21`

#### CB-11 prompt_weight_tolerance

- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:33`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

#### CB-12 chained_plan_and_execute

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:184` (multi-turn state threading)
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757` (turn sequencing)
- `/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts:91` (tool selection chain)

### Phase 8 - Life-Mgmt Profile

#### WF-C late user injection remains coherent

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:209`

#### WF-D CUL retention

- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`

#### WF-E plain-text turns without fake tool use

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`
- `/G:/2026%20Projects/openclaude/src/query.ts:1367`

#### WF-F scope boundary

- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:995`
- `/G:/2026%20Projects/openclaude/src/components/messages/UserToolResultMessage/UserToolRejectMessage.tsx:21`

#### WF-G / WF-G-explicit / WF-G-decay

- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

### Phase 3 / 4 / 5 - Runtime Capability Upgrades

#### Plain-text assistant turns are valid when workflow permits

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`

#### Tool surfaces are explicit and bounded

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:213`
- `/G:/2026%20Projects/openclaude/src/query.ts:669`

#### Context-noise playback is fixed and repeatable

- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

#### Runtime survives tool failures instead of crashing

- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:469`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:995`

### Phase 9 - Scoring And Classification

#### Every derived score is auditable from raw run data

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:789`
- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:991`

#### Verification-sensitive scoring

- `/G:/2026%20Projects/openclaude/src/tools/AgentTool/built-in/verificationAgent.ts:12`

### Phase 10 - Reporting

#### Trace must preserve tool calls, results, and failures

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:757`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:337`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:469`

#### Interrupts and missing tool results remain visible and repairable

- `/G:/2026%20Projects/openclaude/src/query.ts:1017`
- `/G:/2026%20Projects/openclaude/src/query.ts:1490`
- `/G:/2026%20Projects/openclaude/src/services/api/claude.ts:1298`

### Highest-Value References Overall

- `/G:/2026%20Projects/openclaude/src/QueryEngine.ts:209`
- `/G:/2026%20Projects/openclaude/src/query.ts:669`
- `/G:/2026%20Projects/openclaude/src/query.ts:1367`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:337`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:469`
- `/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts:995`
- `/G:/2026%20Projects/openclaude/src/utils/tokens.ts:201`
- `/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts:225`

### Gnuckle Target Mapping

Use this table to translate the OpenClaude references into confirmed `gnuckle` implementation surfaces.

This is the shortest path from:

- "this behavior exists in OpenClaude"

to:

- "this is where to implement the analogous behavior in `gnuckle`"

| Benchmark need | OpenClaude reference(s) | Confirmed gnuckle target | Why this target |
|---|---|---|---|
| Workflow declaration and per-workflow execution mode | `QueryEngine.ts:209`, `QueryEngine.ts:213`, `query.ts:1367` | `gnuckle/workflows.json`, `gnuckle/agentic_types.py`, `gnuckle/workflow_loader.py` | Workflow-level capability needs to be represented in schema before runtime can honor it |
| Deterministic workflow orchestration | `query.ts:1367`, `toolOrchestration.ts:19` | `gnuckle/benchmark.py`, `gnuckle/agentic_runtime.py` | Run ordering, workflow selection, and per-workflow execution sequencing live here |
| Diagnostic-first routing | `QueryEngine.ts:209`, `QueryEngine.ts:629`, `QueryEngine.ts:861`, `QueryEngine.ts:991` | `gnuckle/benchmark.py` | Type assignment and auditable routing belong at the run-controller level |
| Bounded tool surfaces | `QueryEngine.ts:213`, `query.ts:669`, `toolOrchestration.ts:19` | `gnuckle/tool_executor.py`, `gnuckle/workflow_loader.py` | Tools must be constrained both in manifest validation and execution |
| Tool call validation and malformed tool handling | `toolExecution.ts:614`, `toolExecution.ts:682`, `toolExecution.ts:469` | `gnuckle/agentic_runtime.py`, `gnuckle/tool_executor.py` | Runtime must validate calls and recover or fail clearly when calls are malformed |
| Tool rejection and refusal handling | `toolExecution.ts:469`, `toolExecution.ts:995`, `UserToolRejectMessage.tsx:21` | `gnuckle/tool_executor.py`, `gnuckle/agentic_runtime.py`, `gnuckle/visualize.py` | Rejection needs execution behavior, trace preservation, and report visibility |
| Multi-turn state retention | `QueryEngine.ts:184`, `QueryEngine.ts:757` | `gnuckle/agentic_runtime.py`, `gnuckle/session_store.py` | Conversation state and turn-to-turn continuity live in runtime/session storage |
| Plain-text assistant turns | `QueryEngine.ts:757`, `query.ts:1367` | `gnuckle/agentic_runtime.py`, `gnuckle/agentic_types.py` | The runtime needs an explicit mode switch so non-tool turns are valid when the workflow allows them |
| Mid-task user injection | `QueryEngine.ts:757`, `QueryEngine.ts:209` | `gnuckle/agentic_runtime.py`, `gnuckle/workflow_loader.py` | Injection behavior must be declared in workflow metadata and executed by the runtime |
| Context and token accounting | `query.ts:669`, `utils/tokens.ts:201`, `utils/tokens.ts:46` | `gnuckle/benchmark.py`, `gnuckle/agentic_runtime.py` | Token, context, and resource metrics are gathered during execution and summarized after |
| Context pressure and compaction/decay behavior | `autoCompact.ts:33`, `autoCompact.ts:72`, `autoCompact.ts:225` | `gnuckle/agentic_runtime.py`, `gnuckle/benchmark.py`, optional `gnuckle/benchmark_validation.py` | `CB-6`, `CB-7`, and decay workflows need deterministic pressure simulation and reporting |
| Trace preservation of actions, results, failures, and interruptions | `QueryEngine.ts:757`, `toolExecution.ts:337`, `toolExecution.ts:469`, `query.ts:1017`, `query.ts:1490` | `gnuckle/agentic_runtime.py`, `gnuckle/visualize.py` | Runtime emits the trace; visualizer must expose it cleanly |
| Verification-sensitive scoring | `verificationAgent.ts:12` | `gnuckle/benchmark.py`, optional `gnuckle/benchmark_scorer.py` | Verification should be a score input, not an afterthought hidden in one workflow path |
| Auditable derived scores | `QueryEngine.ts:789`, `QueryEngine.ts:991` | `gnuckle/benchmark.py`, `gnuckle/visualize.py`, optional `gnuckle/benchmark_reports.py` | Derived scores must remain explainable from raw evidence in JSON and HTML |
| Resource viability reporting | `QueryEngine.ts:789`, `claude.ts:2924`, `claude.ts:2993`, `utils/tokens.ts:46` | `gnuckle/benchmark.py`, `gnuckle/agentic_runtime.py`, `gnuckle/visualize.py` | Resource metrics must be collected per run and then surfaced in reports |
| Fixed fixture and ground-truth validation | `query.ts:1367`, `query.ts:669` | `gnuckle/workflow_loader.py`, optional `gnuckle/benchmark_validation.py`, `gnuckle/fixtures/...` | Deterministic benchmark validity starts with fixture completeness and declared expectations |

### Priority Crosswalk

If implementation time is constrained, reference these pairings first:

1. `QueryEngine.ts:209` -> `gnuckle/workflow_loader.py` and `gnuckle/benchmark.py`
2. `query.ts:669` -> `gnuckle/agentic_runtime.py` and `gnuckle/benchmark.py`
3. `query.ts:1367` -> `gnuckle/benchmark.py`
4. `toolExecution.ts:337` and `toolExecution.ts:469` -> `gnuckle/tool_executor.py` and `gnuckle/agentic_runtime.py`
5. `utils/tokens.ts:201` -> `gnuckle/benchmark.py`
6. `autoCompact.ts:225` -> `gnuckle/agentic_runtime.py`

Those pairings cover most of the hard benchmark behaviors:

- deterministic routing
- bounded execution
- trace integrity
- refusal and failure handling
- token/context accounting
- under-load decay measurement

---

## Recommended Build Order

This is the recommended execution order for actual development:

1. extend workflow schema and loader
2. build fixture and ground-truth validation
3. add required tool-surface support
4. add plain-text turn handling
5. add mid-task injection support
6. implement diagnostic workflows and routing
7. implement Core battery
8. implement `life-mgmt` workflows
9. implement scoring and classification
10. update JSON and HTML reporting
11. add validation and regression tests

This order minimizes rework because:

- runtime capabilities land before workflows that depend on them
- scoring lands after the workflows exist
- reporting lands after the output shape stabilizes

---

## Hard Release Gate

Do not call the `18` implementation complete until all of the following are true in the same branch state:

1. the diagnostic suite runs and assigns a Type
2. the Core battery runs and produces a Core score
3. the `life-mgmt` profile runs and produces a weighted profile score
4. `CB-10`, `CB-11`, and `CB-12` produce tool-denial, prompt-weight, and chained-execution outputs
5. `WF-G-explicit` and `WF-G-decay` produce diagnostic metrics outside the profile composite
6. `WF-C` proves mid-task injection works
7. `WF-E` proves plain-text assistant turns work
8. every workflow runs at least `3` times and reports mean plus standard deviation
9. the final output includes `Type`, `Grade`, `Core Score`, `Profile Score`, `Composite`, and usability flags
10. sampler config and model metadata are recorded in the run output
11. the benchmark can be re-run on the same fixtures without content drift
12. JSON output contains the raw evidence needed to audit the final score
13. the HTML report makes the benchmark understandable without opening source code

---

## Summary

`18` is not complete when the first workflow passes.

It is complete when:

- the benchmark system can run the full Core battery
- the first full profile exists
- the harness supports the required conversation behaviors
- deterministic fixtures and ground truth are in place
- repeated runs expose mean and variance instead of one-off scores
- prompt-weight and tool-denial behavior are reported explicitly
- scoring and reporting match the spec
- the outputs are strong enough to use as the benchmark reference

This note is intended to be used as the grocery list during development.

If a task is not checked off here, it should not be assumed done.
