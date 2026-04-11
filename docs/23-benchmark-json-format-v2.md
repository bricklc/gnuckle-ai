# 23 Benchmark JSON Format V2

## Purpose

This document defines a cleaner benchmark JSON format for community-authored benchmark scripts.

The goal is to make benchmark files:

- easy to read
- easy to validate
- easy for an LLM to generate correctly
- easy for the runtime to execute deterministically

This format is designed for persistent-session benchmark runs where the benchmark acts like a user in a harness and the model acts like the assistant.

---

## Key Idea

Think of the benchmark JSON as a script.

- The **tool manifest** defines what tools exist in the benchmark world.
- The **session block** defines the global behavior of the session.
- The **turn list** defines what the benchmark says to the model, what tool results should be returned if the model calls tools, and how the turn should be scored.

In simple terms:

- top of file = what exists in this world
- turn list = what happens in this session

---

## Why This Format

The old style works, but it mixes together:

- tool availability
- session behavior
- turn behavior
- scoring rules

The v2 format separates those concerns so both humans and LLMs can generate valid files more reliably.

The most important design change is:

- a **single tool manifest list at the top**

That gives the runtime and the author a clear source of truth for the session tool surface.

---

## Simple Explainer

### What is a benchmark JSON?

It is a deterministic scenario file.

It tells the benchmark runtime:

- what tools the model is allowed to see
- what the system prompt is
- what user prompts to send
- what mocked tool results to return
- what correct behavior looks like

### Why are there mocked tool results?

Because this is a benchmark, not a live environment.

Mocked tool results are used so:

- every model sees the same world
- every quant/cache variant sees the same world
- the benchmark is repeatable
- hallucinations can be detected
- scoring is deterministic

If the model calls `read_file("notes.txt")`, the benchmark should already know what `notes.txt` contains for that turn or session state.

That is why the JSON includes expected tool results.

### What does a turn do?

A turn is one benchmark-authored user message plus the scoring and mocks needed to evaluate that moment in the session.

Each turn says:

- this is the user message
- these are the relevant or active tools
- if the model calls tool X, return this mock result
- check whether the model behaved correctly

---

## V2 Structure

The recommended top-level structure is:

```json
{
  "meta": {},
  "session": {},
  "tool_manifest": [],
  "turns": [],
  "scoring": {}
}
```

---

## Top-Level Fields

### `meta`

Describes the benchmark file itself.

Recommended fields:

```json
"meta": {
  "id": "persistent_tool_stress_v2",
  "title": "Persistent Tool Stress Test",
  "version": "2.0",
  "author": "gnuckle-ai",
  "description": "Tests tool retention, selection accuracy, and degradation under growing context in a persistent session.",
  "tags": ["tool-use", "stress", "context-pressure", "retention"]
}
```

### `session`

Defines global session behavior.

Recommended fields:

```json
"session": {
  "type": "session",
  "mode": "persistent",
  "carry_state_across_turns": true,
  "finish_policy": "checkpoint_or_final_only",
  "system_prompt": "You are a bounded benchmark agent. Use only the provided tools. Follow standing rules.",
  "standing_rules": [
    "Never call a tool that is not provided.",
    "When directly reporting file contents, do not alter them.",
    "Use bullet points when the user asks for a summary."
  ]
}
```

### `tool_manifest`

Defines the global tool surface for the benchmark world.

This is the single source of truth for what tools exist in the session.

Recommended shape:

```json
"tool_manifest": [
  {
    "name": "read_file",
    "description": "Read a file from the workspace.",
    "category": "filesystem"
  },
  {
    "name": "write_file",
    "description": "Write a file to the workspace.",
    "category": "filesystem"
  },
  {
    "name": "finish",
    "description": "Mark a checkpoint or end the session.",
    "category": "control"
  }
]
```

### `turns`

Defines the ordered benchmark conversation.

Each turn is the next user interaction in the same session.

### `scoring`

Defines benchmark-level scoring mode or policies.

Example:

```json
"scoring": {
  "mode": "criterion_based",
  "track_hallucinated_tools": true,
  "track_omissions": true,
  "track_distortions": true
}
```

---

## Turn Format

Each turn should use one consistent shape.

Recommended format:

```json
{
  "id": "t01_single_echo",
  "title": "Single tool call",
  "user_message": "Use the echo tool to repeat the phrase: benchmark session started.",
  "active_tools": ["echo", "finish"],
  "mock_tool_results": [
    {
      "tool": "echo",
      "call_index": 1,
      "result": {
        "output": "benchmark session started"
      }
    }
  ],
  "expectations": {
    "tool_usage": {
      "must_call": ["echo"],
      "must_not_call": ["write_file", "read_file", "list_files"],
      "ordered_calls": ["echo"]
    },
    "response": {
      "must_contain": ["benchmark session started"],
      "format": "plain_text"
    },
    "session": {
      "must_finish": false
    }
  }
}
```

---

## Turn Field Explainer

### `id`

A unique stable identifier for the turn.

Use short deterministic IDs:

- `t01_single_echo`
- `t02_single_read`
- `t03_two_tool_sequence`

### `title`

Human-readable explanation of what the turn tests.

### `user_message`

The user-facing prompt sent to the model for this turn.

This should read like a normal user message, not like benchmark metadata.

### `active_tools`

Optional narrowed tool list for the turn.

Use this when:

- only some tools should be exposed in this moment
- you want to test bounded tool awareness

If omitted, the runtime may expose the full `tool_manifest`.

### `mock_tool_results`

Defines what the harness should return if the model calls a tool.

This is how the benchmark simulates the environment.

Recommended shape:

```json
{
  "tool": "read_file",
  "call_index": 1,
  "result": {
    "output": "Reminder: meeting at 3pm. Bring laptop."
  }
}
```

If a tool may be called multiple times in one turn, use multiple entries:

```json
"mock_tool_results": [
  {
    "tool": "read_file",
    "call_index": 1,
    "result": {
      "output": "TODO:\n- Fix login bug\n- Deploy staging\n- Write auth tests"
    }
  },
  {
    "tool": "read_file",
    "call_index": 2,
    "result": {
      "output": "Status report contents here"
    }
  }
]
```

### `expectations`

Defines how the turn should be scored.

This should be split into named groups so the JSON remains easy to generate and validate.

Recommended groups:

- `tool_usage`
- `response`
- `session`

---

## Expectations Format

### Tool usage expectations

```json
"tool_usage": {
  "must_call": ["read_file"],
  "must_not_call": ["write_file", "append_file"],
  "ordered_calls": ["list_files", "read_file", "write_file"],
  "expect_refusal": false
}
```

Meaning:

- `must_call`: tool names that should appear
- `must_not_call`: tool names that should not appear
- `ordered_calls`: required order if sequencing matters
- `expect_refusal`: whether refusal is the correct behavior

### Response expectations

```json
"response": {
  "must_contain": ["8080", "login bug"],
  "must_not_contain": ["send_email", "5432"],
  "format": "bullet_points"
}
```

Meaning:

- `must_contain`: phrases or facts expected in the answer
- `must_not_contain`: phrases indicating hallucination or contradiction
- `format`: output style requirement

Suggested `format` enum values:

- `plain_text`
- `bullet_points`
- `json`
- `yaml_front_matter`
- `ordered_list`

### Session expectations

```json
"session": {
  "must_finish": false,
  "checkpoint": false
}
```

Meaning:

- `must_finish`: whether `finish` is required on this turn
- `checkpoint`: whether this turn is a checkpoint-style turn

For persistent-session realism, `must_finish` should usually be `false` except for checkpoint or final turns.

---

## Recommended Session Semantics

For realistic harness simulation, use these rules:

- `session.mode` should usually be `persistent`
- `carry_state_across_turns` should usually be `true`
- intermediate turns should usually set `must_finish` to `false`
- only checkpoint or final turns should require `finish`
- prior tool effects should remain visible to later turns

This makes the benchmark feel like one ongoing agent run rather than many isolated tasks.

---

## Full Example

```json
{
  "meta": {
    "id": "persistent_tool_stress_v2",
    "title": "Persistent Tool Stress Test",
    "version": "2.0",
    "author": "gnuckle-ai",
    "description": "Tests tool retention, selection accuracy, and degradation under growing context in a persistent session.",
    "tags": ["tool-use", "stress", "context-pressure", "retention"]
  },
  "session": {
    "type": "session",
    "mode": "persistent",
    "carry_state_across_turns": true,
    "finish_policy": "checkpoint_or_final_only",
    "system_prompt": "You are a bounded benchmark agent. Use only the provided tools. Follow standing rules.",
    "standing_rules": [
      "Never call a tool that is not provided.",
      "When directly reporting file contents, do not alter them.",
      "Use bullet points when the user asks for a summary."
    ]
  },
  "tool_manifest": [
    {
      "name": "echo",
      "description": "Repeat a phrase exactly.",
      "category": "utility"
    },
    {
      "name": "read_file",
      "description": "Read a file from the workspace.",
      "category": "filesystem"
    },
    {
      "name": "write_file",
      "description": "Write a file to the workspace.",
      "category": "filesystem"
    },
    {
      "name": "list_files",
      "description": "List files in the workspace.",
      "category": "filesystem"
    },
    {
      "name": "finish",
      "description": "End the session or mark a checkpoint.",
      "category": "control"
    }
  ],
  "turns": [
    {
      "id": "t01_single_echo",
      "title": "Single tool call",
      "user_message": "Use the echo tool to repeat the phrase: benchmark session started.",
      "active_tools": ["echo", "finish"],
      "mock_tool_results": [
        {
          "tool": "echo",
          "call_index": 1,
          "result": {
            "output": "benchmark session started"
          }
        }
      ],
      "expectations": {
        "tool_usage": {
          "must_call": ["echo"],
          "must_not_call": ["write_file", "read_file", "list_files"],
          "ordered_calls": ["echo"],
          "expect_refusal": false
        },
        "response": {
          "must_contain": ["benchmark session started"],
          "must_not_contain": [],
          "format": "plain_text"
        },
        "session": {
          "must_finish": false,
          "checkpoint": false
        }
      }
    },
    {
      "id": "t02_summary_checkpoint",
      "title": "Checkpoint summary",
      "user_message": "Summarize what you have done so far.",
      "active_tools": ["echo", "read_file", "write_file", "list_files", "finish"],
      "mock_tool_results": [],
      "expectations": {
        "tool_usage": {
          "must_call": [],
          "must_not_call": ["send_email"],
          "ordered_calls": [],
          "expect_refusal": false
        },
        "response": {
          "must_contain": ["benchmark session started"],
          "must_not_contain": [],
          "format": "bullet_points"
        },
        "session": {
          "must_finish": true,
          "checkpoint": true
        }
      }
    }
  ],
  "scoring": {
    "mode": "criterion_based",
    "track_hallucinated_tools": true,
    "track_omissions": true,
    "track_distortions": true
  }
}
```

---

## Authoring Guidance For Humans

When writing benchmark JSON manually:

1. Define the session behavior first.
2. Define the full tool manifest once.
3. Write turns in real user language.
4. Keep each turn's `mock_tool_results` minimal and deterministic.
5. Use `expectations` to make scoring explicit.
6. Do not rely on hidden runtime behavior if it can be stated in the JSON.

---

## Authoring Guidance For LLMs

If an LLM is generating a benchmark JSON, the prompt should tell it:

- use the v2 benchmark format
- preserve the exact top-level fields
- use one consistent turn object shape
- keep tool names drawn only from the declared `tool_manifest`
- put all mocked tool outputs in `mock_tool_results`
- put all scoring rules in `expectations`
- avoid inventing extra keys unless requested

LLMs are much more reliable when:

- field names are repetitive
- enums are visible
- examples are provided
- the schema is stable

---

## What This Improves

This format improves:

- readability
- schema validation
- community authoring
- LLM generation quality
- persistent-session realism
- runtime determinism

Most importantly, it makes the benchmark file read like a session script instead of a loosely structured config blob.

---

## Summary

The v2 format should be understood simply:

- `meta` = what this benchmark file is
- `session` = how the session behaves
- `tool_manifest` = what tools exist in this benchmark world
- `turns` = what happens in order
- `mock_tool_results` = what the environment returns if tools are called
- `expectations` = how correctness is scored

That is the intended authoring model for community benchmark scripts.
