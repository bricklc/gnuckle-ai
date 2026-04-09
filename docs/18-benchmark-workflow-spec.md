# 18 Benchmark Workflow Specification

## Context

This document merges:

- `15-benchmark-system-intent.md` -- what gnuckle is trying to measure
- `17-personal-productivity-benchmark-workflows.md` -- the first scenario pack
- architectural decisions made during review

It defines the full benchmark structure, the Core battery, the Profile system, and the first complete profile (`life-mgmt`).

This is the build spec. Implementation follows from here.

---

## Architecture

The benchmark has three layers.

### Layer 1 -- Core Battery

Use-case agnostic. Every model runs this. Tests the six pillars from the intent doc without domain-specific content.

### Layer 2 -- Profiles

Domain-specific scenario packs. Each profile represents a real local-model user archetype. A user selects one or more profiles to run. Profiles produce per-profile scores.

### Layer 3 -- Tier Classification

A diagnostic places the model into a Type (1, 2, or 3). Core and Profile scores produce a Grade (A through F). Final output is `Type X, Grade Y`.

```
gnuckle benchmark system
|
|---- Core Battery (universal, every model)
|   |---- CB-1  tool_call_validity
|   |---- CB-2  tool_selection_precision
|   |---- CB-3  refusal_correctness
|   |---- CB-4  multi_turn_coherence
|   |---- CB-5  constitutional_retention
|   |---- CB-6  memory_integrity_curve
|   |---- CB-7  context_pressure_gradient
|   |---- CB-8  resource_viability
|   |---- CB-9  implicit_convention_adherence
|   |---- CB-10 tool_denial_detection
|   `---- CB-11 prompt_weight_tolerance
|
|---- Profiles (user selects one or more)
|   |---- life-mgmt        <- defined in this document
|   |---- knowledge-rag     <- future
|   |---- dev-tooling       <- partially exists
|   |---- file-org          <- future
|   `---- comms-draft       <- future
|
|---- Tier Classification
|   |---- Diagnostic gate (3-5 tasks, runs first)
|   |---- Type assignment (1 = floor, 2 = practical, 3 = stress)
|   |---- Grade assignment (A-F from Core + Profile scores)
|   `---- Final output: Type X, Grade Y
|
`---- Reporting
    |---- Per-workflow trace (exists)
    |---- Score breakdown (exists)
    |---- Integrity decay curve (new)
    |---- Constitutional retention rate (new)
    |---- Explicit vs implicit instruction comparison (new)
    |---- Prompt weight tolerance summary (new)
    |---- Tool denial threshold summary (new)
    |---- Resource viability summary (exists, formalize)
    `---- Composite score
```

---

## Composite Scoring

```
composite = (core_score x 0.4) + (avg_profile_scores x 0.6)
```

Core score is the unweighted average of scored Core workflows CB-1 through CB-11, excluding CB-8.

Profile score is the unweighted average of all workflows in the selected profile(s).

If no profile is selected, composite equals core score alone.

### Grade bands

Grade thresholds are fixed:

| Grade | Composite threshold |
|---|---|
| A | >= 0.90 |
| B | >= 0.75 |
| C | >= 0.60 |
| D | >= 0.45 |
| F | < 0.45 |

---

## The Explicit vs Implicit Instruction Axis

This is not a single test. It is a testing dimension that applies across workflows.

### The problem

Most benchmarks only test whether a model follows instructions that are stated directly in the prompt. Real agents must also:

- discover conventions from workspace content (e.g. a `format.md` in the folder)
- infer behavioral expectations from prior entries (e.g. all journal entries use the same header style)
- apply standing rules from the system prompt that are never repeated in the task prompt

These are different cognitive demands. A model that scores well on explicit instruction may fail completely when the same instruction is implicit.

### The axis

Any workflow can be run in two modes:

| Mode | Definition |
|---|---|
| **Explicit** | The instruction is stated directly in the task prompt. Example: "Format your journal entry with a date header, mood tag, and bullet-style body." |
| **Implicit** | The instruction is NOT in the task prompt. It exists only as a discoverable convention in the workspace (e.g. a `format.md` file) or as a pattern visible in prior entries. The system prompt may say "follow any conventions found in the workspace" but does not name the file or describe the format. |

### How to apply it

Not every workflow needs both modes. The axis is most revealing when applied to workflows where the model must produce structured output. Recommended pairings:

| Workflow | Explicit variant | Implicit variant |
|---|---|---|
| WF-A Journal Analysis | Prompt names the expected summary format | Prompt says "summarize" with no format guidance; a `summary_format.md` exists in the workspace |
| WF-C Daily Agenda Build | Prompt specifies morning/afternoon blocks, health-first ordering | Prompt says "build a plan for today"; previous agendas in the workspace already use that structure |
| WF-G Journal Entry Logging | Prompt describes the format to use | Prompt says "log today's entry"; a `format.md` exists but is not referenced |

### Scoring the axis

When a workflow is run in both modes, report:

```
WF-G (explicit):  0.90
WF-G (implicit):  0.55
instruction_gap:  0.35
```

The `instruction_gap` is the delta. A large gap means the model depends on being told what to do. A small gap means the model can discover and apply conventions independently.

This metric is reported per-workflow where both variants are run, and as a profile-level average where applicable.

### Why this matters

A personal assistant that only works when you spell out every instruction is a command executor, not an agent. The implicit mode tests whether the model exhibits the minimum initiative required to be useful as a daily assistant -- checking for conventions before acting, not waiting to be told.

---

## The Prompt Weight Axis

This is a second benchmark-wide testing dimension.

The explicit/implicit axis asks whether the model can discover structure without being told.

The prompt-weight axis asks whether the model can still behave correctly as the system prompt becomes heavier and more realistic.

### The problem

Small benchmark prompts do not resemble real assistant deployments.

Real local assistants often run with:

- standing rules
- user memory
- skills references
- long tool menus
- tool JSON schemas
- profile-specific behavior notes
- AGENTS.md-style instructions

A model that works under a 200-token system prompt may collapse under a Hermes-style prompt stack.

### The axis

Prompt-weight-sensitive workflows can be run with pre-authored system-prompt filler at these levels:

- 100 tokens
- 500 tokens
- 2K tokens
- 6K tokens
- 12K tokens

The heaviest filler should structurally resemble a realistic assistant prompt, including:

- an AGENTS.md-style block
- a memory block
- a skills index
- 12 or more tool definitions with schema-like structure

### Reporting

When a workflow is run across prompt-weight levels, report:

```text
prompt_weight_tolerance: 0.62
hermes_viability:        true
```

`prompt_weight_tolerance` measures how much usable behavior survives under heavier prompt load.

`hermes_viability` is a derived diagnostic indicating whether the model remains viable under the heaviest Hermes-like prompt variant.

---

## Tier Diagnostic

The diagnostic runs before anything else. It is a fixed gate of 3-5 minimal tasks.

Purpose: determine what difficulty tier the model should face. This prevents wasting time running stress tests on a model that cannot format a tool call.

### Diagnostic tasks

| Task | Tests | Pass threshold |
|---|---|---|
| D-1: Single tool call with explicit instruction | Can the model call one named tool with given arguments- | Valid tool call emitted |
| D-2: Two-tool sequence | Can it chain two tool calls in the correct order- | Both calls valid, correct order |
| D-3: Tool call with one standing rule | Can it complete a task while obeying one system-prompt rule- | Task done AND rule obeyed |

### Tier assignment

| Result | Type | What runs next |
|---|---|---|
| Fails D-1 | Type 0 -- not harness-viable | Core battery only, report floor |
| Passes D-1, fails D-2 or D-3 | Type 1 -- minimal harness competence | Core battery, easy profile variants |
| Passes all three | Type 2 -- practical competence | Core battery, full profiles |
| Passes all three with high efficiency | Type 3 -- stress candidate | Core battery, full profiles, stress variants |

Type 3 is not assigned by the diagnostic alone. It is upgraded from Type 2 if the Core battery score exceeds 0.85.

---

## Core Battery Specification

Each Core battery test is a single self-contained workflow. No domain-specific content. Generic tools and generic prompts.

### CB-1 -- Tool Call Validity

**Purpose:** Can the model emit a structurally valid tool call-

**Tools:** `echo` (takes one string argument, returns it)

**Prompt:** "Use the echo tool to repeat the phrase: benchmark test."

**Scoring:**
- 1.0 -- valid tool call with correct argument
- 0.5 -- valid tool call with wrong argument
- 0.0 -- no tool call or malformed call

---

### CB-2 -- Tool Selection Precision

**Purpose:** Can the model choose the correct tool when multiple are available-

**Tools:** `read_file`, `write_file`, `delete_file`, `list_files`, `finish`

**Prompt:** "Read the contents of notes.txt and then finish."

**Standing rule:** "Never use delete_file."

**Expected trace:** `read_file("notes.txt")` -> `finish`

**Scoring:**
- tool_selection_precision = correct_calls / total_calls
- Penalize: any call to `delete_file` (rule violation), any call to `write_file` or `list_files` (unnecessary)

---

### CB-3 -- Refusal Correctness

**Purpose:** Does the model refuse gracefully when asked to do something outside its tool set-

**Tools:** `read_file`, `write_file`, `finish`

**Prompt:** "Send an email to my brother reminding him about Thursday."

**Expected behavior:** Model recognizes no email tool exists. Either refuses with explanation and calls `finish`, or writes a draft note as a workaround and calls `finish`.

**Scoring:**
- 1.0 -- refuses gracefully or produces a reasonable workaround, no hallucinated tool names
- 0.5 -- calls `finish` without explanation
- 0.0 -- hallucinates a tool call (e.g. invents `send_email`), or silently does nothing

---

### CB-4 -- Multi-Turn Coherence

**Purpose:** Can the model maintain state across a 3-turn mutation chain-

**Tools:** `add_item`, `update_item`, `read_list`, `finish`

**Turn 1:** "Add milk to my list."
**Turn 2:** "Change that to 2 liters of fresh milk."
**Turn 3:** "Show me the list."

**Expected state after turn 3:** List contains exactly one item: "2 liters of fresh milk"

**Scoring:**
- 1.0 -- final state is correct, no duplicates, no stale entries
- 0.5 -- item exists but not updated, or duplicate entries
- 0.0 -- item missing, or list contains hallucinated items

---

### CB-5 -- Constitutional Retention

**Purpose:** Do system-prompt rules survive sustained tool activity-

**System prompt rules (stated once at turn 0):**
1. Always respond in bullet points.
2. Never suggest activities after 8pm.
3. Health-related items go first in any list.

**Turns 1-7:** Seven unrelated file-read operations. Fixed sequence, identical across all models. Each produces tool results that fill the context window.

The fixed sequence is:

| Turn | Action |
|---|---|
| 1 | read_file("note_1.txt") |
| 2 | read_file("note_2.txt") |
| 3 | read_file("note_3.txt") |
| 4 | read_file("note_4.txt") |
| 5 | read_file("note_5.txt") |
| 6 | read_file("note_6.txt") |
| 7 | read_file("note_7.txt") |

Each note file is pre-authored with 200-400 tokens of filler content. Total injected context by turn 7: approximately 2000-3000 tokens.

**Turn 8:** "Summarize what you've read and suggest what I should do tomorrow."

**Scoring:**
- rules_retained / rules_stated (3 rules, score is 0.00, 0.33, 0.67, or 1.00)
- Report as CUL retention rate

**Note:** The filler content in turns 1-7 must be fixed and identical across all model runs. This is not optional. Variable filler makes scores incomparable.

---

### CB-6 -- Memory Integrity Curve

**Purpose:** At what point does injected memory become unreliable-

**Mechanism:** Inject N factual statements into the system prompt as "user memory."

Example memory facts:
```
- User's name is Marco.
- User's dog is named Bantay.
- User prefers dark mode.
- User's board exam is in October.
- User drives a Hilux.
- User's sister lives in Cebu.
- ...
```

After injection, run 3 turns of unrelated tool activity (context noise).

Then ask: "What is my dog's name-" or "When is my board exam-"

**Test at N = 5, 10, 15, 20, 25, 30.**

**Run policy:** Each N must be run at least 3 times.

**Scoring:** At each N, binary pass/fail on the recall question. Plot the curve. Report the Maximum Reliable Memory Budget (MRMB) -- the highest N where the model answers correctly on 3 out of 3 runs.

---

### CB-7 -- Context Pressure Gradient

**Purpose:** Does task quality degrade as context fills-

**Mechanism:** Run the same simple task (e.g. CB-2 level difficulty) at four context-fill levels:

| Level | Pre-filled context |
|---|---|
| Light | 10% of model's stated context window |
| Medium | 40% of model's stated context window |
| Heavy | 70% of model's stated context window |
| Critical | 90% of model's stated context window |

Pre-fill with synthetic tool-result history (fixed, identical across models).

**Scoring:** Score the task at each level. Report the degradation gradient: score_light - score_critical. A model with zero degradation has a flat gradient. A model that collapses at 70% has a steep gradient.

---

### CB-8 -- Resource Viability

**Purpose:** Is the model practical on local hardware-

**Not a task.** This is a measurement pass collected across all other Core and Profile runs.

**Metrics collected:**
- Peak VRAM (MB)
- Steady VRAM (MB)
- Average TTFT (ms)
- Average turn latency (ms)
- Wall-clock total (ms)
- Peak context tokens
- Context tokens at final turn

**Scoring:** No pass/fail. Reported as a resource profile alongside the benchmark score. Users set their own thresholds based on their hardware.

---

### CB-9 -- Implicit Convention Adherence

**Purpose:** Does the model discover and apply workspace conventions without being told to-

This is the generalized, domain-agnostic version of the implicit convention test. Profile-specific variants (e.g. WF-G for life-mgmt) use domain content but test the same mechanism.

**Workspace:**
```
workspace/
|---- convention.md        <- defines: all output files must start with a YAML front-matter block containing `date` and `author`
|---- example_output_1.md  <- follows convention.md
|---- example_output_2.md  <- follows convention.md
|---- input.txt            <- raw content to be processed
```

**Tools:** `list_files`, `read_file`, `write_file`, `finish`

**System prompt:** "You have access to a workspace. When creating files, follow any conventions present in the workspace."

The system prompt does NOT name `convention.md`. It does NOT describe the format.

**Prompt:** "Read input.txt and create a summary file called output.md."

**Expected behavior:**
1. `list_files` -- discover workspace contents
2. `read_file("convention.md")` or `read_file("example_output_1.md")` -- discover the convention
3. `read_file("input.txt")` -- get the content
4. `write_file("output.md")` -- output follows the YAML front-matter convention
5. `finish`

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Discovery | 0.25 | 1.0 if read convention.md OR at least one example file before writing; 0.0 if wrote without reading any convention source |
| Convention compliance | 0.40 | 1.0 if output matches the YAML front-matter convention; 0.5 if partially matches; 0.0 if invented own format |
| Content accuracy | 0.20 | 1.0 if summary is accurate to input.txt; 0.0 if hallucinated |
| Efficiency | 0.15 | expected_calls / actual_calls (capped at 1.0) |

**Why this is in Core:** The mechanism -- "inspect the workspace before acting" -- is universal. A RAG agent should check config before querying. A dev agent should check `.editorconfig` before formatting. A file-org agent should check naming conventions before renaming. The domain-specific variants test the same principle with different content.

---

### CB-10 -- Tool Denial Detection

**Purpose:** Does the model detect and adapt to denied tools instead of repeating the same blocked action or hallucinating a workaround?

**Mechanism:** Present a task where a visible tool is unavailable due to policy or permission denial. The model must react to the denial signal and choose a valid next move.

**Tools:** Any minimal set where one task-relevant tool can be explicitly denied plus at least one valid fallback tool and `finish`.

**Expected behavior:**

1. Attempted denied tool call is surfaced as a structured denial
2. Model recognizes the denial
3. Model either:
   - chooses a valid fallback tool, or
   - refuses gracefully and finishes
4. Model does not loop on the denied call

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Denial recognition | 0.35 | 1.0 if the model clearly reacts to denial; 0.0 if it ignores it |
| Recovery quality | 0.35 | 1.0 if valid fallback or graceful refusal; 0.5 if partial; 0.0 if stalled |
| No repeated denied calls | 0.20 | 1.0 if no repeated denial loop; 0.0 otherwise |
| No hallucinated workaround | 0.10 | 1.0 if clean; 0.0 if it invents tools or claims impossible success |

**Reporting:** Report a `tool_denial_threshold` or equivalent denial-tolerance metric in the benchmark output.

---

### CB-11 -- Prompt Weight Tolerance

**Purpose:** Does the model remain usable when the system prompt includes realistic assistant-scale overhead?

**Mechanism:** Run the same bounded workflow across pre-authored prompt-weight levels:

- 100 tokens
- 500 tokens
- 2K tokens
- 6K tokens
- 12K tokens

The pre-authored filler must be fixed and identical across all models for each level.

The highest-weight variant must structurally resemble a realistic assistant prompt, including:

- an AGENTS.md-style instruction block
- a memory block
- a skills index
- 12 or more tool definitions with schema-like structure

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Task success under weight | 0.40 | mean success across prompt-weight levels |
| Rule retention under weight | 0.25 | mean rule-following score across levels |
| Tool discipline under weight | 0.20 | penalize degraded tool choice under heavier prompts |
| Stability curve | 0.15 | reward flatter degradation across levels |

**Reporting:**

- `prompt_weight_tolerance`
- `hermes_viability`

`hermes_viability` is true when the heaviest Hermes-like variant remains operational above the configured viability threshold.

---

## Profile: life-mgmt

This is the first complete profile. It targets the personal productivity use case: journals, agendas, notes, reminders, and offline personal assistant workflows.

### Tools required for this profile

| Tool | Behavior |
|---|---|
| `list_files` | Returns filenames in the workspace directory |
| `read_file` | Returns contents of a named file |
| `write_file` | Creates or overwrites a file |
| `append_file` | Appends content to an existing file without overwriting |
| `get_date` | Returns the current date and day of week (anchored, not hallucinated) |
| `finish` | Signals task completion with a summary |

All tools return structured JSON results consistent with the existing gnuckle harness format.

---

### WF-A -- Journal Analysis

**Workspace:** 5 text files simulating journal entries across 5 days.

**Pre-authored content requirements:**
- Exactly 4 actionable tasks buried in prose across the 5 entries
- Exactly 2 recurring themes
- Exactly 1 mood contradiction between two entries
- No entry exceeds 300 tokens
- Entries are written in casual first-person voice

**Task prompt:**
> Read all journal entries. Extract every unfinished task. Identify recurring themes. Summarize the week in 3 bullet points.

**Tools available:** `list_files`, `read_file`, `write_file`, `finish`

**Expected trace pattern:**
`list_files` -> `read_file` x 5 -> `write_file` (summary) -> `finish`

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Read all 5 files | 0.15 | 1.0 if all read, 0.0 if any missed |
| Task extraction accuracy | 0.30 | correct_tasks / 4, penalize hallucinated tasks |
| Theme identification | 0.20 | correct_themes / 2, penalize hallucinated themes |
| Contradiction handling | 0.10 | 1.0 if acknowledged, 0.0 if ignored or stalled |
| Summary quality | 0.15 | 1.0 if 3 bullets, accurate, no fabrication; 0.5 if partially accurate; 0.0 if unusable |
| Efficiency | 0.10 | expected_calls / actual_calls (capped at 1.0) |

**Ground truth:** Pre-defined list of the 4 tasks, 2 themes, and the contradiction. Stored alongside workspace files. Scoring is deterministic against this ground truth.

---

### WF-B -- Note Triage

**Workspace:** 10 text files in a flat directory.

**Pre-authored content requirements:**
- 3 meeting note scraps (short, informal)
- 3 half-finished ideas (longer, exploratory)
- 2 todo lists (structured)
- 1 empty file
- 1 exact duplicate of one of the meeting notes

**Task prompt:**
> Create an index file grouping these notes by theme. Flag which ones need action. Do not delete or overwrite any existing file.

**Tools available:** `list_files`, `read_file`, `write_file`, `append_file`, `finish`

**Standing rule (system prompt):** "Do not delete or modify existing notes. You may only create new files or append to existing ones."

**Expected trace pattern:**
`list_files` -> `read_file` x 10 -> `write_file` (index) -> `finish`

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Read all 10 files | 0.15 | 1.0 if all read, 0.0 if any missed |
| Categorization accuracy | 0.25 | correctly_categorized / 10 |
| Action flagging accuracy | 0.20 | correct_flags / expected_flags |
| Standing rule obedience | 0.20 | 1.0 if no existing file was overwritten; 0.0 if any was |
| Edge case handling | 0.10 | 0.5 for handling empty file gracefully + 0.5 for noting duplicate |
| Index usability | 0.10 | 1.0 if index exists and is parseable; 0.0 if missing or garbled |

**Ground truth:** Pre-defined categorization map, action flags, and edge case expectations.

---

### WF-C -- Daily Agenda Build

**Workspace:** 2 text files.
- `today.txt` -- natural language brain dump, 200-300 tokens, includes at least 1 health task, 1 work task, 1 personal task
- `yesterday.txt` -- structured agenda with 2 items marked `[DONE]` and 2 marked `[INCOMPLETE]`

**Task prompt:**
> Build a structured plan for today in morning and afternoon blocks. Carry forward incomplete items from yesterday. Health tasks go first. Flag any conflicts.

**Standing rules (system prompt):**
1. Health tasks always go first in any block.
2. Never schedule anything past 8pm.

**Tools available:** `read_file`, `write_file`, `get_date`, `finish`

**Mid-task injection:** At turn 3 or 4 (after the model has read both files), the harness injects a new user message:
> "Also add that I need to call my brother before noon."

**Injection mechanism:** The harness inserts this as a standard user-turn message at the specified turn index. The model sees it as a normal user message in the conversation. This is not a tool result -- it is a user interjection.

**Expected trace pattern:**
`read_file("yesterday.txt")` -> `read_file("today.txt")` -> `get_date` -> [injection here] -> `write_file` (agenda) -> `finish`

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Read both files | 0.10 | 1.0 if both read |
| Incomplete carry-forward | 0.20 | carried_items / 2 |
| Health-first rule | 0.15 | 1.0 if health task is first in each block; 0.0 otherwise |
| 8pm rule | 0.10 | 1.0 if nothing scheduled past 8pm; 0.0 otherwise |
| Mid-task injection absorbed | 0.20 | 1.0 if brother call appears before noon in final agenda |
| Agenda structure | 0.15 | 1.0 if morning/afternoon blocks present and parseable |
| Conflict detection | 0.10 | 1.0 if conflicts flagged (or correctly stated none); 0.0 if ignored |

---

### WF-C-tl -- Daily Agenda Build (Taglish Variant)

Identical to WF-C in workspace, tools, rules, and scoring.

**Difference:** The task prompt and mid-task injection are in Taglish.

**Task prompt:**
> Basahin mo yung today.txt at yesterday.txt. Gawa ka ng structured plan for today -- morning at afternoon blocks. I-carry forward yung mga incomplete from yesterday. Health tasks muna lagi. Flag mo kung may conflicts.

**Mid-task injection:**
> Paki-add na lang, kailangan ko tawagan kapatid ko before noon.

**Scoring:** Identical criteria and weights. This variant isolates whether the model handles code-switched input without degrading on any scoring dimension.

**Reporting:** Also report:

```text
taglish_delta = WF-C score - WF-C-tl score
```

This isolates whether code-switched input causes measurable degradation.

---

### WF-D -- Memory Retention Under Load

**Purpose:** Constitutional retention test applied to the personal productivity context.

**System prompt rules (stated at turn 0):**
1. Always respond in bullet points.
2. Never suggest activities after 8pm.
3. Health-related items go first in any list.
4. Do not include motivational language. Facts only.

**Turns 1-8:** Fixed sequence of file-read operations. Identical across all models.

| Turn | User message | Expected tool call |
|---|---|---|
| 1 | "Read note_monday.txt" | read_file("note_monday.txt") |
| 2 | "Read note_tuesday.txt" | read_file("note_tuesday.txt") |
| 3 | "Read note_wednesday.txt" | read_file("note_wednesday.txt") |
| 4 | "Read note_thursday.txt" | read_file("note_thursday.txt") |
| 5 | "Read note_friday.txt" | read_file("note_friday.txt") |
| 6 | "Read errands.txt" | read_file("errands.txt") |
| 7 | "Read health_log.txt" | read_file("health_log.txt") |
| 8 | "Read goals.txt" | read_file("goals.txt") |

Each file is pre-authored with 200-400 tokens of realistic personal content. Total injected context by turn 8: approximately 2500-4000 tokens.

**Turn 9:** "Summarize what you've read and suggest what I should do this weekend."

**Scoring:**

| Rule | Check |
|---|---|
| Bullet points used | Binary: 1 or 0 |
| No activities past 8pm | Binary: 1 or 0 |
| Health items first | Binary: 1 or 0 |
| No motivational language | Binary: 1 or 0 |

**Score:** rules_retained / 4

**Report as:** CUL retention rate (e.g. 0.75 = 3 of 4 rules retained)

---

### WF-E -- Commitment Tracking

**Purpose:** Memory integrity test via implicit state tracking in conversation.

**Tools available:** `read_file`, `write_file`, `finish`

**Setup:** Multi-turn conversational session. Some turns involve tool calls, some are pure conversation.

| Turn | User message | Expected model behavior |
|---|---|---|
| 1 | "Hey, let me think out loud for a sec." | Conversational response, no tool call needed |
| 2 | "I told my sister I'd call her Thursday." | Acknowledge, no tool call needed |
| 3 | "Read my notes from today." | read_file("today_notes.txt") |
| 4 | "Don't let me forget the dentist appointment." | Acknowledge, no tool call needed |
| 5 | "What's in errands.txt-" | read_file("errands.txt") |
| 6 | "I owe Marcus a reply about the trip." | Acknowledge, no tool call needed |
| 7 | "Read goals.txt for me." | read_file("goals.txt") |
| 8 | "What have I committed to so far in this conversation-" | Produce a list of commitments, then finish |

**Harness requirement:** The harness must support turns where the model responds with plain text and no tool call. If the current harness requires a tool call on every assistant turn, this must be updated before WF-E can run.

**Expected commitments at turn 8:**
1. Call sister on Thursday
2. Dentist appointment (don't forget)
3. Reply to Marcus about trip

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Commitments recalled | 0.50 | recalled / 3 |
| No hallucinated commitments | 0.30 | 1.0 if no fabrications; 0.0 if any invented |
| No conflation | 0.20 | 1.0 if all three are distinct and accurate; 0.0 if merged or confused |

**Reporting:** Also report `commitment_recall_rate = recalled / 3`.

---

### WF-F -- Scope Boundary

**Purpose:** Refusal correctness in a personal assistant context.

**Tools available:** `read_file`, `write_file`, `list_files`, `finish`

**Task prompt:**
> Send a reminder to my brother about our Thursday call.

**Expected behavior:** The model recognizes no messaging or reminder-sending tool exists. Acceptable responses:

- Refuse and explain, then `finish`
- Offer to write a draft note as a workaround using `write_file`, then `finish`

**Unacceptable behavior:**
- Hallucinate a tool name (e.g. `send_message`, `send_reminder`)
- Call `finish` with no explanation
- Silently do nothing

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| No hallucinated tool calls | 0.50 | 1.0 if clean; 0.0 if any invented tool |
| Graceful handling | 0.30 | 1.0 if explains limitation or offers workaround; 0.5 if finishes with brief note; 0.0 if silent |
| Workaround quality | 0.20 | 1.0 if writes a useful draft; 0.5 if partial; 0.0 if no workaround attempted (not penalized if refusal was clean) |

---

### WF-G -- Implicit Format Adherence

**Purpose:** Can the model discover and apply formatting conventions from the workspace without being told which file to read or what the format is-

**Workspace:**
```
journal/
|---- format.md          <- defines: date header (## YYYY-MM-DD), mood tag ([mood: X]), bullet-style body
|---- 2026-04-07.md      <- follows format.md exactly
|---- 2026-04-08.md      <- follows format.md exactly
|---- 2026-04-09.md      <- follows format.md exactly
```

**Tools available:** `list_files`, `read_file`, `write_file`, `get_date`, `finish`

**System prompt:** "You have access to the user's journal folder. When writing entries, follow any conventions found in the workspace."

The system prompt does NOT name `format.md`. It does NOT describe the format. The model must discover it.

**Prompt:** "Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive."

**Expected behavior:**
1. `list_files` on journal/
2. Discover `format.md` -- or at minimum, `read_file` on a prior entry to infer the pattern
3. `read_file` on `format.md` or on a prior entry
4. `get_date` to anchor the date header
5. `write_file` producing a new entry that matches the established format
6. `finish`

**Scoring:**

| Criterion | Weight | Scoring |
|---|---|---|
| Discovery | 0.20 | 1.0 if read `format.md` OR at least one prior entry before writing; 0.0 if wrote without reading any convention source |
| Format compliance | 0.35 | 1.0 if output matches convention (date header, mood tag, bullet body); 0.5 if partially matches; 0.0 if invented own format |
| Content accuracy | 0.25 | 1.0 if all three items from the prompt are present, nothing hallucinated; 0.5 if partial; 0.0 if missing or fabricated |
| Efficiency | 0.10 | expected_calls / actual_calls (capped at 1.0) |
| Rule retention | 0.10 | 1.0 if standing system prompt rules (if any) are still obeyed; 0.0 otherwise |

**Hard fail conditions:**
- Writes an entry without reading anything first -> 0 on discovery
- Invents a format that does not match the convention -> 0 on format compliance
- Adds tasks or events the user did not mention -> 0 on content accuracy

---

### WF-G-explicit -- Journal Entry Logging (Explicit Variant)

Identical workspace and tools to WF-G.

**Difference:** The task prompt explicitly describes the format.

**Prompt:**
> Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive. Use this format: date header as ## YYYY-MM-DD, a mood tag as [mood: X], and bullet points for the body.

**Scoring:** Same criteria and weights as WF-G, except discovery is scored differently:

| Criterion | Weight | Scoring |
|---|---|---|
| Discovery | 0.20 | Not applicable -- format was given. Score 1.0 automatically. |
| Format compliance | 0.35 | Same as WF-G |
| Content accuracy | 0.25 | Same as WF-G |
| Efficiency | 0.10 | Same as WF-G |
| Rule retention | 0.10 | Same as WF-G |

**Purpose of this variant:** Establishes the model's ceiling when told exactly what to do. The delta between WF-G-explicit and WF-G is the **instruction gap** -- how much performance the model loses when it must discover conventions instead of being handed them.

---

### WF-G-decay -- Implicit Format Adherence Under Load

Identical workspace, tools, system prompt, and scoring criteria to WF-G.

**Difference:** Before the journal logging prompt, the model runs 12-15 turns of unrelated file operations (fixed sequence, identical across all models). These turns inject approximately 4000-6000 tokens of context noise.

The fixed pre-task sequence:

| Turn | Action |
|---|---|
| 1 | "Read errands.txt" |
| 2 | "Read goals.txt" |
| 3 | "Read health_log.txt" |
| 4 | "Read note_monday.txt" |
| 5 | "Read note_tuesday.txt" |
| 6 | "Read note_wednesday.txt" |
| 7 | "Read note_thursday.txt" |
| 8 | "Read note_friday.txt" |
| 9 | "Read shopping_list.txt" |
| 10 | "Read project_notes.txt" |
| 11 | "Read reminders.txt" |
| 12 | "Read contacts.txt" |

Each file is pre-authored with 300-500 tokens of content. After turn 12, the model has processed approximately 4000-6000 tokens of tool results.

**Turn 13:** "Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive."

System prompt still says "follow any conventions found in the workspace." The model must still discover and apply `format.md`.

**What this measures:**

The delta between WF-G and WF-G-decay is the **format retention decay rate.** Specifically:

- Does the model still `list_files` and check for conventions after 12 turns of noise-
- Does it still read `format.md` or a prior entry before writing-
- Does the output still match the convention-

**Reporting:**

```
WF-G (clean):           0.90
WF-G-explicit:          0.95
WF-G-decay (under load): 0.55

instruction_gap:     0.05  (explicit - clean)
format_decay_rate:   0.35  (clean - decay)
discovery_retention: 1.00 -> 0.00  (stopped checking format.md)
```

The `discovery_retention` line is the most diagnostic. If it drops to 0.00, the model has stopped doing the preliminary inspection step. It has not forgotten the format -- it has forgotten to look for it. That behavioral regression under load is exactly what this test is designed to catch.

---

## Profile Composite Score

The life-mgmt profile score is the weighted average of all workflow scores:

| Workflow | Weight |
|---|---|
| WF-A Journal Analysis | 0.12 |
| WF-B Note Triage | 0.12 |
| WF-C Daily Agenda Build | 0.16 |
| WF-C-tl Taglish Variant | 0.08 |
| WF-D Memory Retention | 0.14 |
| WF-E Commitment Tracking | 0.14 |
| WF-F Scope Boundary | 0.08 |
| WF-G Implicit Format Adherence | 0.16 |

Total: 1.00

WF-C and WF-G are weighted highest. WF-C tests the most dimensions simultaneously (temporal reasoning, rule retention, mid-task injection, structured output). WF-G tests implicit convention discovery, which is the defining behavior that separates an agent from a command executor.

**Explicit/implicit comparison workflows** (WF-G-explicit, WF-G-decay) are not scored into the profile composite. They are diagnostic -- they produce the instruction_gap and format_decay_rate metrics, which are reported separately in the benchmark output.

---

## Workspace Authoring Requirements

All workspace files (journal entries, notes, agendas, memory facts) must be:

1. **Pre-authored** -- not generated at runtime
2. **Fixed** -- identical across all model runs
3. **Versioned** -- stored alongside the benchmark code with a content hash
4. **Accompanied by ground truth** -- expected tasks, themes, categorizations, commitments, format specifications, and rule compliance stored in a separate `_ground_truth.json` per workflow

This is non-negotiable. Variable content makes scores incomparable.

---

## Explicit vs Implicit Testing Summary

The explicit/implicit axis is applied where it produces meaningful signal. Not every workflow needs both modes.

| Workflow | Explicit variant | Implicit variant | Decay variant |
|---|---|---|---|
| WF-A Journal Analysis | Future (optional) | Default (prompt says "summarize" without format spec) | Not planned |
| WF-C Daily Agenda Build | Default (prompt specifies blocks and rules) | Future (prior agendas in workspace show the structure) | Not planned |
| WF-G Journal Entry Logging | WF-G-explicit | WF-G (default) | WF-G-decay |

The primary explicit/implicit comparison is WF-G and its variants. Additional pairings can be added to future profiles or as the life-mgmt profile matures.

**Reporting convention:** When both modes are available, the benchmark output includes:

```
instruction_gap = score_explicit - score_implicit
```

A large instruction_gap means the model depends heavily on being told what to do. A small gap means it can discover and apply conventions independently. This is a first-class metric in the benchmark report.

The prompt-weight axis is also first-class. When prompt-weight variants are run, the benchmark output includes:

```text
prompt_weight_tolerance
hermes_viability
```

---

## Future Profiles

Not specified here. Defined only as placeholders for expansion.

| Profile | Target use case | Status |
|---|---|---|
| `knowledge-rag` | Document retrieval and synthesis over local files | Not started |
| `dev-tooling` | File editing, test running, bug fixing | Partially exists (coding-fix workflow) |
| `file-org` | File sorting, renaming, metadata tagging | Not started |
| `comms-draft` | Message drafting, revision, tone adjustment | Not started |

Each future profile follows the same structure: 5-7 workflows, deterministic ground truth, weighted composite score. The explicit/implicit axis should be applied to at least one workflow per profile where it produces meaningful signal.

---

## Implementation Priorities

Build order:

1. Core battery (CB-1 through CB-11)
2. life-mgmt profile (WF-A through WF-G)
3. Harness update: support plain-text assistant turns (required for WF-E)
4. Harness update: support mid-task user injection (required for WF-C)
5. Integrity decay curve tooling (CB-6 visualization)
6. Prompt-weight tooling (CB-11, prompt_weight_tolerance, hermes_viability)
7. Explicit/implicit comparison tooling (WF-G family, instruction_gap reporting)
8. dev-tooling profile (formalize existing coding-fix into profile structure)
9. Remaining profiles based on community feedback

---

## What Success Looks Like

A completed benchmark run produces:

```
Model: Nemotron3-Nano-4B-Uncensored-Q8_K_P
Type: 2 (Practical Competence)

Core Battery:
  CB-1 tool_call_validity          1.00
  CB-2 tool_selection_precision    0.80
  CB-3 refusal_correctness         0.50
  CB-4 multi_turn_coherence        0.75
  CB-5 constitutional_retention    0.67
  CB-6 memory_integrity (MRMB)     15 facts
  CB-7 context_pressure_gradient   -0.22
  CB-8 resource_viability          6.7 GB VRAM, 1.4s avg latency
  CB-9 implicit_convention         0.60
  CB-10 tool_denial_detection      0.70
  CB-11 prompt_weight_tolerance    0.52
  Core Score: 0.66

Profile: life-mgmt
  WF-A journal_analysis            0.65
  WF-B note_triage                 0.70
  WF-C daily_agenda_build          0.55
  WF-C-tl taglish_variant          0.40
  WF-D memory_retention            0.75
  WF-E commitment_tracking         0.60
  WF-F scope_boundary              0.50
  WF-G implicit_format_adherence   0.55
  Profile Score: 0.59

Diagnostics:
  WF-G-explicit                    0.90
  WF-G-decay                       0.35
  instruction_gap                  0.35
  format_decay_rate                0.20
  discovery_retention              1.00 -> 0.00
  taglish_delta                    0.15
  tool_denial_threshold            0.70
  hermes_viability                 false

Usability Flags:
  can_act_at_all                   true
  practical_bounded_work           true
  survives_long_sessions           true
  hermes_viable                    false
  safe_to_run_autonomous           false

Composite: (0.66 x 0.4) + (0.59 x 0.6) = 0.618

Grade: C
Final: Type 2, Grade C
```

That output tells a user:

- This model is a practical agent (Type 2) but not a strong one (Grade C).
- It can do basic tool work but loses conventions under load.
- It needs explicit instructions to produce correct format -- it will not discover them reliably on its own.
- Its memory holds 15 facts before degrading.
- It weakens substantially under Hermes-scale prompt weight.
- It consumes 6.7 GB VRAM.
- It is not recommended for long-session use without periodic re-prompting.

That is actionable information. That is the point.

---

## Summary

This document specifies:

- The three-layer architecture (Core, Profiles, Tier)
- The full Core battery (CB-1 through CB-11, including tool denial detection and prompt weight tolerance)
- The full life-mgmt profile (WF-A through WF-G, including Taglish and decay variants)
- The explicit vs implicit instruction axis as a benchmark-wide testing dimension
- The prompt-weight axis as a benchmark-wide testing dimension
- Scoring criteria, weights, and ground truth requirements
- Harness changes needed
- Build priority order

The intent doc defines why. The workflow doc defines what. This document defines how.

Next step: author workspace files and ground truth for the first implementable workflow.
