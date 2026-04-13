#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""
Generate an interactive HTML skill conversion comparison report.

Measures original and rebuilt skill directories, combines with LLM-generated
analysis (cuts, retained content, verdict), and renders a self-contained
HTML report showing the stark before/after comparison.

Usage:
  python3 generate-convert-report.py <original-path> <rebuilt-path> <analysis-json> [-o output.html] [--open]
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def measure_skill(skill_path: Path) -> dict:
    """Measure a skill directory or single file for lines, words, chars, sections, files."""
    total_lines = 0
    total_words = 0
    total_chars = 0
    total_sections = 0
    md_file_count = 0
    non_md_file_count = 0

    if skill_path.is_file():
        md_files = [skill_path]
    else:
        md_files = sorted(skill_path.rglob('*.md'))

    for f in md_files:
        content = f.read_text(encoding='utf-8')
        lines = content.splitlines()
        total_lines += len(lines)
        total_words += sum(len(line.split()) for line in lines)
        total_chars += len(content)
        total_sections += sum(1 for line in lines if line.startswith('## '))
        md_file_count += 1

    if skill_path.is_dir():
        for f in skill_path.rglob('*'):
            if f.is_file() and f.suffix != '.md':
                non_md_file_count += 1

    return {
        'lines': total_lines,
        'words': total_words,
        'chars': total_chars,
        'sections': total_sections,
        'files': md_file_count + non_md_file_count,
        'estimated_tokens': int(total_words * 1.3),
    }


def calculate_reductions(original: dict, rebuilt: dict) -> dict:
    """Calculate percentage reductions for each metric."""
    reductions = {}
    for key in ('lines', 'words', 'chars', 'sections', 'estimated_tokens'):
        orig_val = original.get(key, 0)
        new_val = rebuilt.get(key, 0)
        if orig_val > 0:
            reductions[key] = f'{round((1 - new_val / orig_val) * 100)}%'
        else:
            reductions[key] = 'N/A'
    return reductions


def build_report_data(original_metrics: dict, rebuilt_metrics: dict,
                      analysis: dict, reductions: dict) -> dict:
    """Assemble the full report data structure."""
    return {
        'meta': {
            'skill_name': analysis.get('skill_name', 'Unknown'),
            'original_source': analysis.get('original_source', ''),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        },
        'metrics': {
            'original': original_metrics,
            'rebuilt': rebuilt_metrics,
        },
        'reductions': reductions,
        'cuts': analysis.get('cuts', []),
        'retained': analysis.get('retained', []),
        'verdict': analysis.get('verdict', ''),
    }


# ── HTML Template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BMad Method &middot; Skill Conversion: SKILL_NAME</title>
<style>
:root {
  --bg: #0d1117; --surface: #161b22; --surface2: #21262d; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e; --text-dim: #6e7681;
  --critical: #f85149; --high: #f0883e; --medium: #d29922; --low: #58a6ff;
  --strength: #3fb950; --accent: #58a6ff; --accent-hover: #79c0ff;
  --purple: #a371f7;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #ffffff; --surface: #f6f8fa; --surface2: #eaeef2; --border: #d0d7de;
    --text: #1f2328; --text-muted: #656d76; --text-dim: #8c959f;
    --critical: #cf222e; --high: #bc4c00; --medium: #9a6700; --low: #0969da;
    --strength: #1a7f37; --accent: #0969da; --accent-hover: #0550ae;
    --purple: #8250df;
  }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; padding: 2rem; max-width: 900px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
.hero { text-align: center; padding: 2rem 1rem; margin-bottom: 1.5rem; border: 1px solid var(--border); border-radius: 0.75rem; background: var(--surface); }
.hero-pct { font-size: 4rem; font-weight: 800; color: var(--strength); line-height: 1; }
.hero-label { font-size: 1.1rem; color: var(--text-muted); margin-top: 0.25rem; }
.hero-sub { font-size: 0.9rem; color: var(--text-dim); margin-top: 0.5rem; }
.metrics-table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; }
.metrics-table th { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 2px solid var(--border); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
.metrics-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.95rem; }
.metrics-table .num { font-family: var(--mono); text-align: right; }
.metrics-table .reduction { font-weight: 700; color: var(--strength); text-align: right; }
.bar-cell { width: 30%; }
.bar-container { display: flex; height: 1.25rem; border-radius: 0.25rem; overflow: hidden; background: color-mix(in srgb, var(--critical) 15%, transparent); }
.bar-rebuilt { background: var(--strength); border-radius: 0.25rem 0 0 0.25rem; transition: width 0.3s; }
.section { border: 1px solid var(--border); border-radius: 0.5rem; margin: 0.75rem 0; overflow: hidden; }
.section-header { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; background: var(--surface); cursor: pointer; user-select: none; }
.section-header:hover { background: var(--surface2); }
.section-header .arrow { font-size: 0.7rem; transition: transform 0.15s; color: var(--text-muted); width: 1rem; }
.section-header.open .arrow { transform: rotate(90deg); }
.section-header .label { font-weight: 600; flex: 1; }
.section-body { display: none; }
.section-body.open { display: block; }
.cut-item { padding: 0.75rem 1rem; border-top: 1px solid var(--border); }
.cut-item:hover { background: var(--surface); }
.cut-category { font-weight: 600; font-size: 0.95rem; }
.cut-desc { font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem; }
.cut-examples { margin-top: 0.5rem; padding-left: 1.25rem; }
.cut-examples li { font-size: 0.85rem; color: var(--text-dim); padding: 0.1rem 0; }
.badge { display: inline-flex; align-items: center; padding: 0.15rem 0.5rem; border-radius: 2rem; font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem; }
.badge-high { background: color-mix(in srgb, var(--critical) 20%, transparent); color: var(--critical); }
.badge-medium { background: color-mix(in srgb, var(--medium) 20%, transparent); color: var(--medium); }
.badge-low { background: color-mix(in srgb, var(--low) 20%, transparent); color: var(--low); }
.retained-item { padding: 0.5rem 1rem; border-top: 1px solid var(--border); }
.retained-category { font-weight: 600; font-size: 0.9rem; color: var(--strength); }
.retained-desc { font-size: 0.85rem; color: var(--text-muted); }
.verdict { margin-top: 1.5rem; padding: 1.25rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--surface); font-size: 1rem; line-height: 1.6; color: var(--text); font-style: italic; }
.verdict::before { content: "Bottom line: "; font-weight: 700; font-style: normal; color: var(--purple); }
.footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-dim); text-align: center; }
</style>
</head>
<body>

<div style="color:var(--purple);font-size:0.8rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:0.25rem">BMad Method</div>
<h1>Skill Conversion: <span id="skill-name"></span></h1>
<div class="subtitle" id="subtitle"></div>

<div class="hero" id="hero"></div>

<table class="metrics-table">
  <thead>
    <tr>
      <th>Metric</th>
      <th class="num">Original</th>
      <th class="num">Rebuilt</th>
      <th class="num">Reduction</th>
      <th class="bar-cell">Comparison</th>
    </tr>
  </thead>
  <tbody id="metrics-body"></tbody>
</table>

<div id="cuts-section"></div>
<div id="retained-section"></div>
<div class="verdict" id="verdict"></div>

<div class="footer">
  Generated by <strong>BMad Workflow Builder</strong> &middot; <code>--convert</code>
</div>

<script>
const DATA = JSON.parse(document.getElementById('report-data').textContent);

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function fmt(n) { return typeof n === 'number' ? n.toLocaleString() : String(n); }

function init() {
  const m = DATA.meta;
  document.getElementById('skill-name').textContent = m.skill_name;
  const parts = [m.original_source, m.timestamp ? m.timestamp.split('T')[0] : ''].filter(Boolean);
  document.getElementById('subtitle').textContent = parts.join(' \u2022 ');

  // Hero — overall token reduction
  const tokenRed = DATA.reductions.estimated_tokens || DATA.reductions.words || '0%';
  const origTok = DATA.metrics.original.estimated_tokens || 0;
  const newTok = DATA.metrics.rebuilt.estimated_tokens || 0;
  document.getElementById('hero').innerHTML =
    '<div class="hero-pct">' + esc(tokenRed) + '</div>' +
    '<div class="hero-label">leaner</div>' +
    '<div class="hero-sub">' + fmt(origTok) + ' tokens \u2192 ' + fmt(newTok) + ' tokens</div>';

  // Metrics table
  var rows = [
    ['Lines', 'lines'], ['Words', 'words'], ['Characters', 'chars'],
    ['Sections', 'sections'], ['Files', 'files'], ['Est. Tokens', 'estimated_tokens']
  ];
  var tbody = '';
  rows.forEach(function(r) {
    var label = r[0], key = r[1];
    var orig = DATA.metrics.original[key] || 0;
    var rebuilt = DATA.metrics.rebuilt[key] || 0;
    var reduction = DATA.reductions[key] || (key === 'files' ? '' : 'N/A');
    var pct = orig > 0 ? (rebuilt / orig * 100) : 0;
    tbody += '<tr>';
    tbody += '<td>' + label + '</td>';
    tbody += '<td class="num">' + fmt(orig) + '</td>';
    tbody += '<td class="num">' + fmt(rebuilt) + '</td>';
    tbody += '<td class="reduction">' + (reduction || '') + '</td>';
    tbody += '<td class="bar-cell"><div class="bar-container">';
    tbody += '<div class="bar-rebuilt" style="width:' + pct.toFixed(1) + '%"></div>';
    tbody += '</div></td>';
    tbody += '</tr>';
  });
  document.getElementById('metrics-body').innerHTML = tbody;

  renderCuts();
  renderRetained();

  // Verdict
  var v = DATA.verdict || '';
  if (v) document.getElementById('verdict').appendChild(document.createTextNode(v));
  else document.getElementById('verdict').style.display = 'none';
}

function renderCuts() {
  var cuts = DATA.cuts || [];
  if (!cuts.length) return;
  var html = '<div class="section"><div class="section-header open" onclick="toggle(this)">';
  html += '<span class="arrow">&#9654;</span>';
  html += '<span class="label">What Was Cut (' + cuts.length + ' categories)</span>';
  html += '</div><div class="section-body open">';
  cuts.forEach(function(cut) {
    html += '<div class="cut-item">';
    var sev = cut.severity || 'medium';
    html += '<span class="badge badge-' + sev + '">' + esc(sev) + '</span>';
    html += '<span class="cut-category">' + esc(cut.category) + '</span>';
    html += '<div class="cut-desc">' + esc(cut.description) + '</div>';
    if (cut.examples && cut.examples.length) {
      html += '<ul class="cut-examples">';
      cut.examples.forEach(function(ex) { html += '<li>' + esc(ex) + '</li>'; });
      html += '</ul>';
    }
    html += '</div>';
  });
  html += '</div></div>';
  document.getElementById('cuts-section').innerHTML = html;
}

function renderRetained() {
  var items = DATA.retained || [];
  if (!items.length) return;
  var html = '<div class="section"><div class="section-header open" onclick="toggle(this)">';
  html += '<span class="arrow">&#9654;</span>';
  html += '<span class="label">What Survived (' + items.length + ' categories)</span>';
  html += '</div><div class="section-body open">';
  items.forEach(function(r) {
    html += '<div class="retained-item">';
    html += '<div class="retained-category">' + esc(r.category) + '</div>';
    html += '<div class="retained-desc">' + esc(r.description) + '</div>';
    html += '</div>';
  });
  html += '</div></div>';
  document.getElementById('retained-section').innerHTML = html;
}

function toggle(el) {
  el.classList.toggle('open');
  el.nextElementSibling.classList.toggle('open');
}

init();
</script>
</body>
</html>"""


def generate_html(report_data: dict) -> str:
    """Inject report data into the HTML template."""
    data_json = json.dumps(report_data, indent=None, ensure_ascii=False)
    data_tag = f'<script id="report-data" type="application/json">{data_json}</script>'
    html = HTML_TEMPLATE.replace(
        '<script>\nconst DATA',
        f'{data_tag}\n<script>\nconst DATA',
    )
    skill_name = report_data.get('meta', {}).get('skill_name', 'Unknown')
    html = html.replace('SKILL_NAME', html_lib.escape(skill_name))
    return html


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate an interactive HTML skill conversion comparison report',
    )
    parser.add_argument(
        'original_path',
        type=Path,
        help='Path to original skill (directory or single .md file)',
    )
    parser.add_argument(
        'rebuilt_path',
        type=Path,
        help='Path to rebuilt skill directory',
    )
    parser.add_argument(
        'analysis_json',
        type=Path,
        help='Path to LLM-generated convert-analysis.json',
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output HTML file path (default: <analysis-dir>/convert-report.html)',
    )
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open the HTML report in the default browser',
    )
    args = parser.parse_args()

    # Validate inputs
    for label, path in [('Original', args.original_path),
                        ('Rebuilt', args.rebuilt_path),
                        ('Analysis', args.analysis_json)]:
        if not path.exists():
            print(f'Error: {label} path not found: {path}', file=sys.stderr)
            return 2

    # Measure both skills
    original_metrics = measure_skill(args.original_path)
    rebuilt_metrics = measure_skill(args.rebuilt_path)
    reductions = calculate_reductions(original_metrics, rebuilt_metrics)

    # Load LLM analysis
    analysis = json.loads(args.analysis_json.read_text(encoding='utf-8'))

    # Build report data
    report_data = build_report_data(
        original_metrics, rebuilt_metrics, analysis, reductions,
    )

    # Save structured report data alongside analysis
    report_data_path = args.analysis_json.parent / 'convert-report-data.json'
    report_data_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    # Generate HTML
    html = generate_html(report_data)
    output_path = args.output or (args.analysis_json.parent / 'convert-report.html')
    output_path.write_text(html, encoding='utf-8')

    # Summary to stdout
    print(json.dumps({
        'html_report': str(output_path),
        'original': original_metrics,
        'rebuilt': rebuilt_metrics,
        'reductions': reductions,
    }))

    if args.open:
        system = platform.system()
        if system == 'Darwin':
            subprocess.run(['open', str(output_path)])
        elif system == 'Linux':
            subprocess.run(['xdg-open', str(output_path)])
        elif system == 'Windows':
            subprocess.run(['start', str(output_path)], shell=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
