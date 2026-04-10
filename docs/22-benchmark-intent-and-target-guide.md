# 22 Benchmark Intent And Target Guide

## Purpose

This document defines the intended scope, target questions, and operating boundaries of the `gnuckle` benchmark.

It exists to prevent the benchmark from drifting into:

- a generic LLM benchmark
- a pure coding benchmark
- a copy of existing frontier-agent benchmarks
- a speculative benchmark for future local models that do not yet represent the real operating ceiling

This guide is the benchmark's targeting reference.

If `18` defines the benchmark structure and `19` defines the build sequence, this document defines what the benchmark is trying to prove, for whom, and against what real-world expectations.

---

## Key Points

- The benchmark is for **local model agent viability**, not general chatbot quality.
- The benchmark targets **current local-model ceilings**, not hypothetical future systems.
- The benchmark measures **working-harness behavior**, not isolated answer quality.
- The benchmark is designed for **small**, **mid**, and **top-end** local model bands.
- The benchmark uses **deterministic mocked tools and fixed fixtures** so scores remain auditable.
- The benchmark treats **behavioral integrity**, **memory decay**, **context survivability**, and **resource viability** as first-class concerns.
- The benchmark should answer what a user can **reliably trust a local model to do now**.

---

## Core Intent

The benchmark exists to answer a practical question:

> If I run a local model inside a small but real agent harness, what class of work can I trust it to do, how long can it keep doing that work, and what resources does it cost?

That question is more useful than asking whether the model is "smart" in the abstract.

The benchmark does not attempt to measure intelligence in the broadest sense.

It measures whether a local model can behave like a useful agent inside a constrained harness that resembles how real users operate systems such as:

- OpenClaude
- Hermes Agent
- OpenClaw

The benchmark should therefore focus on:

- tool-mediated action
- multi-turn statefulness
- repeated task execution
- instruction and preference retention
- memory pressure
- context growth
- verification discipline
- runtime cost on local hardware

---

## What The Benchmark Is Not

The benchmark is not intended to be:

- a one-shot chat benchmark
- a pure function-calling benchmark
- a live-web benchmark
- a browser-agent benchmark
- a frontier-cloud benchmark
- a benchmark for future agent capabilities that local models cannot currently approach

The benchmark also should not be optimized around:

- maximum difficulty for its own sake
- flashy demos
- unconstrained autonomy
- tasks that cannot be scored deterministically

The purpose is not to make the hardest benchmark possible.

The purpose is to make the most useful benchmark for evaluating the present-day reliable operating range of local agentic models.

---

## The Niche

The benchmark's niche is:

**persistent local-agent viability under harness conditions**

This means the benchmark should emphasize:

- local execution realities
- constrained tool use
- persistent or repeated sessions
- memory and context pressure
- instruction decay
- behavioral integrity over time
- runtime speed and VRAM cost

This is different from most common benchmark niches:

- SWE-bench style coding benchmarks emphasize software task completion
- WebArena style benchmarks emphasize browser environments
- BFCL style benchmarks emphasize function-call correctness
- Needle-in-a-Haystack emphasizes retrieval under long context

Those are all useful references, but none of them directly answer:

> Can I run this local model in a harness for real bounded work, and if so, for what kinds of tasks and for how long before it degrades?

That is the niche.

---

## Target User Questions

The benchmark should help a user answer questions like:

- Can this local model do basic harness work at all?
- Can it survive a multi-step task without losing the thread?
- Can it keep following the system prompt after many tool calls?
- Can it preserve stored user preferences and memory?
- How much memory can I inject before it becomes unreliable?
- How much context can be consumed before behavior degrades?
- Is it fast enough for interactive use?
- Is it only usable for background cron-style jobs?
- How much VRAM does it need to be practical?
- Is this model better suited for small tasks, medium practical workflows, or long chained work?

If the benchmark cannot help answer those questions, it is mis-scoped.

---

## The Ceiling-Oriented Approach

The benchmark should be designed around **current local-model ceilings**.

It should not begin from the assumption that local models can already match the best cloud agents across all domains.

Instead, it should establish whether current assumptions about local models are actually true.

The benchmark should test:

- the lower floor of viability
- the practical usefulness band
- the current top-end local ceiling

This means the benchmark is **ceiling-validation-oriented**.

Its job is to determine:

- what small local models can really do
- what mid-sized local models can reliably sustain
- what top-end local models can achieve before they decay

If a future model exceeds the benchmark's current ceiling assumptions, that is the time to expand the benchmark.

Not before.

---

## Current Target Bands

The benchmark should be organized around three present-day operating bands.

### 1. Small Models

This band is about minimum viability.

Questions:

- Can the model make valid tool calls?
- Can it follow a simple chain?
- Can it finish a bounded task correctly?
- Does it fail immediately once the session becomes noisy?

Expected use class if successful:

- very small bounded tasks
- simple extraction
- narrow assistants
- basic low-risk automation

### 2. Mid Models

This band is about practical usefulness.

Questions:

- Can the model handle realistic multi-step tasks?
- Can it recover from one or two failures?
- Can it retain simple standing rules?
- Can it survive repeated runs and light memory load?

Expected use class if successful:

- personal assistant tasks
- file and note workflows
- recurring cron-style jobs
- constrained coding or editing tasks
- medium-complexity structured workflows

### 3. Top-End Local Models

This band is about current ceiling discovery.

Questions:

- How far can the model go before drift?
- Can it preserve constitutional behavior under load?
- Can it keep discovering and applying conventions under context pressure?
- Can it sustain longer chains without bluffing or losing verification discipline?

Expected use class if successful:

- longer chained workflows
- more capable coding assistance
- multi-step planning and execution
- repeated agent sessions with light to moderate persistence

The top-end band is still bounded.

The benchmark should not assume that a top-end local model is a safe fully autonomous general agent.

---

## The Benchmark World Model

The benchmark should simulate a real agent harness, but keep the environment deterministic.

That means:

- tools are mocked
- file contents are fixed
- search results are pre-authored
- dates are anchored
- injected memory is controlled
- context noise is fixed
- scoring uses known ground truth

This is required because the benchmark needs to detect:

- hallucination
- omission
- distortion
- behavioral drift
- failure to inspect before acting
- failure to verify before finish

Live systems add noise.

Mocked systems make scores comparable.

---

## What Must Be Measured

The benchmark's central measurements are:

### 1. Agentic Competence

Can the model:

- choose tools
- use them in the right order
- react to results
- complete a task

### 2. Behavioral Integrity

Can the model keep following:

- system prompt rules
- standing workflow rules
- persistent user preferences
- required response behaviors

### 3. Memory Integrity

Can the model preserve:

- injected memory facts
- commitments made earlier in the session
- preferences committed to memory

### 4. Context Survivability

How much transcript, tool-result, and memory load can the model tolerate before quality regresses?

### 5. Recovery Behavior

When the model makes a mistake or receives a failed result, does it:

- adapt
- retry intelligently
- choose a different path

Or does it:

- loop
- hallucinate
- bluff success

### 6. Verification Discipline

Does the model actually check its work before finishing?

### 7. Resource Viability

Can the model do the above with acceptable:

- VRAM
- RAM
- latency
- throughput
- wall-clock time

---

## Why Integrity And Decay Matter

For local agent harnesses, the central failure mode is often not total inability.

It is **decay**.

Over time, the harness accumulates:

- tool results
- prior turns
- injected memory
- standing rules
- user preferences
- context noise

As these accumulate, the model may still produce plausible responses while becoming less reliable.

This benchmark therefore treats the following as first-class:

- **Constitution Under Load (CUL)**
  - whether behavior rules survive long chains and noise
- **Integrity Decay Curve**
  - how reliability falls as the context and memory burden increase
- **Maximum Reliable Memory Budget (MRMB)**
  - the largest memory load the model can carry while remaining reliable

These are not side metrics.

They are central to whether a local model can be trusted as an agent.

---

## What Counts As Success

A benchmark result is useful only if it lets a user make a grounded decision.

The benchmark is successful when its output can tell a user:

- whether the model is harness-viable at all
- whether it belongs in the small, mid, or top-end local operating band
- whether it is trustworthy only for short tasks, or also for repeated work
- whether it requires aggressive memory pruning
- whether it can preserve system and user rules
- whether it is interactive-usable or background-only

The benchmark should produce results that are operationally interpretable, not just numerically interesting.

---

## Benchmark Doctrine

The benchmark should follow these rules:

1. Prefer working-harness realism over benchmark spectacle.
2. Prefer deterministic fixtures over live variability.
3. Prefer grounded task completion over plausible summaries.
4. Prefer behavioral integrity metrics over one-dimensional scores.
5. Prefer present-day local ceilings over speculative future difficulty.
6. Prefer auditability over hidden benchmark magic.
7. Prefer actionable outputs over abstract performance claims.

---

## Evolution Rule

The benchmark should evolve only when the field moves.

That means:

- if small models begin consistently clearing the current floor, the floor can be raised
- if mid models begin consistently matching the current practical band, the practical band can be made harder
- if top-end local models begin saturating the current stress tests, new stress variants can be added

Until then, the benchmark should remain focused on measuring where local models are now.

This is a feature, not a limitation.

The benchmark becomes credible by staying tied to current reality.

---

## Relationship To Existing Benchmark Docs

This guide should be read alongside:

- `docs/15-benchmark-system-intent.md`
- `docs/18-benchmark-workflow-spec.md`
- `docs/19-benchmark-workflow-implementation-plan.md`

Relationship:

- `15` explains the original benchmark intent
- `18` defines the benchmark structure and workflows
- `19` defines the implementation sequence and success gates
- `22` defines the benchmark's present-day target and niche

If future scope expands materially beyond the current local-model ceiling orientation, a new numbered targeting document should be created instead of silently mutating this one.

---

## Summary

The benchmark exists to determine the present-day reliable operating ceiling of local models inside a working agent harness.

It should answer:

- what small models can minimally do
- what mid models can practically sustain
- what top-end local models can achieve before decay

It should do this using:

- deterministic fixtures
- mocked tools
- grounded scoring
- integrity and decay tracking
- resource measurements

The benchmark's niche is not generic intelligence.

Its niche is:

**whether a local model can behave as a reliable agent in a persistent harness, for how long, and at what cost.**
