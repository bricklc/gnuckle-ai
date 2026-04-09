# 11 V2 Agentic Benchmark Plan

## Purpose

This note defines the purpose and planned scope of `gnuckle` v2 agentic benchmarking.

V2 exists to answer a stronger question than v1.

V1 asks:

- can the model complete a bounded agentic task?

V2 asks:

- can the model complete bounded agentic work
- while preserving tool choice quality
- while preserving behavioral rules
- while preserving prompt and memory integrity
- while remaining operationally usable on local hardware

This is still a pragmatic benchmark, not a full agent platform.

## Core Benchmark Question

For local agentic inference, users need to know:

1. Can the model solve the task?
2. Can it keep obeying the original rules as the session grows?
3. Can it keep remembering the original request and loaded memory?
4. How much context and memory can it tolerate before reliability decays?
5. How much VRAM and time does that cost?

V2 must answer those questions directly.

## V2 Benchmark Dimensions

V2 should be organized around these benchmark dimensions:

1. `Capability`
   - can the model finish bounded agentic work?
2. `Tool Choice`
   - does it choose the correct tool from a realistic menu?
3. `Constitution Under Load`
   - does it preserve required behavioral rules under tool noise and long context?
4. `Integrity Decay Curve`
   - when does it start to ignore old prompts, old commitments, or loaded memory?
5. `Local Resource Pressure`
   - what token, context, VRAM, and runtime cost does that behavior require?

## V2 Workloads

V2 should keep the benchmark small enough to run locally but broad enough to reveal drift.

The benchmark suite should contain at least:

1. `Coding Repair`
   - read, edit, test, finish
2. `Tool Routing`
   - choose correctly among multiple tools with distractors
3. `Constitution Under Load`
   - maintain persistent behavioral rules across turns and tool calls
4. `Integrity Decay`
   - preserve old prompt, user preferences, and memory facts under growing load

## Required Data Layers

Every v2 episode should record three parallel data layers.

### 1. Inference Usage

- provider input tokens
- provider output tokens
- current context estimate
- context window
- context percent used

### 2. Runtime Performance

- TTFT
- tokens per second
- wall-clock time
- turn latency

### 3. Hardware Pressure

- VRAM current
- VRAM peak
- RAM current
- RAM peak
- KV cache usage when available

## Local-First Design Rule

V2 must remain useful for users running local `llama.cpp`-style inference.

That means:

- VRAM must be treated as first-class benchmark data
- context pressure must be visible, not inferred vaguely
- benchmark results must help users decide how much memory and prompt load they can safely keep in session

## Product Rule

V2 must still feel like `gnuckle`.

Required continuity:

- ape-themed copy remains consistent
- model selector remains simple
- profiles remain supported
- benchmark output remains immediately usable
- visualizer remains static HTML

## Build Order

Implementation should happen in this order:

1. finalize v2 metrics and benchmark definitions
2. add missing runtime telemetry
3. implement v2 workload classes
4. implement v2 HTML visualizer
5. add post-run visualizer prompt and browser launch flow

## Acceptance Rule

V2 should not be considered ready until:

- benchmark metrics are locked in docs
- runtime output contains those metrics
- HTML visualizer shows those metrics clearly
- results remain understandable for local-model users

