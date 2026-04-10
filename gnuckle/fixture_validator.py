from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixtureExpectation:
    directory: str
    required_files: tuple[str, ...]
    requires_ground_truth: bool = False


FIXTURE_EXPECTATIONS: tuple[FixtureExpectation, ...] = (
    FixtureExpectation("benchmark_core/cb_01_tool_call_validity", ("README.md",)),
    FixtureExpectation("benchmark_core/cb_02_tool_selection", ("notes.txt",)),
    FixtureExpectation("benchmark_core/cb_03_refusal", ("README.md",)),
    FixtureExpectation("benchmark_core/cb_04_multi_turn", ("README.md",), True),
    FixtureExpectation("benchmark_core/cb_05_constitutional", tuple(f"note_{idx}.txt" for idx in range(1, 8)), True),
    FixtureExpectation("benchmark_core/cb_06_memory_integrity", ("memory_facts.json", "noise_1.txt", "noise_2.txt", "noise_3.txt"), True),
    FixtureExpectation("benchmark_core/cb_07_context_pressure", ("notes.txt", "context_filler.txt"), True),
    FixtureExpectation("benchmark_core/cb_08_resource_viability", ("README.md",)),
    FixtureExpectation("benchmark_core/cb_09_implicit_convention", ("convention.md", "example_output_1.md", "example_output_2.md", "input.txt"), True),
    FixtureExpectation("benchmark_core/cb_10_tool_denial", ("README.md", "workspace_file.txt"), True),
    FixtureExpectation("benchmark_core/cb_11_prompt_weight", ("task_note.txt",), True),
    FixtureExpectation("benchmark_core/cb_12_chained_execution", ("brief.txt", "inputs.txt", "schedule.txt", "constraints.txt"), True),
    FixtureExpectation("benchmark_life_mgmt/wf_a_journal_analysis", tuple(f"day_{idx}.txt" for idx in range(1, 6)), True),
    FixtureExpectation("benchmark_life_mgmt/wf_b_note_triage", (
        "meeting_alpha.txt",
        "meeting_beta.txt",
        "meeting_gamma.txt",
        "idea_alpha.txt",
        "idea_beta.txt",
        "idea_gamma.txt",
        "todo_home.txt",
        "todo_work.txt",
        "empty.txt",
        "meeting_alpha_copy.txt",
    ), True),
    FixtureExpectation("benchmark_life_mgmt/wf_c_daily_agenda", ("today.txt", "yesterday.txt"), True),
    FixtureExpectation("benchmark_life_mgmt/wf_c_tl_taglish_agenda", ("README.md",), True),
    FixtureExpectation("benchmark_life_mgmt/wf_d_memory_retention", (
        "note_monday.txt",
        "note_tuesday.txt",
        "note_wednesday.txt",
        "note_thursday.txt",
        "note_friday.txt",
        "errands.txt",
        "health_log.txt",
        "goals.txt",
    ), True),
    FixtureExpectation("benchmark_life_mgmt/wf_e_commitment_tracking", ("today_notes.txt", "errands.txt", "goals.txt"), True),
    FixtureExpectation("benchmark_life_mgmt/wf_f_scope_boundary", ("README.md",)),
    FixtureExpectation("benchmark_life_mgmt/wf_g_implicit_format", ("format.md", "2026-04-07.md", "2026-04-08.md", "2026-04-09.md"), True),
    FixtureExpectation("benchmark_life_mgmt/wf_g_explicit_format", ("format.md", "2026-04-07.md", "2026-04-08.md", "2026-04-09.md"), True),
    FixtureExpectation("benchmark_life_mgmt/wf_g_decay_format", (
        "format.md",
        "2026-04-07.md",
        "2026-04-08.md",
        "2026-04-09.md",
        "errands.txt",
        "goals.txt",
        "health_log.txt",
        "note_monday.txt",
        "note_tuesday.txt",
        "note_wednesday.txt",
        "note_thursday.txt",
        "note_friday.txt",
        "shopping_list.txt",
        "project_notes.txt",
        "reminders.txt",
        "contacts.txt",
    ), True),
)

PROMPT_WEIGHT_EXPECTATIONS = ("100.md", "500.md", "2000.md", "6000.md", "12000.md")


def package_root() -> Path:
    return Path(__file__).resolve().parent


def fixtures_root() -> Path:
    return package_root() / "fixtures"


def sha256_text(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_ground_truth(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ground truth must be a JSON object")
    if "workflow_id" not in data:
        raise ValueError("ground truth missing workflow_id")
    return data


def validate_fixture(expectation: FixtureExpectation) -> dict:
    base = fixtures_root() / expectation.directory
    errors: list[str] = []
    hashes: dict[str, str] = {}
    if not base.is_dir():
        return {"directory": expectation.directory, "ok": False, "errors": [f"missing directory: {base}"], "hashes": {}}
    for filename in expectation.required_files:
        file_path = base / filename
        if not file_path.is_file():
            errors.append(f"missing file: {file_path}")
            continue
        hashes[filename] = sha256_text(file_path)
    if expectation.requires_ground_truth:
        gt_path = base / "_ground_truth.json"
        if not gt_path.is_file():
            errors.append(f"missing ground truth: {gt_path}")
        else:
            try:
                load_ground_truth(gt_path)
                hashes["_ground_truth.json"] = sha256_text(gt_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"invalid ground truth {gt_path}: {exc}")
    return {"directory": expectation.directory, "ok": not errors, "errors": errors, "hashes": hashes}


def validate_prompt_weight() -> dict:
    base = fixtures_root() / "benchmark_shared" / "prompt_weight"
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for filename in PROMPT_WEIGHT_EXPECTATIONS:
        file_path = base / filename
        if not file_path.is_file():
            errors.append(f"missing prompt-weight filler: {file_path}")
            continue
        text = file_path.read_text(encoding="utf-8")
        hashes[filename] = sha256_text(file_path)
        if filename == "12000.md":
            for marker in ("## AGENTS", "## Memory", "## Skills Index", "## Tool Definitions"):
                if marker not in text:
                    errors.append(f"12000.md missing required marker: {marker}")
            if text.count("### Tool ") < 12:
                errors.append("12000.md must include at least 12 tool definitions")
    return {"directory": "benchmark_shared/prompt_weight", "ok": not errors, "errors": errors, "hashes": hashes}


def validate_all() -> dict:
    fixture_results = [validate_fixture(expectation) for expectation in FIXTURE_EXPECTATIONS]
    prompt_weight_result = validate_prompt_weight()
    all_results = fixture_results + [prompt_weight_result]
    return {"ok": all(item["ok"] for item in all_results), "fixtures": all_results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic benchmark fixtures.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    result = validate_all()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print("Fixture validation:", "PASS" if result["ok"] else "FAIL")
        for entry in result["fixtures"]:
            print(f"- {entry['directory']}: {'ok' if entry['ok'] else 'error'}")
            for error in entry["errors"]:
                print(f"  - {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
