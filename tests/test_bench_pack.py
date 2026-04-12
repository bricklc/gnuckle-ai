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


def base_manifest_dict() -> dict:
    return {
        "schema": 1,
        "id": "demo_pack",
        "version": "0.5.0",
        "gnuckle_min": "0.5.0",
        "author": {"name": "gnuckle-core", "contact": "https://example.com"},
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
        payload = json.dumps({"benchmarks": [{"id": "demo_pack", "description": "demo"}]}).encode("utf-8")

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
        self.assertTrue(lock_path().exists())

    def test_load_manifest_file_rejects_duplicate_keys(self) -> None:
        path = Path(self.tmpdir.name) / "dup.yaml"
        path.write_text('{"schema":1,"schema":1}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_manifest_file(path)
