"""
gnuckle visualize - read benchmark JSONs and produce a static HTML dashboard.
ape learn to draw. ape now draw.
"""

import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template

from gnuckle.ape import ape_print

CACHE_LABEL_ALIASES = {
    "f16": "f16",
    "q8_0": "q8_0",
    "q8-0": "q8_0",
    "q4_0": "q4_0",
    "q4-0": "q4_0",
    "turbo3": "turbo3",
    "turbo4": "turbo4",
}
CACHE_COLORS = {
    "turbo3": "#186a3b",
    "turbo4": "#0f8a5f",
    "q4_0": "#1c7ed6",
    "q8_0": "#6c757d",
    "f16": "#c92a2a",
}
CACHE_ORDER = ["f16", "q8_0", "q4_0", "turbo3", "turbo4"]
COMPRESSION = {
    "f16": "1.0",
    "q8_0": "2.0",
    "q4_0": "3.6",
    "turbo3": "4.4",
    "turbo4": "5.0",
}
TURN1_COLOR = "#C0DD97"


def canonical_cache_label(label: str) -> str:
    return CACHE_LABEL_ALIASES.get(str(label or "").strip(), str(label or "unknown"))


def cache_color(label: str) -> str:
    return CACHE_COLORS.get(canonical_cache_label(label), "#888780")


def cache_compression(label: str) -> str:
    return COMPRESSION.get(canonical_cache_label(label), "n/a")


def ordered_cache_labels(labels) -> list[str]:
    seen = []
    for label in labels:
        label = str(label)
        if label not in seen:
            seen.append(label)
    return sorted(
        seen,
        key=lambda label: (
            CACHE_ORDER.index(canonical_cache_label(label))
            if canonical_cache_label(label) in CACHE_ORDER
            else len(CACHE_ORDER),
            label,
        ),
    )

HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>turboquant benchmark dashboard - $model_name</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-sans); }
.dash { padding: 1rem 0; }
.header { margin-bottom: 1rem; }
.header h1 { font-size: 18px; font-weight: 600; color: var(--color-text-primary); }
.header .sub { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.section-label { font-size: 11px; font-weight: 500; color: var(--color-text-tertiary); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px,1fr)); gap: 8px; margin-bottom: 1.5rem; }
.mcard { background: var(--color-background-secondary); border-radius: var(--border-radius-md); padding: 0.75rem 1rem; }
.mcard .val { font-size: 20px; font-weight: 500; color: var(--color-text-primary); }
.mcard .lbl { font-size: 11px; color: var(--color-text-secondary); margin-top: 2px; }
.mcard .sub { font-size: 11px; margin-top: 4px; }
.good { color: var(--color-text-success); }
.warn { color: var(--color-text-warning); }
.bad { color: var(--color-text-danger); }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
.chart-wrap { background: var(--color-background-primary); border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-lg); padding: 1rem; }
.chart-full { background: var(--color-background-primary); border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-lg); padding: 1rem; margin-bottom: 1rem; }
.chart-title { font-size: 13px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 4px; }
.chart-sub { font-size: 11px; color: var(--color-text-secondary); margin-bottom: 12px; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 10px; font-size: 11px; color: var(--color-text-secondary); }
.legend span { display: flex; align-items: center; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.tq-badge { display: inline-block; background: #E1F5EE; color: #0F6E56; font-size: 10px; padding: 2px 7px; border-radius: var(--border-radius-md); font-weight: 500; margin-left: 6px; }
.annotation-box { border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-md); padding: 0.75rem 1rem; margin-top: 1rem; font-size: 12px; color: var(--color-text-secondary); line-height: 1.6; }
.annotation-box strong { color: var(--color-text-primary); font-weight: 500; }
.table-wrap { overflow-x: auto; margin-top: 1rem; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { font-weight: 500; font-size: 11px; color: var(--color-text-secondary); text-align: left; padding: 6px 10px; border-bottom: 0.5px solid var(--color-border-tertiary); }
td { padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-tertiary); color: var(--color-text-primary); }
tr:last-child td { border-bottom: none; }
.highlight-row td { background: #E1F5EE; color: #0F6E56; }
.turn-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin-top: 1rem; }
.turn-card { background: var(--color-background-primary); border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-lg); padding: 1rem; }
.turn-card-header { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-bottom: 0.75rem; }
.turn-card-title { font-size: 13px; font-weight: 500; color: var(--color-text-primary); }
.turn-card-sub { font-size: 11px; color: var(--color-text-secondary); }
.turn-list { display: grid; gap: 0.75rem; }
.turn-row { display: grid; grid-template-columns: 132px minmax(0, 1fr); gap: 0.75rem; padding-top: 0.75rem; border-top: 0.5px solid var(--color-border-tertiary); }
.turn-row:first-child { border-top: none; padding-top: 0; }
.turn-meta { font-size: 11px; color: var(--color-text-secondary); line-height: 1.5; }
.turn-meta strong { display: block; color: var(--color-text-primary); font-size: 12px; margin-bottom: 2px; }
.turn-body { min-width: 0; }
.turn-block { margin-bottom: 0.45rem; }
.turn-block:last-child { margin-bottom: 0; }
.turn-block-label { font-size: 10px; font-weight: 600; color: var(--color-text-tertiary); letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 3px; }
.turn-block-text { font-size: 12px; color: var(--color-text-primary); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.footer { margin-top: 1rem; font-size: 11px; color: var(--color-text-tertiary); }
@media (max-width: 900px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-grid { grid-template-columns: 1fr; }
  .turn-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .metric-grid { grid-template-columns: 1fr; }
  .turn-row { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="dash">
  <div class="header">
    <h1>TurboQuant benchmark dashboard</h1>
    <div class="sub">$model_name &middot; $timestamp &middot; $num_turns turns per cache type &middot; $num_cache_types cache types &middot; $system_prompt_summary</div>
  </div>

  <div class="section-label">benchmark outcomes &mdash; data from json</div>

  <div class="metric-grid">
$metric_cards
  </div>

  <div class="chart-full">
    <div class="chart-title">metric 3 &mdash; context scaling degradation <span class="tq-badge">TurboQuant key claim</span></div>
    <div class="chart-sub">generation speed (tok/s) across tool call turns &mdash; this is what TurboQuant is designed to flatten</div>
    <div class="legend">
$degrad_legend
    </div>
    <div style="position: relative; width: 100%; height: 220px;">
      <canvas id="degradChart"></canvas>
    </div>
    <div class="annotation-box">
      <strong>What this exposes:</strong> lower degradation means the cache stays flatter as context grows. Higher VRAM headroom and stable tok/s across turns are the main signals to compare across cache types.
    </div>
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">metric 4 &mdash; VRAM at peak context</div>
      <div class="chart-sub">KV cache memory at turn $num_turns of tool chain (MB)</div>
      <div class="legend">
$vram_legend
      </div>
      <div style="position: relative; width: 100%; height: 180px;">
        <canvas id="vramChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">metric 2 &mdash; TTFT across turns</div>
      <div class="chart-sub">time to first token (ms) as context grows</div>
      <div class="legend">
$ttft_legend
      </div>
      <div style="position: relative; width: 100%; height: 180px;">
        <canvas id="ttftChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">metric 1 &mdash; generation speed</div>
      <div class="chart-sub">tok/s at short vs long context (turn 1 vs turn $num_turns)</div>
      <div class="legend">
        <span><span class="dot" style="background:$turn1_color"></span>turn 1</span>
        <span><span class="dot" style="background:$hero_color"></span>turn $num_turns</span>
      </div>
      <div style="position: relative; width: 100%; height: 180px;">
        <canvas id="speedChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">metric 5 &mdash; tool call accuracy</div>
      <div class="chart-sub">% valid JSON tool calls per turn range</div>
      <div class="legend">
$acc_legend
      </div>
      <div style="position: relative; width: 100%; height: 180px;">
        <canvas id="accChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-full">
    <div class="chart-title">full benchmark matrix &mdash; all metrics &times; all cache types</div>
    <div class="chart-sub">JSON data rendered into a static HTML dashboard</div>
    <div class="table-wrap">
      <table>
        <tr>
          <th>Cache type</th>
          <th>Compression</th>
          <th>Prompt (t/s)</th>
          <th>Gen (t/s)</th>
          <th>Gen tok/s (t1)</th>
          <th>Gen tok/s ($num_turns)</th>
          <th>Degradation</th>
          <th>TTFT t1 (ms)</th>
          <th>TTFT $num_turns (ms)</th>
          <th>Context MiB</th>
          <th>VRAM peak (MB)</th>
          <th>Tool accuracy</th>
        </tr>
$table_rows
      </table>
    </div>
    <div class="annotation-box" style="margin-top: 12px;">
      <strong>How to read this table:</strong> compare turn-1 speed, long-context speed, degradation, TTFT, VRAM peak, and tool accuracy across cache types. The highlighted row is the selected TurboQuant cache when present.
    </div>
  </div>

  <div class="turn-grid">
$turn_sections
  </div>

  <div class="footer">generated by gnuckle $version</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const turns = $turns_js;
const gridColor = 'rgba(128,128,128,0.12)';
const tickColor = '#888780';
const tickFont = { size: 10 };

new Chart(document.getElementById('degradChart'), {
  type: 'line',
  data: {
    labels: turns,
    datasets: [$degrad_datasets]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { title: { display: true, text: 'tool call turn', color: tickColor, font: { size: 11 } }, ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } },
      y: { title: { display: true, text: 'tok/s', color: tickColor, font: { size: 11 } }, min: $tps_min, max: $tps_max, ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('vramChart'), {
  type: 'bar',
  data: {
    labels: $vram_labels,
    datasets: [{ data: $vram_data, backgroundColor: $vram_colors }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { display: false } },
      y: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('ttftChart'), {
  type: 'line',
  data: {
    labels: turns,
    datasets: [$ttft_datasets]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } },
      y: { title: { display: true, text: 'ms', color: tickColor, font: { size: 10 } }, max: $ttft_max, ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('speedChart'), {
  type: 'bar',
  data: {
    labels: $speed_labels,
    datasets: [
      { label: 'turn 1', data: $speed_t1, backgroundColor: '$turn1_color' },
      { label: 'turn $num_turns', data: $speed_tn, backgroundColor: '$hero_color' }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { display: false } },
      y: { min: $tps_min, max: $tps_max, ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('accChart'), {
  type: 'bar',
  data: {
    labels: $acc_labels,
    datasets: [$acc_datasets]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { display: false } },
      y: { min: 85, max: 101, ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});
</script>
</body>
</html>
"""
)

AGENTIC_HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentic benchmark dashboard - $model_name</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-sans); }
.dash { padding: 1rem 0; }
.header { margin-bottom: 1rem; }
.header h1 { font-size: 18px; font-weight: 600; color: var(--color-text-primary); }
.header .sub { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.section-label { font-size: 11px; font-weight: 500; color: var(--color-text-tertiary); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 8px; margin-bottom: 1rem; }
.mcard { background: var(--color-background-secondary); border-radius: var(--border-radius-md); padding: 0.75rem 1rem; }
.mcard .val { font-size: 20px; font-weight: 500; color: var(--color-text-primary); }
.mcard .lbl { font-size: 11px; color: var(--color-text-secondary); margin-top: 2px; }
.mcard .sub { font-size: 11px; margin-top: 4px; }
.good { color: var(--color-text-success); }
.warn { color: var(--color-text-warning); }
.bad { color: var(--color-text-danger); }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
.chart-wrap { background: var(--color-background-primary); border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-lg); padding: 1rem; }
.chart-title { font-size: 13px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 4px; }
.chart-sub { font-size: 11px; color: var(--color-text-secondary); margin-bottom: 12px; }
.table-wrap { overflow-x: auto; margin-top: 1rem; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { font-weight: 500; font-size: 11px; color: var(--color-text-secondary); text-align: left; padding: 6px 10px; border-bottom: 0.5px solid var(--color-border-tertiary); }
td { padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-tertiary); color: var(--color-text-primary); vertical-align: top; }
tr:last-child td { border-bottom: none; }
.trace-list { display: grid; gap: 0.75rem; margin-top: 1rem; }
.trace-row { display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 0.75rem; padding: 0.9rem 1rem; background: var(--color-background-primary); border: 0.5px solid var(--color-border-tertiary); border-radius: var(--border-radius-lg); }
.trace-meta { font-size: 11px; color: var(--color-text-secondary); line-height: 1.5; }
.trace-meta strong { display: block; color: var(--color-text-primary); font-size: 12px; margin-bottom: 2px; }
.trace-body { min-width: 0; }
.trace-block { margin-bottom: 0.45rem; }
.trace-block:last-child { margin-bottom: 0; }
.trace-block-label { font-size: 10px; font-weight: 600; color: var(--color-text-tertiary); letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 3px; }
.trace-block-text { font-size: 12px; color: var(--color-text-primary); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.footer { margin-top: 1rem; font-size: 11px; color: var(--color-text-tertiary); }
@media (max-width: 900px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .metric-grid { grid-template-columns: 1fr; }
  .trace-row { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="dash">
  <div class="header">
    <h1>Agentic benchmark dashboard</h1>
    <div class="sub">$model_name &middot; $timestamp &middot; cache $cache_label &middot; workflow $workflow_title &middot; session $session_mode</div>
  </div>

  <div class="section-label">episode outcome</div>
  <div class="metric-grid">
$outcome_cards
  </div>

  <div class="section-label">performance and resources</div>
  <div class="metric-grid">
$resource_cards
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">context pressure across the trace</div>
      <div class="chart-sub">estimated context occupancy over assistant and tool steps</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="contextChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">failure and recovery counts</div>
      <div class="chart-sub">invalid calls, retries, execution failures, denials, and repairs</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="failureChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">VRAM usage across the trace</div>
      <div class="chart-sub">peak VRAM (MB) at each assistant and tool step</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="vramTraceChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">score breakdown</div>
      <div class="chart-sub">raw score parts kept visible for benchmark honesty</div>
      <div class="table-wrap">
        <table>
$score_rows
        </table>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">tool choice and integrity</div>
      <div class="chart-sub">expected tools, wrong calls, and prompt retention signals</div>
      <div class="table-wrap">
        <table>
$selection_rows
        </table>
      </div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">agent trace timeline</div>
    <div class="chart-sub">assistant, tool, repair, verification, and final-result flow</div>
    <div class="trace-list">
$trace_rows
    </div>
  </div>

  <div class="footer">generated by gnuckle $version</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const gridColor = 'rgba(128,128,128,0.12)';
const tickColor = '#888780';
const tickFont = { size: 10 };

new Chart(document.getElementById('contextChart'), {
  type: 'line',
  data: {
    labels: $context_labels,
    datasets: [{
      label: 'ours',
      data: $context_values,
      borderColor: '#378ADD',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3
    }, {
      label: '$context_tokenizer_label',
      data: $context_tokenizer_values,
      borderColor: '#E0A458',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
      spanGaps: true
    }, {
      label: '$context_measured_label',
      data: $context_measured_values,
      borderColor: '#2A8C4A',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
      spanGaps: true
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: true } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } },
      y: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('failureChart'), {
  type: 'bar',
  data: {
    labels: $failure_labels,
    datasets: [{
      data: $failure_values,
      backgroundColor: ['#E24B4A', '#E0A458', '#378ADD', '#6A4C93', '#888780', '#2A8C4A']
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { display: false } },
      y: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});

new Chart(document.getElementById('vramTraceChart'), {
  type: 'line',
  data: {
    labels: $vram_labels,
    datasets: [{
      label: 'VRAM peak (MB)',
      data: $vram_values,
      borderColor: '#6A4C93',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
      spanGaps: true
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: true } },
    scales: {
      x: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } },
      y: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
    }
  }
});
</script>
</body>
</html>
"""
)


def _find_results_dirs(results_path: Path) -> list[Path]:
    json_files = sorted(results_path.glob("*.json"))
    if json_files:
        return [results_path]

    candidate_dirs = []
    for child in results_path.iterdir():
        if not child.is_dir():
            continue
        child_json = list(child.glob("*.json"))
        if child_json:
            newest = max(f.stat().st_mtime for f in child_json)
            candidate_dirs.append((newest, child))

    candidate_dirs.sort(key=lambda item: item[0], reverse=True)
    return [child for _newest, child in candidate_dirs]


def _select_results_dir(results_path: Path) -> Path | None:
    candidates = _find_results_dirs(results_path)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if candidates[0] == results_path and len(candidates) == 1:
        return results_path

    print("\n  Available benchmark runs (ape see banana folders):\n")
    for idx, candidate in enumerate(candidates, start=1):
        json_count = len(list(candidate.glob("*.json")))
        print(f"  [{idx}] {candidate.name}  ({json_count} json)")
    print()

    while True:
        try:
            choice = int(input("  ape pick run [number]: ").strip())
        except ValueError:
            print("  not valid. ape need folder number.")
            continue
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
        print("  number outside banana range. ape try again.")


def load_results(results_dir: Path):
    """Load benchmark JSON files, keeping the latest file for each cache."""
    files = sorted(results_dir.glob("benchmark_*.json"), reverse=True)
    by_cache = {}

    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            label = data["meta"]["cache_label"]
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        if label not in by_cache:
            by_cache[label] = data

    return by_cache


def load_agentic_result(results_dir: Path):
    files = sorted(results_dir.glob("agentic_*.json"), reverse=True)
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("benchmark_mode") == "agentic":
            return data
    return None


def load_agentic_results(results_dir: Path) -> dict[str, dict]:
    """Load all agentic JSONs, keeping the latest per cache label."""
    files = sorted(results_dir.glob("agentic_*.json"), reverse=True)
    by_cache = {}
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("benchmark_mode") != "agentic":
            continue
        label = data.get("cache_label", "unknown")
        if label not in by_cache:
            by_cache[label] = data
    return by_cache


def _session_cache_label_from_path(file_path: Path, benchmark_id: str | None) -> str:
    stem = file_path.stem
    prefix = f"session_{benchmark_id}_" if benchmark_id else "session_"
    if benchmark_id and stem == f"session_{benchmark_id}":
        return "f16"
    if stem.startswith(prefix):
        suffix = stem[len(prefix):]
        return canonical_cache_label(suffix) if suffix else "f16"
    return "unknown"


def load_session_results(results_dir: Path) -> dict[str, dict]:
    files = sorted(results_dir.glob("session_*.json"), reverse=True)
    by_cache = {}
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = data.get("meta", {})
        if meta.get("type") != "session":
            continue
        label = _session_cache_label_from_path(file_path, meta.get("benchmark_id"))
        if label not in by_cache:
            data["_cache_label"] = label
            by_cache[label] = data
    return by_cache


def detect_benchmark_mode(results_dir: Path) -> str | None:
    if any(results_dir.glob("agentic_*.json")):
        return "agentic"
    if any(results_dir.glob("session_*.json")):
        return "session"
    if any(results_dir.glob("benchmark_*.json")):
        return "legacy"
    return None


def extract_metrics(data):
    """Pull summary metrics from a single cache type run."""
    turns = data.get("turns", [])
    meta = data.get("meta", {})
    throughput_benchmark = meta.get("throughput_benchmark", {}) or {}
    tps_list = [t.get("tps", 0) for t in turns if t.get("tps", 0) > 0]
    ttft_list = [t.get("ttft_ms") for t in turns if t.get("ttft_ms") is not None]
    acc_list = [t.get("tool_accuracy_pct") for t in turns if t.get("tool_accuracy_pct") is not None]

    vram_peak = 0
    if turns:
        last_vram = turns[-1].get("vram_after_mb", [])
        if isinstance(last_vram, list) and last_vram:
            vram_peak = max(last_vram)

    t1_tps = tps_list[0] if tps_list else 0
    tn_tps = tps_list[-1] if tps_list else 0
    degradation = round(100 * (tn_tps - t1_tps) / t1_tps, 1) if t1_tps else 0

    return {
        "prompt_tps_bench": throughput_benchmark.get("prompt_tokens_per_second"),
        "gen_tps_bench": throughput_benchmark.get("generation_tokens_per_second"),
        "throughput_available": bool(throughput_benchmark.get("available")),
        "tps_t1": round(t1_tps, 2),
        "tps_tn": round(tn_tps, 2),
        "tps_all": [round(v, 2) for v in tps_list],
        "ttft_t1": round(ttft_list[0], 1) if ttft_list else 0,
        "ttft_tn": round(ttft_list[-1], 1) if ttft_list else 0,
        "ttft_all": [round(v, 1) for v in ttft_list],
        "degradation": degradation,
        "vram_peak": vram_peak,
        "acc_avg": round(sum(acc_list) / len(acc_list), 1) if acc_list else 0,
        "acc_all": [round(v, 1) for v in acc_list],
        "num_turns": len(turns),
    }


def deg_class(value):
    if abs(value) <= 5:
        return "good"
    if abs(value) <= 15:
        return "warn"
    return "bad"


def format_num(value, digits=1):
    text = f"{value:,.{digits}f}"
    if digits == 1 and text.endswith(".0"):
        return text[:-2]
    return text


def format_pct(value, digits=1):
    text = f"{value:.{digits}f}%"
    if digits == 1 and text.endswith(".0%"):
        return text[:-3] + "%"
    return text


def format_delta(value, digits=3):
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}"


def delta_class(value):
    if value is None:
        return "delta-flat"
    if value > 0.02:
        return "delta-up"
    if value < -0.02:
        return "delta-down"
    return "delta-flat"


def legend_html(entries):
    return "\n".join(
        f'      <span><span class="dot" style="background:{color}"></span>{escape(label)}</span>'
        for label, color in entries
    )


def truncate_text(text, limit=220):
    if not text:
        return ""
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def format_token_triplet(heuristic, tokenizer, tokenizer_label_text="OpenAI cl100k_base", measured=None, measured_label_text="llama.cpp exact"):
    ours = f"ours {heuristic}" if heuristic is not None else "ours n/a"
    theirs = (
        f"{tokenizer_label_text} {tokenizer}"
        if tokenizer is not None
        else f"{tokenizer_label_text} unavailable"
    )
    exact = (
        f"{measured_label_text} {measured}"
        if measured is not None
        else f"{measured_label_text} unavailable"
    )
    return f"{ours} · {theirs} · {exact}"


def summarize_tool_calls(turn):
    names = turn.get("tool_call_names")
    if names:
        return ", ".join(names)

    tool_accuracy = turn.get("tool_accuracy") or []
    extracted = [entry.get("tool") for entry in tool_accuracy if entry.get("tool")]
    if extracted:
        return ", ".join(extracted)

    count = turn.get("tool_calls_count", 0)
    return f"{count} tool call(s)" if count else "none"


def build_turn_section(cache, data):
    turns = data.get("turns", [])
    if not turns:
        return ""

    rows = []
    for turn in turns:
        prompt = truncate_text(turn.get("prompt", ""))
        response = truncate_text(turn.get("assistant_preview", "")) or "(tool-call only or no assistant text captured)"
        ttft = turn.get("ttft_ms")
        ttft_label = f"{ttft} ms" if ttft is not None else "n/a"
        acc = turn.get("tool_accuracy_pct")
        acc_label = f"{acc}%" if acc is not None else "n/a"
        tool_summary = summarize_tool_calls(turn)
        turn_error = truncate_text(turn.get("error", ""), limit=180)

        rows.append(
            f"""        <div class="turn-row">
          <div class="turn-meta">
            <strong>turn {turn.get("turn", "?"):02d}</strong>
            <div>tok/s: {format_num(turn.get("tps", 0), 2)}</div>
            <div>ttft: {escape(str(ttft_label))}</div>
            <div>tok: {escape(str(turn.get("tokens_generated", 0)))}</div>
            <div>tools: {escape(str(turn.get("tool_calls_count", 0)))}</div>
            <div>acc: {escape(str(acc_label))}</div>
            <div>ctx: {escape(format_token_triplet(turn.get("context_tokens_heuristic", turn.get("context_tokens_estimate")), turn.get("context_tokens_tokenizer"), turn.get("tokenizer_label", "OpenAI cl100k_base"), turn.get("context_tokens_measured"), turn.get("measured_label", "llama.cpp exact")))}</div>
          </div>
          <div class="turn-body">
            <div class="turn-block">
              <div class="turn-block-label">prompt</div>
              <div class="turn-block-text">{escape(prompt or "(empty)")}</div>
            </div>
            <div class="turn-block">
              <div class="turn-block-label">response</div>
              <div class="turn-block-text">{escape(response)}</div>
            </div>
            <div class="turn-block">
              <div class="turn-block-label">tools</div>
              <div class="turn-block-text">{escape(tool_summary)}</div>
            </div>
            {f'''<div class="turn-block">
              <div class="turn-block-label">error</div>
              <div class="turn-block-text">{escape(turn_error)}</div>
            </div>''' if turn_error else ""}
          </div>
        </div>"""
        )

    return (
        f"""    <div class="turn-card">
      <div class="turn-card-header">
        <div class="turn-card-title">{escape(cache)} turns</div>
        <div class="turn-card-sub">telemetry + prompt/response preview</div>
      </div>
      <div class="turn-list">
{chr(10).join(rows)}
      </div>
    </div>"""
    )


def line_dataset(label, data, color):
    return (
        "{"
        f"label:{json.dumps(label)},"
        f"data:{json.dumps(data)},"
        f"borderColor:{json.dumps(color)},"
        f"backgroundColor:'transparent',"
        "borderWidth:2,"
        "pointRadius:2,"
        "tension:0.3"
        "}"
    )


def bucket_acc(acc_list, num_turns):
    if not acc_list:
        return [0, 0, 0, 0]

    buckets = []
    start = 0
    for bucket_idx in range(4):
        end = round((bucket_idx + 1) * len(acc_list) / 4)
        chunk = acc_list[start:end]
        buckets.append(round(sum(chunk) / len(chunk), 1) if chunk else 0)
        start = end
    while len(buckets) < 4:
        buckets.append(0)
    return buckets[:4]


def clamp_tick_range(values, lower_pad=2, upper_pad=2):
    if not values:
        return 0, 20
    low = max(0, int(min(values) - lower_pad))
    high = int(max(values) + upper_pad)
    if high <= low:
        high = low + 1
    return low, high


def build_html(by_cache, model_name, timestamp, system_prompt_summary="system prompt unknown"):
    """Generate the static dashboard HTML from benchmark JSON data."""
    ordered = ordered_cache_labels(by_cache.keys())
    metrics = {cache: extract_metrics(by_cache[cache]) for cache in ordered}

    if not ordered:
        raise ValueError("no cache types available")

    num_turns = max((metrics[cache]["num_turns"] for cache in ordered), default=20)
    turns_js = json.dumps(list(range(1, num_turns + 1)))

    hero = "turbo3" if "turbo3" in metrics else max(ordered, key=lambda c: metrics[c]["tps_t1"])
    hero_m = metrics[hero]
    baseline = "f16" if "f16" in metrics else min(ordered, key=lambda c: metrics[c]["vram_peak"] or float("inf"))
    baseline_m = metrics.get(baseline, hero_m)

    if len(ordered) > 1:
        speed_compare = max(
            (c for c in ordered if c != hero),
            key=lambda c: metrics[c]["tps_t1"],
            default=baseline,
        )
    else:
        speed_compare = hero
    speed_compare_m = metrics.get(speed_compare, hero_m)

    metric_cards = "\n".join(
        [
            f"""    <div class="mcard">
      <div class="val">{format_num(hero_m["prompt_tps_bench"]) if hero_m["prompt_tps_bench"] is not None else 'n/a'}</div>
      <div class="lbl">Prompt (t/s)</div>
      <div class="sub {'good' if hero_m['prompt_tps_bench'] is not None else 'warn'}">llama-bench prompt processing</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_num(hero_m["gen_tps_bench"]) if hero_m["gen_tps_bench"] is not None else 'n/a'}</div>
      <div class="lbl">Gen (t/s)</div>
      <div class="sub {'good' if hero_m['gen_tps_bench'] is not None else 'warn'}">llama-bench token generation</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_num(hero_m["tps_t1"])}</div>
      <div class="lbl">runtime tok/s {escape(hero)}</div>
      <div class="sub {deg_class(hero_m["tps_t1"] - speed_compare_m["tps_t1"])}">vs {format_num(speed_compare_m["tps_t1"])} {escape(speed_compare)}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_num(hero_m["ttft_t1"], 0)}ms</div>
      <div class="lbl">TTFT {escape(hero)}</div>
      <div class="sub {'good' if hero_m['ttft_t1'] <= baseline_m['ttft_t1'] else 'warn'}">vs {format_num(baseline_m['ttft_t1'], 0)}ms {escape(baseline)}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_pct(abs(hero_m["degradation"]))}</div>
      <div class="lbl">speed drop turn {num_turns}</div>
      <div class="sub {deg_class(hero_m['degradation'])}">{escape(hero)} {'stays flat' if abs(hero_m['degradation']) <= 5 else 'shows drift'}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_num(hero_m["vram_peak"], 0)} MB</div>
      <div class="lbl">KV cache peak</div>
      <div class="sub {'good' if hero_m['vram_peak'] <= baseline_m['vram_peak'] else 'warn'}">vs {format_num(baseline_m['vram_peak'], 0)} {escape(baseline)}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_pct(hero_m["acc_avg"])}</div>
      <div class="lbl">tool call accuracy</div>
      <div class="sub {'good' if hero_m['acc_avg'] >= 95 else 'warn'}">valid JSON per turn</div>
    </div>""",
        ]
    )

    degrad_legend = legend_html(
        [(cache, cache_color(cache)) for cache in ordered]
    )
    vram_legend = degrad_legend
    ttft_legend = degrad_legend
    acc_legend = degrad_legend

    degrad_datasets = ",".join(
        line_dataset(cache, metrics[cache]["tps_all"][:num_turns], cache_color(cache))
        for cache in ordered
    )
    ttft_datasets = ",".join(
        line_dataset(cache, metrics[cache]["ttft_all"][:num_turns], cache_color(cache))
        for cache in ordered
    )

    vram_labels = json.dumps(ordered)
    vram_data = json.dumps([metrics[cache]["vram_peak"] for cache in ordered])
    vram_colors = json.dumps([cache_color(cache) for cache in ordered])

    speed_labels = json.dumps(ordered)
    speed_t1 = json.dumps([metrics[cache]["tps_t1"] for cache in ordered])
    speed_tn = json.dumps([metrics[cache]["tps_tn"] for cache in ordered])

    acc_bucket_labels = json.dumps(
        [
            f"t1-{max(1, num_turns // 4)}",
            f"t{max(1, num_turns // 4 + 1)}-{max(1, num_turns // 2)}",
            f"t{max(1, num_turns // 2 + 1)}-{max(1, (3 * num_turns) // 4)}",
            f"t{max(1, (3 * num_turns) // 4 + 1)}-{num_turns}",
        ]
    )
    acc_datasets = ",".join(
        "{"
        f"label:{json.dumps(cache)},"
        f"data:{json.dumps(bucket_acc(metrics[cache]['acc_all'], num_turns))},"
        f"backgroundColor:{json.dumps(cache_color(cache))}"
        "}"
        for cache in ordered
    )

    table_rows = []
    for cache in ordered:
        m = metrics[cache]
        row_class = ' class="highlight-row"' if cache == hero else ""
        emphasis = ("<strong>", "</strong>") if cache == hero else ("", "")
        table_rows.append(
            f"""        <tr{row_class}>
          <td>{emphasis[0]}{escape(cache)}{emphasis[1]}</td>
          <td>{emphasis[0]}{(format_num(float(cache_compression(cache)), 1) + '&times;') if cache_compression(cache) != 'n/a' else 'n/a'}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["prompt_tps_bench"]) if m["prompt_tps_bench"] is not None else 'n/a'}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["gen_tps_bench"]) if m["gen_tps_bench"] is not None else 'n/a'}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["tps_t1"])}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["tps_tn"])}{emphasis[1]}</td>
          <td class="{deg_class(m['degradation'])}">{emphasis[0]}{format_pct(m["degradation"])}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["ttft_t1"], 0)}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["ttft_tn"], 0)}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["vram_peak"] / 1024.0, 2)}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["vram_peak"], 0)}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_pct(m["acc_avg"])}{emphasis[1]}</td>
        </tr>"""
        )

    all_tps = [value for cache in ordered for value in metrics[cache]["tps_all"]]
    all_ttft = [value for cache in ordered for value in metrics[cache]["ttft_all"]]
    tps_min, tps_max = clamp_tick_range(all_tps, lower_pad=2, upper_pad=2)
    _, ttft_max = clamp_tick_range(all_ttft, lower_pad=0, upper_pad=0)
    ttft_max = int(ttft_max * 1.15) if ttft_max else 2000

    try:
        version = _get_version()
    except Exception:
        version = "0.1.0"

    turn_sections = "\n".join(build_turn_section(cache, by_cache[cache]) for cache in ordered)

    return HTML_TEMPLATE.safe_substitute(
        model_name=escape(model_name),
        timestamp=escape(timestamp),
        system_prompt_summary=escape(system_prompt_summary),
        num_turns=num_turns,
        num_cache_types=len(ordered),
        metric_cards=metric_cards,
        degrad_legend=degrad_legend,
        vram_legend=vram_legend,
        ttft_legend=ttft_legend,
        acc_legend=acc_legend,
        turn1_color=TURN1_COLOR,
        hero_color=CACHE_COLORS.get(hero, "#3B6D11"),
        table_rows="\n".join(table_rows),
        turn_sections=turn_sections,
        version=escape(version),
        turns_js=turns_js,
        degrad_datasets=degrad_datasets,
        ttft_datasets=ttft_datasets,
        vram_labels=vram_labels,
        vram_data=vram_data,
        vram_colors=vram_colors,
        speed_labels=speed_labels,
        speed_t1=speed_t1,
        speed_tn=speed_tn,
        acc_labels=acc_bucket_labels,
        acc_datasets=acc_datasets,
        tps_min=tps_min,
        tps_max=tps_max,
        ttft_max=ttft_max,
    )


def _status_class(ok):
    return "good" if ok else "bad"


def _trace_title(entry_type):
    mapping = {
        "event": "event",
        "assistant_action": "assistant",
        "repair_prompt": "repair",
        "tool_call": "tool call",
        "tool_result": "tool result",
        "tool_retry": "retry",
        "verification": "verification",
        "final_result": "final result",
    }
    return mapping.get(entry_type, entry_type.replace("_", " "))


def _build_agentic_trace_rows(trace):
    rows = []
    for idx, entry in enumerate(trace, start=1):
        title = _trace_title(entry.get("type", "step"))
        turn = entry.get("turn")
        meta_lines = [f"<strong>{escape(title)}</strong>"]
        if turn is not None:
            meta_lines.append(f"<div>turn: {escape(str(turn))}</div>")
        if entry.get("attempt") is not None:
            meta_lines.append(f"<div>attempt: {escape(str(entry.get('attempt')))}</div>")
        if entry.get("latency_ms") is not None:
            meta_lines.append(f"<div>latency: {escape(str(entry.get('latency_ms')))} ms</div>")
        if entry.get("context_tokens_estimate") is not None:
            meta_lines.append(
                f"<div>ctx: {escape(format_token_triplet(entry.get('context_tokens_heuristic', entry.get('context_tokens_estimate')), entry.get('context_tokens_tokenizer'), entry.get('tokenizer_label', 'OpenAI cl100k_base'), entry.get('context_tokens_measured'), entry.get('measured_label', 'llama.cpp exact')))}</div>"
            )
        hardware = entry.get("hardware_usage") or {}
        if hardware.get("vram_peak_mb") is not None:
            meta_lines.append(f"<div>vram: {escape(str(hardware.get('vram_peak_mb')))} MB</div>")

        body_blocks = []
        if entry.get("content"):
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">content</div>
  <div class="trace-block-text">{escape(truncate_text(entry.get("content"), 500))}</div>
</div>"""
            )
        if entry.get("tool_calls"):
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">tool calls</div>
  <div class="trace-block-text">{escape(truncate_text(json.dumps(entry.get("tool_calls"), ensure_ascii=True), 500))}</div>
</div>"""
            )
        if entry.get("arguments") is not None:
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">arguments</div>
  <div class="trace-block-text">{escape(truncate_text(json.dumps(entry.get("arguments"), ensure_ascii=True), 500))}</div>
</div>"""
            )
        if entry.get("result") is not None:
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">result</div>
  <div class="trace-block-text">{escape(truncate_text(json.dumps(entry.get("result"), ensure_ascii=True), 500))}</div>
</div>"""
            )
        if entry.get("reason"):
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">reason</div>
  <div class="trace-block-text">{escape(truncate_text(entry.get("reason"), 300))}</div>
</div>"""
            )
        if entry.get("summary"):
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">summary</div>
  <div class="trace-block-text">{escape(truncate_text(entry.get("summary"), 300))}</div>
</div>"""
            )
        if entry.get("failure_reason"):
            body_blocks.append(
                f"""<div class="trace-block">
  <div class="trace-block-label">failure</div>
  <div class="trace-block-text">{escape(str(entry.get("failure_reason")))}</div>
</div>"""
            )
        if not body_blocks:
            body_blocks.append(
                """<div class="trace-block">
  <div class="trace-block-label">note</div>
  <div class="trace-block-text">(no extra payload)</div>
</div>"""
            )

        rows.append(
            f"""      <div class="trace-row">
        <div class="trace-meta">
          {''.join(meta_lines)}
        </div>
        <div class="trace-body">
          {''.join(body_blocks)}
        </div>
      </div>"""
        )
    return "\n".join(rows)


def build_agentic_html(data):
    if data.get("workflow_results"):
        return build_agentic_suite_html_modern(data)

    aggregate = data.get("aggregate", {})
    episode = (data.get("episodes") or [{}])[0]
    performance = episode.get("performance", {})
    scores = episode.get("scores", {})
    failures = episode.get("failure_events", {})
    token_usage = episode.get("token_usage", {})
    hardware_usage = episode.get("hardware_usage", {})
    tool_selection = episode.get("tool_selection", {})
    workflow = data.get("workflow", {})
    model_name = data.get("model_id", "unknown model")
    generated_at = data.get("generated_at", datetime.now().isoformat())
    cache_label = data.get("cache_label", "unknown")
    session_mode = data.get("session_mode", "unknown")
    workflow_title = workflow.get("title", workflow.get("workflow_id", "unknown workflow"))
    split_config = (data.get("runtime_config") or {}).get("split_config", {})
    token_counting = (data.get("runtime_config") or {}).get("token_counting", {})
    split_summary = f"{split_config.get('split_mode', 'layer')} (main-gpu={split_config.get('main_gpu', 0)})"
    context_percent = token_usage.get("context_percent_used", aggregate.get("context_percent_used"))
    context_percent_text = f"{context_percent}%" if context_percent is not None else "n/a"
    tokenizer_label_text = token_usage.get("tokenizer_label") or "OpenAI cl100k_base"
    measured_label_text = token_usage.get("measured_label") or "llama.cpp exact"
    total_provider_tokens = (
        episode.get("provider_usage_total_tokens")
        or (episode.get("provider_usage") or {}).get("total_tokens")
        or aggregate.get("provider_total_tokens", 0)
    )
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    outcome_cards = "\n".join(
        [
            f"""    <div class="mcard">
      <div class="val">{escape(str(episode.get("status", "unknown")))}</div>
      <div class="lbl">episode status</div>
      <div class="sub {_status_class(episode.get("status") == "completed")}">{'task held together' if episode.get('status') == 'completed' else 'ape see drift or failure'}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{'yes' if episode.get('task_completed') else 'no'}</div>
      <div class="lbl">task completed</div>
      <div class="sub {_status_class(bool(episode.get('task_completed')))}">workflow success</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{'yes' if episode.get('verification_passed') else 'no'}</div>
      <div class="lbl">verification passed</div>
      <div class="sub {_status_class(bool(episode.get('verification_passed')))}">checks after finish</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{format_num(scores.get('episode_score', 0), 3)}</div>
      <div class="lbl">episode score</div>
      <div class="sub {_status_class((scores.get('episode_score') or 0) >= 0.8)}">scored, not guessed</div>
    </div>""",
        ]
    )

    resource_cards = "\n".join(
        [
            f"""    <div class="mcard">
      <div class="val">{format_num(performance.get('wall_clock_ms', 0), 0)} ms</div>
      <div class="lbl">wall clock</div>
      <div class="sub">avg turn {format_num(performance.get('avg_turn_latency_ms', 0), 0)} ms</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{escape(str(token_usage.get('context_tokens_heuristic', token_usage.get('context_tokens_estimate', aggregate.get('peak_context_tokens_heuristic', aggregate.get('peak_context_tokens_estimate', 0))))))}</div>
      <div class="lbl">peak context pressure</div>
      <div class="sub">{escape(format_token_triplet(token_usage.get('context_tokens_heuristic', token_usage.get('context_tokens_estimate', aggregate.get('peak_context_tokens_heuristic', aggregate.get('peak_context_tokens_estimate', 0)))), token_usage.get('context_tokens_tokenizer', aggregate.get('peak_context_tokens_tokenizer')), tokenizer_label_text, token_usage.get('context_tokens_measured', aggregate.get('peak_context_tokens_measured')), measured_label_text))}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{escape(str(hardware_usage.get('vram_peak_mb', aggregate.get('vram_peak_mb', 0))))} MB</div>
      <div class="lbl">VRAM peak</div>
      <div class="sub">steady {escape(str(hardware_usage.get('vram_steady_mb', aggregate.get('vram_steady_mb', 0))))} MB</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{escape(str(token_usage.get('input_tokens', aggregate.get('provider_input_tokens', 0))))}/{escape(str(token_usage.get('output_tokens', aggregate.get('provider_output_tokens', 0))))}</div>
      <div class="lbl">provider in/out tokens</div>
      <div class="sub">total {escape(str(total_provider_tokens))}</div>
    </div>""",
            f"""    <div class="mcard">
      <div class="val">{escape(str(token_counting.get('status', 'estimated')))}</div>
      <div class="lbl">token counting mode</div>
      <div class="sub">{escape(str(token_counting.get('primary_method', 'char/4 heuristic')))} · {escape(str(token_counting.get('secondary_method', 'tokenizer unavailable')))}</div>
    </div>""",
        ]
    )

    score_rows = "\n".join(
        [
            f"          <tr><th>component</th><th>value</th></tr>",
            f"          <tr><td>task success</td><td>{format_num(scores.get('task_success', 0), 3)}</td></tr>",
            f"          <tr><td>constraint obedience</td><td>{format_num(scores.get('constraint_obedience', 0), 3)}</td></tr>",
            f"          <tr><td>verification</td><td>{format_num(scores.get('verification', 0), 3)}</td></tr>",
            f"          <tr><td>efficiency</td><td>{format_num(scores.get('efficiency', 0), 3)}</td></tr>",
            f"          <tr><td>episode score</td><td>{format_num(scores.get('episode_score', 0), 3)}</td></tr>",
        ]
    )

    selection_rows = "\n".join(
        [
            f"          <tr><th>field</th><th>value</th></tr>",
            f"          <tr><td>active tools</td><td>{escape(', '.join(tool_selection.get('active_tools', [])) or 'none')}</td></tr>",
            f"          <tr><td>expected tools</td><td>{escape(', '.join(tool_selection.get('expected_tools', [])) or 'none')}</td></tr>",
            f"          <tr><td>split config</td><td>{escape(split_summary)}</td></tr>",
            f"          <tr><td>token counting</td><td>{escape(str(token_counting.get('status', 'estimated')))} ({escape(str(token_counting.get('primary_method', 'char/4 heuristic')))}; {escape(str(token_counting.get('secondary_method', 'tokenizer unavailable')))})</td></tr>",
            f"          <tr><td>tool selection precision</td><td>{format_num(tool_selection.get('tool_selection_precision', 0), 3)}</td></tr>",
            f"          <tr><td>wrong tool calls</td><td>{escape(str(failures.get('wrong_tool_calls', 0)))}</td></tr>",
            f"          <tr><td>unnecessary tool calls</td><td>{escape(str(failures.get('unnecessary_tool_calls', 0)))}</td></tr>",
            f"          <tr><td>disallowed tool calls</td><td>{escape(str(failures.get('disallowed_tool_calls', 0)))}</td></tr>",
            f"          <tr><td>repeated bad tool calls</td><td>{escape(str(failures.get('repeated_bad_tool_calls', 0)))}</td></tr>",
            f"          <tr><td>false completion claims</td><td>{escape(str(failures.get('false_completion_claims', 0)))}</td></tr>",
            f"          <tr><td>token warning</td><td>{escape(str(token_counting.get('warning', 'none')))}</td></tr>",
            f"          <tr><td>failure reason</td><td>{escape(str(episode.get('failure_reason') or 'none'))}</td></tr>",
        ]
    )

    trace = episode.get("trace", [])
    context_labels = []
    context_values = []
    context_tokenizer_values = []
    context_measured_values = []
    for idx, entry in enumerate(trace, start=1):
        value = entry.get("context_tokens_estimate")
        if value is None:
            continue
        context_labels.append(f"{entry.get('type', 'step')} {idx}")
        context_values.append(int(value))
        context_tokenizer_values.append(
            int(entry.get("context_tokens_tokenizer"))
            if entry.get("context_tokens_tokenizer") is not None
            else None
        )
        context_measured_values.append(
            int(entry.get("context_tokens_measured"))
            if entry.get("context_tokens_measured") is not None
            else None
        )
    if not context_labels:
        context_labels = ["no-data"]
        context_values = [0]
        context_tokenizer_values = [None]
        context_measured_values = [None]

    vram_labels = []
    vram_values = []
    for idx, entry in enumerate(trace, start=1):
        hardware = entry.get("hardware_usage") or {}
        vram_peak = hardware.get("vram_peak_mb")
        if vram_peak is None:
            continue
        vram_labels.append(f"{entry.get('type', 'step')} {idx}")
        vram_values.append(int(vram_peak))
    if not vram_labels:
        vram_labels = ["no-data"]
        vram_values = [0]

    failure_labels = json.dumps(
        ["invalid", "retries", "exec fail", "denials", "synthetic", "bad finish", "repeat bad", "false done"]
    )
    failure_values = json.dumps(
        [
            int(failures.get("invalid_tool_calls", 0)),
            int(failures.get("retry_events", 0)),
            int(failures.get("execution_failures", 0)),
            int(failures.get("permission_denials", 0)),
            int(failures.get("synthetic_tool_results", 0)),
            int(failures.get("malformed_finish_events", 0)),
            int(failures.get("repeated_bad_tool_calls", 0)),
            int(failures.get("false_completion_claims", 0)),
        ]
    )

    version = _get_version()
    trace_rows = _build_agentic_trace_rows(trace)

    return AGENTIC_HTML_TEMPLATE.safe_substitute(
        model_name=escape(model_name),
        timestamp=escape(timestamp),
        cache_label=escape(str(cache_label)),
        workflow_title=escape(str(workflow_title)),
        session_mode=escape(str(session_mode)),
        outcome_cards=outcome_cards,
        resource_cards=resource_cards,
        score_rows=score_rows,
        selection_rows=selection_rows,
        trace_rows=trace_rows,
        context_labels=json.dumps(context_labels),
        context_values=json.dumps(context_values),
        context_tokenizer_values=json.dumps(context_tokenizer_values),
        context_tokenizer_label=escape(tokenizer_label_text),
        context_measured_values=json.dumps(context_measured_values),
        context_measured_label=escape(measured_label_text),
        failure_labels=failure_labels,
        failure_values=failure_values,
        vram_labels=json.dumps(vram_labels),
        vram_values=json.dumps(vram_values),
        version=escape(version),
    )


def build_agentic_suite_html(data):
    summary = data.get("summary", {})
    workflow_results = data.get("workflow_results", [])
    diagnostics = data.get("diagnostics", [])
    model_name = escape(str(data.get("model_id", "unknown model")))
    cache_label = escape(str(data.get("cache_label", "unknown")))
    session_mode = escape(str(data.get("session_mode", "unknown")))
    workflow_suite = escape(str(data.get("workflow_suite", "benchmark")))
    generated_at = data.get("generated_at", datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    derived = summary.get("derived_metrics", {})
    diagnostic_rows = "\n".join(
        f"<tr><td>{escape(item.get('workflow_id', 'unknown'))}</td><td>{format_num(item.get('workflow_score_mean', 0), 3)}</td><td>{escape(str(item.get('run_count', 0)))}</td></tr>"
        for item in diagnostics
    ) or "<tr><td colspan='3'>no diagnostics</td></tr>"
    workflow_rows = "\n".join(
        f"<tr><td>{escape(item.get('workflow_id', 'unknown'))}</td><td>{escape(item.get('benchmark_layer', 'unknown'))}</td><td>{escape(str(item.get('profile_id') or '-'))}</td><td>{format_num(item.get('workflow_score_mean', 0), 3)}</td><td>{format_num(item.get('workflow_score_stddev', 0), 3)}</td><td>{escape(', '.join(item.get('usability_flags', [])) or '-')}</td></tr>"
        for item in workflow_results
    )
    metric_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(json.dumps(value))}</td></tr>"
        for key, value in derived.items()
    )
    flags = ", ".join(summary.get("usability_flags", [])) or "none"
    version = _get_version()
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentic benchmark dashboard - {model_name}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; color: #202124; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.sub {{ color: #5f6368; margin-bottom: 18px; font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; margin-bottom: 18px; }}
.card {{ border: 1px solid #dadce0; border-radius: 10px; padding: 12px; background: #f8f9fa; }}
.val {{ font-size: 22px; font-weight: 700; }}
.lbl {{ font-size: 12px; color: #5f6368; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e0e0e0; font-size: 13px; vertical-align: top; }}
th {{ font-size: 12px; color: #5f6368; text-transform: uppercase; letter-spacing: 0.04em; }}
</style></head><body>
<h1>Agentic benchmark dashboard</h1>
<div class="sub">{model_name} · {escape(timestamp)} · cache {cache_label} · suite {workflow_suite} · session {session_mode}</div>
<div class="grid">
  <div class="card"><div class="val">{escape(str(summary.get('type', 'unknown')))}</div><div class="lbl">Type</div></div>
  <div class="card"><div class="val">{escape(str(summary.get('grade', 'unknown')))}</div><div class="lbl">Grade</div></div>
  <div class="card"><div class="val">{format_num(summary.get('core_score', 0), 3)}</div><div class="lbl">Core score</div></div>
  <div class="card"><div class="val">{format_num(summary.get('profile_score', 0), 3) if summary.get('profile_score') is not None else 'n/a'}</div><div class="lbl">Profile score</div></div>
  <div class="card"><div class="val">{format_num(summary.get('composite_score', 0), 3)}</div><div class="lbl">Composite score</div></div>
  <div class="card"><div class="val">{escape(flags)}</div><div class="lbl">Usability flags</div></div>
</div>
<h2>Diagnostics</h2>
<table><tr><th>Workflow</th><th>Mean score</th><th>Runs</th></tr>{diagnostic_rows}</table>
<h2>Workflow Results</h2>
<table><tr><th>Workflow</th><th>Layer</th><th>Profile</th><th>Mean</th><th>Stddev</th><th>Flags</th></tr>{workflow_rows}</table>
<h2>Derived Metrics</h2>
<table><tr><th>Metric</th><th>Value</th></tr>{metric_rows}</table>
<div style="color:#5f6368;font-size:12px;">generated by gnuckle {escape(version)}</div>
</body></html>"""


def _extract_agentic_metrics(data: dict) -> dict:
    """Pull comparable metrics from an agentic run summary."""
    if data.get("workflow_results"):
        summary = data.get("summary", {})
        workflow_results = data.get("workflow_results", [])
        total_workflows = len(workflow_results)
        vram_peaks = [
            float((item.get("runtime_metrics") or {}).get("vram_peak_mb_mean", 0) or 0)
            for item in workflow_results
        ]
        vram_steady = [
            float((item.get("runtime_metrics") or {}).get("vram_steady_mb_mean", 0) or 0)
            for item in workflow_results
        ]
        return {
            "wall_clock_s": 0.0,
            "avg_turn_latency_ms": 0.0,
            "vram_peak_mb": int(max(vram_peaks) if vram_peaks else 0),
            "vram_steady_mb": int(max(vram_steady) if vram_steady else 0),
            "episode_score": round(summary.get("composite_score", 0), 3),
            "task_completed": summary.get("grade") not in {"D", "F"},
            "verification_passed": True,
            "turns_used": total_workflows,
            "tool_calls_used": total_workflows,
            "peak_context_tokens": 0,
            "context_percent_used": None,
            "provider_total_tokens": 0,
            "cache_label": data.get("cache_label", "unknown"),
        }
    episode = (data.get("episodes") or [{}])[0]
    perf = episode.get("performance", {})
    scores = episode.get("scores", {})
    hw = episode.get("hardware_usage", {})
    token_usage = episode.get("token_usage", {})
    aggregate = data.get("aggregate", {})
    return {
        "wall_clock_s": round(perf.get("wall_clock_ms", 0) / 1000, 2),
        "avg_turn_latency_ms": round(perf.get("avg_turn_latency_ms", 0), 1),
        "vram_peak_mb": int(hw.get("vram_peak_mb", aggregate.get("vram_peak_mb", 0)) or 0),
        "vram_steady_mb": int(hw.get("vram_steady_mb", aggregate.get("vram_steady_mb", 0)) or 0),
        "episode_score": round(scores.get("episode_score", 0), 3),
        "task_completed": bool(episode.get("task_completed")),
        "verification_passed": bool(episode.get("verification_passed")),
        "turns_used": int(episode.get("turns_used", 0)),
        "tool_calls_used": int(episode.get("tool_calls_used", 0)),
        "peak_context_tokens": int(
            token_usage.get("context_tokens_measured")
            or token_usage.get("context_tokens_heuristic")
            or aggregate.get("peak_context_tokens_heuristic", 0)
            or 0
        ),
        "context_percent_used": token_usage.get("context_percent_used"),
        "provider_total_tokens": int(
            episode.get("provider_usage_total_tokens")
            or (episode.get("provider_usage") or {}).get("total_tokens", 0)
            or 0
        ),
        "cache_label": data.get("cache_label", "unknown"),
    }


AGENTIC_COMPARISON_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentic KV cache comparison - $model_name</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-sans); }
.dash { padding: 1rem 0; }
.header { margin-bottom: 1rem; }
.header h1 { font-size: 18px; font-weight: 600; color: var(--color-text-primary); }
.header .sub { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }
.section-label { font-size: 11px; font-weight: 500; color: var(--color-text-tertiary); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px; }
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 1rem; }
.chart-wrap { background: var(--color-background-secondary); border-radius: var(--border-radius-md); padding: 0.75rem 1rem; }
.chart-title { font-size: 12px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 2px; }
.chart-sub { font-size: 10px; color: var(--color-text-secondary); margin-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 1rem; }
th { text-align: left; font-weight: 500; color: var(--color-text-secondary); padding: 6px 8px; border-bottom: 1px solid var(--color-border-primary); }
td { padding: 6px 8px; color: var(--color-text-primary); border-bottom: 1px solid var(--color-border-secondary, rgba(128,128,128,0.1)); }
tr.best td { font-weight: 600; }
.footer { margin-top: 1rem; font-size: 10px; color: var(--color-text-tertiary); text-align: center; }
</style>
</head>
<body>
<div class="dash">
  <div class="header">
    <h1>agentic KV cache comparison</h1>
    <div class="sub">$model_name · $workflow_title · $cache_count cache types · $timestamp</div>
  </div>

  <div class="section-label">summary table</div>
  <table>
    <thead>
      <tr>
        <th>cache</th>
        <th>score</th>
        <th>completed</th>
        <th>verified</th>
        <th>turns</th>
        <th>tools</th>
        <th>wall (s)</th>
        <th>avg latency (ms)</th>
        <th>VRAM peak (MB)</th>
        <th>peak context</th>
        <th>provider tokens</th>
      </tr>
    </thead>
    <tbody>
$table_rows
    </tbody>
  </table>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">episode score by cache type</div>
      <div class="chart-sub">higher is better</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="scoreChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">wall clock time (seconds)</div>
      <div class="chart-sub">lower is better</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="wallChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">average turn latency (ms)</div>
      <div class="chart-sub">lower is better</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="latencyChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">VRAM peak (MB)</div>
      <div class="chart-sub">lower means more headroom</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="vramCompChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-grid">
    <div class="chart-wrap">
      <div class="chart-title">peak context tokens</div>
      <div class="chart-sub">token pressure at deepest point in the trace</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="contextCompChart"></canvas>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">provider tokens consumed</div>
      <div class="chart-sub">total input + output tokens reported by the server</div>
      <div style="position: relative; width: 100%; height: 220px;">
        <canvas id="providerChart"></canvas>
      </div>
    </div>
  </div>

  <div class="footer">generated by gnuckle $version</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const gridColor = 'rgba(128,128,128,0.12)';
const tickColor = '#888780';
const tickFont = { size: 10 };
const labels = $cache_labels;
const colors = $cache_colors;
const barOpts = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: tickColor, font: tickFont }, grid: { display: false } },
    y: { ticks: { color: tickColor, font: tickFont }, grid: { color: gridColor } }
  }
};
function makeBar(id, data) {
  new Chart(document.getElementById(id), {
    type: 'bar',
    data: { labels: labels, datasets: [{ data: data, backgroundColor: colors }] },
    options: barOpts
  });
}
makeBar('scoreChart', $score_values);
makeBar('wallChart', $wall_values);
makeBar('latencyChart', $latency_values);
makeBar('vramCompChart', $vram_comp_values);
makeBar('contextCompChart', $context_comp_values);
makeBar('providerChart', $provider_values);
</script>
</body>
</html>
"""
)


def build_agentic_comparison_html(by_cache: dict[str, dict]) -> str:
    """Build comparison HTML across multiple agentic cache-type runs."""
    ordered = ordered_cache_labels(by_cache.keys())
    metrics = {cache: _extract_agentic_metrics(by_cache[cache]) for cache in ordered}

    first = by_cache[ordered[0]]
    model_name = first.get("model_id", "unknown model")
    workflow = first.get("workflow", {})
    workflow_title = workflow.get("title", workflow.get("workflow_id", "unknown workflow"))
    generated_at = first.get("generated_at", datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    best_score = max(m["episode_score"] for m in metrics.values())
    table_rows = []
    for cache in ordered:
        m = metrics[cache]
        is_best = m["episode_score"] == best_score
        row_class = ' class="best"' if is_best else ""
        table_rows.append(
            f"      <tr{row_class}>"
            f"<td>{escape(cache)}</td>"
            f"<td>{format_num(m['episode_score'], 3)}</td>"
            f"<td>{'yes' if m['task_completed'] else 'no'}</td>"
            f"<td>{'yes' if m['verification_passed'] else 'no'}</td>"
            f"<td>{m['turns_used']}</td>"
            f"<td>{m['tool_calls_used']}</td>"
            f"<td>{format_num(m['wall_clock_s'], 2)}</td>"
            f"<td>{format_num(m['avg_turn_latency_ms'], 1)}</td>"
            f"<td>{m['vram_peak_mb']}</td>"
            f"<td>{m['peak_context_tokens']}</td>"
            f"<td>{m['provider_total_tokens']}</td>"
            f"</tr>"
        )

    cache_colors = [cache_color(c) for c in ordered]
    version = _get_version()

    return AGENTIC_COMPARISON_TEMPLATE.safe_substitute(
        model_name=escape(model_name),
        workflow_title=escape(str(workflow_title)),
        cache_count=str(len(ordered)),
        timestamp=escape(timestamp),
        table_rows="\n".join(table_rows),
        cache_labels=json.dumps(ordered),
        cache_colors=json.dumps(cache_colors),
        score_values=json.dumps([metrics[c]["episode_score"] for c in ordered]),
        wall_values=json.dumps([metrics[c]["wall_clock_s"] for c in ordered]),
        latency_values=json.dumps([metrics[c]["avg_turn_latency_ms"] for c in ordered]),
        vram_comp_values=json.dumps([metrics[c]["vram_peak_mb"] for c in ordered]),
        context_comp_values=json.dumps([metrics[c]["peak_context_tokens"] for c in ordered]),
        provider_values=json.dumps([metrics[c]["provider_total_tokens"] for c in ordered]),
        version=escape(version),
    )


def build_agentic_suite_html_modern(data: dict) -> str:
    summary = data.get("summary", {})
    workflow_results = data.get("workflow_results", [])
    diagnostics = data.get("diagnostics", [])
    model_name = escape(str(data.get("model_id", "unknown model")))
    cache_label = escape(str(data.get("cache_label", "unknown")))
    session_mode = escape(str(data.get("session_mode", "unknown")))
    workflow_suite = escape(str(data.get("workflow_suite", "benchmark")))
    generated_at = data.get("generated_at", datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    derived = summary.get("derived_metrics", {})
    diagnostic_rows = "\n".join(
        f"<tr><td>{escape(item.get('workflow_id', 'unknown'))}</td><td>{format_num(item.get('workflow_score_mean', 0), 3)}</td><td>{escape(str(item.get('run_count', 0)))}</td></tr>"
        for item in diagnostics
    ) or "<tr><td colspan='3'>no diagnostics</td></tr>"
    workflow_rows = []
    for item in workflow_results:
        mean = float(item.get("workflow_score_mean", 0) or 0)
        workflow_rows.append(
            "<tr>"
            f"<td><strong>{escape(item.get('workflow_id', 'unknown'))}</strong><div class='minor'>{escape(item.get('benchmark_layer', 'unknown'))} &middot; profile {escape(str(item.get('profile_id') or '-'))}</div></td>"
            f"<td>{format_num(mean, 3)}</td>"
            f"<td>{format_num(item.get('workflow_score_stddev', 0), 3)}</td>"
            f"<td><div class='mini-bar'><span style='width:{max(6, round(mean * 100))}%'></span></div></td>"
            f"<td>{escape(', '.join(item.get('usability_flags', [])) or 'clean')}</td>"
            "</tr>"
        )
    metric_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(json.dumps(value))}</td></tr>"
        for key, value in derived.items()
    ) or "<tr><td colspan='2'>no derived metrics</td></tr>"
    flags = summary.get("usability_flags", [])
    flag_badges = "".join(
        f"<span class='flag'>{escape(flag)}</span>" for flag in flags
    ) or "<span class='flag flag-ok'>no active usability flags</span>"
    diagnostics_strip = "".join(
        f"<div class='diag-pill'><strong>{escape(item.get('workflow_id', 'unknown'))}</strong><span>{format_num(item.get('workflow_score_mean', 0), 3)}</span></div>"
        for item in diagnostics
    ) or "<div class='diag-pill'><strong>none</strong><span>n/a</span></div>"
    version = _get_version()

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentic benchmark dashboard - {model_name}</title>
<style>
:root {{
  --paper: #fffdf8;
  --paper-2: #f8f3e8;
  --ink: #1b1b18;
  --muted: #6c685d;
  --line: rgba(34, 33, 28, 0.12);
  --accent: #174d3a;
  --shadow: 0 16px 40px rgba(36, 30, 18, 0.08);
  --radius: 18px;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background:
  radial-gradient(circle at top left, rgba(204,122,0,0.12), transparent 30%),
  linear-gradient(180deg, #f6f1e7 0%, #efe7d8 100%);
  color: var(--ink); font-family: Georgia, "Times New Roman", serif; }}
.dash {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
.hero {{ background: linear-gradient(135deg, rgba(23,77,58,0.96), rgba(52,36,15,0.92)); color: #f7f2e8; border-radius: 28px; padding: 28px; box-shadow: var(--shadow); margin-bottom: 18px; }}
.eyebrow {{ font: 600 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.78; margin-bottom: 10px; }}
.hero h1 {{ margin: 0; font-size: 34px; line-height: 1.05; }}
.hero .sub {{ margin-top: 10px; color: rgba(247,242,232,0.8); font: 500 13px/1.5 "Segoe UI", sans-serif; }}
.hero-grid, .metrics-grid, .panel-grid {{ display: grid; gap: 14px; }}
.hero-grid {{ grid-template-columns: 1.3fr 0.9fr; margin-top: 18px; }}
.metrics-grid {{ grid-template-columns: repeat(5, minmax(0,1fr)); margin-bottom: 18px; }}
.panel-grid {{ grid-template-columns: 1.15fr 1fr; }}
.card, .panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
.card {{ padding: 18px; }}
.panel {{ padding: 20px; }}
.metric {{ background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.16); border-radius: 18px; padding: 16px; }}
.metric .val {{ font-size: 28px; font-weight: 700; }}
.metric .lbl {{ margin-top: 4px; font: 500 11px/1.4 "Segoe UI", sans-serif; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(247,242,232,0.72); }}
.card .val {{ font-size: 28px; font-weight: 700; }}
.card .lbl {{ margin-top: 6px; color: var(--muted); font: 600 11px/1.3 "Segoe UI", sans-serif; text-transform: uppercase; letter-spacing: 0.08em; }}
.card .sub {{ margin-top: 6px; color: var(--muted); font: 500 12px/1.5 "Segoe UI", sans-serif; }}
.section-title {{ margin: 0 0 10px; font-size: 18px; }}
.section-sub {{ margin: 0 0 14px; color: var(--muted); font: 500 12px/1.5 "Segoe UI", sans-serif; }}
.flag-row, .diag-strip {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.flag {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 6px 10px; background: #f8dfc8; color: #7b3f00; font: 600 11px/1 "Segoe UI", sans-serif; }}
.flag-ok {{ background: #dff3e4; color: #1b7f3b; }}
.diag-pill {{ display: inline-flex; align-items: center; gap: 10px; padding: 10px 12px; background: var(--paper-2); border: 1px solid var(--line); border-radius: 14px; font: 600 12px/1.2 "Segoe UI", sans-serif; }}
.diag-pill span {{ color: var(--accent); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; }}
th {{ color: var(--muted); font: 700 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
td {{ font: 500 13px/1.45 "Segoe UI", sans-serif; }}
tr:last-child td {{ border-bottom: none; }}
.minor {{ margin-top: 3px; color: var(--muted); font-size: 11px; }}
.mini-bar {{ width: 100%; height: 10px; background: #ece4d5; border-radius: 999px; overflow: hidden; }}
.mini-bar span {{ display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #c98b2b, #174d3a); }}
.footer {{ margin-top: 16px; color: var(--muted); font: 500 11px/1.4 "Segoe UI", sans-serif; }}
@media (max-width: 1100px) {{
  .metrics-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
  .hero-grid, .panel-grid {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 680px) {{
  .dash {{ padding: 14px; }}
  .metrics-grid {{ grid-template-columns: 1fr; }}
}}
</style></head><body>
<div class="dash">
  <section class="hero">
    <div class="eyebrow">Agentic benchmark suite</div>
    <h1>{workflow_suite} on {cache_label}</h1>
    <div class="sub">{model_name} &middot; {escape(timestamp)} &middot; session {session_mode}</div>
    <div class="hero-grid">
      <div class="metric">
        <div class="val">{escape(str(summary.get('type', 'unknown')))} / {escape(str(summary.get('grade', 'unknown')))}</div>
        <div class="lbl">Type and grade</div>
      </div>
      <div class="metric">
        <div class="val">{format_num(summary.get('composite_score', 0), 3)}</div>
        <div class="lbl">Composite score</div>
      </div>
    </div>
  </section>
  <section class="metrics-grid">
    <div class="card"><div class="val">{format_num(summary.get('core_score', 0), 3)}</div><div class="lbl">Core score</div><div class="sub">Core battery average after diagnostics routing.</div></div>
    <div class="card"><div class="val">{format_num(summary.get('profile_score', 0), 3) if summary.get('profile_score') is not None else 'n/a'}</div><div class="lbl">Profile score</div><div class="sub">Life-mgmt profile score when profile workflows are active.</div></div>
    <div class="card"><div class="val">{len(workflow_results)}</div><div class="lbl">Workflows scored</div><div class="sub">Diagnostics are reported separately to keep routing visible.</div></div>
    <div class="card"><div class="val">{len(diagnostics)}</div><div class="lbl">Diagnostics</div><div class="sub">The three gate checks that decide the type ceiling.</div></div>
    <div class="card"><div class="val">{len(flags)}</div><div class="lbl">Usability flags</div><div class="sub">Operational warnings carried into the suite summary.</div></div>
  </section>
  <section class="panel-grid">
    <div class="panel">
      <h2 class="section-title">Usability flags</h2>
      <p class="section-sub">Flags stay exposed so the grade cannot hide operational problems.</p>
      <div class="flag-row">{flag_badges}</div>
    </div>
    <div class="panel">
      <h2 class="section-title">Diagnostic readout</h2>
      <p class="section-sub">Routing inputs shown as compact score pills.</p>
      <div class="diag-strip">{diagnostics_strip}</div>
    </div>
  </section>
  <section class="panel" style="margin-top:18px;">
    <h2 class="section-title">Diagnostics</h2>
    <p class="section-sub">Mean diagnostic score and run count for each gate check.</p>
    <table><tr><th>Workflow</th><th>Mean score</th><th>Runs</th></tr>{diagnostic_rows}</table>
  </section>
  <section class="panel" style="margin-top:18px;">
    <h2 class="section-title">Workflow results</h2>
    <p class="section-sub">Each workflow keeps its own mean, spread, and active flags. The bar is only a legibility aid.</p>
    <table><tr><th>Workflow</th><th>Mean</th><th>Stddev</th><th>Visual</th><th>Flags</th></tr>{''.join(workflow_rows) or "<tr><td colspan='5'>no workflow results</td></tr>"}</table>
  </section>
  <section class="panel" style="margin-top:18px;">
    <h2 class="section-title">Derived metrics</h2>
    <p class="section-sub">Suite-level metrics remain raw so weak spots are not smoothed over.</p>
    <table><tr><th>Metric</th><th>Value</th></tr>{metric_rows}</table>
  </section>
  <div class="footer">generated by gnuckle {escape(version)}</div>
</div>
</body></html>"""


def build_agentic_comparison_html_modern(by_cache: dict[str, dict]) -> str:
    ordered = ordered_cache_labels(by_cache.keys())
    first = by_cache[ordered[0]]
    model_name = escape(str(first.get("model_id", "unknown model")))
    workflow_suite = escape(str(first.get("workflow_suite", "benchmark")))
    generated_at = first.get("generated_at", datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    baseline = "f16" if "f16" in ordered else ordered[0]
    suite_summaries = {cache: by_cache[cache].get("summary", {}) for cache in ordered}
    baseline_summary = suite_summaries[baseline]

    workflow_ids = []
    for cache in ordered:
        for item in by_cache[cache].get("diagnostics", []):
            workflow_id = item.get("workflow_id", "unknown")
            if workflow_id not in workflow_ids:
                workflow_ids.append(workflow_id)
        for item in by_cache[cache].get("workflow_results", []):
            workflow_id = item.get("workflow_id", "unknown")
            if workflow_id not in workflow_ids:
                workflow_ids.append(workflow_id)

    workflow_maps = {
        cache: {
            item.get("workflow_id", "unknown"): item
            for item in (by_cache[cache].get("diagnostics", []) + by_cache[cache].get("workflow_results", []))
        }
        for cache in ordered
    }

    def workflow_score(cache: str, workflow_id: str):
        item = workflow_maps.get(cache, {}).get(workflow_id, {})
        value = item.get("workflow_score_mean")
        return None if value is None else float(value or 0)

    def workflow_vram(cache: str, workflow_id: str):
        item = workflow_maps.get(cache, {}).get(workflow_id, {})
        runtime = item.get("runtime_metrics") or {}
        value = runtime.get("vram_peak_mb_mean")
        return None if value is None else float(value or 0)

    def suite_vram_peak(cache: str):
        peaks = [
            float((item.get("runtime_metrics") or {}).get("vram_peak_mb_max", 0) or 0)
            for item in by_cache[cache].get("workflow_results", [])
        ]
        return max(peaks) if peaks else 0.0

    baseline_vram_peak = suite_vram_peak(baseline)
    leaderboard_rows = []
    for cache in ordered:
        summary = suite_summaries[cache]
        composite_delta = float(summary.get("composite_score", 0) or 0) - float(baseline_summary.get("composite_score", 0) or 0)
        vram_peak = suite_vram_peak(cache)
        vram_delta = vram_peak - baseline_vram_peak if baseline_vram_peak or vram_peak else None
        flag_text = ", ".join(summary.get("usability_flags", [])) or "clean"
        leaderboard_rows.append(
            "<tr>"
            f"<td><span class='cache-pill' style='--cache:{cache_color(cache)}'>{escape(cache)}</span></td>"
            f"<td>{escape(str(summary.get('type', 'unknown')))}</td>"
            f"<td>{escape(str(summary.get('grade', 'unknown')))}</td>"
            f"<td>{format_num(summary.get('composite_score', 0), 3)}</td>"
            f"<td class='{delta_class(composite_delta)}'>{format_delta(composite_delta)}</td>"
            f"<td>{format_num(summary.get('core_score', 0), 3)}</td>"
            f"<td>{format_num(summary.get('profile_score', 0), 3) if summary.get('profile_score') is not None else 'n/a'}</td>"
            f"<td>{format_num(vram_peak, 0) if vram_peak else 'n/a'}<div class='delta {delta_class(-vram_delta if vram_delta is not None else None)}'>{format_delta(vram_delta, 0) if vram_delta is not None else 'n/a'}</div></td>"
            f"<td>{escape(flag_text)}</td>"
            "</tr>"
        )

    workflow_rows = []
    max_spread = 0.0
    widest_workflow = "n/a"
    for workflow_id in workflow_ids:
        scores = [workflow_score(cache, workflow_id) for cache in ordered if workflow_score(cache, workflow_id) is not None]
        spread = (max(scores) - min(scores)) if scores else 0.0
        if spread > max_spread:
            max_spread = spread
            widest_workflow = workflow_id
        row_cells = [f"<td><strong>{escape(workflow_id)}</strong></td>"]
        baseline_score_for_workflow = workflow_score(baseline, workflow_id)
        for cache in ordered:
            score = workflow_score(cache, workflow_id)
            delta = None if baseline_score_for_workflow is None or score is None else score - baseline_score_for_workflow
            score_text = "n/a" if score is None else format_num(score, 3)
            cell_class = delta_class(delta)
            delta_text = "" if cache == baseline else f"<div class='delta {cell_class}'>{format_delta(delta)}</div>"
            row_cells.append(f"<td class='{cell_class}'>{score_text}{delta_text}</td>")
        row_cells.append(f"<td>{format_num(spread, 3)}</td>")
        workflow_rows.append("<tr>" + "".join(row_cells) + "</tr>")

    vram_missing = all(
        workflow_vram(cache, workflow_id) in (None, 0.0)
        for cache in ordered
        for workflow_id in workflow_ids
    )
    vram_datasets = [
        {
            "label": cache,
            "data": [workflow_vram(cache, workflow_id) for workflow_id in workflow_ids],
            "borderColor": cache_color(cache),
            "backgroundColor": "transparent",
            "borderWidth": 3 if cache == baseline else 2,
            "pointRadius": 2,
            "spanGaps": True,
            "tension": 0.25,
        }
        for cache in ordered
    ]

    best_cache = max(ordered, key=lambda cache: float(suite_summaries[cache].get("composite_score", 0) or 0))
    best_score = float(suite_summaries[best_cache].get("composite_score", 0) or 0)
    baseline_score = float(baseline_summary.get("composite_score", 0) or 0)
    turbo3_delta = None
    if "turbo3" in suite_summaries:
        turbo3_delta = float(suite_summaries["turbo3"].get("composite_score", 0) or 0) - baseline_score
    grade_line = " | ".join(f"{cache}:{suite_summaries[cache].get('grade', 'n/a')}" for cache in ordered)
    version = _get_version()

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>agentic benchmark dashboard - {model_name}</title>
<style>
:root {{
  --bg: #f3ece0;
  --paper: #fffdf8;
  --paper-2: #f6f0e3;
  --ink: #191814;
  --muted: #6b675c;
  --line: rgba(30, 26, 18, 0.12);
  --gold: #bb7a1c;
  --forest: #174d3a;
  --shadow: 0 18px 45px rgba(44, 34, 18, 0.08);
  --radius: 20px;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: var(--ink); background:
  radial-gradient(circle at top right, rgba(23,77,58,0.1), transparent 26%),
  radial-gradient(circle at left center, rgba(187,122,28,0.13), transparent 30%),
  linear-gradient(180deg, #f6f1e8 0%, #efe5d3 100%);
  font-family: Georgia, "Times New Roman", serif; }}
.dash {{ max-width: 1520px; margin: 0 auto; padding: 24px; }}
.hero {{ background: linear-gradient(140deg, rgba(18,64,49,0.98), rgba(56,38,14,0.94)); color: #f6f1e7; border-radius: 30px; padding: 28px; box-shadow: var(--shadow); margin-bottom: 18px; }}
.eyebrow {{ font: 600 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.78; margin-bottom: 10px; }}
.hero h1 {{ margin: 0; font-size: 40px; line-height: 1.02; }}
.hero .sub {{ margin-top: 10px; color: rgba(246,241,231,0.78); font: 500 13px/1.6 "Segoe UI", sans-serif; }}
.hero-grid, .stats-grid, .panel-grid {{ display: grid; gap: 14px; }}
.hero-grid {{ grid-template-columns: 1.3fr 0.9fr; margin-top: 20px; }}
.stats-grid {{ grid-template-columns: repeat(4, minmax(0,1fr)); margin-bottom: 18px; }}
.panel-grid {{ grid-template-columns: 1fr 1fr; }}
.hero-card, .card, .panel {{ border-radius: var(--radius); box-shadow: var(--shadow); }}
.hero-card {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.14); padding: 16px; }}
.hero-card .val {{ font-size: 30px; font-weight: 700; }}
.hero-card .lbl {{ margin-top: 4px; color: rgba(246,241,231,0.72); font: 600 11px/1.4 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
.card, .panel {{ background: var(--paper); border: 1px solid var(--line); }}
.card {{ padding: 18px; }}
.panel {{ padding: 20px; }}
.card .val {{ font-size: 28px; font-weight: 700; }}
.card .lbl {{ margin-top: 6px; color: var(--muted); font: 600 11px/1.3 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
.card .sub {{ margin-top: 6px; color: var(--muted); font: 500 12px/1.5 "Segoe UI", sans-serif; }}
.section-title {{ margin: 0 0 10px; font-size: 18px; }}
.section-sub {{ margin: 0 0 14px; color: var(--muted); font: 500 12px/1.5 "Segoe UI", sans-serif; }}
.callout {{ padding: 14px 16px; border-radius: 16px; background: var(--paper-2); border: 1px solid var(--line); font: 500 13px/1.6 "Segoe UI", sans-serif; color: var(--muted); }}
.callout strong {{ color: var(--ink); }}
.cache-pill {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: color-mix(in srgb, var(--cache) 12%, white); color: var(--ink); font: 700 11px/1 "Segoe UI", sans-serif; text-transform: uppercase; letter-spacing: 0.06em; }}
.cache-pill::before {{ content: ""; width: 9px; height: 9px; border-radius: 999px; background: var(--cache); }}
.delta {{ margin-top: 4px; font: 700 11px/1 "Segoe UI", sans-serif; }}
.delta-up {{ color: #1b7f3b; }}
.delta-down {{ color: #b42318; }}
.delta-flat {{ color: var(--muted); }}
.chart-panel {{ margin-top: 18px; }}
.chart-shell {{ position: relative; width: 100%; height: 360px; }}
.data-warning {{ margin-top: 10px; color: #7b3f00; font: 600 12px/1.5 "Segoe UI", sans-serif; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ color: var(--muted); font: 700 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
td {{ font: 500 13px/1.45 "Segoe UI", sans-serif; }}
tr:last-child td {{ border-bottom: none; }}
.matrix-wrap {{ overflow-x: auto; }}
.delta-up td, td.delta-up {{ background: rgba(27,127,59,0.06); }}
.delta-down td, td.delta-down {{ background: rgba(180,35,24,0.06); }}
.footer {{ margin-top: 16px; color: var(--muted); font: 500 11px/1.4 "Segoe UI", sans-serif; }}
@media (max-width: 1100px) {{
  .hero-grid, .panel-grid {{ grid-template-columns: 1fr; }}
  .stats-grid {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
}}
@media (max-width: 700px) {{
  .dash {{ padding: 14px; }}
  .stats-grid {{ grid-template-columns: 1fr; }}
}}
</style></head><body>
<div class="dash">
  <section class="hero">
    <div class="eyebrow">Agentic benchmark comparison</div>
    <h1>{workflow_suite}: f16 through turbo3</h1>
    <div class="sub">{model_name} &middot; {escape(timestamp)} &middot; baseline {escape(baseline)} &middot; {len(ordered)} cache variants</div>
    <div class="hero-grid">
      <div class="hero-card"><div class="val">{escape(best_cache)} at {format_num(best_score, 3)}</div><div class="lbl">Best composite score</div></div>
      <div class="hero-card"><div class="val">{format_delta(turbo3_delta) if turbo3_delta is not None else 'n/a'}</div><div class="lbl">Turbo3 delta vs {escape(baseline)}</div></div>
    </div>
  </section>
  <section class="stats-grid">
    <div class="card"><div class="val">{format_num(best_score - baseline_score, 3)}</div><div class="lbl">Gain over baseline</div><div class="sub">Best cache composite minus {escape(baseline)} composite.</div></div>
    <div class="card"><div class="val">{format_num(max(float(suite_summaries[c].get('composite_score', 0) or 0) for c in ordered) - min(float(suite_summaries[c].get('composite_score', 0) or 0) for c in ordered), 3)}</div><div class="lbl">Score spread</div><div class="sub">Wider spread means cache choice materially changes the benchmark result.</div></div>
    <div class="card"><div class="val">{escape(widest_workflow)}</div><div class="lbl">Widest workflow spread</div><div class="sub">Largest per-workflow variation across cache quants.</div></div>
    <div class="card"><div class="val">{grade_line}</div><div class="lbl">Grade ladder</div><div class="sub">Full grade snapshot, left to right in cache order.</div></div>
  </section>
  <section class="panel-grid">
    <div class="panel">
      <h2 class="section-title">Cache leaderboard</h2>
      <p class="section-sub">Overall suite scores and direct delta against the {escape(baseline)} baseline.</p>
      <table>
        <tr><th>Cache</th><th>Type</th><th>Grade</th><th>Composite</th><th>Delta vs {escape(baseline)}</th><th>Core</th><th>Profile</th><th>VRAM peak</th><th>Flags</th></tr>
        {''.join(leaderboard_rows)}
      </table>
    </div>
    <div class="panel">
      <h2 class="section-title">How to read this page</h2>
      <p class="section-sub">The benchmark result is no longer trapped in one cache at a time.</p>
      <div class="callout">
        <strong>Rows compare the suite output directly.</strong> The leaderboard shows whether a cache change improves or hurts the benchmark.
        <br><strong>The matrix below is the real audit surface.</strong> Each workflow cell shows the score for that cache, with a delta against <strong>{escape(baseline)}</strong>.
        <br><strong>Spread matters.</strong> If one workflow swings hard while the overall score looks similar, that is where the quant tradeoff is hiding.
      </div>
    </div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">VRAM load through all passes</h2>
    <p class="section-sub">Mean peak VRAM for each cache, drawn across benchmark pass order from diagnostics into the main workflow suite.</p>
    <div class="chart-shell"><canvas id="vramPassChart"></canvas></div>
    {"<div class='data-warning'>This saved run does not contain per-pass suite VRAM metrics. Re-run the benchmark with the updated scorer to populate this graph.</div>" if vram_missing else ""}
  </section>
  <section class="panel" style="margin-top:18px;">
    <h2 class="section-title">Workflow delta matrix</h2>
    <p class="section-sub">Every workflow score by cache, with per-cell difference against the {escape(baseline)} baseline.</p>
    <div class="matrix-wrap">
      <table>
        <tr><th>Workflow</th>{''.join(f'<th>{escape(cache)}</th>' for cache in ordered)}<th>Spread</th></tr>
        {''.join(workflow_rows) or "<tr><td colspan='99'>no workflow rows</td></tr>"}
      </table>
    </div>
  </section>
  <div class="footer">generated by gnuckle {escape(version)}</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const gridColor = 'rgba(107,103,92,0.16)';
const tickColor = '#6b675c';
const tickFont = {{ size: 10 }};
new Chart(document.getElementById('vramPassChart'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(workflow_ids)},
    datasets: {json.dumps(vram_datasets)}
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: true }} }},
    scales: {{
      x: {{
        ticks: {{ color: tickColor, font: tickFont, maxRotation: 45, minRotation: 45 }},
        grid: {{ color: gridColor }}
      }},
      y: {{
        ticks: {{ color: tickColor, font: tickFont }},
        grid: {{ color: gridColor }},
        title: {{ display: true, text: 'VRAM peak (MB)', color: tickColor, font: {{ size: 11 }} }}
      }}
    }}
  }}
}});
</script>
</body></html>"""


def build_session_comparison_html(by_cache: dict[str, dict]) -> str:
    ordered = ordered_cache_labels(by_cache.keys())
    first = by_cache[ordered[0]]
    meta = first.get("meta", {})
    model_name = escape(str(first.get("model_id", "unknown model")))
    benchmark_title = escape(str(meta.get("benchmark_title", meta.get("benchmark_id", "session benchmark"))))
    generated_at = meta.get("timestamp", datetime.now().isoformat())
    try:
        timestamp = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        timestamp = generated_at

    baseline = "f16" if "f16" in ordered else ordered[0]
    baseline_data = by_cache[baseline]
    baseline_agg = baseline_data.get("aggregate", {})
    benchmark_id = str(meta.get("benchmark_id", "session"))
    turns = first.get("turns", [])
    turn_labels = [str(turn.get("turn_id", turn.get("turn", "?"))) for turn in turns]

    def agg(cache: str) -> dict:
        return by_cache[cache].get("aggregate", {})

    def turn_metrics(turn: dict) -> dict:
        return turn.get("metrics") or {}

    def cumulative_token_series(cache: str) -> list[int | None]:
        running_total = 0
        values: list[int | None] = []
        for turn in by_cache[cache].get("turns", []):
            metrics = turn_metrics(turn)
            cumulative = metrics.get("provider_usage_cumulative_total")
            if cumulative is not None:
                try:
                    running_total = int(cumulative)
                except Exception:
                    running_total = running_total
                values.append(running_total)
                continue
            per_turn = metrics.get("provider_usage_total")
            if per_turn is None:
                values.append(None)
                continue
            try:
                running_total += int(per_turn)
            except Exception:
                values.append(None)
                continue
            values.append(running_total)
        return values

    def cache_turn_map(cache: str) -> dict:
        return {
            str(turn.get("turn_id", turn.get("turn", "?"))): turn
            for turn in by_cache[cache].get("turns", [])
        }

    turn_maps = {cache: cache_turn_map(cache) for cache in ordered}
    table_rows = []
    for cache in ordered:
        summary = agg(cache)
        avg_score = float(summary.get("average_score", 0) or 0)
        pass_rate = float(summary.get("pass_rate", 0) or 0)
        elapsed = float(summary.get("session_elapsed_s", 0) or 0)
        vram_peak = float(((summary.get("final_hardware") or {}).get("vram_peak_mb", 0)) or 0)
        total_tokens = int(summary.get("provider_usage_total_tokens", 0) or 0)
        delta_score = avg_score - float(baseline_agg.get("average_score", 0) or 0)
        table_rows.append(
            "<tr>"
            f"<td><span class='cache-pill' style='--cache:{cache_color(cache)}'>{escape(cache)}</span></td>"
            f"<td>{format_num(avg_score, 3)}</td>"
            f"<td>{format_pct(pass_rate * 100, 1)}</td>"
            f"<td>{int(summary.get('pass_count', 0) or 0)}/{int(meta.get('total_turns', 0) or len(turn_labels))}</td>"
            f"<td>{format_num(elapsed, 1)}</td>"
            f"<td>{format_num(total_tokens, 0)}</td>"
            f"<td>{format_num(vram_peak, 0)}</td>"
            f"<td class='{delta_class(delta_score)}'>{format_delta(delta_score)}</td>"
            "</tr>"
        )

    matrix_rows = []
    widest_turn = "n/a"
    max_spread = 0.0
    for turn_label in turn_labels:
        score_values = []
        row = [f"<td><strong>{escape(turn_label)}</strong></td>"]
        baseline_turn = turn_maps.get(baseline, {}).get(turn_label, {})
        baseline_score = (baseline_turn.get("scores") or {}).get("turn_score")
        for cache in ordered:
            turn = turn_maps.get(cache, {}).get(turn_label, {})
            score = (turn.get("scores") or {}).get("turn_score")
            if score is not None:
                score_values.append(float(score))
            delta = None if baseline_score is None or score is None else float(score) - float(baseline_score)
            cell_class = delta_class(delta)
            score_text = "n/a" if score is None else format_num(score, 3)
            delta_text = "" if cache == baseline else f"<div class='delta {cell_class}'>{format_delta(delta)}</div>"
            row.append(f"<td class='{cell_class}'>{score_text}{delta_text}</td>")
        spread = (max(score_values) - min(score_values)) if score_values else 0.0
        if spread > max_spread:
            max_spread = spread
            widest_turn = turn_label
        row.append(f"<td>{format_num(spread, 3)}</td>")
        matrix_rows.append("<tr>" + "".join(row) + "</tr>")

    vram_datasets = []
    ttft_datasets = []
    token_datasets = []
    ttft_token_datasets = []
    for cache in ordered:
        turns_for_cache = by_cache[cache].get("turns", [])
        cumulative_tokens = cumulative_token_series(cache)
        vram_datasets.append(
            {
                "label": cache,
                "data": [((turn_metrics(turn).get("hardware") or {}).get("vram_peak_mb")) for turn in turns_for_cache],
                "borderColor": cache_color(cache),
                "backgroundColor": "transparent",
                "borderWidth": 3 if cache == baseline else 2,
                "pointRadius": 2,
                "spanGaps": True,
                "tension": 0.25,
            }
        )
        ttft_datasets.append(
            {
                "label": cache,
                "data": [turn_metrics(turn).get("ttft_ms") for turn in turns_for_cache],
                "borderColor": cache_color(cache),
                "backgroundColor": "transparent",
                "borderWidth": 3 if cache == baseline else 2,
                "pointRadius": 2,
                "spanGaps": True,
                "tension": 0.25,
            }
        )
        token_datasets.append(
            {
                "label": cache,
                "data": cumulative_tokens,
                "borderColor": cache_color(cache),
                "backgroundColor": "transparent",
                "borderWidth": 3 if cache == baseline else 2,
                "pointRadius": 2,
                "spanGaps": True,
                "tension": 0.25,
            }
        )
        ttft_token_datasets.append(
            {
                "label": cache,
                "data": [
                    {
                        "x": cumulative_tokens[index] if index < len(cumulative_tokens) else None,
                        "y": turn_metrics(turn).get("ttft_ms"),
                    }
                    for index, turn in enumerate(turns_for_cache)
                    if (index < len(cumulative_tokens) and cumulative_tokens[index] is not None and turn_metrics(turn).get("ttft_ms") is not None)
                ],
                "borderColor": cache_color(cache),
                "backgroundColor": cache_color(cache),
                "pointRadius": 4 if cache == baseline else 3,
                "pointHoverRadius": 5,
                "showLine": False,
            }
        )

    best_cache = max(ordered, key=lambda cache: float(agg(cache).get("average_score", 0) or 0))
    version = _get_version()
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>session benchmark dashboard - {model_name}</title>
<style>
:root {{
  --paper: #fffdf8;
  --paper-2: #f6f0e3;
  --ink: #191814;
  --muted: #6b675c;
  --line: rgba(30, 26, 18, 0.12);
  --shadow: 0 18px 45px rgba(44, 34, 18, 0.08);
  --radius: 20px;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: var(--ink); background:
  radial-gradient(circle at top right, rgba(23,77,58,0.1), transparent 26%),
  radial-gradient(circle at left center, rgba(187,122,28,0.13), transparent 30%),
  linear-gradient(180deg, #f6f1e8 0%, #efe5d3 100%);
  font-family: Georgia, "Times New Roman", serif; }}
.dash {{ max-width: 1520px; margin: 0 auto; padding: 24px; }}
.hero {{ background: linear-gradient(140deg, rgba(18,64,49,0.98), rgba(56,38,14,0.94)); color: #f6f1e7; border-radius: 30px; padding: 28px; box-shadow: var(--shadow); margin-bottom: 18px; }}
.eyebrow {{ font: 600 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.78; margin-bottom: 10px; }}
.hero h1 {{ margin: 0; font-size: 40px; line-height: 1.02; }}
.hero .sub {{ margin-top: 10px; color: rgba(246,241,231,0.78); font: 500 13px/1.6 "Segoe UI", sans-serif; }}
.stats-grid, .panel-grid {{ display: grid; gap: 14px; }}
.stats-grid {{ grid-template-columns: repeat(4, minmax(0,1fr)); margin-bottom: 18px; }}
.panel-grid {{ grid-template-columns: 1fr 1fr; }}
.card, .panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
.card {{ padding: 18px; }}
.panel {{ padding: 20px; }}
.card .val {{ font-size: 28px; font-weight: 700; }}
.card .lbl {{ margin-top: 6px; color: var(--muted); font: 600 11px/1.3 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
.card .sub, .section-sub {{ margin-top: 6px; color: var(--muted); font: 500 12px/1.5 "Segoe UI", sans-serif; }}
.section-title {{ margin: 0 0 10px; font-size: 18px; }}
.cache-pill {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: color-mix(in srgb, var(--cache) 12%, white); color: var(--ink); font: 700 11px/1 "Segoe UI", sans-serif; text-transform: uppercase; letter-spacing: 0.06em; }}
.cache-pill::before {{ content: ""; width: 9px; height: 9px; border-radius: 999px; background: var(--cache); }}
.delta {{ margin-top: 4px; font: 700 11px/1 "Segoe UI", sans-serif; }}
.delta-up {{ color: #1b7f3b; }}
.delta-down {{ color: #b42318; }}
.delta-flat {{ color: var(--muted); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ color: var(--muted); font: 700 11px/1.2 "Segoe UI", sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }}
td {{ font: 500 13px/1.45 "Segoe UI", sans-serif; }}
tr:last-child td {{ border-bottom: none; }}
.matrix-wrap {{ overflow-x: auto; }}
.chart-panel {{ margin-top: 18px; }}
.chart-shell {{ position: relative; width: 100%; height: 320px; }}
td.delta-up {{ background: rgba(27,127,59,0.06); }}
td.delta-down {{ background: rgba(180,35,24,0.06); }}
.footer {{ margin-top: 16px; color: var(--muted); font: 500 11px/1.4 "Segoe UI", sans-serif; }}
@media (max-width: 1100px) {{ .stats-grid, .panel-grid {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<div class="dash">
  <section class="hero">
    <div class="eyebrow">Session benchmark comparison</div>
    <h1>{benchmark_title}</h1>
    <div class="sub">{model_name} &middot; {escape(timestamp)} &middot; benchmark {escape(benchmark_id)} &middot; baseline {escape(baseline)}</div>
  </section>
  <section class="stats-grid">
    <div class="card"><div class="val">{escape(best_cache)}</div><div class="lbl">Best cache</div><div class="sub">Highest average session score across compared quants.</div></div>
    <div class="card"><div class="val">{format_num(agg(best_cache).get('average_score', 0), 3)}</div><div class="lbl">Best average score</div><div class="sub">Session-wide average over all authored turns.</div></div>
    <div class="card"><div class="val">{widest_turn}</div><div class="lbl">Widest turn spread</div><div class="sub">Turn with the largest score variation across cache quants.</div></div>
    <div class="card"><div class="val">{int(meta.get('total_turns', len(turn_labels)) or len(turn_labels))}</div><div class="lbl">Turns in session</div><div class="sub">Persistent transcript depth for the stress run.</div></div>
  </section>
  <section class="panel-grid">
    <div class="panel">
      <h2 class="section-title">Cache leaderboard</h2>
      <p class="section-sub">Session score, pass rate, elapsed time, token use, and VRAM peak by quant.</p>
      <table>
        <tr><th>Cache</th><th>Avg score</th><th>Pass rate</th><th>Passes</th><th>Time (s)</th><th>Total tokens</th><th>VRAM peak</th><th>Delta vs {escape(baseline)}</th></tr>
        {''.join(table_rows)}
      </table>
    </div>
    <div class="panel">
      <h2 class="section-title">What happened</h2>
      <p class="section-sub">The folder was valid. The visualizer just did not recognize session benchmark filenames before this fix.</p>
      <p class="section-sub">This page now compares session runs the same way the other dashboards compare legacy and agentic outputs.</p>
    </div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">VRAM through session turns</h2>
    <p class="section-sub">Peak VRAM by turn across all compared cache quants.</p>
    <div class="chart-shell"><canvas id="vramTurnChart"></canvas></div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">TTFT through session turns</h2>
    <p class="section-sub">Time to first token by turn across all compared cache quants.</p>
    <div class="chart-shell"><canvas id="ttftTurnChart"></canvas></div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">Token count through session turns</h2>
    <p class="section-sub">Cumulative provider token usage as the persistent transcript grows.</p>
    <div class="chart-shell"><canvas id="tokenTurnChart"></canvas></div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">TTFT over total token use</h2>
    <p class="section-sub">Each point shows turn TTFT against cumulative session token usage for that cache quant.</p>
    <div class="chart-shell"><canvas id="ttftTokenChart"></canvas></div>
  </section>
  <section class="panel chart-panel">
    <h2 class="section-title">Turn score delta matrix</h2>
    <p class="section-sub">Every authored session turn, with score deltas against the {escape(baseline)} baseline.</p>
    <div class="matrix-wrap">
      <table>
        <tr><th>Turn</th>{''.join(f'<th>{escape(cache)}</th>' for cache in ordered)}<th>Spread</th></tr>
        {''.join(matrix_rows)}
      </table>
    </div>
  </section>
  <div class="footer">generated by gnuckle {escape(version)}</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const gridColor = 'rgba(107,103,92,0.16)';
const tickColor = '#6b675c';
const tickFont = {{ size: 10 }};
function makeLine(id, labels, datasets, yTitle) {{
  new Chart(document.getElementById(id), {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: true }} }},
      scales: {{
        x: {{ ticks: {{ color: tickColor, font: tickFont, maxRotation: 45, minRotation: 45 }}, grid: {{ color: gridColor }} }},
        y: {{ ticks: {{ color: tickColor, font: tickFont }}, grid: {{ color: gridColor }}, title: {{ display: true, text: yTitle, color: tickColor, font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}}
function makeScatter(id, datasets, xTitle, yTitle) {{
  new Chart(document.getElementById(id), {{
    type: 'scatter',
    data: {{ datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: true }} }},
      scales: {{
        x: {{ ticks: {{ color: tickColor, font: tickFont }}, grid: {{ color: gridColor }}, title: {{ display: true, text: xTitle, color: tickColor, font: {{ size: 11 }} }} }},
        y: {{ ticks: {{ color: tickColor, font: tickFont }}, grid: {{ color: gridColor }}, title: {{ display: true, text: yTitle, color: tickColor, font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}}
makeLine('vramTurnChart', {json.dumps(turn_labels)}, {json.dumps(vram_datasets)}, 'VRAM peak (MB)');
makeLine('ttftTurnChart', {json.dumps(turn_labels)}, {json.dumps(ttft_datasets)}, 'TTFT (ms)');
makeLine('tokenTurnChart', {json.dumps(turn_labels)}, {json.dumps(token_datasets)}, 'Cumulative tokens');
makeScatter('ttftTokenChart', {json.dumps(ttft_token_datasets)}, 'Cumulative tokens', 'TTFT (ms)');
</script>
</body></html>"""


def _get_version():
    try:
        from gnuckle import __version__

        return __version__
    except Exception:
        return "0.1.0"


def run_visualize(results_dir: str):
    """Main entry point for gnuckle visualize."""
    results_path = Path(results_dir)

    if not results_path.is_dir():
        print(f"  no folder: {results_path}")
        print("  run gnuckle benchmark first. get data. then draw.")
        sys.exit(1)

    resolved_results = _select_results_dir(results_path)
    if resolved_results is None:
        print(f"  no benchmark JSONs in: {results_path}")
        print("  folder empty. ape no draw nothing. run benchmark first.")
        sys.exit(1)
    if resolved_results != results_path:
        print(f"  ape choose run: {resolved_results.name}")
    results_path = resolved_results

    ape_print("loading")
    benchmark_mode = detect_benchmark_mode(results_path)
    if benchmark_mode == "agentic":
        agentic_by_cache = load_agentic_results(results_path)
        if not agentic_by_cache:
            print(f"  no agentic benchmark JSONs in: {results_path}")
            print("  folder empty. ape no draw nothing. run benchmark first.")
            sys.exit(1)
        print("  mode: agentic")
        print(f"  found {len(agentic_by_cache)} cache type(s): {', '.join(agentic_by_cache.keys())}")
        first_data = next(iter(agentic_by_cache.values()))
        print(f"  model: {first_data.get('model_id', 'unknown model')}")
        ape_print("loading")

        if len(agentic_by_cache) > 1:
            html = build_agentic_comparison_html_modern(agentic_by_cache)
            out_file = results_path / "agentic_benchmark_dashboard.html"
            detail_html = build_agentic_html(first_data)
            detail_file = results_path / "agentic_single_cache_dashboard.html"
            detail_file.write_text(detail_html, encoding="utf-8")
            comparison_html = build_agentic_comparison_html_modern(agentic_by_cache)
            comparison_file = results_path / "agentic_comparison_dashboard.html"
            comparison_file.write_text(comparison_html, encoding="utf-8")
            print(f"\n  comparison saved: {comparison_file}")
            print(f"  single-cache detail saved: {detail_file}")
            print(f"  {len(agentic_by_cache)} cache types compared. ape see the difference now. yes.")
        else:
            html = build_agentic_html(first_data)
            out_file = results_path / "agentic_benchmark_dashboard.html"
    elif benchmark_mode == "session":
        session_by_cache = load_session_results(results_path)
        if not session_by_cache:
            print(f"  no session benchmark JSONs in: {results_path}")
            print("  folder empty. ape no draw nothing. run benchmark first.")
            sys.exit(1)
        print("  mode: session")
        print(f"  found {len(session_by_cache)} cache type(s): {', '.join(session_by_cache.keys())}")
        first_data = next(iter(session_by_cache.values()))
        print(f"  benchmark: {first_data.get('meta', {}).get('benchmark_title', first_data.get('meta', {}).get('benchmark_id', 'unknown'))}")
        ape_print("loading")
        html = build_session_comparison_html(session_by_cache)
        out_file = results_path / "session_benchmark_dashboard.html"
    else:
        by_cache = load_results(results_path)

        if not by_cache:
            print(f"  no benchmark JSONs in: {results_path}")
            print("  folder empty. ape no draw nothing. run benchmark first.")
            sys.exit(1)

        first = next(iter(by_cache.values()))
        model_name = first.get("meta", {}).get("model", "unknown model")
        timestamp = first.get("meta", {}).get("timestamp", datetime.now().isoformat())
        prompt_tokens = first.get("meta", {}).get("system_prompt_tokens_heuristic", first.get("meta", {}).get("system_prompt_tokens_approx"))
        prompt_tokens_tokenizer = first.get("meta", {}).get("system_prompt_tokens_tokenizer")
        prompt_tokens_measured = first.get("meta", {}).get("system_prompt_tokens_measured")
        prompt_source = first.get("meta", {}).get("system_prompt_source", "unknown_prompt")
        tokenizer_label_text = first.get("meta", {}).get("tokenizer_label", "OpenAI cl100k_base")
        measured_label_text = first.get("meta", {}).get("measured_label", "llama.cpp exact")
        token_counting = first.get("meta", {}).get("token_counting", {})
        split_config = first.get("meta", {}).get("split_config", {})
        split_summary = f"split {split_config.get('split_mode', 'layer')} (main-gpu={split_config.get('main_gpu', 0)})"
        try:
            timestamp = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
        system_prompt_summary = (
            f"system prompt {prompt_source} ({format_token_triplet(prompt_tokens, prompt_tokens_tokenizer, tokenizer_label_text, prompt_tokens_measured, measured_label_text)}) · "
            f"{split_summary} · tokens {token_counting.get('status', 'estimated')} "
            f"({token_counting.get('primary_method', 'char/4 heuristic')}; {token_counting.get('secondary_method', 'tokenizer unavailable')}"
            f"{('; ' + token_counting.get('tertiary_method')) if token_counting.get('tertiary_method') else ''})"
        )

        print(f"  found {len(by_cache)} cache type(s): {', '.join(by_cache.keys())}")
        print(f"  model: {model_name}")
        ape_print("loading")

        html = build_html(by_cache, model_name, timestamp, system_prompt_summary=system_prompt_summary)
        out_file = results_path / "turboquant_benchmark_dashboard.html"

    out_file.write_text(html, encoding="utf-8")

    print(f"\n  dashboard saved: {out_file}")
    print("  open in browser. look at charts. yes. good.")
    return out_file
