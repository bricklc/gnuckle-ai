"""Manifest-backed benchmark execution."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from gnuckle.bench_pack.manifest import verify_installed_manifest
from gnuckle.bench_pack.parser import parse_metrics
from gnuckle.bench_pack.trust import append_audit_log, datasets_dir, logits_dir, sanitized_subprocess_env


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


def _safe_model_stem(model_path: Path) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_path.stem).strip("._") or "model"


def _baseline_logits_path(pack_id: str, model_path: Path) -> Path:
    target = logits_dir() / pack_id
    target.mkdir(parents=True, exist_ok=True)
    return target / f"{_safe_model_stem(model_path)}_f16.dat"


def _run_stage(binary_path: Path, manifest, stage, context: dict) -> subprocess.CompletedProcess[str]:
    cmd = [str(binary_path)] + _render_args(stage.args_template, context)
    return subprocess.run(
        cmd,
        check=False,
        shell=False,
        capture_output=True,
        text=True,
        timeout=manifest.timeout_seconds,
        env=sanitized_subprocess_env(),
    )


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
            stages = [candidate for candidate in manifest.stages if _stage_matches(candidate.when, cache_label)]
            if not stages:
                results[pack_id] = {"available": False, "skipped": True, "error": "no stage for this cache label"}
                continue
            baseline_cache = manifest.requires_baseline or "f16"
            baseline_path = _baseline_logits_path(pack_id, model_path)
            if manifest.requires_baseline and cache_label != baseline_cache and not baseline_path.exists():
                results[pack_id] = {
                    "available": False,
                    "skipped": True,
                    "error": f"missing baseline logits from {baseline_cache}",
                }
                continue
            with tempfile.NamedTemporaryFile(prefix=f"{pack_id}_{cache_label}_", suffix=".dat", delete=False) as tmp_file:
                tmp_logits_path = Path(tmp_file.name)
            context = {
                "model_path": str(model_path),
                "dataset_path": str(dataset_path) if dataset_path else "",
                "logits_in": str(baseline_path if manifest.requires_baseline else tmp_logits_path),
                "logits_out": str(baseline_path if manifest.requires_baseline and cache_label == baseline_cache else tmp_logits_path),
                "baseline_path": str(baseline_path),
                "cache_k": cache_k,
                "cache_v": cache_v,
                "cache_label": cache_label,
                "main_gpu": (split_config or {}).get("main_gpu", 0),
                "split_mode": (split_config or {}).get("split_mode", "none"),
                "tensor_split": (split_config or {}).get("tensor_split", ""),
            }
            outputs = []
            failed = None
            for stage in stages:
                completed = _run_stage(binary_path, manifest, stage, context)
                combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
                outputs.append(combined)
                if completed.returncode != 0:
                    failed = completed
                    break
            combined_output = "\n".join(outputs)
            if failed is not None:
                results[pack_id] = {"available": False, "error": f"{manifest.binary} failed with exit code {failed.returncode}"}
            else:
                if manifest.requires_baseline and cache_label == baseline_cache and not baseline_path.exists():
                    baseline_path.touch()
                parsed = parse_metrics(manifest.parse, combined_output)
                if manifest.requires_baseline and cache_label == baseline_cache:
                    parsed.setdefault("mean_kld", 0.0)
                    parsed.setdefault("p99_kld", 0.0)
                    parsed.setdefault("top1_agreement_pct", 100.0)
                    parsed.setdefault("top5_agreement_pct", 100.0)
                    parsed["baseline_generated"] = True
                if manifest.report and manifest.report.primary_metric:
                    parsed["primary_metric"] = manifest.report.primary_metric
                    parsed["delta_mode"] = manifest.report.delta_vs_baseline or "relative"
                    parsed["column_label"] = manifest.report.column_label
                    if manifest.report.tier_thresholds:
                        parsed["tier_thresholds"] = dict(manifest.report.tier_thresholds)
                parsed["available"] = True
                parsed["binary"] = manifest.binary
                parsed["pack_version"] = manifest.version
                if manifest.requires_baseline:
                    parsed["baseline_cache"] = baseline_cache
                    parsed["logits_file"] = str(baseline_path)
                results[pack_id] = parsed
            append_audit_log("run", pack_id=pack_id, manifest_sha256=manifest_hash, details={"cache_label": cache_label})
        except Exception as exc:
            results[pack_id] = {"available": False, "error": str(exc)}
    return results
