from __future__ import annotations

import unittest

from gnuckle.benchmark import (
    NON_SERVER_ARG_ALLOWLIST,
    build_llama_args,
    build_llama_args_non_server,
    parse_llama_bench_output,
    parse_llama_perplexity_output,
)
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

    def test_extract_metrics_reads_dict_keyed_quality_benchmarks(self) -> None:
        data = {
            "meta": {
                "throughput_benchmark": {
                    "available": True,
                    "prompt_tokens_per_second": 20.1,
                    "generation_tokens_per_second": 11.4,
                },
                "quality_benchmarks": {
                    "wikitext2_ppl": {
                        "available": True,
                        "perplexity": 6.123,
                    },
                },
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
        self.assertEqual(metrics["wikitext2_perplexity"], 6.123)
        self.assertTrue(metrics["quality_available"])
        self.assertEqual(metrics["tps_t1"], 10.0)
        self.assertEqual(metrics["tps_tn"], 8.0)
        self.assertEqual(metrics["vram_peak"], 1300)
        self.assertEqual(metrics["peak_context_tokens"], 4096)
        self.assertEqual(metrics["total_context_tokens"], 6144)

    def test_extract_metrics_back_compat_reads_legacy_quality_benchmark(self) -> None:
        """Old JSONs with the singular `quality_benchmark` key keep rendering."""
        data = {
            "meta": {
                "throughput_benchmark": {},
                "quality_benchmark": {"available": True, "perplexity": 7.5},
            },
            "turns": [{"tps": 5.0, "ttft_ms": 200.0, "tool_accuracy_pct": 100.0, "vram_after_mb": [1000]}],
            "aggregate": {},
        }
        metrics = extract_metrics(data)
        self.assertEqual(metrics["wikitext2_perplexity"], 7.5)
        self.assertTrue(metrics["quality_available"])

    def test_extract_metrics_handles_missing_quality_benchmarks(self) -> None:
        """--skip-quality runs produce JSONs with no quality data; don't crash."""
        data = {
            "meta": {"throughput_benchmark": {}},
            "turns": [{"tps": 5.0, "ttft_ms": 200.0, "tool_accuracy_pct": 100.0, "vram_after_mb": [1000]}],
            "aggregate": {},
        }
        metrics = extract_metrics(data)
        self.assertIsNone(metrics["wikitext2_perplexity"])
        self.assertFalse(metrics["quality_available"])

    def test_session_comparison_dashboard_separates_context_and_provider_tokens(self) -> None:
        data = {
            "model_id": "demo-model",
            "meta": {
                "benchmark_id": "demo_session",
                "benchmark_title": "Demo Session",
                "timestamp": "2026-04-12T07:11:58",
                "total_turns": 2,
                "quality_benchmarks": {
                    "wikitext2_ppl": {"available": True, "perplexity": 6.789},
                },
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
        self.assertIn("PPL WT2", html)
        self.assertIn("6.789", html)
        self.assertIn("120,000/131,072", html)
        self.assertIn("640,000", html)
        self.assertIn("600,000", html)
        self.assertIn("not the same thing as single-turn active context", html)

    def test_parse_llama_perplexity_output_extracts_final_ppl(self) -> None:
        raw = """
llama_perf_context_print:        load time =     321.42 ms
some other line
Final estimate: PPL = 6.4321 +/- 0.0123
"""
        parsed = parse_llama_perplexity_output(raw)
        self.assertEqual(parsed["perplexity"], 6.4321)

    def test_build_llama_args_non_server_filters_sampler_flags(self) -> None:
        """Sampler-only flags from server_args must not leak into llama-bench/perplexity."""
        preset_server_args = {
            "temp": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "repeat_penalty": 1.1,
        }
        filtered = build_llama_args_non_server(preset_server_args)
        self.assertEqual(filtered, [], "sampler flags must be dropped for non-server binaries")

    def test_build_llama_args_non_server_preserves_universal_flags(self) -> None:
        """Known-universal args (flash-attn, threads) should pass through."""
        preset_server_args = {
            "flash_attn": True,
            "threads": 8,
            "temp": 0.6,  # must be dropped
        }
        filtered = build_llama_args_non_server(preset_server_args)
        self.assertIn("--flash-attn", filtered)
        self.assertIn("--threads", filtered)
        self.assertNotIn("--temp", filtered)

    def test_build_llama_args_unfiltered_still_includes_everything(self) -> None:
        """The server path (build_llama_args) must NOT filter — server needs all flags."""
        args = build_llama_args({"temp": 0.6, "host": "0.0.0.0"})
        self.assertIn("--temp", args)
        self.assertIn("--host", args)

    def test_non_server_allowlist_is_a_frozenset(self) -> None:
        """Sanity check that the allowlist cannot be mutated at runtime."""
        self.assertIsInstance(NON_SERVER_ARG_ALLOWLIST, frozenset)


if __name__ == "__main__":
    unittest.main()
