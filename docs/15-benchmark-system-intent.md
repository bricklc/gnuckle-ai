# 15 Benchmark System Intent

## Purpose

This note defines the starting hypothesis of the `gnuckle` benchmark system.

It does **not** define every implementation detail.

It defines:

- what we believe we are measuring
- why we believe a single flat benchmark is not enough
- what kinds of failure we care about
- what the system is meant to reveal about local models

This is the intent document for the benchmark system.

## Starting Hypothesis

The core hypothesis is:

**local models should not be judged only by whether they answer one prompt or finish one task.**

They should be judged by whether they can:

- function inside a bounded agent harness
- choose tools correctly
- preserve behavioral rules from the system prompt
- preserve the original user request over time
- preserve loaded memory and prior commitments
- remain reliable as the session becomes longer and noisier
- remain usable within local token and VRAM limits

In other words:

**the benchmark is trying to measure not just capability, but agentic reliability under pressure.**

## Why A Flat Benchmark Is Not Enough

A single fixed benchmark hides too much.

If the benchmark is too hard:

- weak models only fail
- we learn almost nothing about their floor
- we cannot tell whether they are unusable or just mis-tiered

If the benchmark is too easy:

- strong models only pass
- we learn almost nothing about their ceiling
- we cannot tell when they drift, decay, or become unreliable

So the benchmark system should not ask only:

- did the model pass?

It should ask:

- what class of agentic work can this model handle?
- where is its minimum reliable level?
- where is its ceiling?
- where does it start to fall apart?

## What We Are Actually Testing For

The benchmark system is testing for six things.

### 1. Harness Competence

Can the model operate inside a bounded tool-using harness at all?

This includes:

- valid tool calling
- basic file or task interaction
- bounded completion behavior
- ability to finish or fail cleanly

This is the minimum viable agent floor.

### 2. Practical Agentic Competence

Can the model do useful bounded work reliably?

This includes:

- reading files
- editing files
- running tests
- choosing the right tool from a visible menu
- recovering from tool failure
- verifying before claiming success

This is the practical usefulness layer.

### 3. Tool Choice Quality

Can the model choose the correct tool when multiple tools are available?

This matters because real agents do not operate with only one obvious path.

The benchmark is not only testing:

- can the model format a tool call?

It is also testing:

- can the model choose the correct tool at the correct time?
- can it avoid unnecessary tool calls?
- can it avoid disallowed or irrelevant actions?

### 4. Constitutional Retention

Can the model preserve required behavioral rules from the system prompt as the episode grows?

This is called:

- `Constitution Under Load`

The benchmark should test whether the model still obeys standing rules after:

- repeated turns
- repeated tool calls
- tool failures
- longer transcripts
- growing context pressure

The model should not only complete tasks.

It should remain the **same kind of agent** over time.

### 5. Prompt And Memory Integrity

Can the model still remember:

- the initial user request
- persistent user preferences
- loaded memory facts
- prior commitments

after the session becomes crowded with tool calls, tool results, and accumulated context?

This is the integrity question.

The benchmark should identify when the model begins to:

- ignore old prompts
- ignore initial requests
- forget loaded memory
- contradict prior state
- drift away from the intended behavior

This is not just memory recall.

It is:

- prompt integrity
- behavior integrity
- memory integrity

under context pressure.

### 6. Local Resource Viability

Can the model do all of the above while remaining practical on local hardware?

This includes:

- provider token usage
- context occupancy
- TTFT
- wall-clock latency
- VRAM usage
- RAM usage
- long-session stability

A local model benchmark is incomplete if it can say:

- the model succeeded

but cannot say:

- how much context it consumed
- how much VRAM it required
- whether it remained stable as load increased

## The Benchmark Philosophy

The benchmark system is designed around three beliefs.

### 1. Failure Is Data

Model failures should not simply kill the run.

They should be preserved as benchmark evidence.

This includes:

- invalid tool calls
- retries
- execution failures
- permission denials
- malformed finish behavior
- verification failures
- behavioral drift

If the run fails, that failure is part of what we wanted to measure.

### 2. Reliability Matters More Than Isolated Brilliance

A model that occasionally does something impressive but cannot maintain behavior or verification discipline is not a dependable agent.

So the benchmark is biased toward:

- repeatability
- recovery
- stability
- integrity

not only flash performance.

### 3. Context Is A Competitive Resource

In agentic systems, many things compete for context:

- system prompt
- user request
- tool calls
- tool results
- memory
- summaries
- retrieved context
- formatting rules
- scheduler metadata

So the benchmark must treat context as a scarce operational budget.

This is why the system cares about:

- context occupancy
- integrity decay
- maximum reliable memory budget

and not only raw context-window claims.

## Why The System Is Tiered

The benchmark system should be adaptive, not flat.

That means a short diagnostic should place the model into an appropriate agentic tier.

The point is not to flatter the model.

The point is to get a more truthful answer.

Weak models should be tested for:

- minimum viable harness competence

Moderate models should be tested for:

- practical bounded agent usefulness

Strong models should be tested for:

- stress behavior
- drift
- memory decay
- constitutional retention

This makes the output more useful than one score.

The intended result is:

- `Type + Grade`

For example:

- `Type 1, D`
- `Type 2, B`
- `Type 3, A`

That tells the user:

- what class of work the model can handle
- where its floor is
- where its ceiling is

## The Meaning Of The Main Benchmark Concepts

### Legacy Benchmark

The legacy benchmark is the systems benchmark.

It answers:

- how does the local inference stack behave?
- how do cache types affect speed, TTFT, and VRAM?
- how stable is tool calling in a shallow setting?

This is not the full agent benchmark.

It is the technical baseline.

### Agentic Benchmark

The agentic benchmark is the bounded-harness benchmark.

It answers:

- can the model behave like a working agent?

This includes:

- tool choice
- verification
- recovery
- bounded task completion
- integrity under pressure

### Constitution Under Load

This tests whether standing system-prompt rules survive the noise of real usage.

It is about behavioral retention.

### Integrity Decay Curve

This tests how prompt and memory integrity degrade as memory load and context pressure increase.

It is about survivability over time.

### Maximum Reliable Memory Budget

This is the practical threshold.

It answers:

- how much memory can be injected before the model stops being dependable?

This is more useful than simply saying:

- the model supports a large context window

## What Success Looks Like

A successful benchmark system should let a user answer questions like:

- can this model function as an agent at all?
- can it do practical bounded work?
- can it choose tools well?
- can it recover from failure?
- can it keep obeying the system prompt?
- can it keep remembering the original request?
- how much memory can it carry before drift starts?
- how much VRAM does it cost?
- what is the model’s reliable tier and where is its ceiling?

If the system can answer those questions clearly, then it is doing its job.

## Summary

The `gnuckle` benchmark system is not intended to be a generic benchmark for “model quality.”

Its intent is narrower and more useful.

It is trying to measure:

- bounded agentic competence
- reliability under pressure
- tool choice quality
- behavioral retention
- prompt and memory integrity
- local resource viability

The benchmark should therefore report not only:

- whether the model passed

but also:

- what kind of agent it is
- what it can reliably sustain
- where it starts to decay

That is the system intent.
