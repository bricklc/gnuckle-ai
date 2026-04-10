# 21 Handoff - Phase 2 Audit And Remaining Success Metrics

## Date

2026-04-10

## Version

gnuckle 0.2.9

## Branch State

`main` at `8317560` plus uncommitted Phase 2 fixture and handoff changes in the working tree.

## Session Focus

Audit Phase 2 against the normative success metrics in `docs/19-benchmark-workflow-implementation-plan.md`, cross-check content constraints from `docs/18-benchmark-workflow-spec.md`, and prepare a clean handoff for the remaining benchmark implementation work grounded by `docs/16-openclaude-reference-map.md`.

---

## Do Now

- Fix the Phase 2 audit failures before starting Phase 3:
  - commit or at least stage and review the authored fixture tree
  - calibrate prompt-weight filler by actual token counts instead of word counts
  - expand undersized authored fixtures that do not meet doc 18 content-length constraints

## Blockers

- Phase 2 is structurally complete but not fully benchmark-valid yet.
- The current handoff in `docs/20-handoff-phase1-complete.md` contains stale Phase 2 text that conflicts with the verified working-tree state.

## Do Not Change

- Do not replace the existing agentic runtime with a second benchmark runner.
- Do not loosen the authored constraints from docs 18 and 19 just to fit the current fixtures.
- Do not treat Phase 2 as complete merely because `gnuckle.fixture_validator` passes; validator coverage is necessary but not sufficient.

## Critical Links

- Spec: `docs/18-benchmark-workflow-spec.md`
- Plan: `docs/19-benchmark-workflow-implementation-plan.md`
- Grounding: `docs/16-openclaude-reference-map.md`
- Prior handoff: `docs/20-handoff-phase1-complete.md`
- Validator: `gnuckle/fixture_validator.py`
- Fixture generator: `scripts/generate_phase2_fixtures.py`

---

## Phase 2 Audit

### Audit Inputs

- `python -m gnuckle.fixture_validator --json`
- direct file inventory under `gnuckle/fixtures/`
- direct content-length spot checks against doc 18 authored constraints
- `git ls-files` for repo-tracking status

### Success Metric Results

| Metric from doc 19 | Status | Evidence | Audit note |
|---|---|---|---|
| every fixture directory is committed to the repo | `FAIL` | `git ls-files` does not list the new Phase 2 fixture tree or validator files | Present in working tree only; not yet committed/tracked |
| every fixture directory is stable across runs | `PARTIAL` | generator is non-destructive; validator recomputes hashes | Stability is plausible in-tree, but not yet proven from committed content |
| every required workflow has a `_ground_truth.json` | `PASS` | validator passes; direct missing-count check returned `0` | Coverage is complete for all required deterministic workflows |
| fixture files satisfy the authored constraints from `18` | `PARTIAL` | several spot checks fail length targets | See findings below |
| fixture hashes can be recorded or recomputed for auditability | `PASS` | validator emits SHA-256 hashes for files and ground truth | Satisfies auditability requirement |
| prompt-weight filler exists at all required size levels | `PARTIAL` | `100.md`, `500.md`, `2000.md`, `6000.md`, `12000.md` exist | Files exist, but sizing is not token-calibrated |
| fixture and ground-truth validation can run before any model inference starts | `PASS` | `python -m gnuckle.fixture_validator` passes independently | Pre-inference validation path exists |

### Findings

1. `Phase 2` is not fully closed because the authored files are still uncommitted. Doc 19 says fixture directories must be committed to the repo, not just present locally.
2. The prompt-weight pack labels are not token-true. The generator uses word-count targets, not tokenizer-backed token targets.
   - Spot check word counts:
   - `100.md`: 236 words
   - `500.md`: 644 words
   - `2000.md`: 2072 words
   - `6000.md`: 6016 words
   - `12000.md`: 12068 words
   - This means the pack is structurally present, but the size labels do not currently mean what docs 18 and 19 require.
3. `CB-12` authored fixture files are materially below the spec’s `150-300` token target per file.
   - `brief.txt`: 44 words
   - `inputs.txt`: 19 words
   - `schedule.txt`: 23 words
   - `constraints.txt`: 37 words
4. `WF-C` `today.txt` is materially below the spec’s `200-300` token target.
   - `today.txt`: 67 words
5. `docs/20-handoff-phase1-complete.md` is internally inconsistent.
   - It now includes a correct Phase 2 completion note near the top.
   - It still also contains the stale old “Phase 2 in progress” section later in the file.
   - Next session should treat this doc as historically useful but not fully clean.

### Conclusion

Phase 2 passes the **completeness/validation** bar but not yet the full **normative authored-constraint** bar. Treat it as:

- structurally implemented
- validator-backed
- not fully benchmark-valid until the content-size mismatches and repo-tracking gap are resolved

---

## Remaining Success Metrics

### Phase 3 - Required Tool Surface

Required from doc 19:

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

Success metrics:

- tool surfaces are explicit, bounded, and workflow-selectable
- executor rejects undeclared tools cleanly
- tool denial behavior is traceable for `CB-10`
- refusal and denial results are preserved as structured trace artifacts

OpenClaude grounding from doc 16:

- explicit tool availability and injection
- bounded tool orchestration
- tool execution and in-band failure handling
- permission denials remain distinct from tool failure

### Phase 4 - Plain-Text Assistant Turn Handling

Success metrics:

- workflows can explicitly permit plain-text assistant turns
- runtime does not misclassify permitted plain-text turns as malformed tool behavior
- plain-text turns stay visible in traces and session history

Primary dependent workflow:

- `WF-E`

OpenClaude grounding:

- persistent multi-turn loop
- valid assistant turns without forced tool use

### Phase 5 - Mid-Task User Injection

Success metrics:

- injections can be scheduled deterministically
- injected turns remain visible in raw traces
- scoring can attribute success to whether the injection was absorbed

Primary dependent workflow:

- `WF-C`

OpenClaude grounding:

- persistent transcript growth
- deterministic turn sequencing

### Phase 6 - Tier Diagnostic And Routing

Required outputs:

- `D-1`, `D-2`, `D-3`
- Type assignment
- routing decision
- stress-variant enablement state

Success metrics:

- diagnostic runs before the main suite
- tier assignment is deterministic
- `Type 0` still produces useful floor output
- final summary includes both Type and Grade

OpenClaude grounding:

- deterministic workflow execution
- auditable run-level state and derived output

### Phase 7 - Core Battery Implementation

Must implement all Core workflows `CB-1` through `CB-12`, excluding `CB-8` from Core-score aggregation.

Key outputs that must exist:

- `tool_selection_precision`
- `MRMB`
- context degradation gradient
- convention-discovery component scores
- tool-denial threshold output
- `prompt_weight_tolerance`
- `hermes_viability`
- chained-execution scoring with audit evidence

OpenClaude grounding:

- multi-turn state threading
- tool validation and failure recovery
- context-budget accounting
- compaction/decay behavior
- verification-sensitive success rules

### Phase 8 - Life-Mgmt Profile Implementation

Must implement:

- `WF-A` through `WF-G`
- `WF-C-tl`
- `WF-G-explicit`
- `WF-G-decay`

Profile-specific outputs that must exist:

- `taglish_delta`
- `instruction_gap`
- `format_decay_rate`
- `discovery_retention`
- CUL retention
- `commitment_recall_rate`

### Phase 9 - Scoring, Classification, And Benchmark Output

Must produce:

- per-workflow score
- Core score
- weighted profile score
- composite score
- Type
- Grade
- usability flags
- raw audit evidence in JSON

Success metrics:

- grade math and composite math are reproducible from raw data
- diagnostic-only variants remain outside the profile composite where required
- repeated runs report mean and standard deviation

### Phase 10 - Reporting And Visualizer

Must clearly surface:

- Type and Grade
- Core/Profile/Diagnostic sections
- `MRMB`
- `instruction_gap`
- `format_decay_rate`
- `taglish_delta`
- tool-denial threshold
- prompt-weight tolerance
- Hermes viability
- resource viability
- sampler config and model metadata

OpenClaude grounding:

- traces preserve tool calls, results, denials, failures, and interruptions

### Phase 11 - Validation, Regression, And Release Readiness

Must add tests for:

- manifest validation
- fixture completeness validation
- composite math
- grade thresholds
- `MRMB` 3/3 pass logic
- routing and type assignment
- injection behavior
- plain-text turns
- prompt-weight and denial variants
- run-count aggregation and variance
- sampler-config capture
- model-metadata capture
- visualizer compatibility or explicit versioned failure

---

## Release Gate Still Open

Per doc 19, the benchmark is still incomplete until all of the following are true in the same branch state:

1. diagnostic suite runs and assigns a Type
2. Core battery runs and produces a Core score
3. `life-mgmt` profile runs and produces a weighted profile score
4. `CB-10`, `CB-11`, and `CB-12` emit their required special outputs
5. `WF-G-explicit` and `WF-G-decay` report diagnostic metrics outside the profile composite
6. `WF-C` proves mid-task injection works
7. `WF-E` proves plain-text assistant turns work
8. every workflow runs at least 3 times and reports mean plus standard deviation
9. final output includes Type, Grade, Core Score, Profile Score, Composite, and usability flags
10. sampler config and model metadata are recorded in run output
11. benchmark can be re-run on the same fixtures without content drift
12. JSON output contains the raw evidence needed to audit the final score
13. HTML report makes the benchmark understandable without opening source code

---

## Quick Repro

Commands run during this audit:

```bash
python scripts/generate_phase2_fixtures.py
python -m gnuckle.fixture_validator --json
git ls-files gnuckle/fixtures gnuckle/fixture_validator.py scripts/generate_phase2_fixtures.py docs/20-handoff-phase1-complete.md
```

Expected outputs:

- validator returns `ok: true`
- `git ls-files` should remain incomplete until files are added/committed

---

## Notes

- The next session should clean `docs/20-handoff-phase1-complete.md` or supersede it entirely with this document.
- Do not mistake fixture completeness for end-to-end benchmark validity; most of the benchmark still depends on Phases 3 through 11.
