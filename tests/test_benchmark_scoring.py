from __future__ import annotations

import unittest

from gnuckle.benchmark_scoring import assign_type, finalize_benchmark_summary, grade_for_score


class BenchmarkScoringTests(unittest.TestCase):
    def test_assign_type_respects_diagnostic_thresholds(self) -> None:
        self.assertEqual(assign_type({"d_1_single_tool_call": 0.0}), "Type 0")
        self.assertEqual(
            assign_type(
                {
                    "d_1_single_tool_call": 1.0,
                    "d_2_two_tool_sequence": 0.5,
                    "d_3_rule_retention": 1.0,
                }
            ),
            "Type 1",
        )
        self.assertEqual(
            assign_type(
                {
                    "d_1_single_tool_call": 1.0,
                    "d_2_two_tool_sequence": 1.0,
                    "d_3_rule_retention": 1.0,
                }
            ),
            "Type 2",
        )

    def test_grade_bands_match_spec(self) -> None:
        self.assertEqual(grade_for_score(0.95), "A")
        self.assertEqual(grade_for_score(0.80), "B")
        self.assertEqual(grade_for_score(0.62), "C")
        self.assertEqual(grade_for_score(0.46), "D")
        self.assertEqual(grade_for_score(0.10), "F")

    def test_finalize_summary_emits_type_grade_and_derived_metrics(self) -> None:
        diagnostics = [
            {"workflow_id": "d_1_single_tool_call", "workflow_score_mean": 1.0},
            {"workflow_id": "d_2_two_tool_sequence", "workflow_score_mean": 1.0},
            {"workflow_id": "d_3_rule_retention", "workflow_score_mean": 1.0},
        ]
        workflows = [
            {"workflow_id": "cb_02_tool_selection", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.9, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_06_memory_integrity", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.92, "derived_metrics": {"MRMB": {"mean": 4096, "stddev": 0.0, "values": [4096]}}, "usability_flags": []},
            {"workflow_id": "cb_07_context_pressure", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.9, "derived_metrics": {"context_degradation_gradient": {"mean": 0.25, "stddev": 0.0, "values": [0.25]}}, "usability_flags": []},
            {"workflow_id": "cb_10_tool_denial", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.85, "derived_metrics": {"tool_denial_threshold_output": {"mean": 0.85, "stddev": 0.0, "values": [0.85]}}, "usability_flags": []},
            {"workflow_id": "cb_11_prompt_weight_100", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.9, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_12_chained_execution", "benchmark_layer": "core", "profile_id": None, "workflow_score_mean": 0.92, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "wf_c_daily_agenda", "benchmark_layer": "profile", "profile_id": "life-mgmt", "workflow_score_mean": 0.7, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "wf_e_commitment_tracking", "benchmark_layer": "profile", "profile_id": "life-mgmt", "workflow_score_mean": 0.8, "derived_metrics": {"commitment_recall_rate": {"mean": 0.8, "stddev": 0.0, "values": [0.8]}}, "usability_flags": []},
            {"workflow_id": "wf_d_memory_retention", "benchmark_layer": "profile", "profile_id": "life-mgmt", "workflow_score_mean": 0.75, "derived_metrics": {"CUL_retention": {"mean": 0.75, "stddev": 0.0, "values": [0.75]}}, "usability_flags": []},
            {"workflow_id": "wf_g_implicit_format", "benchmark_layer": "profile", "profile_id": "life-mgmt", "workflow_score_mean": 0.65, "derived_metrics": {"discovery_retention": {"mean": 1.0, "stddev": 0.0, "values": [1.0]}}, "usability_flags": []},
            {"workflow_id": "wf_g_explicit_format", "benchmark_layer": "diagnostic_variant", "profile_id": "life-mgmt", "workflow_score_mean": 0.9, "derived_metrics": {"discovery_retention": {"mean": 1.0, "stddev": 0.0, "values": [1.0]}}, "usability_flags": []},
            {"workflow_id": "wf_g_decay_format", "benchmark_layer": "diagnostic_variant", "profile_id": "life-mgmt", "workflow_score_mean": 0.45, "derived_metrics": {"discovery_retention": {"mean": 0.0, "stddev": 0.0, "values": [0.0]}}, "usability_flags": []},
            {"workflow_id": "wf_c_tl_taglish_agenda", "benchmark_layer": "diagnostic_variant", "profile_id": "life-mgmt", "workflow_score_mean": 0.6, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_11_prompt_weight_500", "benchmark_layer": "diagnostic_variant", "profile_id": None, "workflow_score_mean": 0.88, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_11_prompt_weight_2000", "benchmark_layer": "diagnostic_variant", "profile_id": None, "workflow_score_mean": 0.8, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_11_prompt_weight_6000", "benchmark_layer": "diagnostic_variant", "profile_id": None, "workflow_score_mean": 0.7, "derived_metrics": {}, "usability_flags": []},
            {"workflow_id": "cb_11_prompt_weight_12000", "benchmark_layer": "diagnostic_variant", "profile_id": None, "workflow_score_mean": 0.65, "derived_metrics": {}, "usability_flags": []}
        ]
        summary = finalize_benchmark_summary(
            workflow_summaries=workflows,
            diagnostics=diagnostics,
            cache_label="q4_0",
            model_name="model.gguf",
            session_mode="fresh_session",
            workflow_suite="benchmark",
            runtime_config={},
            generated_at="2026-04-10T00:00:00",
        )
        self.assertEqual(summary["summary"]["type"], "Type 3")
        self.assertIn(summary["summary"]["grade"], {"A", "B", "C", "D", "F"})
        self.assertIn("instruction_gap", summary["summary"]["derived_metrics"])
        self.assertIn("prompt_weight_tolerance", summary["summary"]["derived_metrics"])


if __name__ == "__main__":
    unittest.main()
