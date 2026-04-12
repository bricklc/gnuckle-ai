"""Manifest-backed benchmark execution."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from gnuckle.bench_pack.manifest import verify_installed_manifest
from gnuckle.bench_pack.parser import parse_metrics
from gnuckle.bench_pack.trust import append_audit_log, datasets_dir, sanitized_subprocess_env


def _resolve_binary(binary_name: str, server_path: Path | None) -> Path | None:
    from gnuckle.benchmark import find_bench, find_perplexity

    if binary_name in {"llama-bench", "llama-bench.exe"} and server_path:
        return find_bench(server_path)
    if binary_name in {"llama-perplexity", "llama-perplexity.exe"} and server_path:
        return find_perplexity(server_path)
    candidate = Path(binary_name)
    if candidate.is_file():
        return candidate
    return None


def _stage_matches(when: str | None, cache_label: str) -> bool:
    if not when:
        return True
    when = when.strip()
    if when.startswith('cache_label == "'):
        expected = when[len('cache_label == "'):-1]
        return cache_label == expected
    if when.startswith('cache_label != "'):
        expected = when[len('cache_label != "'):-1]
        return cache_label != expected
    raise ValueError(f"unsupported stage predicate: {when}")


def _resolve_placeholder(name: str, context: dict) -> str:
    value = context.get(name)
    if value is None:
        raise ValueError(f"missing placeholder value: {name}")
    return str(value)


def _render_args(args_template: list[str], context: dict) -> list[str]:
    rendered = []
    for item in args_template:
        if item.startswith("{") and item.endswith("}"):
            rendered.append(_resolve_placeholder(item[1:-1], context))
        else:
            rendered.append(item)
    return rendered


def _dataset_path_for_manifest(manifest) -> Path | None:
    if manifest.dataset is None:
        return None
    root = datasets_dir() / manifest.dataset.id
    if manifest.dataset.extract:
        return root / manifest.dataset.extract
    return root


def run_quality_packs(pack_ids: list[str], *, server_path: Path | None, model_path: Path,
                      cache_label: str, cache_k: str, cache_v: str, split_config: dict | None = None) -> dict:
    results = {}
    for pack_id in pack_ids:
        try:
            manifest, manifest_hash, _ = verify_installed_manifest(pack_id)
        except Exception as exc:
            results[pack_id] = {"available": False, "error": str(exc)}
            continue

        try:
            binary_path = _resolve_binary(manifest.binary, server_path)
            if binary_path is None:
                results[pack_id] = {"available": False, "error": f"{manifest.binary} binary not found"}
                continue
            dataset_path = _dataset_path_for_manifest(manifest)
            stage = next((candidate for candidate in manifest.stages if _stage_matches(candidate.when, cache_label)), None)
            if stage is None:
                results[pack_id] = {"available": False, "skipped": True, "error": "no stage for this cache label"}
                continue
            with tempfile.NamedTemporaryFile(prefix=f"{pack_id}_{cache_label}_", suffix=".dat", delete=False) as logits_tmp:
                logits_out = Path(logits_tmp.name)
            context = {
                "model_path": str(model_path),
                "dataset_path": str(dataset_path) if dataset_path else "",
                "logits_in": str(logits_out),
                "logits_out": str(logits_out),
                "cache_k": cache_k,
                "cache_v": cache_v,
                "cache_label": cache_label,
                "main_gpu": (split_config or {}).get("main_gpu", 0),
                "split_mode": (split_config or {}).get("split_mode", "none"),
                "tensor_split": (split_config or {}).get("tensor_split", ""),
            }
            cmd = [str(binary_path)] + _render_args(stage.args_template, context)
            completed = subprocess.run(
                cmd,
                check=False,
                shell=False,
                capture_output=True,
                text=True,
                timeout=manifest.timeout_seconds,
                env=sanitized_subprocess_env(),
            )
            combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
            if completed.returncode != 0:
                results[pack_id] = {"available": False, "error": f"{manifest.binary} failed with exit code {completed.returncode}"}
            else:
                parsed = parse_metrics(manifest.parse, combined)
                parsed["available"] = True
                parsed["binary"] = manifest.binary
                results[pack_id] = parsed
            append_audit_log("run", pack_id=pack_id, manifest_sha256=manifest_hash, details={"cache_label": cache_label})
        except Exception as exc:
            results[pack_id] = {"available": False, "error": str(exc)}
    return results
