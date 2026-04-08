# 10 OpenClaude Failure Handling Grounding

## Purpose

This note locks the minimal failure-handling pattern we borrow from the local `openclaude` reference into `gnuckle`.

The goal is not feature parity.

The goal is to preserve agent structure under failure so that:

- the model can recover in-band
- failures remain measurable benchmark data
- the transcript does not become structurally invalid

## What Matters From OpenClaude

The important pattern is:

1. validate
2. authorize
3. execute
4. wrap every failure as a tool result

That means:

- tool failures should stay in the conversation
- permission denials should be counted separately
- execution failures should not silently disappear
- malformed tool calls should still produce one matching result per tool use

## Rules For Gnuckle

### 1. Never leave orphaned tool calls

For every assistant `tool_call`, `gnuckle` must emit exactly one matching tool result into runtime history.

Allowed forms:

- successful tool result
- synthetic error tool result

### 2. Keep failures in-band

Tool failure must not be represented only as a Python exception or terminal log.

It must also become:

- trace data
- saved JSON data
- transcript-visible tool result data when a tool call exists

### 3. Separate failure classes

At minimum, `gnuckle` must quantify these separately:

- `input_validation_error`
- `permission_denied`
- `execution_error`
- malformed finish behavior
- harness error

### 4. Let the model recover

When a tool call fails:

- append the error tool result to history
- continue the bounded runtime loop unless a terminal rule is reached

The model should see the failed result as normal context for the next action.

### 5. Retry malformed tool calls once

Malformed tool calls are worth one bounded retry because:

- they are common in local function-calling
- the retry itself is useful benchmark data

After the retry budget is spent:

- keep the failure as a quantified result
- do not discard the turn

## Minimal Implementation Contract

For v1, the following approximation is sufficient:

```text
validate -> authorize -> execute -> wrap
```

If any stage fails:

```text
emit tool_result(is_error=true)
record failure counter
continue loop if still within budget
```

## Tool Awareness Contract

To approximate the OpenClaude pattern closely enough for `gnuckle`:

- the model must receive an explicit active tool list with the API request
- the system/user instructions must mention the active tool list
- workflows may define a narrower expected tool subset for scoring

This keeps two separate ideas visible:

- `active_tools`
  - the full menu shown to the model
- `expected_tools`
  - the tools that were actually appropriate for the workflow

This allows `gnuckle` to measure tool choice quality, not just tool formatting.

## Reporting Contract

The following counts must remain visible in benchmark output whenever applicable:

- invalid tool calls
- retry events
- malformed finish events
- execution failures
- permission denials
- synthetic tool results

## Why This Is The Right Scope

This keeps the benchmark small enough for `gnuckle` while still preserving the key OpenClaude property:

- failure remains part of agent state instead of breaking the harness model.
