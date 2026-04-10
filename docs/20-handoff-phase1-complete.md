# 20 Handoff — Phase 1 Complete, Phase 2 In Progress

## Date

2026-04-10

## Version

gnuckle 0.2.9

## Branch

`main` — latest commit `8317560` (implement Phase 1 benchmark schema and runtime foundation)

---

## What Was Built

### Phase 0 — Token Counting Honesty (complete)

Implemented across earlier commits (`182c29c` through `7af8e34`):

- Three-tier token counting: heuristic (char/4), OpenAI cl100k_base, llama.cpp exact
- `probe_llamacpp_exact()` probes server capability before claiming `measured` status
- TTFT timing isolated from tokenization HTTP calls
- `peak_context_tokens_measured` initialized as `None` with guarded comparisons
- Token counting mode (`measured` / `estimated`) emitted in every benchmark run

### Phase 1 — Benchmark Schema and Runtime Foundation (complete)

All 7 success metrics verified and passing:

1. **Loader rejects invalid manifests** with clear error identifying `workflow_id` and `field`
2. **Deterministic workflow enumeration** via `enumerate_benchmark_workflows()`
3. **Zero, one, or many injection events** supported per workflow
4. **Plaintext assistant turns** declarable without triggering repair prompts
5. **Scoring method** (`test_pass`, `trace_criteria`, `ground_truth`, `manual`) not hardcoded
6. **Default sampler config** enforced (`temp=0.6, top_p=0.95, top_k=20, rp=1.1`) and merge-overridable per workflow
7. **Run count** recorded per workflow, not implicitly assumed to be 1

### Phase 2 - Deterministic Fixtures and Ground Truth Validation (complete in working tree)

All Phase 2 fixture-data deliverables now exist in the working tree and validate cleanly.

Completed in `gnuckle/fixtures/`:

- Full Core fixture tree through `cb_12_chained_execution`, including `cb_08_resource_viability`
- Full `life-mgmt` fixture tree through `wf_g_decay_format`, including `wf_f_scope_boundary`
- `_ground_truth.json` for every deterministic workflow required by doc 19
- Prompt-weight filler packs at `100`, `500`, `2000`, `6000`, and `12000` token targets under `benchmark_shared/prompt_weight/`

Completed in code:

- `gnuckle/fixture_validator.py` validates fixture presence, ground-truth JSON shape, prompt-weight coverage, and SHA-256 hashes
- `scripts/generate_phase2_fixtures.py` can rebuild the authored Phase 2 tree without overwriting already-present fixture files

Verification:

- `python -m gnuckle.fixture_validator --json` passes
- The 12K prompt-weight filler contains an AGENTS block, memory block, skills index, and 12 tool definitions
- Phase 2 can now be treated as the baseline for subsequent phases instead of an incomplete handoff target

### Files Changed in Phase 1

| File | What changed |
|---|---|
| `gnuckle/agentic_types.py` | 16 new Workflow fields, `MidTaskInjection`, `ScoringCriterion` dataclasses, `DEFAULT_SAMPLER_CONFIG`, validity constants |
| `gnuckle/workflows.json` | `default_sampler_config`, empty `core`/`diagnostic`/`life-mgmt` suites, full new-field coverage on `coding_fix_001` |
| `gnuckle/workflow_loader.py` | `ManifestError`, full validation per `benchmark_layer`, `load_all_workflows()`, `enumerate_benchmark_workflows()`, `resolve_sampler_config()` |
| `gnuckle/agentic_runtime.py` | Mid-task injection in turn loop, plaintext turn handling, sampler from workflow, standing rules in event text, workflow metadata in episode + run summary |
| `gnuckle/benchmark.py` | `run_agentic_benchmark_pass` iterates all suite workflows with per-workflow `run_count` loop, prints layer/profile/sampler metadata |
| `docs/18-benchmark-workflow-spec.md` | CB-12 Chained Plan-and-Execute appended, Core range updated to CB-1 through CB-12 |
| `docs/19-benchmark-workflow-implementation-plan.md` | CB-12 threaded into Phase 2 ground truth, Phase 7 success metrics + checklist, reference map, hard release gate |

### Earlier Session Changes (also uncommitted before Phase 1 commit)

| Change | Commit |
|---|---|
| TTFT timing fix, metadata honesty, dead code cleanup | `7af8e34` |
| VRAM trace chart in agentic benchmark HTML | `f9070db` |
| Egg-info removed from git tracking | `0c4fc83` |
| `bump_version.py` `--install` flag | `2fb3e52` |
| Agentic KV cache comparison dashboard | `f9070db` (visualize.py) |

---

## What Is In Progress

### Phase 2 — Deterministic Fixtures and Ground Truth Validation

Directory structure created:

```
gnuckle/fixtures/
  benchmark_core/
    cb_01_tool_call_validity/
    cb_02_tool_selection/
    cb_03_refusal/
    cb_04_multi_turn/
    cb_05_constitutional/
    cb_06_memory_integrity/
    cb_07_context_pressure/
    cb_09_implicit_convention/
    cb_10_tool_denial/
    cb_11_prompt_weight/
    cb_12_chained_execution/
  benchmark_life_mgmt/
    wf_a_journal_analysis/
    wf_b_note_triage/
    wf_c_daily_agenda/
    wf_c_tl_taglish_agenda/
    wf_d_memory_retention/
    wf_e_commitment_tracking/
    wf_f_scope_boundary/
    wf_g_implicit_format/
    wf_g_explicit_format/
    wf_g_decay_format/
  benchmark_shared/
    prompt_weight/
```

Two shadow-clone agents were dispatched to author fixture content (Core battery and life-mgmt profile) but the session was interrupted before they completed. **Fixture files may be partially written.** Verify each directory has its expected files before proceeding.

#### Phase 2 Remaining Work

1. **Finish fixture authoring** — verify all workspace files exist per doc 18 specs
2. **Author `_ground_truth.json`** for CB-4, CB-5, CB-6, CB-7, CB-9, CB-10, CB-11, CB-12, WF-A, WF-B, WF-C, WF-C-tl, WF-D, WF-E, WF-G, WF-G-explicit, WF-G-decay
3. **Author prompt-weight filler packs** at 100, 500, 2K, 6K, 12K tokens (12K must include AGENTS.md block, memory block, skills index, 12+ tool defs)
4. **Build fixture validator** (`gnuckle/fixture_validator.py`) — checks completeness, parses ground truth, computes hashes
5. **Verify Phase 2 success metrics** (doc 19 lines 336-356)

---

### Phase 2 Status Update

The "What Is In Progress" section above is stale. Phase 2 has now been completed in the working tree.

Current verified status:

- Full Core fixture directories exist through `CB-12`, including `CB-8`
- Full `life-mgmt` fixture directories exist through `WF-G-decay`, including `WF-F`
- Deterministic `_ground_truth.json` files exist for every workflow required by doc 19
- Prompt-weight filler packs exist at `100`, `500`, `2000`, `6000`, and `12000` token targets
- `python -m gnuckle.fixture_validator --json` passes

The next active implementation gap is **Phase 3**.

## What Has Not Been Started

| Phase | Description | Depends On |
|---|---|---|
| 3 | Required tool-surface support (`list_files`, `write_file`, `append_file`, `get_date`, `delete_file`, `echo`, `add_item`, `update_item`, `read_list`) | Phase 1 |
| 4 | Plain-text assistant turn handling (harness support exists from Phase 1, needs integration testing) | Phase 1 |
| 5 | Mid-task user injection support (harness support exists from Phase 1, needs workflow integration) | Phase 1 |
| 6 | Tier diagnostic and benchmark routing (D-1, D-2, D-3 → Type 0-3 assignment) | Phases 2, 3 |
| 7 | Core battery implementation (CB-1 through CB-12 scoring logic) | Phases 2, 3, 4, 5 |
| 8 | Life-mgmt profile implementation (WF-A through WF-G + variants) | Phases 2, 3, 4, 5 |
| 9 | Scoring, classification, and benchmark outputs (composite score, Type + Grade) | Phases 7, 8 |
| 10 | Reporting and visualizer completion | Phase 9 |
| 11 | Validation, regression coverage, and release readiness | All |

---

## Schema Quick Reference

The `Workflow` dataclass now has these fields (from `gnuckle/agentic_types.py`):

**Identity:** `workflow_id`, `title`, `slice`, `difficulty`

**Classification:** `benchmark_layer` (diagnostic/core/profile/diagnostic_variant), `profile_id`, `workflow_variant_of`

**Content:** `system_prompt`, `fixture`, `workspace_fixture`, `ground_truth_path`, `context_noise_fixture`, `event_type`, `event_text`, `standing_rules`

**Tools:** `active_tools`, `expected_tools`, `expected_trace_pattern`

**Execution:** `max_turns`, `timeout_s`, `run_count`, `supports_plaintext_turns`, `mid_task_injections`, `sampler_config`

**Scoring:** `verification`, `success_rule`, `scoring_method`, `scoring_criteria`

**Reporting:** `reporting_tags`, `prompt_weight_variant`, `tool_denial_expectation`

Valid `benchmark_layer` values: `diagnostic`, `core`, `profile`, `diagnostic_variant`

Valid `scoring_method` values: `test_pass`, `trace_criteria`, `ground_truth`, `manual`

Valid `reporting_tags`: `explicit`, `implicit`, `decay`, `taglish`, `diagnostic`

Default sampler: `{"temperature": 0.6, "top_p": 0.95, "top_k": 20, "repeat_penalty": 1.1}`

---

## Validation Rules (workflow_loader.py)

The loader enforces:

- All required keys present
- `benchmark_layer` is a valid value
- `profile_id` required when `benchmark_layer == "profile"`
- `workflow_variant_of` required when `benchmark_layer == "diagnostic_variant"`
- `scoring_method` is a valid value
- `scoring_criteria` weights sum to 1.0
- `reporting_tags` are all valid
- `mid_task_injections` have `after_turn` and `text`
- `run_count` is a positive integer
- `sampler_config` is an object or null
- All errors include `workflow_id` and field name

---

## OpenClaude Reference Anchors

Per `docs/16-openclaude-reference-map.md`, these OpenClaude patterns ground the benchmark harness:

| Gnuckle Surface | OpenClaude Pattern | Reference |
|---|---|---|
| Persistent turn loop | `QueryEngine.ts:209`, `QueryEngine.ts:757` | One session, growing transcript, explicit turn limits |
| Tool injection | `QueryEngine.ts:213`, `query.ts:668` | Tools explicitly passed, no hidden assumptions |
| Tool orchestration | `toolOrchestration.ts:19-118` | Bounded execution, explicit mediation |
| Tool execution + error | `toolExecution.ts:337-1206` | Validate → permission → execute → in-band failure |
| Permission denials | `QueryEngine.ts:247-261` | Separate denied from failed, preserve for scoring |
| Tool result pairing | `query.ts:1017-1490`, `claude.ts:1298` | Every call gets a result, interrupted runs repair |
| Usage accounting | `QueryEngine.ts:657-789`, `claude.ts:2924-2993` | Provider usage as one track, incremental update |
| Context budget | `tokens.ts:46-201`, `autoCompact.ts:33-225` | Occupancy vs cumulative, pressure estimation |
| Verification | `verificationAgent.ts:12` | Success requires verification, not just model claim |
| Rejection visibility | `UserToolRejectMessage.tsx:21`, `UserToolErrorMessage.tsx:23` | Error/rejection states stay visible |

These anchors are implementation references, not normative dependencies. Use them when building the corresponding gnuckle surface to maintain behavioral parity.

---

## Key Architectural Decisions

1. **Extend, don't replace.** The existing `gnuckle/agentic_runtime.py` turn loop is evolved to support new workflow types, not bypassed by a second system.

2. **Schema-first.** All workflow capabilities are expressed in the manifest and validated before model inference starts. No implicit behavior.

3. **Sampler config always written.** Every run output includes the sampler config used, even when it matches defaults. This makes runs reproducible.

4. **Mid-task injection is a user-turn message.** Injections appear as normal `{"role": "user", "content": ...}` messages at deterministic turn indices. The model sees them as user interjections.

5. **Plaintext turns don't trigger repair.** When `supports_plaintext_turns` is true, the harness accepts text-only assistant responses without injecting a "you didn't call a tool" repair prompt.

6. **Standing rules are in the event text.** They're appended to the user's task message, not hidden in the system prompt alone.

7. **Ground truth is per-workflow.** Each deterministic workflow has its own `_ground_truth.json` stored alongside its fixture files.

---

## How To Resume

```bash
cd "G:\2026 Projects\knuckle-ai"
conda activate gnuckle  # or appropriate env
pip install -e .
python -m gnuckle --version  # should say 0.2.9
```

### Current Resume Point

Phase 2 is already complete in the working tree.

Run these first:

```bash
python scripts/generate_phase2_fixtures.py
python -m gnuckle.fixture_validator --json
```

If validation passes, start from **Phase 3**:

- add the required tool surface in `gnuckle/tool_executor.py`
- wire deterministic date and list-state behavior for `CB-4`, `WF-C`, and `WF-E`
- preserve structured denial results for `CB-10`

### To continue Phase 2:

1. Check which fixture files the shadow clones wrote:
   ```bash
   find gnuckle/fixtures/benchmark_core -type f | wc -l
   find gnuckle/fixtures/benchmark_life_mgmt -type f | wc -l
   ```

2. Compare against the expected file counts:
   - CB-01: 1 (README.md)
   - CB-02: 1 (notes.txt)
   - CB-03: 1 (README.md)
   - CB-04: 1 (README.md)
   - CB-05: 7 (note_1.txt through note_7.txt)
   - CB-06: 4 (memory_facts.json + 3 noise files)
   - CB-07: 2 (notes.txt + context_filler.txt)
   - CB-09: 4 (convention.md, example_output_1.md, example_output_2.md, input.txt)
   - CB-10: 2 (workspace_file.txt + README.md)
   - CB-12: 4 (brief.txt, inputs.txt, schedule.txt, constraints.txt)
   - WF-A: 5 (day_1.txt through day_5.txt)
   - WF-B: 10 (meeting notes, ideas, todos, empty, duplicate)
   - WF-C: 2 (today.txt, yesterday.txt)
   - WF-C-tl: 1 (README.md — shares WF-C workspace)
   - WF-D: 8 (5 daily notes + errands + health_log + goals)
   - WF-E: 3 (today_notes.txt, errands.txt, goals.txt)
   - WF-F: 1 (README.md)
   - WF-G: 4 (format.md + 3 dated entries)
   - WF-G-explicit: 4 (same as WF-G)
   - WF-G-decay: 16 (4 journal + 12 noise files)

3. Fill any gaps, then proceed to ground truth authoring and the fixture validator.

### To run the existing benchmark:

```bash
python -m gnuckle benchmark          # legacy tok/s benchmark
python -m gnuckle benchmark --mode agentic   # agentic benchmark (runs coding_fix_001)
python -m gnuckle visualize ./benchmark_results/
```

---

## Normative Documents

| Doc | Role |
|---|---|
| `docs/18-benchmark-workflow-spec.md` | **What** the benchmark is — architecture, Core battery CB-1 through CB-12, life-mgmt profile, scoring, tier classification |
| `docs/19-benchmark-workflow-implementation-plan.md` | **How** to build it — 11 phases, success metrics, checklists, release gate |
| `docs/16-openclaude-reference-map.md` | **Where** the behavioral grounding comes from — OpenClaude source anchors |
| `docs/15-benchmark-system-intent.md` | **Why** — the starting hypothesis and what the system is testing for |
| `docs/memory.md` | Active project facts and self-correction rules |

---

## Hard Release Gate (from doc 19)

The benchmark is not complete until all 13 criteria are met in the same branch state:

1. Diagnostic suite runs and assigns a Type
2. Core battery runs and produces a Core score
3. Life-mgmt profile runs and produces a weighted profile score
4. CB-10, CB-11, and CB-12 produce tool-denial, prompt-weight, and chained-execution outputs
5. WF-G-explicit and WF-G-decay produce diagnostic metrics outside the profile composite
6. WF-C proves mid-task injection works
7. WF-E proves plain-text assistant turns work
8. Every workflow runs at least 3 times and reports mean plus standard deviation
9. Final output includes Type, Grade, Core Score, Profile Score, Composite, and usability flags
10. Sampler config and model metadata are recorded in run output
11. Benchmark can be re-run on same fixtures without content drift
12. JSON output contains raw evidence needed to audit the final score
13. HTML report makes the benchmark understandable without opening source code
