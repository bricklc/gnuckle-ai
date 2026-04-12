from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gnuckle.cli import cmd_bench_list
from gnuckle.bench_pack.installer import RecoverableInstallError, _safe_extract_zip, install_pack, remove_pack, verify_installed_packs
from gnuckle.bench_pack.manifest import load_manifest_file
from gnuckle.bench_pack.parser import parse_metrics
from gnuckle.bench_pack.registry import save_local_index, sync_registry
from gnuckle.bench_pack.schema import validate_manifest_dict
from gnuckle.benchmark import annotate_quality_benchmarks, resolve_quality_bench_ids
from gnuckle.bench_pack.trust import (
    INSTALL_DISCLAIMER,
    append_audit_log,
    audit_log_path,
    benchmarks_dir,
    datasets_dir,
    ensure_home_layout,
    lock_path,
    sanitized_subprocess_env,
)
from gnuckle.visualize import extract_metrics


def base_manifest_dict() -> dict:
    return {
        "schema": 1,
        "id": "demo_pack",
        "name": "Demo Pack",
        "version": "0.5.0",
        "gnuckle_min": "0.5.0",
        "author": {"name": "gnuckle-core", "contact": "https://example.com"},
        "homepage": "https://example.com/demo-pack",
        "downloads": 0,
        "description": "demo",
        "license": "MIT",
        "kind": "quality",
        "tags": ["demo"],
        "binary": "llama-perplexity",
        "stages": [
            {
                "id": "single",
                "args_template": ["-m", "{model_path}", "-f", "{dataset_path}"],
            }
        ],
        "parse": {
            "value": {"pattern": r"Value:\s+([0-9]+\.[0-9]+)", "unit": "float"}
        },
        "timeout_seconds": 60,
    }


class BenchPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.env = patch.dict(os.environ, {"GNUCKLE_HOME": self.tmpdir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        ensure_home_layout()

    def _write_manifest(self, data: dict, name: str = "manifest.yaml") -> Path:
        path = Path(self.tmpdir.name) / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_manifest_validation_rejects_security_violations(self) -> None:
        base = base_manifest_dict()
        cases = [
            ("binary allowlist", {"binary": "python"}),
            ("unsafe args", {"stages": [{"id": "single", "args_template": ["bad arg"]}]}),
            ("unknown placeholder", {"stages": [{"id": "single", "args_template": ["{evil}"]}]}),
            (
                "non https url",
                {"dataset": {"id": "demo", "url": "http://example.com/file.zip", "sha256": "a" * 64, "size_bytes_max": 10}},
            ),
            (
                "missing sha256",
                {"dataset": {"id": "demo", "url": "https://huggingface.co/file.zip", "size_bytes_max": 10}},
            ),
            ("nested quantifier regex", {"parse": {"value": {"pattern": r"(a+)+b"}}}),
            ("unknown field", {"mystery": True}),
        ]
        for label, patch_data in cases:
            with self.subTest(label=label):
                candidate = dict(base)
                candidate.update(patch_data)
                with self.assertRaises(ValueError):
                    validate_manifest_dict(candidate)

    def test_install_flow_shows_disclaimer_and_requires_confirmation(self) -> None:
        manifest_path = self._write_manifest(base_manifest_dict())
        prompts = []

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return "n"

        result = install_pack(str(manifest_path), input_func=fake_input)
        self.assertFalse(result["installed"])
        self.assertTrue(result["cancelled"])
        self.assertIn("Proceed with install?", prompts[0])
        self.assertIn("Gnuckle is not a sandbox.", prompts[0])
        self.assertIn(INSTALL_DISCLAIMER.splitlines()[0], prompts[0])

    def test_audit_log_records_install_update_remove_and_run(self) -> None:
        manifest_path = self._write_manifest(base_manifest_dict())
        install_pack(str(manifest_path), assume_yes=True)
        append_audit_log("registry_update", details={"count": 0})
        append_audit_log("run", pack_id="demo_pack", manifest_sha256="abc", details={"cache_label": "f16"})
        remove_pack("demo_pack")
        entries = [json.loads(line) for line in audit_log_path().read_text(encoding="utf-8").splitlines() if line.strip()]
        actions = [entry["action"] for entry in entries]
        self.assertIn("install", actions)
        self.assertIn("registry_update", actions)
        self.assertIn("run", actions)
        self.assertIn("remove", actions)
        self.assertTrue(all("timestamp" in entry for entry in entries))

    def test_sanitized_subprocess_env_strips_tokens(self) -> None:
        env = sanitized_subprocess_env(
            {
                "PATH": "C:/bin",
                "HOME": "C:/home",
                "OPENAI_API_KEY": "secret",
                "GITHUB_TOKEN": "secret",
                "HF_TOKEN": "secret",
                "PASSWORD": "secret",
                "CUDA_VISIBLE_DEVICES": "0",
            }
        )
        self.assertEqual(env["PATH"], "C:/bin")
        self.assertEqual(env["HOME"], "C:/home")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("HF_TOKEN", env)
        self.assertNotIn("PASSWORD", env)

    def test_sha256_mismatch_deletes_download_and_raises_recoverable_error(self) -> None:
        data = base_manifest_dict()
        data["dataset"] = {
            "id": "demo",
            "url": "https://huggingface.co/demo.zip",
            "sha256": "b" * 64,
            "size_bytes_max": 1024,
            "archive": "zip",
            "extract": "data.txt",
        }
        manifest_path = self._write_manifest(data)
        with patch("gnuckle.bench_pack.installer._download_bytes", return_value=b"wrong"):
            with self.assertRaises(RecoverableInstallError):
                install_pack(str(manifest_path), assume_yes=True)
        self.assertFalse((datasets_dir() / "demo").exists())

    def test_zip_extraction_rejects_traversal_symlinks_and_oversized_entries(self) -> None:
        cases = []

        traversal_zip = Path(self.tmpdir.name) / "traversal.zip"
        with zipfile.ZipFile(traversal_zip, "w") as zf:
            zf.writestr("../escape.txt", "nope")
        cases.append(("traversal", traversal_zip, 1024))

        symlink_zip = Path(self.tmpdir.name) / "symlink.zip"
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(symlink_zip, "w") as zf:
            zf.writestr(info, "target")
        cases.append(("symlink", symlink_zip, 1024))

        oversize_zip = Path(self.tmpdir.name) / "oversize.zip"
        with zipfile.ZipFile(oversize_zip, "w") as zf:
            zf.writestr("big.bin", b"x" * 32)
        cases.append(("oversize", oversize_zip, 8))

        for label, archive, limit in cases:
            with self.subTest(label=label):
                with self.assertRaises(RecoverableInstallError):
                    _safe_extract_zip(archive, Path(self.tmpdir.name) / f"out_{label}", size_limit=limit)

    def test_parser_truncates_output_before_regex(self) -> None:
        parser = {"value": SimpleNamespace(pattern=r"Value:\s+([0-9]+\.[0-9]+)")}
        big_text = ("A" * 1_000_001) + "Value: 9.9"
        result = parse_metrics(parser, big_text)
        self.assertTrue(result["capture_truncated"])
        self.assertNotIn("value", result)

    def test_benchmarks_lock_detects_manifest_tamper(self) -> None:
        manifest_path = self._write_manifest(base_manifest_dict())
        install_pack(str(manifest_path), assume_yes=True)
        installed_manifest = benchmarks_dir() / "demo_pack" / "manifest.yaml"
        os.chmod(installed_manifest, stat.S_IWRITE | stat.S_IREAD)
        data = json.loads(installed_manifest.read_text(encoding="utf-8"))
        data["description"] = "tampered"
        installed_manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        verified = verify_installed_packs()
        self.assertEqual(len(verified["tampered"]), 1)
        self.assertEqual(verified["tampered"][0]["id"], "demo_pack")

    def test_shell_false_is_enforced_in_bench_pack_sources(self) -> None:
        bench_pack_dir = Path("gnuckle") / "bench_pack"
        for path in bench_pack_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", source, msg=f"unsafe shell=True in {path}")
        runner_source = (bench_pack_dir / "runner.py").read_text(encoding="utf-8")
        self.assertIn("shell=False", runner_source)

    def test_bench_list_handles_empty_registry_cleanly(self) -> None:
        captured = io.StringIO()
        with redirect_stdout(captured):
            cmd_bench_list(SimpleNamespace())
        output = json.loads(captured.getvalue())
        self.assertEqual(output["installed"], [])
        self.assertEqual(output["available"], [])

    def test_registry_update_and_local_index_roundtrip(self) -> None:
        payload = json.dumps({
            "benchmarks": [{
                "id": "demo_pack",
                "name": "Demo Pack",
                "version": "0.5.0",
                "author": "community-author",
                "downloads": 12,
                "homepage": "https://example.com/demo-pack",
                "description": "demo"
            }]
        }).encode("utf-8")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return payload

        with patch("gnuckle.bench_pack.registry.urlopen", return_value=FakeResponse()):
            entries = sync_registry("https://example.com/index.json")
        self.assertEqual(entries[0]["id"], "demo_pack")
        self.assertEqual(entries[0]["name"], "Demo Pack")
        self.assertEqual(entries[0]["author"], "community-author")
        self.assertEqual(entries[0]["downloads"], 12)
        self.assertEqual(entries[0]["homepage"], "https://example.com/demo-pack")
        self.assertTrue(lock_path().exists())

    def test_load_manifest_file_rejects_duplicate_keys(self) -> None:
        path = Path(self.tmpdir.name) / "dup.yaml"
        path.write_text('{"schema":1,"schema":1}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_manifest_file(path)

    def test_bundled_registry_has_standard_quality_seed_manifests(self) -> None:
        index_path = Path("benchmark-index") / "index.json"
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        entries = payload["benchmarks"]
        self.assertEqual([entry["id"] for entry in entries], ["wikitext2_ppl", "kld_vs_f16", "hellaswag"])
        for entry in entries:
            self.assertEqual(entry["author"], "gnuckle-ai")
            self.assertEqual(entry["downloads"], 0)
            self.assertEqual(entry["homepage"], "https://github.com/bricklc/gnuckle-ai")
            manifest_path = Path("benchmark-index") / entry["path"]
            manifest, _, _ = load_manifest_file(manifest_path)
            self.assertEqual(manifest.id, entry["id"])
            self.assertEqual(manifest.author.name, "gnuckle-ai")
            self.assertEqual(manifest.binary, "llama-perplexity")

    def test_install_wikitext2_from_registry_entry_succeeds_on_clean_home(self) -> None:
        dataset_bytes = io.BytesIO()
        with zipfile.ZipFile(dataset_bytes, "w") as zf:
            zf.writestr("wikitext-2-raw/wiki.test.raw", "demo")
        archive_bytes = dataset_bytes.getvalue()
        dataset_sha = __import__("hashlib").sha256(archive_bytes).hexdigest()

        registry_root = Path(self.tmpdir.name) / "registry_src"
        manifest_dir = registry_root / "benchmarks" / "core" / "wikitext2_ppl"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = base_manifest_dict()
        manifest["id"] = "wikitext2_ppl"
        manifest["name"] = "WikiText-2 Perplexity"
        manifest["version"] = "1.0.0"
        manifest["gnuckle_min"] = "0.6.0"
        manifest["homepage"] = "https://github.com/bricklc/gnuckle-ai"
        manifest["downloads"] = 0
        manifest["dataset"] = {
            "id": "wikitext-2-raw-v1",
            "url": "https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip",
            "sha256": dataset_sha,
            "size_bytes_max": 4096,
            "archive": "zip",
            "extract": "wikitext-2-raw/wiki.test.raw",
        }
        manifest["parse"] = {"perplexity": {"pattern": r"\bPPL\s*=\s*([0-9]+\.[0-9]+)"}}
        manifest_path = manifest_dir / "manifest.yaml"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        index_path = registry_root / "index.json"
        index_path.write_text(
            json.dumps({"benchmarks": [{
                "id": "wikitext2_ppl",
                "name": "WikiText-2 Perplexity",
                "version": "1.0.0",
                "author": "gnuckle-ai",
                "downloads": 0,
                "homepage": "https://github.com/bricklc/gnuckle-ai",
                "path": "benchmarks/core/wikitext2_ppl/manifest.yaml"
            }]}, indent=2),
            encoding="utf-8",
        )

        from gnuckle.bench_pack.installer import _download_bytes as real_download

        def fake_download(url: str, *, size_limit: int) -> bytes:
            if url.startswith("https://huggingface.co/"):
                return archive_bytes
            return real_download(url, size_limit=size_limit)

        sync_registry(index_path.resolve().as_uri())
        with patch("gnuckle.bench_pack.installer._download_bytes", side_effect=fake_download):
            result = install_pack("wikitext2_ppl", assume_yes=True)
        self.assertTrue(result["installed"])
        self.assertTrue((benchmarks_dir() / "wikitext2_ppl" / "manifest.yaml").exists())
        self.assertTrue((datasets_dir() / "wikitext-2-raw-v1" / "wikitext-2-raw" / "wiki.test.raw").exists())

    def test_pack_runtime_wikitext2_output_feeds_visualizer_metrics(self) -> None:
        manifest = base_manifest_dict()
        manifest["id"] = "wikitext2_ppl"
        manifest["name"] = "WikiText-2 Perplexity"
        manifest["version"] = "1.0.0"
        manifest["gnuckle_min"] = "0.6.0"
        manifest["homepage"] = "https://github.com/bricklc/gnuckle-ai"
        manifest["downloads"] = 0
        manifest["dataset"] = None
        manifest["parse"] = {"perplexity": {"pattern": r"\bPPL\s*=\s*([0-9]+\.[0-9]+)"}}
        manifest_path = self._write_manifest(manifest, "wikitext2_manifest.yaml")
        install_pack(str(manifest_path), assume_yes=True)

        from gnuckle.bench_pack.runner import run_quality_packs

        fake_completed = SimpleNamespace(returncode=0, stdout="final PPL = 6.4321", stderr="")
        model_path = Path(self.tmpdir.name) / "model.gguf"
        model_path.write_text("gguf", encoding="utf-8")

        with patch("gnuckle.bench_pack.runner._resolve_binary", return_value=Path("llama-perplexity")), patch(
            "gnuckle.bench_pack.runner.subprocess.run", return_value=fake_completed
        ):
            results = run_quality_packs(
                ["wikitext2_ppl"],
                server_path=None,
                model_path=model_path,
                cache_label="f16",
                cache_k="f16",
                cache_v="f16",
            )
        metrics = extract_metrics({"meta": {"quality_benchmarks": results}, "turns": [{"tps": 1.0}], "aggregate": {}})
        self.assertEqual(results["wikitext2_ppl"]["perplexity"], 6.4321)
        self.assertEqual(metrics["wikitext2_perplexity"], 6.4321)

    def test_pack_runtime_kld_uses_f16_baseline_then_compares_other_cache(self) -> None:
        manifest = base_manifest_dict()
        manifest["id"] = "kld_vs_f16"
        manifest["name"] = "KLD vs f16"
        manifest["version"] = "1.0.0"
        manifest["gnuckle_min"] = "0.7.0"
        manifest["homepage"] = "https://github.com/bricklc/gnuckle-ai"
        manifest["downloads"] = 0
        manifest["requires_baseline"] = "f16"
        manifest["dataset"] = None
        manifest["stages"] = [
            {"id": "save_baseline", "when": 'cache_label == "f16"', "args_template": ["--kl-divergence-base", "{logits_out}"]},
            {"id": "compare", "when": 'cache_label != "f16"', "args_template": ["--kl-divergence", "--kl-divergence-base", "{logits_in}"]},
        ]
        manifest["parse"] = {
            "mean_kld": {"pattern": r"Mean KLD:\s+([0-9]+\.[0-9]+)"},
            "p99_kld": {"pattern": r"KLD 99%:\s+([0-9]+\.[0-9]+)"},
            "top1_agreement_pct": {"pattern": r"Top-1 match:\s+([0-9]+\.[0-9]+)%"},
            "top5_agreement_pct": {"pattern": r"Top-5 match:\s+([0-9]+\.[0-9]+)%"},
        }
        manifest["report"] = {"column_label": "KLD vs f16", "primary_metric": "mean_kld", "delta_vs_baseline": "none", "sort": "ascending"}
        manifest_path = self._write_manifest(manifest, "kld_manifest.yaml")
        install_pack(str(manifest_path), assume_yes=True)

        from gnuckle.bench_pack.runner import run_quality_packs

        model_path = Path(self.tmpdir.name) / "model.gguf"
        model_path.write_text("gguf", encoding="utf-8")

        with patch("gnuckle.bench_pack.runner._resolve_binary", return_value=Path("llama-perplexity")), patch(
            "gnuckle.bench_pack.runner.subprocess.run",
            side_effect=[
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="Mean KLD: 0.0082\nKLD 99%: 0.041\nTop-1 match: 97.8%\nTop-5 match: 99.6%", stderr=""),
            ],
        ):
            baseline = run_quality_packs(
                ["kld_vs_f16"],
                server_path=None,
                model_path=model_path,
                cache_label="f16",
                cache_k="f16",
                cache_v="f16",
            )
            compared = run_quality_packs(
                ["kld_vs_f16"],
                server_path=None,
                model_path=model_path,
                cache_label="q8_0",
                cache_k="q8_0",
                cache_v="q8_0",
            )

        annotated_baseline = annotate_quality_benchmarks(baseline, None)
        annotated_compared = annotate_quality_benchmarks(compared, annotated_baseline)
        self.assertEqual(annotated_baseline["kld_vs_f16"]["mean_kld"], 0.0)
        self.assertEqual(annotated_baseline["quality_tier"], "lossless")
        self.assertEqual(annotated_compared["kld_vs_f16"]["mean_kld"], 0.0082)
        self.assertEqual(annotated_compared["kld_vs_f16"]["delta_vs_baseline"], 0.0082)
        self.assertEqual(annotated_compared["quality_tier"], "excellent")

    def test_manifest_and_registry_metadata_match_ckan_shape(self) -> None:
        manifest = validate_manifest_dict(base_manifest_dict())
        self.assertEqual(manifest.name, "Demo Pack")
        self.assertEqual(manifest.version, "0.5.0")
        self.assertEqual(manifest.author.name, "gnuckle-core")
        self.assertEqual(manifest.downloads, 0)
        self.assertEqual(manifest.homepage, "https://example.com/demo-pack")

    def test_run_full_benchmark_passes_pack_quality_results_into_legacy_output(self) -> None:
        from gnuckle.benchmark import run_full_benchmark

        manifest = base_manifest_dict()
        manifest["id"] = "wikitext2_ppl"
        manifest["name"] = "WikiText-2 Perplexity"
        manifest["version"] = "1.0.0"
        manifest["gnuckle_min"] = "0.6.0"
        manifest["homepage"] = "https://github.com/bricklc/gnuckle-ai"
        manifest["downloads"] = 0
        manifest["dataset"] = None
        manifest["parse"] = {"perplexity": {"pattern": r"\bPPL\s*=\s*([0-9]+\.[0-9]+)"}}
        manifest_path = self._write_manifest(manifest, "run_manifest.yaml")
        install_pack(str(manifest_path), assume_yes=True)

        model_path = Path(self.tmpdir.name) / "model.gguf"
        server_path = Path(self.tmpdir.name) / "llama-server.exe"
        model_path.write_text("gguf", encoding="utf-8")
        server_path.write_text("exe", encoding="utf-8")
        output_dir = Path(self.tmpdir.name) / "out"
        captured = {}

        def fake_run_benchmark_pass(cache_label, model_path_arg, output_dir_arg, num_turns, port, **kwargs):
            captured["quality_benchmarks"] = kwargs["quality_benchmarks"]
            path = output_dir_arg / f"legacy_{cache_label}.json"
            captured.setdefault("paths", {})[cache_label] = path
            path.write_text(
                json.dumps(
                    {
                        "meta": {"quality_benchmarks": kwargs["quality_benchmarks"]},
                        "turns": [{"tps": 1.0, "ttft_ms": 1.0, "vram_after_mb": [1]}],
                        "aggregate": {},
                    }
                ),
                encoding="utf-8",
            )
            return path

        with patch("gnuckle.benchmark.start_server", return_value=SimpleNamespace(pid=1)), patch(
            "gnuckle.benchmark.kill_server", return_value=None
        ), patch("gnuckle.benchmark.wait_for_server", return_value=True), patch(
            "gnuckle.benchmark.warmup_server", return_value=True
        ), patch(
            "gnuckle.benchmark.collect_llama_bench_metrics", return_value={"available": False, "error": "missing"}
        ), patch(
            "gnuckle.benchmark._print_run_banner", return_value=None
        ), patch(
            "gnuckle.benchmark.run_benchmark_pass", side_effect=fake_run_benchmark_pass
        ), patch(
            "gnuckle.benchmark.prompt_open_visualizer", return_value=None
        ), patch(
            "gnuckle.bench_pack.runner._resolve_binary", return_value=Path("llama-perplexity")
        ), patch(
            "gnuckle.bench_pack.runner.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="PPL = 6.1", stderr="")
        ):
            run_full_benchmark(
                benchmark_mode="legacy",
                model_path=model_path,
                server_path=server_path,
                output_dir=output_dir,
                num_turns=1,
                port=8080,
                quality_bench_ids=["wikitext2_ppl"],
            )

        self.assertEqual(captured["quality_benchmarks"]["wikitext2_ppl"]["perplexity"], 6.1)
        metrics = extract_metrics(json.loads(captured["paths"]["f16"].read_text(encoding="utf-8")))
        self.assertEqual(metrics["wikitext2_perplexity"], 6.1)

    def test_standard_quality_shortcut_resolves_to_ppl_and_kld(self) -> None:
        installed = ["wikitext2_ppl", "kld_vs_f16", "hellaswag"]
        self.assertEqual(resolve_quality_bench_ids(None, installed), ["wikitext2_ppl", "kld_vs_f16"])
        self.assertEqual(resolve_quality_bench_ids(["standard"], installed), ["wikitext2_ppl", "kld_vs_f16"])
        self.assertEqual(resolve_quality_bench_ids(["full"], installed), ["wikitext2_ppl", "kld_vs_f16", "hellaswag"])
        self.assertEqual(resolve_quality_bench_ids(["all"], installed), installed)

    def test_hardcoded_collect_llama_perplexity_metrics_is_removed(self) -> None:
        source = Path("gnuckle") / "benchmark.py"
        text = source.read_text(encoding="utf-8")
        self.assertNotIn("def collect_llama_perplexity_metrics(", text)
