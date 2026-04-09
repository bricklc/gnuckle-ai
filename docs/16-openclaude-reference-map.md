# OpenClaude Reference Map

Purpose:
- keep the exact OpenClaude grounding points in one place for future benchmark work
- preserve the source anchors that define the intended harness behavior
- reduce drift when implementing v2 agentic benchmark features

This note is reference-only.
It does not replace the benchmark intent or success-metrics docs.
It exists so implementation can consistently return to the same source anchors.

## Persistent Multi-Turn Loop

- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L209)
- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L757)
- [query.ts](/G:/2026%20Projects/openclaude/src/query.ts#L1367)

Intent:
- one session
- one growing transcript
- repeated assistant -> tool_call -> tool_result -> assistant
- explicit turn limits
- explicit terminal result

## Tool Availability and Injection

- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L213)
- [query.ts](/G:/2026%20Projects/openclaude/src/query.ts#L668)
- [runAgent.ts](/G:/2026%20Projects/openclaude/src/tools/AgentTool/runAgent.ts#L915)

Intent:
- tools are explicitly passed into the runtime
- the model sees the active tool list in both prompt/runtime context
- hidden tool assumptions are avoided

## Tool Orchestration

- [toolOrchestration.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts#L19)
- [toolOrchestration.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts#L91)
- [toolOrchestration.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolOrchestration.ts#L118)

Intent:
- bounded orchestration of tool use
- explicit mediation between assistant actions and tool execution
- consistent orchestration path across tools

## Tool Execution and Error Handling

- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L337)
- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L614)
- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L682)
- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L995)
- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L1206)
- [toolExecution.ts](/G:/2026%20Projects/openclaude/src/services/tools/toolExecution.ts#L469)

Intent:
- validate input
- check permission
- execute tool
- wrap failures as in-band tool results
- keep the loop alive after recoverable failure

## Permission Denials

- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L247)
- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L261)

Intent:
- separate denied actions from execution failures
- keep permission-denial data available for scoring and analysis

## Tool Result Pairing and Interrupt Repair

- [query.ts](/G:/2026%20Projects/openclaude/src/query.ts#L1017)
- [query.ts](/G:/2026%20Projects/openclaude/src/query.ts#L1490)
- [claude.ts](/G:/2026%20Projects/openclaude/src/services/api/claude.ts#L1298)

Intent:
- every tool call should have one matching tool result
- interrupted runs should repair missing tool results
- traces should remain structurally valid

## Usage Accounting

- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L657)
- [QueryEngine.ts](/G:/2026%20Projects/openclaude/src/QueryEngine.ts#L789)
- [claude.ts](/G:/2026%20Projects/openclaude/src/services/api/claude.ts#L2924)
- [claude.ts](/G:/2026%20Projects/openclaude/src/services/api/claude.ts#L2993)

Intent:
- keep provider-reported usage as one accounting track
- update usage incrementally during streamed responses
- accumulate usage across the session

## Context Budget and Token Estimation

- [tokens.ts](/G:/2026%20Projects/openclaude/src/utils/tokens.ts#L46)
- [tokens.ts](/G:/2026%20Projects/openclaude/src/utils/tokens.ts#L79)
- [tokens.ts](/G:/2026%20Projects/openclaude/src/utils/tokens.ts#L201)
- [autoCompact.ts](/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts#L33)
- [autoCompact.ts](/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts#L72)
- [autoCompact.ts](/G:/2026%20Projects/openclaude/src/services/compact/autoCompact.ts#L225)

Intent:
- separate current context occupancy from cumulative usage
- estimate pressure against the effective window
- support decay and survivability measurements

## Verification Behavior

- [verificationAgent.ts](/G:/2026%20Projects/openclaude/src/tools/AgentTool/built-in/verificationAgent.ts#L12)

Intent:
- success is not the model claiming completion
- success requires verification

## Optional Delegation

- [AgentTool.tsx](/G:/2026%20Projects/openclaude/src/tools/AgentTool/AgentTool.tsx#L239)
- [AgentTool.tsx](/G:/2026%20Projects/openclaude/src/tools/AgentTool/AgentTool.tsx#L797)

Intent:
- bounded child-agent execution is a later-stage extension
- useful for v2 or Type 3, not required for core v1 validity

## UI Handling of Rejections and Errors

- [UserToolRejectMessage.tsx](/G:/2026%20Projects/openclaude/src/components/messages/UserToolResultMessage/UserToolRejectMessage.tsx#L21)
- [UserToolErrorMessage.tsx](/G:/2026%20Projects/openclaude/src/components/messages/UserToolResultMessage/UserToolErrorMessage.tsx#L23)

Intent:
- rejection and tool error states should remain visible
- error visibility matters for both operator understanding and benchmark analysis

## Implementation Reminder

Use these anchors to preserve the benchmark’s core hypothesis:
- a model is not only being tested on whether it can act once
- it is being tested on whether it can remain agentically reliable over time
- under transcript growth
- under tool noise
- under failure
- under context pressure
- under local hardware constraints
