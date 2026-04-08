# 01 Agentic Loop Benchmark

## Why this note exists

The current benchmark measures tool-calling turns, but it is still too close to a single request-response harness. For a benchmark that makes sense to agent users and to local inference people, `gnuckle` needs a real loop:

1. assistant plans
2. assistant calls tool(s)
3. tool outputs are appended
4. assistant reasons again
5. loop repeats until final answer or hard stop

That loop is the thing we should measure, not just one streamed completion.

## Research takeaways

Two patterns showed up clearly in the docs:

1. LangGraph pattern
- `llm -> conditional edge -> tool node -> llm -> ... -> end`
- the loop stops only when the last assistant message has no tool calls
- this is the cleanest benchmark model because it makes the loop explicit

2. OpenAI Agents runner pattern
- run current agent
- if output is final, stop
- if output contains tool calls, execute tools and append results
- if output hands off, switch agent and continue
- useful telemetry points:
  - agent start/end
  - llm call count
  - tool invocation count
  - run usage
  - max-turn guard

## What `gnuckle` should benchmark

For the agentic mode, each benchmark case should be a workflow, not just a prompt.

Minimum workflow shape:

1. seed instruction
- system prompt for tool-first behavior

2. user task
- something that requires multiple tool decisions

3. loop
- assistant response
- if tool calls exist, execute mock tools
- append tool outputs
- ask assistant to continue
- repeat until final answer or max loop count

4. stop conditions
- no tool calls and final assistant answer exists
- loop count exceeded
- invalid tool call exceeded threshold
- model stalls or returns empty content repeatedly

## Proposed benchmark object

Each benchmark case should define:

- `id`
- `name`
- `goal`
- `system_prompt`
- `user_prompt`
- `tools_allowed`
- `expected_tool_path`
- `max_loops`
- `success_rule`
- `notes`

Example categories:

1. single-tool retrieval
- one tool call, then final answer

2. sequential multi-tool
- time -> weather -> calendar

3. corrective loop
- first tool result forces a second decision

4. branching loop
- model must choose between search, tasks, calendar, or weather

5. final synthesis
- multiple tool outputs must be summarized correctly

## Telemetry to capture per loop

Per loop step:

- `loop_index`
- `assistant_ttft_ms`
- `assistant_elapsed_s`
- `assistant_tokens_generated`
- `assistant_tps`
- `context_tokens_approx`
- `tool_calls_count`
- `tool_call_names`
- `tool_call_arguments`
- `tool_validity`
- `tool_execution_count`
- `assistant_preview`
- `tool_result_preview`
- `vram_before_mb`
- `vram_after_mb`

Per workflow:

- `workflow_completed`
- `workflow_success`
- `final_answer_present`
- `final_answer_preview`
- `llm_call_count`
- `tool_call_count_total`
- `invalid_tool_calls_total`
- `empty_response_count`
- `max_loop_reached`
- `wall_time_s`

## Metrics that matter

Primary:

- workflow success rate
- loops to completion
- valid tool path rate
- total LLM calls per workflow
- total wall time per workflow
- decode speed across loops
- TTFT across loops

Secondary:

- final answer quality
- tool argument accuracy
- context growth rate
- VRAM growth per loop

## Benchmark modes

`gnuckle` should probably separate these modes:

1. `agentic`
- real looped tool workflows
- success/failure oriented

2. `turboquant`
- long-context quality/speed/memory mode
- not tool-centric

The current benchmark is closer to `agentic-lite`. It should become a stricter loop runner.

## Practical next implementation

Near-term changes:

1. add workflow definitions file
- likely `gnuckle/workflows.json`

2. change a turn into a loop
- each benchmark case runs until final answer or max loops

3. persist richer per-loop outputs
- assistant preview
- tool preview
- stop reason

4. update dashboard
- workflow cards
- loop timeline
- telemetry + prompt/response split view

5. add strict correctness scoring
- did the model use the right tools
- did it terminate cleanly
- did it synthesize a final answer

## Notes for later

- handoffs can be added later, but they are not needed for v1
- approval checkpoints can also wait
- first goal is a deterministic loop benchmark with clear stop reasons

## Sources

- LangGraph workflow pattern from Context7:
  - `/websites/langchain_oss_python_langgraph`
- OpenAI Agents loop pattern from Context7:
  - `/openai/openai-agents-python`
