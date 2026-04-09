# 14 V2 Visualizer And Post-Run Flow

## Purpose

This note defines the visualizer and post-run UX contract for `gnuckle` v2.

The visualizer must serve both:

- legacy benchmark runs
- agentic benchmark runs

And the benchmark command must offer an immediate path into the static HTML view.

## Visualizer Contract

The visualizer remains:

- static HTML
- local-only
- generated from benchmark JSON

The visualizer must support:

1. legacy cache comparison reports
2. agentic episode reports
3. inline run-folder selector when multiple saved runs exist

## Agentic Visualizer Sections

The agentic report should include at least:

### 1. Run Summary

- model
- cache label
- workflow suite
- session mode
- generated time

### 2. Outcome Cards

- status
- task completed
- verification passed
- episode score
- tool selection precision
- constitution adherence rate
- integrity score

### 3. Resource Cards

- provider input tokens
- provider output tokens
- provider total tokens
- peak context estimate
- context percent used
- peak VRAM
- steady VRAM
- peak RAM

### 4. Performance Cards

- TTFT
- tokens per second
- wall-clock runtime
- average turn latency
- turns used
- tool calls used

### 5. Failure And Recovery

- invalid tool calls
- retry events
- execution failures
- permission denials
- synthetic tool results
- malformed finish events

### 6. Trace Timeline

- assistant step
- tool call
- tool result
- retry
- verification
- final result

### 7. Integrity Sections

- constitution under load results
- prompt and memory integrity results
- drift point indicators
- MRMB where applicable

## Post-Run Prompt Contract

After benchmark completion, the CLI should ask:

```text
benchmark is complete. it took __seconds (or minutes).
do you want to open the visualizer now? [y/n]
```

If the user says yes:

- generate the HTML visualizer if needed
- open it in the default browser

If the user says no:

- print:

```text
visualizer banana is saved in ./path for viewing later.
```

## Browser Launch Rule

Browser launch should be:

- local only
- explicit after user confirmation
- based on the exact run folder selected

## Implementation Rule

This post-run flow should be shared across both benchmark modes where a visualizer exists.

Legacy:

- prompt to open legacy dashboard

Agentic:

- prompt to open agentic dashboard once implemented

