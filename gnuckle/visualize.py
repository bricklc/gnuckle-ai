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

CACHE_COLORS = {
    "turbo3": "#3B6D11",
    "turbo4": "#2A8C4A",
    "q4_0": "#378ADD",
    "q8_0": "#888780",
    "f16": "#E24B4A",
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
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 8px; margin-bottom: 1.5rem; }
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
          <th>Gen tok/s (t1)</th>
          <th>Gen tok/s ($num_turns)</th>
          <th>Degradation</th>
          <th>TTFT t1 (ms)</th>
          <th>TTFT $num_turns (ms)</th>
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


def extract_metrics(data):
    """Pull summary metrics from a single cache type run."""
    turns = data.get("turns", [])
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
    ordered = [c for c in CACHE_ORDER if c in by_cache]
    ordered.extend(sorted(c for c in by_cache if c not in ordered))
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
      <div class="val">{format_num(hero_m["tps_t1"])}</div>
      <div class="lbl">tok/s {escape(hero)}</div>
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
        [(cache, CACHE_COLORS.get(cache, "#999999")) for cache in ordered]
    )
    vram_legend = degrad_legend
    ttft_legend = degrad_legend
    acc_legend = degrad_legend

    degrad_datasets = ",".join(
        line_dataset(cache, metrics[cache]["tps_all"][:num_turns], CACHE_COLORS.get(cache, "#999999"))
        for cache in ordered
    )
    ttft_datasets = ",".join(
        line_dataset(cache, metrics[cache]["ttft_all"][:num_turns], CACHE_COLORS.get(cache, "#999999"))
        for cache in ordered
    )

    vram_labels = json.dumps(ordered)
    vram_data = json.dumps([metrics[cache]["vram_peak"] for cache in ordered])
    vram_colors = json.dumps([CACHE_COLORS.get(cache, "#999999") for cache in ordered])

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
        f"backgroundColor:{json.dumps(CACHE_COLORS.get(cache, '#999999'))}"
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
          <td>{emphasis[0]}{format_num(float(COMPRESSION.get(cache, "1.0")), 1)}&times;{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["tps_t1"])}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["tps_tn"])}{emphasis[1]}</td>
          <td class="{deg_class(m['degradation'])}">{emphasis[0]}{format_pct(m["degradation"])}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["ttft_t1"], 0)}{emphasis[1]}</td>
          <td>{emphasis[0]}{format_num(m["ttft_tn"], 0)}{emphasis[1]}</td>
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

    ape_print("loading")
    by_cache = load_results(results_path)

    if not by_cache:
        print(f"  no benchmark JSONs in: {results_path}")
        print("  folder empty. ape no draw nothing. run benchmark first.")
        sys.exit(1)

    first = next(iter(by_cache.values()))
    model_name = first.get("meta", {}).get("model", "unknown model")
    timestamp = first.get("meta", {}).get("timestamp", datetime.now().isoformat())
    prompt_tokens = first.get("meta", {}).get("system_prompt_tokens_approx")
    prompt_source = first.get("meta", {}).get("system_prompt_source", "unknown_prompt")
    try:
        timestamp = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    if prompt_tokens:
        system_prompt_summary = f"system prompt {prompt_source} (~{prompt_tokens} tok)"
    else:
        system_prompt_summary = f"system prompt {prompt_source}"

    print(f"  found {len(by_cache)} cache type(s): {', '.join(by_cache.keys())}")
    print(f"  model: {model_name}")
    ape_print("loading")

    html = build_html(by_cache, model_name, timestamp, system_prompt_summary=system_prompt_summary)

    out_file = results_path / "turboquant_benchmark_dashboard.html"
    out_file.write_text(html, encoding="utf-8")

    print(f"\n  dashboard saved: {out_file}")
    print("  open in browser. look at charts. yes. good.")
