"""Generated benchmark workflow manifest."""

from __future__ import annotations


def _wf(
    workflow_id,
    title,
    fixture,
    event_text,
    *,
    benchmark_layer,
    difficulty,
    active_tools,
    expected_tools=None,
    max_turns=8,
    timeout_s=180,
    run_count=3,
    system_prompt="You are Gnuckle, a bounded benchmark agent. Use only the active tools, follow the workspace and prompt constraints, and finish when the task is complete.",
    slice_name="benchmark",
    profile_id=None,
    workflow_variant_of=None,
    standing_rules=None,
    mid_task_injections=None,
    supports_plaintext_turns=False,
    reporting_tags=None,
    prompt_weight_variant=None,
    denied_tools=None,
    ground_truth_path=None,
    scoring_method="ground_truth",
    expected_trace_pattern=None,
):
    tools = list(active_tools)
    return {
        "workflow_id": workflow_id,
        "title": title,
        "slice": slice_name,
        "difficulty": difficulty,
        "benchmark_layer": benchmark_layer,
        "profile_id": profile_id,
        "workflow_variant_of": workflow_variant_of,
        "system_prompt": system_prompt,
        "fixture": fixture,
        "ground_truth_path": ground_truth_path,
        "event": {
            "event_type": "interactive_request",
            "payload": {"text": event_text},
        },
        "standing_rules": list(standing_rules or []),
        "allowed_tools": tools,
        "active_tools": tools,
        "expected_tools": list(expected_tools or tools),
        "denied_tools": list(denied_tools or []),
        "expected_trace_pattern": list(expected_trace_pattern or (expected_tools or tools)),
        "max_turns": max_turns,
        "timeout_s": timeout_s,
        "run_count": run_count,
        "supports_plaintext_turns": supports_plaintext_turns,
        "mid_task_injections": list(mid_task_injections or []),
        "verification": {"required": False, "method": "manual", "command": []},
        "success_rule": {"type": "manual"},
        "scoring_method": scoring_method,
        "scoring_criteria": [],
        "reporting_tags": list(reporting_tags or []),
        "prompt_weight_variant": prompt_weight_variant,
        "tool_denial_expectation": None,
    }


def benchmark_manifest() -> dict:
    tools = {
        "echo": ["echo", "finish"],
        "files": ["list_files", "read_file", "write_file", "finish"],
        "files_append": ["list_files", "read_file", "write_file", "append_file", "finish"],
        "read": ["read_file", "finish"],
        "refusal": ["read_file", "write_file", "finish"],
        "agenda": ["list_files", "read_file", "write_file", "get_date", "finish"],
        "journal": ["list_files", "read_file", "write_file", "get_date", "finish"],
        "list_state": ["add_item", "update_item", "read_list", "finish"],
    }

    diagnostic = [
        _wf(
            "d_1_single_tool_call",
            "Diagnostic Single Tool Call",
            "benchmark_core/cb_01_tool_call_validity",
            "Use the echo tool to repeat the phrase: benchmark test.",
            benchmark_layer="diagnostic",
            difficulty="easy",
            active_tools=tools["echo"],
            expected_tools=tools["echo"],
            max_turns=4,
            timeout_s=120,
            reporting_tags=["diagnostic"],
        ),
        _wf(
            "d_2_two_tool_sequence",
            "Diagnostic Two Tool Sequence",
            "benchmark_core/cb_04_multi_turn",
            "Add milk to my list.",
            benchmark_layer="diagnostic",
            difficulty="easy",
            active_tools=tools["list_state"],
            expected_tools=tools["list_state"],
            max_turns=6,
            timeout_s=120,
            reporting_tags=["diagnostic"],
            system_prompt="You are Gnuckle, a bounded benchmark agent. Keep list state accurate across turns and finish only when the list is correct.",
            mid_task_injections=[
                {"after_turn": 1, "text": "Change that to diagnostic task updated."},
                {"after_turn": 2, "text": "Show me the list and then finish."},
            ],
        ),
        _wf(
            "d_3_rule_retention",
            "Diagnostic Rule Retention",
            "benchmark_core/cb_05_constitutional",
            "Read note_1.txt.",
            benchmark_layer="diagnostic",
            difficulty="easy",
            active_tools=tools["read"],
            expected_tools=tools["read"],
            max_turns=4,
            timeout_s=120,
            reporting_tags=["diagnostic"],
            system_prompt="You are Gnuckle, a bounded benchmark agent. Always answer in bullet points. Use tools when needed, then finish.",
            standing_rules=["Always respond in bullet points."],
            mid_task_injections=[{"after_turn": 1, "text": "Summarize what you read in bullet points and then finish."}],
        ),
    ]

    core = [
        _wf("cb_01_tool_call_validity", "CB-1 Tool Call Validity", "benchmark_core/cb_01_tool_call_validity", "Use the echo tool to repeat the phrase: benchmark test.", benchmark_layer="core", difficulty="easy", active_tools=tools["echo"], expected_tools=tools["echo"], max_turns=4, timeout_s=120),
        _wf("cb_02_tool_selection", "CB-2 Tool Selection Precision", "benchmark_core/cb_02_tool_selection", "Read the contents of notes.txt and then finish.", benchmark_layer="core", difficulty="easy", active_tools=["read_file", "write_file", "list_files", "finish"], expected_tools=["read_file", "finish"], max_turns=5, timeout_s=120, scoring_method="trace_criteria", standing_rules=["Never use delete_file."], system_prompt="You are Gnuckle, a bounded benchmark agent. Read only what is necessary. Finish after the request is complete."),
        _wf("cb_03_refusal", "CB-3 Refusal Correctness", "benchmark_core/cb_03_refusal", "Send an email to my brother reminding him about Thursday.", benchmark_layer="core", difficulty="easy", active_tools=tools["refusal"], expected_tools=["write_file", "finish"], max_turns=5, timeout_s=120, supports_plaintext_turns=True, system_prompt="You are Gnuckle, a bounded benchmark agent. If the tool set cannot complete the task, explain the limitation or offer a bounded workaround, then finish."),
        _wf("cb_04_multi_turn", "CB-4 Multi-Turn Coherence", "benchmark_core/cb_04_multi_turn", "Add milk to my list.", benchmark_layer="core", difficulty="easy", active_tools=tools["list_state"], expected_tools=tools["list_state"], max_turns=6, timeout_s=120, system_prompt="You are Gnuckle, a bounded benchmark agent. Keep list state accurate across turns and finish only when the list is correct.", mid_task_injections=[{"after_turn": 1, "text": "Change that to 2 liters of fresh milk."}, {"after_turn": 2, "text": "Show me the list and then finish."}]),
        _wf("cb_05_constitutional", "CB-5 Constitutional Retention", "benchmark_core/cb_05_constitutional", "Read note_1.txt.", benchmark_layer="core", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=12, timeout_s=180, standing_rules=["Always respond in bullet points.", "Never suggest activities after 8pm.", "Health-related items go first in any list."], system_prompt="You are Gnuckle, a bounded benchmark agent. Always respond in bullet points. Never suggest activities after 8pm. Health-related items go first in any list.", mid_task_injections=[{"after_turn": 1, "text": "Read note_2.txt."}, {"after_turn": 2, "text": "Read note_3.txt."}, {"after_turn": 3, "text": "Read note_4.txt."}, {"after_turn": 4, "text": "Read note_5.txt."}, {"after_turn": 5, "text": "Read note_6.txt."}, {"after_turn": 6, "text": "Read note_7.txt."}, {"after_turn": 7, "text": "Summarize what you've read and suggest what I should do tomorrow. Then finish."}]),
        _wf("cb_06_memory_integrity", "CB-6 Memory Integrity Curve", "benchmark_core/cb_06_memory_integrity", "Read memory_facts.json.", benchmark_layer="core", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=9, timeout_s=180, system_prompt="You are Gnuckle, a bounded benchmark agent. Preserve factual details across injected noise, then answer from memory and finish.", mid_task_injections=[{"after_turn": 1, "text": "Read noise_1.txt."}, {"after_turn": 2, "text": "Read noise_2.txt."}, {"after_turn": 3, "text": "Read noise_3.txt."}, {"after_turn": 4, "text": "What is the dog's name, the board exam month, the vehicle, and the sister location? Then finish."}]),
        _wf("cb_07_context_pressure", "CB-7 Context Pressure Gradient", "benchmark_core/cb_07_context_pressure", "Read notes.txt.", benchmark_layer="core", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=8, timeout_s=180, system_prompt="You are Gnuckle, a bounded benchmark agent. Preserve the launch facts under growing context pressure, then finish.", mid_task_injections=[{"after_turn": 1, "text": "Read context_filler.txt."}, {"after_turn": 2, "text": "Read context_filler.txt again."}, {"after_turn": 3, "text": "Read context_filler.txt one more time."}, {"after_turn": 4, "text": "Summarize the launch blockers and timing facts you saw, then finish."}]),
        _wf("cb_08_resource_viability", "CB-8 Resource Viability", "benchmark_core/cb_08_resource_viability", "Use the echo tool to confirm the harness is resource-stable.", benchmark_layer="core", difficulty="medium", active_tools=tools["echo"], expected_tools=tools["echo"], max_turns=4, timeout_s=120, scoring_method="manual"),
        _wf("cb_09_implicit_convention", "CB-9 Implicit Convention Adherence", "benchmark_core/cb_09_implicit_convention", "Inspect the workspace, then write summary.md capturing the current launch state and finish.", benchmark_layer="core", difficulty="medium", active_tools=tools["files"], expected_tools=tools["files"], max_turns=8, timeout_s=180, reporting_tags=["implicit"], system_prompt="You are Gnuckle, a bounded benchmark agent. Follow any conventions you discover in the workspace before writing anything new."),
        _wf("cb_10_tool_denial", "CB-10 Tool Denial Detection", "benchmark_core/cb_10_tool_denial", "Read workspace_file.txt, update it with a short status note, and then finish.", benchmark_layer="core", difficulty="medium", active_tools=tools["refusal"], expected_tools=["read_file", "finish"], max_turns=6, timeout_s=180, supports_plaintext_turns=True, denied_tools=["write_file"], system_prompt="You are Gnuckle, a bounded benchmark agent. Inspect tool results and adapt when a tool is denied. Do not loop on a denied tool."),
        _wf("cb_11_prompt_weight_100", "CB-11 Prompt Weight Tolerance (100)", "benchmark_core/cb_11_prompt_weight", "Read task_note.txt. Summarize the maintenance plan and finish.", benchmark_layer="core", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=5, timeout_s=180, prompt_weight_variant="100", system_prompt="You are Gnuckle, a bounded benchmark agent. Read the task note, summarize the patch plan accurately, and then finish."),
        _wf("cb_12_chained_execution", "CB-12 Chained Plan And Execute", "benchmark_core/cb_12_chained_execution", "Inspect the workspace, build plan.md for today, avoid blocked slots, put urgent work first, and include every required item before you finish.", benchmark_layer="core", difficulty="hard", active_tools=tools["files"], expected_tools=tools["files"], max_turns=10, timeout_s=240, standing_rules=["Urgent items must appear before non-urgent items.", "No task may be assigned to a blocked slot.", "Every item from inputs.txt must appear in plan.md."], system_prompt="You are Gnuckle, a bounded benchmark agent. Inspect the workspace, read the planning files, write plan.md, and finish only when the plan satisfies the stated constraints."),
    ]

    profile = [
        _wf("wf_a_journal_analysis", "WF-A Journal Analysis", "benchmark_life_mgmt/wf_a_journal_analysis", "Read all journal entries. Extract every unfinished task. Identify recurring themes. Summarize the week in 3 bullet points. Save the output to summary.md and then finish.", benchmark_layer="profile", difficulty="easy", active_tools=tools["files"], expected_tools=tools["files"], slice_name="life-mgmt", profile_id="life-mgmt", reporting_tags=["implicit"], system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Read the journal workspace carefully, extract tasks and themes accurately, write a concise summary file, then finish."),
        _wf("wf_b_note_triage", "WF-B Note Triage", "benchmark_life_mgmt/wf_b_note_triage", "Create an index file grouping these notes by theme. Flag which ones need action. Do not delete or overwrite any existing file.", benchmark_layer="profile", difficulty="easy", active_tools=tools["files_append"], expected_tools=["list_files", "read_file", "write_file", "finish"], slice_name="life-mgmt", profile_id="life-mgmt", standing_rules=["Do not delete or modify existing notes. You may only create new files or append to existing ones."], system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Inspect the note workspace, do not alter existing notes, create one index file, and then finish."),
        _wf("wf_c_daily_agenda", "WF-C Daily Agenda Build", "benchmark_life_mgmt/wf_c_daily_agenda", "Read today.txt and yesterday.txt. Build a structured plan for today with morning and afternoon blocks. Carry forward incomplete items from yesterday. Health tasks first. Save to agenda.md and then finish.", benchmark_layer="profile", difficulty="medium", active_tools=tools["agenda"], expected_tools=["read_file", "write_file", "get_date", "finish"], slice_name="life-mgmt", profile_id="life-mgmt", standing_rules=["Health tasks go first.", "Never schedule activities after 8pm."], system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Build structured daily plans. Health tasks go first. Never schedule anything past 8pm. Save the plan to agenda.md and then finish.", mid_task_injections=[{"after_turn": 2, "text": "Add one more item: Call my brother before noon."}]),
        _wf("wf_d_memory_retention", "WF-D Memory Retention Under Load", "benchmark_life_mgmt/wf_d_memory_retention", "Read note_monday.txt.", benchmark_layer="profile", difficulty="hard", active_tools=tools["read"], expected_tools=tools["read"], max_turns=14, timeout_s=240, slice_name="life-mgmt", profile_id="life-mgmt", standing_rules=["Always respond in bullet points.", "Never suggest activities after 8pm.", "Health-related items go first in any list.", "Do not include motivational language. Facts only."], system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Always respond in bullet points. Never suggest activities after 8pm. Health-related items go first in any list. Do not include motivational language. Facts only.", mid_task_injections=[{"after_turn": 1, "text": "Read note_tuesday.txt."}, {"after_turn": 2, "text": "Read note_wednesday.txt."}, {"after_turn": 3, "text": "Read note_thursday.txt."}, {"after_turn": 4, "text": "Read note_friday.txt."}, {"after_turn": 5, "text": "Read errands.txt."}, {"after_turn": 6, "text": "Read health_log.txt."}, {"after_turn": 7, "text": "Read goals.txt."}, {"after_turn": 8, "text": "Summarize what you've read and suggest what I should do this weekend. Then finish."}]),
        _wf("wf_e_commitment_tracking", "WF-E Commitment Tracking", "benchmark_life_mgmt/wf_e_commitment_tracking", "Hey, let me think out loud for a sec.", benchmark_layer="profile", difficulty="medium", active_tools=["read_file", "write_file", "finish"], expected_tools=["read_file", "finish"], max_turns=12, timeout_s=180, slice_name="life-mgmt", profile_id="life-mgmt", supports_plaintext_turns=True, system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Some turns are pure conversation. Remember commitments stated in conversation, use tools when asked, and finish when the user asks for a recap.", mid_task_injections=[{"after_turn": 1, "text": "I told my sister I'd call her Thursday."}, {"after_turn": 2, "text": "Read my notes from today."}, {"after_turn": 3, "text": "Don't let me forget the dentist appointment."}, {"after_turn": 4, "text": "What's in errands.txt?"}, {"after_turn": 5, "text": "I owe Marcus a reply about the trip."}, {"after_turn": 6, "text": "Read goals.txt for me."}, {"after_turn": 7, "text": "What have I committed to so far in this conversation? Then finish."}]),
        _wf("wf_f_scope_boundary", "WF-F Scope Boundary", "benchmark_life_mgmt/wf_f_scope_boundary", "Send a reminder to my brother about our Thursday call.", benchmark_layer="profile", difficulty="easy", active_tools=["read_file", "write_file", "list_files", "finish"], expected_tools=["write_file", "finish"], max_turns=5, timeout_s=120, slice_name="life-mgmt", profile_id="life-mgmt", supports_plaintext_turns=True, system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. If a tool does not exist, explain the boundary clearly or offer a bounded draft workaround, then finish."),
        _wf("wf_g_implicit_format", "WF-G Implicit Format Adherence", "benchmark_life_mgmt/wf_g_implicit_format", "Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive. Save it as 2026-04-10.md and then finish.", benchmark_layer="profile", difficulty="hard", active_tools=tools["journal"], expected_tools=tools["journal"], max_turns=8, timeout_s=180, slice_name="life-mgmt", profile_id="life-mgmt", reporting_tags=["implicit"], system_prompt="You have access to the user's journal folder. When writing entries, follow any conventions found in the workspace."),
    ]

    variants = [
        _wf("wf_c_tl_taglish_agenda", "WF-C Taglish Variant", "benchmark_life_mgmt/wf_c_daily_agenda", "Basahin mo yung today.txt at yesterday.txt. Gawa ka ng structured plan for today -- morning at afternoon blocks. I-carry forward yung incomplete from yesterday. Health tasks muna lagi. Save mo as agenda.md tapos finish.", benchmark_layer="diagnostic_variant", difficulty="medium", active_tools=tools["agenda"], expected_tools=["read_file", "write_file", "get_date", "finish"], slice_name="life-mgmt", profile_id="life-mgmt", workflow_variant_of="wf_c_daily_agenda", ground_truth_path="gnuckle/fixtures/benchmark_life_mgmt/wf_c_tl_taglish_agenda/_ground_truth.json", reporting_tags=["taglish", "diagnostic"], system_prompt="You are Gnuckle, a bounded personal assistant benchmark agent. Build structured daily plans. Health tasks go first. Never schedule anything past 8pm. Save the plan to agenda.md and then finish.", mid_task_injections=[{"after_turn": 2, "text": "Paki-add na lang, kailangan ko tawagan kapatid ko before noon."}]),
        _wf("wf_g_explicit_format", "WF-G Explicit Format Variant", "benchmark_life_mgmt/wf_g_explicit_format", "Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive. Use this format: date header as ## YYYY-MM-DD, a mood tag as [mood: X], and bullet points for the body. Save it as 2026-04-10.md and then finish.", benchmark_layer="diagnostic_variant", difficulty="medium", active_tools=tools["journal"], expected_tools=tools["journal"], max_turns=8, timeout_s=180, slice_name="life-mgmt", profile_id="life-mgmt", workflow_variant_of="wf_g_implicit_format", reporting_tags=["explicit", "diagnostic"], system_prompt="You have access to the user's journal folder. When writing entries, follow any conventions found in the workspace."),
        _wf("wf_g_decay_format", "WF-G Decay Variant", "benchmark_life_mgmt/wf_g_decay_format", "Read errands.txt.", benchmark_layer="diagnostic_variant", difficulty="hard", active_tools=tools["journal"], expected_tools=["read_file", "write_file", "get_date", "finish"], max_turns=18, timeout_s=240, slice_name="life-mgmt", profile_id="life-mgmt", workflow_variant_of="wf_g_implicit_format", reporting_tags=["decay", "diagnostic"], system_prompt="You have access to the user's journal folder. When writing entries, follow any conventions found in the workspace.", mid_task_injections=[{"after_turn": 1, "text": "Read goals.txt."}, {"after_turn": 2, "text": "Read health_log.txt."}, {"after_turn": 3, "text": "Read note_monday.txt."}, {"after_turn": 4, "text": "Read note_tuesday.txt."}, {"after_turn": 5, "text": "Read note_wednesday.txt."}, {"after_turn": 6, "text": "Read note_thursday.txt."}, {"after_turn": 7, "text": "Read note_friday.txt."}, {"after_turn": 8, "text": "Read shopping_list.txt."}, {"after_turn": 9, "text": "Read project_notes.txt."}, {"after_turn": 10, "text": "Read reminders.txt."}, {"after_turn": 11, "text": "Read contacts.txt."}, {"after_turn": 12, "text": "Log today's entry: Skipped gym, reviewed thermodynamics chapter 3, feeling tired but productive. Save it as 2026-04-10.md and then finish."}]),
        _wf("cb_11_prompt_weight_500", "CB-11 Prompt Weight Tolerance (500)", "benchmark_core/cb_11_prompt_weight", "Read task_note.txt. Summarize the maintenance plan and finish.", benchmark_layer="diagnostic_variant", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=5, timeout_s=180, workflow_variant_of="cb_11_prompt_weight_100", reporting_tags=["diagnostic"], prompt_weight_variant="500", system_prompt="You are Gnuckle, a bounded benchmark agent. Read the task note, summarize the patch plan accurately, and then finish."),
        _wf("cb_11_prompt_weight_2000", "CB-11 Prompt Weight Tolerance (2000)", "benchmark_core/cb_11_prompt_weight", "Read task_note.txt. Summarize the maintenance plan and finish.", benchmark_layer="diagnostic_variant", difficulty="medium", active_tools=tools["read"], expected_tools=tools["read"], max_turns=5, timeout_s=180, workflow_variant_of="cb_11_prompt_weight_100", reporting_tags=["diagnostic"], prompt_weight_variant="2000", system_prompt="You are Gnuckle, a bounded benchmark agent. Read the task note, summarize the patch plan accurately, and then finish."),
        _wf("cb_11_prompt_weight_6000", "CB-11 Prompt Weight Tolerance (6000)", "benchmark_core/cb_11_prompt_weight", "Read task_note.txt. Summarize the maintenance plan and finish.", benchmark_layer="diagnostic_variant", difficulty="hard", active_tools=tools["read"], expected_tools=tools["read"], max_turns=5, timeout_s=180, workflow_variant_of="cb_11_prompt_weight_100", reporting_tags=["diagnostic"], prompt_weight_variant="6000", system_prompt="You are Gnuckle, a bounded benchmark agent. Read the task note, summarize the patch plan accurately, and then finish."),
        _wf("cb_11_prompt_weight_12000", "CB-11 Prompt Weight Tolerance (12000)", "benchmark_core/cb_11_prompt_weight", "Read task_note.txt. Summarize the maintenance plan and finish.", benchmark_layer="diagnostic_variant", difficulty="hard", active_tools=tools["read"], expected_tools=tools["read"], max_turns=5, timeout_s=180, workflow_variant_of="cb_11_prompt_weight_100", reporting_tags=["diagnostic"], prompt_weight_variant="12000", system_prompt="You are Gnuckle, a bounded benchmark agent. Read the task note, summarize the patch plan accurately, and then finish."),
    ]

    ordered_ids = [item["workflow_id"] for item in (diagnostic + core + profile + variants)]
    return {
        "suites": {
            "default": ordered_ids,
            "benchmark": ordered_ids,
            "diagnostic": [item["workflow_id"] for item in diagnostic],
            "core": [item["workflow_id"] for item in core],
            "life-mgmt": [item["workflow_id"] for item in profile],
        },
        "workflows": diagnostic + core + profile + variants,
    }
