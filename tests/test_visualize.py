from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gnuckle.benchmark import (
    NON_SERVER_ARG_ALLOWLIST,
    build_llama_args,
    build_llama_args_non_server,
    parse_llamacpp_server_metrics,
    parse_llama_bench_output,
    parse_llama_perplexity_output,
)
from gnuckle.visualize import (
    agentic_results_have_suite_data,
    build_session_comparison_html,
    extract_metrics,
    run_visualize,
)


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

    def test_parse_llamacpp_server_metrics_extracts_eval_and_update_slots(self) -> None:
        raw = """
slot launch_slot_: id 3 | task 0 | new prompt, n_ctx_slot = 131072, n_keep = 0, task.n_tokens = 233
slot update_slots: id 3 | task 0 | prompt processing progress, n_tokens = 229, batch.n_tokens = 229, progress = 0.982833
prompt eval time =     296.63 ms /   233 tokens (    1.27 ms per token,   785.48 tokens per second)
eval time =    16135.97 ms /  1056 tokens (   15.28 ms per token,    65.44 tokens per second)
total time =   16432.61 ms /  1289 tokens
"""
        parsed = parse_llamacpp_server_metrics(raw)
        self.assertTrue(parsed["available"])
        self.assertEqual(parsed["slot_n_ctx"], 131072)
        self.assertEqual(parsed["slot_prompt_tokens"], 233)
        self.assertEqual(parsed["update_slots_n_tokens"], 229)
        self.assertEqual(parsed["update_slots_batch_tokens"], 229)
        self.assertEqual(parsed["update_slots_progress"], 0.982833)
        self.assertEqual(parsed["prompt_eval_ms"], 296.63)
        self.assertEqual(parsed["prompt_eval_tokens"], 233)
        self.assertEqual(parsed["prompt_eval_tokens_per_second"], 785.48)
        self.assertEqual(parsed["eval_ms"], 16135.97)
        self.assertEqual(parsed["eval_tokens"], 1056)
        self.assertEqual(parsed["eval_tokens_per_second"], 65.44)
        self.assertEqual(parsed["total_ms"], 16432.61)
        self.assertEqual(parsed["total_tokens"], 1289)

    def test_extract_metrics_reads_dict_keyed_quality_benchmarks(self) -> None:
        data = {
            "meta": {
                "throughput_benchmark": {
                    "available": True,
                    "prompt_tokens_per_second": 20.1,
                    "generation_tokens_per_second": 11.4,
                },
                "llamacpp_server_metrics": {
                    "prompt_eval_tokens_per_second": 785.48,
                    "eval_tokens_per_second": 65.44,
                    "prompt_eval_ms": 296.63,
                    "eval_ms": 16135.97,
                    "total_ms": 16432.61,
                    "total_tokens": 1289,
                    "slot_prompt_tokens": 233,
                    "update_slots_progress": 0.982833,
                },
                "quality_benchmarks": {
                    "wikitext2_ppl": {
                        "available": True,
                        "perplexity": 6.123,
                        "delta_vs_baseline": 0.01,
                    },
                    "kld_vs_f16": {
                        "available": True,
                        "mean_kld": 0.0082,
                        "p99_kld": 0.041,
                        "top1_agreement_pct": 97.8,
                        "top5_agreement_pct": 99.6,
                        "delta_vs_baseline": 0.0082,
                    },
                    "hellaswag": {
                        "available": True,
                        "value": 62.4,
                        "delta_vs_baseline": -0.0064,
                    },
                    "quality_tier": "excellent",
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
        self.assertEqual(metrics["wikitext2_delta_vs_baseline"], 0.01)
        self.assertTrue(metrics["quality_available"])
        self.assertEqual(metrics["kld_mean"], 0.0082)
        self.assertEqual(metrics["hellaswag_accuracy"], 62.4)
        self.assertEqual(metrics["quality_tier"], "excellent")
        self.assertEqual(metrics["tps_t1"], 10.0)
        self.assertEqual(metrics["tps_tn"], 8.0)
        self.assertEqual(metrics["vram_peak"], 1300)
        self.assertEqual(metrics["peak_context_tokens"], 4096)
        self.assertEqual(metrics["total_context_tokens"], 6144)
        self.assertEqual(metrics["llamacpp_prompt_eval_tps"], 785.48)
        self.assertEqual(metrics["llamacpp_eval_tps"], 65.44)
        self.assertEqual(metrics["llamacpp_slot_prompt_tokens"], 233)
        self.assertEqual(metrics["llamacpp_update_slots_progress"], 0.982833)

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
                    "wikitext2_ppl": {"available": True, "perplexity": 6.789, "delta_vs_baseline": 0.01},
                    "kld_vs_f16": {"available": True, "mean_kld": 0.0082},
                    "hellaswag": {"available": True, "value": 62.4, "delta_vs_baseline": -0.0064},
                    "quality_tier": "excellent",
                },
                "llamacpp_server_metrics": {
                    "prompt_eval_tokens_per_second": 785.48,
                    "eval_tokens_per_second": 65.44,
                    "slot_prompt_tokens": 233,
                    "update_slots_progress": 0.982833,
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
        self.assertIn("excellent", html.lower())
        self.assertIn("6.789", html)
        self.assertIn("120,000/131,072", html)
        self.assertIn("640,000", html)
        self.assertIn("600,000", html)
        self.assertIn("not the same thing as single-turn active context", html)
        self.assertIn("Prompt eval", html)
        self.assertIn("785.5", html)
        self.assertIn("65.4", html)
        self.assertIn("233", html)
        self.assertIn("98.3%", html)

    def test_agentic_results_have_suite_data_detects_empty_suite(self) -> None:
        self.assertFalse(agentic_results_have_suite_data({"f16": {"workflow_results": [], "diagnostics": []}}))
        self.assertTrue(agentic_results_have_suite_data({"f16": {"workflow_results": [{"workflow_id": "wf"}], "diagnostics": []}}))

    def test_run_visualize_falls_back_to_session_when_agentic_suite_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agentic_f16.json").write_text(
                json.dumps(
                    {
                        "benchmark_mode": "agentic",
                        "cache_label": "f16",
                        "model_id": "demo.gguf",
                        "workflow_suite": "benchmark",
                        "generated_at": "2026-04-12T14:38:09",
                        "diagnostics": [],
                        "workflow_results": [],
                        "summary": {"type": "Type 0", "grade": "F", "core_score": 0.0, "profile_score": None, "composite_score": 0.0, "usability_flags": []},
                        "meta": {"quality_benchmarks": {}},
                    }
                ),
                encoding="utf-8",
            )
            (root / "session_persistent_tool_stress_f16.json").write_text(
                json.dumps(
                    {
                        "meta": {
                            "type": "session",
                            "benchmark_id": "persistent_tool_stress",
                            "benchmark_title": "Persistent Tool Stress Test",
                            "timestamp": "2026-04-12T14:38:09",
                            "total_turns": 1,
                            "quality_benchmarks": {},
                        },
                        "aggregate": {
                            "average_score": 0.95,
                            "pass_rate": 1.0,
                            "pass_count": 1,
                            "session_elapsed_s": 12.3,
                            "provider_usage_total_tokens": 600,
                            "format_obedience_rate": 1.0,
                            "literal_semantic_gap_turn_count": 0,
                            "unsupported_claim_count": 0,
                            "recovery_try_count": 0,
                            "peak_context_tokens_estimate": 120,
                            "cumulative_context_tokens_estimate": 220,
                            "final_hardware": {"vram_peak_mb": 2048},
                        },
                        "turns": [{"turn": 1, "turn_id": "t01", "scores": {"turn_score": 0.95}, "metrics": {"context_window": 4096, "provider_usage_cumulative_total": 600, "ttft_ms": 300, "hardware": {"vram_peak_mb": 2048}}}],
                        "model_id": "demo.gguf",
                    }
                ),
                encoding="utf-8",
            )
            out_file = run_visualize(str(root))
            self.assertEqual(out_file.name, "session_benchmark_dashboard.html")
            html = out_file.read_text(encoding="utf-8")
            self.assertIn("Persistent Tool Stress Test", html)
            self.assertIn("Peak Ctx", html)

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
