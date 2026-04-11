from __future__ import annotations

import unittest

from gnuckle.benchmark import parse_llama_bench_output
from gnuckle.visualize import extract_metrics


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


if __name__ == "__main__":
    unittest.main()
