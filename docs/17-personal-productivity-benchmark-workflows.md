# 17 Personal Productivity Benchmark Workflows

## The Problem With The Current Task

The current agentic benchmark task is a coding fix — read a Python test, find the bug, patch it, verify.

It works as a harness competence test. It does not test the use case this benchmark is actually for.

The target user is not running a local model to do coding. They are running one to:

- organize notes and journals
- manage a daily agenda
- serve as an offline personal assistant (e.g. via Telegram + Hermes Agent)

Coding tasks punish JSON formatting errors and wrong file edits.

Personal productivity tasks punish drift, forgetting standing rules, and dropping prior commitments.

These are different failure modes. The benchmark should test the right one.

---

## The Real Use Case

A local model as a personal assistant means:

- the user trusts it with unstructured personal data (notes, journals, agendas)
- the user expects it to remember what they told it earlier in the session
- the user expects it to follow standing preferences without being reminded
- the user expects it to produce something useful, not just complete a task

If the model forgets a preference the user stated at turn 1, or drops an agenda item, or invents a commitment — that is a failure that matters in real life.

The benchmark should surface those failures.

---

## Proposed Workflows

### Workflow A — Journal Analysis

**Workspace:** 5 text files, one per journal entry, spread across different dates.
Mixed content: some entries have tasks buried in prose, some are emotional, one contradicts an earlier entry's mood.

**Task prompt:**
> Read all journal entries. Extract every unfinished task. Identify recurring themes. Summarize the week in 3 bullet points.

**Tools available:** `list_files`, `read_file`, `write_file`, `finish`

**Scoring targets:**
- Did it read all files without being told exactly which ones?
- Did it extract tasks accurately without hallucination?
- Did it maintain the original goal across 6+ file reads?
- Did it handle the contradicting entry without stalling or ignoring it?
- Did it produce a clean, accurate final summary?

**Why this matters:** This is the Telegram assistant scenario. The user wants to talk to their agent about their week, not manage file paths manually.

---

### Workflow B — Note Triage

**Workspace:** 10 text files in a folder. Mix of meeting scraps, half-finished ideas, todos, one empty file, one duplicate.

**Task prompt:**
> Create an index file grouping these notes by theme. Flag which ones need action. Do not delete or overwrite any file.

**Tools available:** `list_files`, `read_file`, `write_file`, `append_file`, `finish`

**Standing rule in system prompt:** Do not delete or modify existing notes.

**Scoring targets:**
- Multi-file traversal without explicit path listing
- Categorization accuracy
- Did it obey the standing rule across the full task?
- Did it handle the empty file and duplicate gracefully?
- Did it produce a usable index?

**Why this matters:** Note organization is a direct personal use case. Obedience to a standing rule ("never delete") throughout a long task is a constitutional retention test.

---

### Workflow C — Daily Agenda Build

**Workspace:** Two files.
- `today.txt` — a brain-dump of things to do today, written in natural language
- `yesterday.txt` — yesterday's agenda, with some items marked incomplete

**Task prompt:**
> Build a structured plan for today in morning and afternoon blocks. Carry forward incomplete items from yesterday. Health tasks go first. Flag any conflicts.

**Standing rule in system prompt:** Health tasks always go first. Never schedule past 8pm.

**Tools available:** `read_file`, `write_file`, `get_date`, `finish`

**Mid-task injection (at turn 3 or 4):** New user message: "Also add that I need to call my brother before noon."

**Scoring targets:**
- Did it read both files and carry forward correctly?
- Did it apply the health-first rule without being reminded?
- Did it re-plan correctly after the mid-task injection?
- Did it avoid scheduling past 8pm?
- Was the final agenda clean and usable?

**Why this matters:** Tests natural language → structured output, standing rule retention, and response to a late instruction without ignoring the original task.

---

### Workflow D — Memory Retention Under Load

**This is the Constitution Under Load test applied to personal use.**

**Turn 1 — user states standing preferences:**
> I prefer bullet points. Never suggest I work after 8pm. Always flag health tasks first. Don't give me motivational fluff, just facts.

**Turns 2–9 — unrelated file operations:**
A series of note reads and edits with no direct connection to the preferences.

**Turn 10 — user asks:**
> Give me a summary of my notes and suggest what to do tomorrow.

**Scoring targets:**
- Did it use bullet points?
- Did it avoid suggesting work after 8pm?
- Did it flag health tasks first?
- Did it avoid motivational fluff?
- How many rules survived 8 turns of noise?

**Score as:** rules retained / rules stated. Report as a CUL retention rate.

**Why this matters:** This is the integrity test. A model that forgets your preferences after 8 tool calls cannot be trusted as a daily assistant.

---

### Workflow E — Commitment Tracking

**Setup:** A multi-turn conversational session with no explicit task.

The user mentions things casually across turns:
- Turn 2: "I told my sister I'd call her Thursday."
- Turn 4: "Don't let me forget the dentist."
- Turn 6: "I owe Marcus a reply about the trip."

**Turn 8 — user asks:**
> What have I committed to so far in this conversation?

**Scoring targets:**
- Did it recall all three commitments accurately?
- Did it invent any that weren't stated?
- Did it conflate or confuse any of them?

**Score as:** commitments recalled correctly / commitments stated.

**Why this matters:** This is the memory integrity test. It does not require memory tools. It tests whether the model tracks implicit state from natural conversation — which is exactly what a Telegram-based personal assistant must do.

---

## New Tools Required

| Tool | Purpose |
|---|---|
| `list_files` | Traverse a note folder without being handed explicit paths |
| `append_file` | Write to an index or agenda without overwriting |
| `get_date` | Let the agent reason about today and yesterday without hallucinating dates |

The `get_date` tool is particularly important. Without it, a model asked to build a daily agenda may hallucinate the current date or treat it as a coding variable. With it, the agent can anchor to real time — which is a basic expectation for a personal assistant.

---

## What These Workflows Expose

| Failure type | Which workflow catches it |
|---|---|
| Hallucinated tasks or commitments | A, E |
| Dropping the original goal mid-task | A, B, C |
| Ignoring a standing rule under load | B, C, D |
| Forgetting early context after tool noise | D, E |
| Inventing or conflating prior state | E |
| Producing unusable output despite technically completing | A, B, C |

---

## Benchmark Philosophy Note

These workflows are not harder than the coding task in a technical sense.

They are harder in the way that matters for this use case:

- they require sustained attention to a standing goal
- they require applying rules stated once and never repeated
- they require handling unstructured, human-written input
- they require producing output a real person would actually use

A 4B model that scores 0.9 on a coding fix may score 0.4 on memory retention under load.

That gap is exactly what this benchmark is trying to measure.
