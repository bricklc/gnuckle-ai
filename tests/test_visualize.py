from __future__ import annotations

import unittest

from gnuckle.benchmark import parse_llama_bench_output
from gnuckle.visualize import build_session_comparison_html, extract_metrics


class VisualizeTests(unittest.TestCase):
    def test_parse_llama_bench_output_extracts_prompt_and_gen_rates(self) -> None:
        raw = """
| model | test | t/s |
| --- | --- | --- |
| demo.gguf | pp512 | 19.3 |
| demo.gguf | tg128 | 10.6 |
"""
        parsed = parse_llama_bench_output(raw)
        self.assertEqual(parsed["prompt_label"], "pp512")
        self.assertEqual(parsed["generation_label"], "tg128")
        self.assertEqual(parsed["prompt_tokens_per_second"], 19.3)
        self.assertEqual(parsed["generation_tokens_per_second"], 10.6)

    def test_extract_metrics_reads_benchmark_throughput_snapshot(self) -> None:
        data = {
            "meta": {
                "throughput_benchmark": {
                    "available": True,
                    "prompt_tokens_per_second": 20.1,
                    "generation_tokens_per_second": 11.4,
                }
            },
            "turns": [
                {"tps": 10.0, "ttft_ms": 500.0, "tool_accuracy_pct": 100.0, "vram_after_mb": [1200]},
                {"tps": 8.0, "ttft_ms": 600.0, "tool_accuracy_pct": 95.0, "vram_after_mb": [1300]},
            ],
            "aggregate": {
                "peak_context_tokens_estimate": 4096,
                "cumulative_context_tokens_estimate": 6144,
            },
        }
        metrics = extract_metrics(data)
        self.assertTrue(metrics["throughput_available"])
        self.assertEqual(metrics["prompt_tps_bench"], 20.1)
        self.assertEqual(metrics["gen_tps_bench"], 11.4)
        self.assertEqual(metrics["tps_t1"], 10.0)
        self.assertEqual(metrics["tps_tn"], 8.0)
        self.assertEqual(metrics["vram_peak"], 1300)
        self.assertEqual(metrics["peak_context_tokens"], 4096)
        self.assertEqual(metrics["total_context_tokens"], 6144)

    def test_session_comparison_dashboard_separates_context_and_provider_tokens(self) -> None:
        data = {
            "model_id": "demo-model",
            "meta": {
                "benchmark_id": "demo_session",
                "benchmark_title": "Demo Session",
                "timestamp": "2026-04-12T07:11:58",
                "total_turns": 2,
            },
            "aggregate": {
                "average_score": 0.95,
                "pass_rate": 1.0,
                "pass_count": 2,
                "session_elapsed_s": 12.3,
                "provider_usage_total_tokens": 600000,
                "format_obedience_rate": 0.98,
                "literal_semantic_gap_turn_count": 1,
                "unsupported_claim_count": 0,
                "recovery_try_count": 0,
                "peak_context_tokens_estimate": 120000,
                "cumulative_context_tokens_estimate": 640000,
                "final_hardware": {"vram_peak_mb": 24576},
            },
            "turns": [
                {"turn": 1, "turn_id": "t01", "scores": {"turn_score": 1.0}, "metrics": {"context_window": 131072, "provider_usage_cumulative_total": 200000, "ttft_ms": 300, "hardware": {"vram_peak_mb": 20000}}},
                {"turn": 2, "turn_id": "t02", "scores": {"turn_score": 0.9}, "metrics": {"context_window": 131072, "provider_usage_cumulative_total": 600000, "ttft_ms": 500, "hardware": {"vram_peak_mb": 24576}}},
            ],
        }
        html = build_session_comparison_html({"f16": data})
        self.assertIn("Peak Ctx", html)
        self.assertIn("Total Ctx", html)
        self.assertIn("Provider tokens", html)
        self.assertIn("120,000/131,072", html)
        self.assertIn("640,000", html)
        self.assertIn("600,000", html)
        self.assertIn("not the same thing as single-turn active context", html)


if __name__ == "__main__":
    unittest.main()
