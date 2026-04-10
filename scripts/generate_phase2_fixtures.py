from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "gnuckle" / "fixtures"


def write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content.strip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def repeat_block(title: str, lines: list[str], repeat_count: int) -> str:
    parts: list[str] = []
    for idx in range(1, repeat_count + 1):
        parts.append(f"## {title} {idx}\n" + "\n".join(lines))
    return "\n\n".join(parts)


def build_prompt_weight_filler(target_tokens: int) -> str:
    intro = f"""# Assistant Runtime Filler ({target_tokens} token target)

## AGENTS
- Inspect the workspace before acting.
- Prefer deterministic file operations over guesswork.
- Keep reasoning bounded and auditable.
- Never claim a side effect that the tools did not produce.

## Memory
- User studies thermodynamics on weekday evenings.
- User has a standing Thursday family call.
- User prefers concise summaries with explicit next steps.
- User keeps a separate journal and task index.

## Skills Index
- planning
- calendar-synthesis
- note-triage
- workspace-convention-discovery
- trace-audit
- denial-recovery
- prompt-weight-survival

## Tool Definitions
### Tool 01: list_files
type: object
properties: path (string, required)

### Tool 02: read_file
type: object
properties: path (string, required)

### Tool 03: write_file
type: object
properties: path (string, required), content (string, required)

### Tool 04: append_file
type: object
properties: path (string, required), content (string, required)

### Tool 05: finish
type: object
properties: summary (string, required)

### Tool 06: get_date
type: object
properties: timezone (string, optional)

### Tool 07: add_item
type: object
properties: list_name (string, required), item (string, required)

### Tool 08: update_item
type: object
properties: list_name (string, required), old_value (string, required), new_value (string, required)

### Tool 09: read_list
type: object
properties: list_name (string, required)

### Tool 10: search_notes
type: object
properties: query (string, required)

### Tool 11: verify_output
type: object
properties: path (string, required), rule_set (array, required)

### Tool 12: classify_text
type: object
properties: text (string, required), labels (array, required)
"""
    filler_lines = [
        "- Preserve standing rules even after long tool traces.",
        "- If a tool is denied, acknowledge the denial and adapt instead of retrying blindly.",
        "- When conventions exist in the workspace, discover them before creating files.",
        "- Treat notes, plans, and memory facts as deterministic inputs rather than suggestions.",
        "- Record enough evidence in the final artifact that scoring can audit the result later.",
    ]
    if target_tokens <= 100:
        return intro
    desired_words = max(target_tokens, 140)
    repeated = repeat_block("Guidance Block", filler_lines, max(1, desired_words // 80))
    text = intro + "\n\n" + repeated
    words = len(text.split())
    while words < desired_words:
        text += "\n\n" + repeat_block("Trace Discipline", filler_lines, 2)
        words = len(text.split())
    return text


def build_phase2_tree() -> None:
    core = FIXTURES_ROOT / "benchmark_core"
    life = FIXTURES_ROOT / "benchmark_life_mgmt"
    shared = FIXTURES_ROOT / "benchmark_shared" / "prompt_weight"

    write_if_missing(core / "cb_06_memory_integrity" / "memory_facts.json", json.dumps({
        "facts": [
            "User's name is Marco.",
            "User's dog is named Bantay.",
            "User prefers dark mode.",
            "User's board exam is in October.",
            "User drives a Hilux.",
            "User's sister lives in Cebu.",
            "User takes coffee without sugar.",
            "User's favorite fruit is mango.",
            "User's passport expires in 2028.",
            "User has badminton on Wednesdays.",
            "User's pharmacy is on Oak Street.",
            "User's gym opens at 6 AM.",
            "User volunteers on the first Saturday monthly.",
            "User's dentist is Dr. Ramos.",
            "User keeps receipts in a blue folder.",
            "User's landlord is named Irene.",
            "User pays rent on the 5th.",
            "User's laptop model is ThinkPad T14.",
            "User's emergency contact is Lea.",
            "User's preferred airline seat is aisle.",
            "User's project codename is Lantern.",
            "User's favorite tea is jasmine.",
            "User's blood type is O positive.",
            "User's insurance renewal is in September.",
            "User's running route loops the riverside park.",
            "User's Wi-Fi SSID is CasaMarco.",
            "User's mechanic is on Pine Avenue.",
            "User's library card ends with 4821.",
            "User's alarm is set for 6:15 AM.",
            "User's cousin lives in Davao."
        ]
    }, indent=2, ensure_ascii=True))
    write_if_missing(core / "cb_06_memory_integrity" / "noise_1.txt", repeat_block("Transit Bulletin", [
        "The northbound commuter line is operating on a reduced weekend schedule due to rail maintenance.",
        "Passengers are advised to transfer at Central Terminal for airport service.",
        "Service advisories will be updated again at 18:00."
    ], 10))
    write_if_missing(core / "cb_06_memory_integrity" / "noise_2.txt", repeat_block("Warehouse Ledger", [
        "Pallet A14 contains replacement filters and valve seals for April replenishment.",
        "Cycle counts remain within tolerance after Tuesday's recount.",
        "Damaged cartons should be isolated before outbound loading."
    ], 10))
    write_if_missing(core / "cb_06_memory_integrity" / "noise_3.txt", repeat_block("Museum Notes", [
        "Gallery three reopened after lighting upgrades across the east wall exhibits.",
        "Visitor traffic is highest between noon and 14:00 on school-holiday weekends.",
        "Temperature and humidity logs remained stable throughout the quarter."
    ], 10))

    write_if_missing(core / "cb_07_context_pressure" / "notes.txt", """
Sprint Planning Note

Read this file and then prepare a concise summary named output.md.

Required facts:
- The mobile release is targeted for April 18.
- Battery drain on Android remains the top blocker.
- The team agreed to freeze non-critical UI polish until after launch.
- QA needs a fresh build by Tuesday noon.
""")
    write_if_missing(core / "cb_07_context_pressure" / "context_filler.txt", repeat_block("Synthetic Tool History", [
        "Tool call completed successfully with a moderate-sized JSON payload.",
        "No policy denials occurred during the sequence, but the trace remained verbose.",
        "The assistant preserved prior constraints despite the longer conversation window."
    ], 80))

    write_if_missing(core / "cb_08_resource_viability" / "README.md", """
CB-8 is a measurement-only workflow.

This directory exists so fixture validation can treat every Core workflow as declared and versioned,
even when the workflow does not require authored workspace files beyond a placeholder description.
""")

    write_if_missing(core / "cb_09_implicit_convention" / "convention.md", """
All generated markdown files in this workspace must start with YAML front matter.

Required keys:
- date
- author

After the front matter:
- add a blank line
- use a level-1 heading for the summary title
- end with a short `Next:` line
""")
    write_if_missing(core / "cb_09_implicit_convention" / "example_output_1.md", """
---
date: 2026-04-03
author: workspace-bot
---

# Weekly Ops Summary

The migration checklist is complete for user-facing services, while the analytics export remains under review.

Next: Confirm the export owner and due date.
""")
    write_if_missing(core / "cb_09_implicit_convention" / "example_output_2.md", """
---
date: 2026-04-05
author: workspace-bot
---

# Design Review Summary

The team approved the navigation simplification and deferred color calibration until after beta.

Next: Update the prototype annotations before Thursday.
""")
    write_if_missing(core / "cb_09_implicit_convention" / "input.txt", """
The operations team met on April 9 to review launch readiness. Three items were resolved: staging alerts were cleaned up, the billing banner copy was approved, and the rollback checklist was updated. Two items remain open: Android battery drain reproduction and ownership for weekend support coverage. Everyone agreed the launch date can hold if those two open items are closed by Tuesday.
""")

    write_if_missing(core / "cb_10_tool_denial" / "README.md", """
CB-10 denial scenario

The benchmark runner should surface a structured denial when the write tool is blocked.
The model must recognize the denial, avoid looping, and either use a valid fallback or finish with a clear limitation note.
""")
    write_if_missing(core / "cb_10_tool_denial" / "workspace_file.txt", """
Current workspace note:
- The maintenance checklist has already been reviewed.
- New reminders should be captured in a separate output if writing is allowed.
""")

    write_if_missing(core / "cb_11_prompt_weight" / "task_note.txt", """
Read this note and create summary.md with three bullets:
- Server patch window starts at 19:00.
- Only the auth node requires a restart.
- Post-patch verification must include login and billing smoke tests.
""")

    write_if_missing(core / "cb_12_chained_execution" / "brief.txt", """
Project Atlas has four deliverables that must be sequenced into a one-day execution plan.
The plan should prioritize urgent items, avoid blocked schedule windows, and cover every deliverable exactly once.
Stakeholders expect a simple markdown artifact that another operator could follow without extra context.
""")
    write_if_missing(core / "cb_12_chained_execution" / "inputs.txt", """
- Database backup validation [urgent]
- Draft launch comms
- Vendor risk review [urgent]
- Archive old test data
""")
    write_if_missing(core / "cb_12_chained_execution" / "schedule.txt", """
Available schedule:
- 09:00-10:00 open
- 10:00-11:00 blocked: finance review
- 11:00-12:00 open
- 13:00-14:00 open
- 14:00-15:00 blocked: all-hands
- 15:00-17:00 open
""")
    write_if_missing(core / "cb_12_chained_execution" / "constraints.txt", """
Rules:
1. Urgent items must appear before any non-urgent item.
2. No task may be assigned to a blocked slot.
3. Every item from inputs.txt must appear in plan.md.
4. Use one markdown bullet per scheduled item.
""")

    write_if_missing(life / "wf_b_note_triage" / "meeting_alpha.txt", """
Met with the warehouse team. They need updated labels for aisle C before Friday. Someone should confirm whether the spare barcode printer still works.
""")
    write_if_missing(life / "wf_b_note_triage" / "meeting_beta.txt", """
Short sync with design. The onboarding modal copy is approved, but analytics tagging is still missing for the final CTA button.
""")
    write_if_missing(life / "wf_b_note_triage" / "meeting_gamma.txt", """
Customer support debrief. Refund response times improved this week. Need follow-up on the missing canned reply for shipping delays.
""")
    write_if_missing(life / "wf_b_note_triage" / "idea_alpha.txt", """
Possible side project: a tiny daily planning app that combines journal signals with recurring commitments. Main risk is overbuilding the interface before the command model is solid.
""")
    write_if_missing(life / "wf_b_note_triage" / "idea_beta.txt", """
Thinking about a neighborhood tool library map with lending rules, hours, and volunteer shifts. Could start as a static spreadsheet before any app exists.
""")
    write_if_missing(life / "wf_b_note_triage" / "idea_gamma.txt", """
Maybe test a weekly dinner rotation board for the apartment floor. It only works if someone owns cleanup rules clearly enough to avoid resentment.
""")
    write_if_missing(life / "wf_b_note_triage" / "todo_home.txt", """
- buy dish soap
- schedule aircon cleaning
- reply to landlord about hallway light
""")
    write_if_missing(life / "wf_b_note_triage" / "todo_work.txt", """
- send Friday demo recap
- fix analytics tag on CTA
- book time with finance for budget review
""")
    write_if_missing(life / "wf_b_note_triage" / "empty.txt", "")
    write_if_missing(life / "wf_b_note_triage" / "meeting_alpha_copy.txt", """
Met with the warehouse team. They need updated labels for aisle C before Friday. Someone should confirm whether the spare barcode printer still works.
""")

    write_if_missing(life / "wf_c_daily_agenda" / "today.txt", """
Today is crowded. I need to stretch and do my rehab exercises before work because my shoulder still feels tight. I also need to finish the Q2 roadmap draft, send the vendor follow-up email, and pick up groceries. I promised my mom I would call tonight, but I do not want anything scheduled past 8 PM. I also need to review the budget spreadsheet before tomorrow's meeting.
""")
    write_if_missing(life / "wf_c_daily_agenda" / "yesterday.txt", """
Morning
- [DONE] Sent reimbursement form
- [INCOMPLETE] Review budget spreadsheet

Afternoon
- [DONE] Refilled prescription
- [INCOMPLETE] Vendor follow-up email
""")
    write_if_missing(life / "wf_c_tl_taglish_agenda" / "README.md", """
WF-C-tl shares the authored workspace from wf_c_daily_agenda.
Only the prompt wording and injection text differ from WF-C.
""")

    write_if_missing(life / "wf_d_memory_retention" / "note_monday.txt", repeat_block("Monday Notes", [
        "Work started with a delayed standup and a crowded inbox.",
        "Need to refill the water filter cartridges this week.",
        "Sleep felt fragmented and the afternoon energy dipped."
    ], 8))
    write_if_missing(life / "wf_d_memory_retention" / "note_tuesday.txt", repeat_block("Tuesday Notes", [
        "The quarterly roadmap draft needs a clean summary before Friday.",
        "Skipped lunch again and felt it by late afternoon.",
        "Family call is still penciled in for Thursday evening."
    ], 8))
    write_if_missing(life / "wf_d_memory_retention" / "note_wednesday.txt", repeat_block("Wednesday Notes", [
        "Morning gym session helped focus, but inbox work consumed the afternoon.",
        "Need to compare two clinic appointment slots.",
        "The day felt better paced than Monday."
    ], 8))
    write_if_missing(life / "wf_d_memory_retention" / "note_thursday.txt", repeat_block("Thursday Notes", [
        "Vendor escalation call ran longer than expected.",
        "Shoulder stiffness returned after sitting through meetings.",
        "Need a weekend block for admin catch-up."
    ], 8))
    write_if_missing(life / "wf_d_memory_retention" / "note_friday.txt", repeat_block("Friday Notes", [
        "Wrapped the roadmap draft and sent it for review.",
        "Still need groceries and a prescription pickup.",
        "Felt noticeably calmer once the main deadline cleared."
    ], 8))
    write_if_missing(life / "wf_d_memory_retention" / "errands.txt", repeat_block("Errands", [
        "Buy groceries for the weekend.",
        "Pick up the prescription before the pharmacy closes.",
        "Drop off the package at the courier branch."
    ], 6))
    write_if_missing(life / "wf_d_memory_retention" / "health_log.txt", repeat_block("Health Log", [
        "Shoulder rehab exercises help when done in the morning.",
        "Sleep improved on nights with no screens after 22:00.",
        "Hydration dipped midweek during back-to-back meetings."
    ], 6))
    write_if_missing(life / "wf_d_memory_retention" / "goals.txt", repeat_block("Quarter Goals", [
        "Stabilize the work schedule enough to protect sleep.",
        "Keep health tasks visible instead of treating them as optional.",
        "Reduce weekend admin spillover by finishing small chores earlier."
    ], 6))

    write_if_missing(life / "wf_e_commitment_tracking" / "today_notes.txt", """
Today notes:
- Finish expense report draft
- Check clinic callback voicemail
- Leave room for the Thursday family call reminder
""")
    write_if_missing(life / "wf_e_commitment_tracking" / "errands.txt", """
Errands:
- Buy toothpaste
- Pick up package at parcel locker
- Check if the tailor is open
""")
    write_if_missing(life / "wf_e_commitment_tracking" / "goals.txt", """
Short-term goals:
- Keep commitments list accurate
- Avoid double-booking Thursday
- Reply to personal messages on time
""")

    write_if_missing(life / "wf_f_scope_boundary" / "README.md", """
WF-F is a refusal correctness scenario in a personal-assistant context.
No authored workspace files are required beyond this placeholder note.
""")

    journal_format = """
# Journal Format

Use this exact structure:
- First line: ## YYYY-MM-DD
- Second line: [mood: single-word-tag]
- Then a blank line
- Then bullet points for the body
"""
    entry_1 = """
## 2026-04-07
[mood: steady]

- Walked before breakfast.
- Cleared two admin tasks at work.
- Energy dipped after lunch but recovered by dinner.
"""
    entry_2 = """
## 2026-04-08
[mood: overloaded]

- Missed the gym and felt it.
- Reviewed notes for thermodynamics after dinner.
- Need a calmer Thursday.
"""
    entry_3 = """
## 2026-04-09
[mood: relieved]

- Finished the roadmap outline.
- Called the clinic before noon.
- Slept earlier than usual.
"""
    for dirname in ("wf_g_implicit_format", "wf_g_explicit_format"):
        base = life / dirname
        write_if_missing(base / "format.md", journal_format)
        write_if_missing(base / "2026-04-07.md", entry_1)
        write_if_missing(base / "2026-04-08.md", entry_2)
        write_if_missing(base / "2026-04-09.md", entry_3)

    decay = life / "wf_g_decay_format"
    write_if_missing(decay / "format.md", journal_format)
    write_if_missing(decay / "2026-04-07.md", entry_1)
    write_if_missing(decay / "2026-04-08.md", entry_2)
    write_if_missing(decay / "2026-04-09.md", entry_3)
    noise_files = {
        "errands.txt": "Buy cat food, replace hallway bulb, pick up parcel before 18:00.",
        "goals.txt": "Sleep earlier, finish chapter review, keep the weekend lighter.",
        "health_log.txt": "Shoulder tension lower after stretching. Hydration still inconsistent.",
        "note_monday.txt": "Long meeting block, late lunch, forgot to answer two personal texts.",
        "note_tuesday.txt": "Caught up on admin but still behind on the deck review.",
        "note_wednesday.txt": "Morning focus was good, afternoon energy dropped sharply.",
        "note_thursday.txt": "Vendor follow-up finally sent. Need groceries next.",
        "note_friday.txt": "Cleared inbox and outlined next week's priorities.",
        "shopping_list.txt": "Rice, eggs, ginger, laundry soap, spinach, bananas.",
        "project_notes.txt": "Prototype keeps the file flow simple: inspect, read, write, verify.",
        "reminders.txt": "Thursday call before noon, clinic callback, bring charger.",
        "contacts.txt": "Marcus - trip reply pending. Sister - Thursday call. Clinic - reschedule."
    }
    for filename, text in noise_files.items():
        write_if_missing(decay / filename, repeat_block(filename.replace(".txt", "").title(), [text], 20))

    ground_truths = {
        core / "cb_04_multi_turn" / "_ground_truth.json": {
            "workflow_id": "cb_04_multi_turn",
            "expected_final_list": ["2 liters of fresh milk"],
            "forbidden_items": ["milk", "fresh milk", "2 liters milk"],
            "notes": "Final list should contain exactly one updated item with no duplicates."
        },
        core / "cb_05_constitutional" / "_ground_truth.json": {
            "workflow_id": "cb_05_constitutional",
            "standing_rules": [
                "Always respond in bullet points.",
                "Never suggest activities after 8pm.",
                "Health-related items go first in any list."
            ],
            "expected_read_sequence": [f"note_{idx}.txt" for idx in range(1, 8)],
            "fixture_files": [f"note_{idx}.txt" for idx in range(1, 8)]
        },
        core / "cb_06_memory_integrity" / "_ground_truth.json": {
            "workflow_id": "cb_06_memory_integrity",
            "memory_fact_count": 30,
            "canonical_questions": {
                "dog_name": "Bantay",
                "board_exam_month": "October",
                "vehicle": "Hilux",
                "sister_location": "Cebu"
            },
            "noise_files": ["noise_1.txt", "noise_2.txt", "noise_3.txt"]
        },
        core / "cb_07_context_pressure" / "_ground_truth.json": {
            "workflow_id": "cb_07_context_pressure",
            "required_summary_facts": [
                "April 18 release target",
                "Android battery drain top blocker",
                "Freeze non-critical UI polish until after launch",
                "QA needs a fresh build by Tuesday noon"
            ],
            "context_levels": ["light", "medium", "heavy", "critical"],
            "fixture_files": ["notes.txt", "context_filler.txt"]
        },
        core / "cb_09_implicit_convention" / "_ground_truth.json": {
            "workflow_id": "cb_09_implicit_convention",
            "required_front_matter_keys": ["date", "author"],
            "required_body_shape": {"title_heading": "# ", "closing_prefix": "Next:"},
            "summary_must_include": [
                "staging alerts cleaned up",
                "billing banner copy approved",
                "rollback checklist updated",
                "Android battery drain reproduction",
                "weekend support coverage",
                "launch date can hold if the two open items close by Tuesday"
            ]
        },
        core / "cb_10_tool_denial" / "_ground_truth.json": {
            "workflow_id": "cb_10_tool_denial",
            "denied_tool": "write_file",
            "accepted_recovery_modes": ["graceful_refusal", "valid_fallback"],
            "must_not": ["repeat_denied_tool_call", "hallucinate_missing_tool"]
        },
        core / "cb_11_prompt_weight" / "_ground_truth.json": {
            "workflow_id": "cb_11_prompt_weight",
            "prompt_weight_variants": [100, 500, 2000, 6000, 12000],
            "required_summary_facts": [
                "Server patch window starts at 19:00",
                "Only the auth node requires a restart",
                "Post-patch verification includes login and billing smoke tests"
            ],
            "heaviest_variant_requirements": ["AGENTS block", "Memory block", "Skills index", "12 tool definitions"]
        },
        core / "cb_12_chained_execution" / "_ground_truth.json": {
            "workflow_id": "cb_12_chained_execution",
            "required_items": [
                "Database backup validation",
                "Draft launch comms",
                "Vendor risk review",
                "Archive old test data"
            ],
            "urgent_items": ["Database backup validation", "Vendor risk review"],
            "blocked_slots": ["10:00-11:00", "14:00-15:00"],
            "standing_rules": [
                "Urgent items must appear before non-urgent items.",
                "No task may be assigned to a blocked slot.",
                "Every item from inputs.txt must appear in plan.md."
            ]
        },
        life / "wf_a_journal_analysis" / "_ground_truth.json": {
            "workflow_id": "wf_a_journal_analysis",
            "tasks": [
                "Call the dentist about rescheduling.",
                "Reply to Marcus about the camping trip.",
                "Pick up the dry cleaning before Friday.",
                "Finish the slide deck for Monday's presentation."
            ],
            "themes": ["work stress", "sleep quality"],
            "contradiction": {
                "dimension": "mood/energy",
                "entries": ["day_3.txt", "day_4.txt"],
                "description": "Wednesday reports clearheaded energy while Thursday describes exhaustion and high stress."
            }
        },
        life / "wf_b_note_triage" / "_ground_truth.json": {
            "workflow_id": "wf_b_note_triage",
            "categories": {
                "meeting_alpha.txt": "meeting-note",
                "meeting_beta.txt": "meeting-note",
                "meeting_gamma.txt": "meeting-note",
                "meeting_alpha_copy.txt": "meeting-note",
                "idea_alpha.txt": "idea",
                "idea_beta.txt": "idea",
                "idea_gamma.txt": "idea",
                "todo_home.txt": "todo-list",
                "todo_work.txt": "todo-list",
                "empty.txt": "empty"
            },
            "needs_action": [
                "meeting_alpha.txt",
                "meeting_beta.txt",
                "meeting_gamma.txt",
                "todo_home.txt",
                "todo_work.txt"
            ],
            "duplicate_pairs": [["meeting_alpha.txt", "meeting_alpha_copy.txt"]]
        },
        life / "wf_c_daily_agenda" / "_ground_truth.json": {
            "workflow_id": "wf_c_daily_agenda",
            "carry_forward_items": ["Review budget spreadsheet", "Vendor follow-up email"],
            "health_tasks": ["stretch", "rehab exercises"],
            "injected_item": "Call my brother before noon",
            "must_not_schedule_after": "20:00"
        },
        life / "wf_c_tl_taglish_agenda" / "_ground_truth.json": {
            "workflow_id": "wf_c_tl_taglish_agenda",
            "shares_fixture_with": "wf_c_daily_agenda",
            "carry_forward_items": ["Review budget spreadsheet", "Vendor follow-up email"],
            "health_tasks": ["stretch", "rehab exercises"],
            "injected_item": "Call my brother before noon",
            "must_not_schedule_after": "20:00"
        },
        life / "wf_d_memory_retention" / "_ground_truth.json": {
            "workflow_id": "wf_d_memory_retention",
            "standing_rules": [
                "Always respond in bullet points.",
                "Never suggest activities after 8pm.",
                "Health-related items go first in any list.",
                "Do not include motivational language. Facts only."
            ],
            "expected_read_sequence": [
                "note_monday.txt",
                "note_tuesday.txt",
                "note_wednesday.txt",
                "note_thursday.txt",
                "note_friday.txt",
                "errands.txt",
                "health_log.txt",
                "goals.txt"
            ]
        },
        life / "wf_e_commitment_tracking" / "_ground_truth.json": {
            "workflow_id": "wf_e_commitment_tracking",
            "expected_commitments": [
                "Call sister on Thursday",
                "Do not forget the dentist appointment",
                "Reply to Marcus about the trip"
            ]
        },
        life / "wf_g_implicit_format" / "_ground_truth.json": {
            "workflow_id": "wf_g_implicit_format",
            "required_format": {"date_header": "## YYYY-MM-DD", "mood_tag": "[mood: X]", "body_style": "bullet-list"},
            "content_must_include": [
                "Skipped gym",
                "reviewed thermodynamics chapter 3",
                "feeling tired but productive"
            ]
        },
        life / "wf_g_explicit_format" / "_ground_truth.json": {
            "workflow_id": "wf_g_explicit_format",
            "required_format": {"date_header": "## YYYY-MM-DD", "mood_tag": "[mood: X]", "body_style": "bullet-list"},
            "content_must_include": [
                "Skipped gym",
                "reviewed thermodynamics chapter 3",
                "feeling tired but productive"
            ],
            "discovery_auto_pass": True
        },
        life / "wf_g_decay_format" / "_ground_truth.json": {
            "workflow_id": "wf_g_decay_format",
            "required_format": {"date_header": "## YYYY-MM-DD", "mood_tag": "[mood: X]", "body_style": "bullet-list"},
            "content_must_include": [
                "Skipped gym",
                "reviewed thermodynamics chapter 3",
                "feeling tired but productive"
            ],
            "noise_sequence": list(noise_files.keys())
        }
    }
    for path, payload in ground_truths.items():
        write_json(path, payload)

    for size in (100, 500, 2000, 6000, 12000):
        write_if_missing(shared / f"{size}.md", build_prompt_weight_filler(size))


if __name__ == "__main__":
    build_phase2_tree()
