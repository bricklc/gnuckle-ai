# 13 Integrity Decay And Constitution Under Load

## Purpose

This note defines two specific v2 benchmark concepts:

1. `Constitution Under Load (CUL)`
2. `Integrity Decay Curve`

These should be treated as named benchmark slices, not vague side ideas.

## 1. Constitution Under Load

`Constitution Under Load` measures whether the model preserves required standing behaviors from the system prompt while the session becomes noisy.

This is not the same as task success.

A model may solve the task and still fail CUL if it stops following the required behavioral rules.

### Examples of constitutional rules

- always include a verification note
- never claim success before checks pass
- always summarize tool failures explicitly
- preserve a fixed answer structure
- state uncertainty when not verified

### CUL metrics

- `constitution_rules_total`
- `constitution_rules_followed`
- `constitution_violations`
- `constitution_adherence_rate`
- `first_constitution_drift_turn`
- `constitution_drift_after_tool_calls`
- `constitution_drift_after_context_percent`

## 2. Integrity Decay Curve

The `Integrity Decay Curve` measures how prompt and memory integrity decline as context and memory load increase.

This is about survivability, not only recall.

The model is carrying forward:

- system rules
- original user request
- user preferences
- stored memory facts
- prior commitments
- prior formatting habits

These compete with:

- tool calls
- tool results
- long transcript history
- summaries
- retrieved memory blocks

### What should be scored

- `original_query_retention`
- `preference_retention`
- `memory_recall_accuracy`
- `contradiction_rate`
- `integrity_score`

### Output shape

The curve should identify:

- stable zone
- drift zone
- failure zone

And report:

- `MRMB`
  - `Maximum Reliable Memory Budget`

## Recommended Test Method

Run the same workflow family at increasing memory loads.

Suggested load steps:

- `5%`
- `10%`
- `20%`
- `30%`
- `40%`
- `50%`

of effective context budget.

At each step, measure:

- task success
- constitution adherence
- original query retention
- memory recall accuracy
- contradiction rate
- latency
- VRAM pressure

## Why This Matters

This gives users actionable operational guidance:

- how much memory can be kept injected?
- when should memory be pruned?
- when should summarization or retrieval replace full-memory injection?

This is more useful than generic “supports 128k context” claims.

## Naming Rule

Use these terms consistently:

- `Constitution Under Load`
- `Integrity Decay Curve`
- `Maximum Reliable Memory Budget`

Do not rename them casually across docs or UI.

