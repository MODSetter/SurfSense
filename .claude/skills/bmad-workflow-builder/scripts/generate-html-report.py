# /// script
# requires-python = ">=3.9"
# ///

#!/usr/bin/env python3
"""
Generate an interactive HTML quality analysis report from report-data.json.

Reads the structured report data produced by the report creator and renders
a self-contained HTML report with:
  - Grade + narrative at top
  - Broken items with fix prompts
  - Opportunity themes with "Fix This Theme" prompt generation
  - Expandable strengths
  - Expandable detailed analysis per dimension
  - Link to full markdown report

Usage:
  python3 generate-html-report.py {quality-report-dir} [--open]
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path


def load_report_data(report_dir: Path) -> dict:
    """Load report-data.json from the report directory."""
    data_file = report_dir / 'report-data.json'
    if not data_file.exists():
        print(f'Error: {data_file} not found', file=sys.stderr)
        sys.exit(2)
    return json.loads(data_file.read_text(encoding='utf-8'))


def build_fix_prompt(skill_path: str, theme: dict) -> str:
    """Build a coherent fix prompt for an entire opportunity theme."""
    prompt = f"## Task: {theme['name']}\n"
    prompt += f"Skill path: {skill_path}\n\n"
    prompt += f"### Problem\n{theme['description']}\n\n"
    prompt += f"### Fix\n{theme['action']}\n\n"
    if theme.get('findings'):
        prompt += "### Specific observations to address:\n\n"
        for i, f in enumerate(theme['findings'], 1):
            loc = f"{f['file']}:{f['line']}" if f.get('file') and f.get('line') else f.get('file', '')
            prompt += f"{i}. **{f['title']}**"
            if loc:
                prompt += f" ({loc})"
            if f.get('detail'):
                prompt += f"\n   {f['detail']}"
            prompt += "\n"
    return prompt.strip()


def build_broken_prompt(skill_path: str, items: list) -> str:
    """Build a fix prompt for all broken items."""
    prompt = f"## Task: Fix Critical Issues\nSkill path: {skill_path}\n\n"
    for i, item in enumerate(items, 1):
        loc = f"{item['file']}:{item['line']}" if item.get('file') and item.get('line') else item.get('file', '')
        prompt += f"{i}. **[{item.get('severity','high').upper()}] {item['title']}**\n"
        if loc:
            prompt += f"   File: {loc}\n"
        if item.get('detail'):
            prompt += f"   Context: {item['detail']}\n"
        if item.get('action'):
            prompt += f"   Fix: {item['action']}\n"
        prompt += "\n"
    return prompt.strip()


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BMad Method · Quality Analysis: SKILL_NAME</title>
<style>
:root {
  --bg: #0d1117; --surface: #161b22; --surface2: #21262d; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e; --text-dim: #6e7681;
  --critical: #f85149; --high: #f0883e; --medium: #d29922; --low: #58a6ff;
  --strength: #3fb950; --suggestion: #a371f7;
  --accent: #58a6ff; --accent-hover: #79c0ff;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #ffffff; --surface: #f6f8fa; --surface2: #eaeef2; --border: #d0d7de;
    --text: #1f2328; --text-muted: #656d76; --text-dim: #8c959f;
    --critical: #cf222e; --high: #bc4c00; --medium: #9a6700; --low: #0969da;
    --strength: #1a7f37; --suggestion: #8250df;
    --accent: #0969da; --accent-hover: #0550ae;
  }
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; padding: 2rem; max-width: 900px; margin: 0 auto; }
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
.subtitle a { color: var(--accent); text-decoration: none; }
.subtitle a:hover { text-decoration: underline; }
.grade { font-size: 2.5rem; font-weight: 700; margin: 0.5rem 0; }
.grade-Excellent { color: var(--strength); }
.grade-Good { color: var(--low); }
.grade-Fair { color: var(--medium); }
.grade-Poor { color: var(--critical); }
.narrative { color: var(--text-muted); font-size: 0.95rem; margin-bottom: 1.5rem; line-height: 1.6; }
.badge { display: inline-flex; align-items: center; padding: 0.15rem 0.5rem; border-radius: 2rem; font-size: 0.75rem; font-weight: 600; }
.badge-critical { background: color-mix(in srgb, var(--critical) 20%, transparent); color: var(--critical); }
.badge-high { background: color-mix(in srgb, var(--high) 20%, transparent); color: var(--high); }
.badge-medium { background: color-mix(in srgb, var(--medium) 20%, transparent); color: var(--medium); }
.badge-low { background: color-mix(in srgb, var(--low) 20%, transparent); color: var(--low); }
.badge-strength { background: color-mix(in srgb, var(--strength) 20%, transparent); color: var(--strength); }
.section { border: 1px solid var(--border); border-radius: 0.5rem; margin: 0.75rem 0; overflow: hidden; }
.section-header { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; background: var(--surface); cursor: pointer; user-select: none; }
.section-header:hover { background: var(--surface2); }
.section-header .arrow { font-size: 0.7rem; transition: transform 0.15s; color: var(--text-muted); width: 1rem; }
.section-header.open .arrow { transform: rotate(90deg); }
.section-header .label { font-weight: 600; flex: 1; }
.section-header .count { font-size: 0.8rem; color: var(--text-muted); }
.section-header .actions { display: flex; gap: 0.5rem; }
.section-body { display: none; }
.section-body.open { display: block; }
.item { padding: 0.75rem 1rem; border-top: 1px solid var(--border); }
.item:hover { background: var(--surface); }
.item-title { font-weight: 600; font-size: 0.9rem; }
.item-file { font-family: var(--mono); font-size: 0.75rem; color: var(--text-muted); }
.item-desc { font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem; }
.item-action { font-size: 0.85rem; margin-top: 0.25rem; }
.item-action strong { color: var(--strength); }
.opp { padding: 1rem; border-top: 1px solid var(--border); }
.opp-header { display: flex; align-items: center; gap: 0.75rem; }
.opp-name { font-weight: 600; font-size: 1rem; flex: 1; }
.opp-count { font-size: 0.8rem; color: var(--text-muted); }
.opp-desc { font-size: 0.9rem; color: var(--text-muted); margin: 0.5rem 0; }
.opp-impact { font-size: 0.85rem; color: var(--text-dim); font-style: italic; }
.opp-findings { margin-top: 0.75rem; padding-left: 1rem; border-left: 2px solid var(--border); display: none; }
.opp-findings.open { display: block; }
.opp-finding { font-size: 0.85rem; padding: 0.25rem 0; color: var(--text-muted); }
.opp-finding .source { font-size: 0.75rem; color: var(--text-dim); }
.btn { background: none; border: 1px solid var(--border); border-radius: 0.25rem; padding: 0.3rem 0.7rem; cursor: pointer; color: var(--text-muted); font-size: 0.8rem; transition: all 0.15s; }
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 600; }
.btn-primary:hover { background: var(--accent-hover); }
.btn.copied { border-color: var(--strength); color: var(--strength); }
.strength-item { padding: 0.5rem 1rem; border-top: 1px solid var(--border); }
.strength-item .title { font-weight: 600; font-size: 0.9rem; color: var(--strength); }
.strength-item .detail { font-size: 0.85rem; color: var(--text-muted); }
.analysis-section { padding: 0.75rem 1rem; border-top: 1px solid var(--border); }
.analysis-section h4 { font-size: 0.9rem; margin-bottom: 0.25rem; }
.analysis-section p { font-size: 0.85rem; color: var(--text-muted); }
.analysis-finding { font-size: 0.85rem; padding: 0.25rem 0 0.25rem 1rem; border-left: 2px solid var(--border); margin: 0.25rem 0; color: var(--text-muted); }
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; align-items: center; justify-content: center; }
.modal-overlay.visible { display: flex; }
.modal { background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1.5rem; width: 90%; max-width: 700px; max-height: 80vh; overflow-y: auto; }
.modal h3 { margin-bottom: 0.75rem; }
.modal pre { background: var(--bg); border: 1px solid var(--border); border-radius: 0.375rem; padding: 1rem; font-family: var(--mono); font-size: 0.8rem; white-space: pre-wrap; word-wrap: break-word; max-height: 50vh; overflow-y: auto; }
.modal-actions { display: flex; gap: 0.75rem; margin-top: 1rem; justify-content: flex-end; }
.recs { padding: 0.75rem 1rem; border-top: 1px solid var(--border); }
.rec { padding: 0.3rem 0; font-size: 0.9rem; }
.rec-rank { font-weight: 700; color: var(--accent); margin-right: 0.5rem; }
.rec-resolves { font-size: 0.8rem; color: var(--text-dim); }
</style>
</head>
<body>

<div style="color:#a371f7;font-size:0.8rem;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:0.25rem">BMad Method</div>
<h1>Quality Analysis: <span id="skill-name"></span></h1>
<div class="subtitle" id="subtitle"></div>

<div id="grade-area"></div>
<div class="narrative" id="narrative"></div>

<div id="broken-section"></div>
<div id="opportunities-section"></div>
<div id="strengths-section"></div>
<div id="recommendations-section"></div>
<div id="detailed-section"></div>

<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <h3 id="modal-title">Generated Prompt</h3>
    <pre id="modal-content"></pre>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">Close</button>
      <button class="btn btn-primary" onclick="copyModal()">Copy to Clipboard</button>
    </div>
  </div>
</div>

<script>
const RAW = JSON.parse(document.getElementById('report-data').textContent);
const DATA = normalize(RAW);

function normalize(d) {
  // Fix meta field variants
  if (d.meta) {
    d.meta.skill_name = d.meta.skill_name || d.meta.skill || d.meta.name || 'Unknown';
    d.meta.scanner_count = typeof d.meta.scanner_count === 'number' ? d.meta.scanner_count
      : Array.isArray(d.meta.scanners_run) ? d.meta.scanners_run.length
      : d.meta.scanner_count || 0;
  }
  // Fix strengths: plain strings → objects
  d.strengths = (d.strengths || []).map(s =>
    typeof s === 'string' ? { title: s, detail: '' } : { title: s.title || '', detail: s.detail || '' }
  );
  // Fix opportunities: title→name, findings_resolved→findings
  (d.opportunities || []).forEach(o => {
    o.name = o.name || o.title || '';
    o.finding_count = o.finding_count || (o.findings || o.findings_resolved || []).length;
    if (!o.findings && o.findings_resolved) o.findings = [];
    o.action = o.action || o.fix || '';
  });
  // Fix broken: description→detail, fix→action
  (d.broken || []).forEach(b => {
    b.detail = b.detail || b.description || '';
    b.action = b.action || b.fix || '';
  });
  // Fix recommendations: description→action
  (d.recommendations || []).forEach((r, i) => {
    r.action = r.action || r.description || '';
    r.rank = r.rank || i + 1;
  });
  // Fix journeys: persona→archetype, friction→friction_points
  if (d.detailed_analysis && d.detailed_analysis.experience) {
    d.detailed_analysis.experience.journeys = (d.detailed_analysis.experience.journeys || []).map(j => ({
      archetype: j.archetype || j.persona || j.name || 'Unknown',
      summary: j.summary || j.journey_summary || j.description || j.friction || '',
      friction_points: j.friction_points || (j.friction ? [j.friction] : []),
      bright_spots: j.bright_spots || (j.bright ? [j.bright] : [])
    }));
  }
  return d;
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function init() {
  const m = DATA.meta;
  document.getElementById('skill-name').textContent = m.skill_name;
  document.getElementById('subtitle').innerHTML =
    `${esc(m.skill_path)} &bull; ${m.timestamp ? m.timestamp.split('T')[0] : ''} &bull; ${m.scanner_count || 0} scanners &bull; <a href="quality-report.md">Full Report &nearr;</a>`;

  document.getElementById('grade-area').innerHTML =
    `<div class="grade grade-${DATA.grade}">${esc(DATA.grade)}</div>`;
  document.getElementById('narrative').textContent = DATA.narrative || '';

  renderBroken();
  renderOpportunities();
  renderStrengths();
  renderRecommendations();
  renderDetailed();
}

function renderBroken() {
  const items = DATA.broken || [];
  if (!items.length) return;
  let html = `<div class="section"><div class="section-header open" onclick="toggleSection(this)">`;
  html += `<span class="arrow">&#9654;</span><span class="label">Broken / Critical (${items.length})</span>`;
  html += `<div class="actions"><button class="btn btn-primary" onclick="event.stopPropagation();showBrokenPrompt()">Fix These</button></div>`;
  html += `</div><div class="section-body open">`;
  items.forEach(item => {
    const loc = item.file ? `${item.file}${item.line ? ':'+item.line : ''}` : '';
    html += `<div class="item">`;
    html += `<span class="badge badge-${item.severity || 'high'}">${esc(item.severity || 'high')}</span> `;
    if (loc) html += `<span class="item-file">${esc(loc)}</span>`;
    html += `<div class="item-title">${esc(item.title)}</div>`;
    if (item.detail) html += `<div class="item-desc">${esc(item.detail)}</div>`;
    if (item.action) html += `<div class="item-action"><strong>Fix:</strong> ${esc(item.action)}</div>`;
    html += `</div>`;
  });
  html += `</div></div>`;
  document.getElementById('broken-section').innerHTML = html;
}

function renderOpportunities() {
  const opps = DATA.opportunities || [];
  if (!opps.length) return;
  let html = `<div class="section"><div class="section-header open" onclick="toggleSection(this)">`;
  html += `<span class="arrow">&#9654;</span><span class="label">Opportunities (${opps.length})</span>`;
  html += `</div><div class="section-body open">`;
  opps.forEach((opp, idx) => {
    html += `<div class="opp">`;
    html += `<div class="opp-header">`;
    html += `<span class="badge badge-${opp.severity || 'medium'}">${esc(opp.severity || 'medium')}</span>`;
    html += `<span class="opp-name">${idx+1}. ${esc(opp.name)}</span>`;
    html += `<span class="opp-count">${opp.finding_count || (opp.findings||[]).length} observations</span>`;
    html += `<button class="btn" onclick="toggleFindings(${idx})">Details</button>`;
    html += `<button class="btn btn-primary" onclick="showThemePrompt(${idx})">Fix This</button>`;
    html += `</div>`;
    html += `<div class="opp-desc">${esc(opp.description)}</div>`;
    if (opp.impact) html += `<div class="opp-impact">Impact: ${esc(opp.impact)}</div>`;
    html += `<div class="opp-findings" id="findings-${idx}">`;
    (opp.findings || []).forEach(f => {
      const loc = f.file ? `${f.file}${f.line ? ':'+f.line : ''}` : '';
      html += `<div class="opp-finding">`;
      html += `<strong>${esc(f.title)}</strong>`;
      if (loc) html += ` <span class="item-file">${esc(loc)}</span>`;
      if (f.source) html += ` <span class="source">[${esc(f.source)}]</span>`;
      if (f.detail) html += `<br>${esc(f.detail)}`;
      html += `</div>`;
    });
    html += `</div></div>`;
  });
  html += `</div></div>`;
  document.getElementById('opportunities-section').innerHTML = html;
}

function renderStrengths() {
  const items = DATA.strengths || [];
  if (!items.length) return;
  let html = `<div class="section"><div class="section-header" onclick="toggleSection(this)">`;
  html += `<span class="arrow">&#9654;</span><span class="label">Strengths (${items.length})</span>`;
  html += `</div><div class="section-body">`;
  items.forEach(s => {
    html += `<div class="strength-item"><div class="title">${esc(s.title)}</div>`;
    if (s.detail) html += `<div class="detail">${esc(s.detail)}</div>`;
    html += `</div>`;
  });
  html += `</div></div>`;
  document.getElementById('strengths-section').innerHTML = html;
}

function renderRecommendations() {
  const recs = DATA.recommendations || [];
  if (!recs.length) return;
  let html = `<div class="section"><div class="section-header open" onclick="toggleSection(this)">`;
  html += `<span class="arrow">&#9654;</span><span class="label">Recommendations</span>`;
  html += `</div><div class="section-body open"><div class="recs">`;
  recs.forEach(r => {
    html += `<div class="rec">`;
    html += `<span class="rec-rank">#${r.rank}</span>`;
    html += `${esc(r.action)}`;
    if (r.resolves) html += ` <span class="rec-resolves">(resolves ${r.resolves} observations)</span>`;
    html += `</div>`;
  });
  html += `</div></div></div>`;
  document.getElementById('recommendations-section').innerHTML = html;
}

function renderDetailed() {
  const da = DATA.detailed_analysis;
  if (!da) return;
  const dims = [
    ['structure', 'Structure & Integrity'],
    ['craft', 'Craft & Writing Quality'],
    ['cohesion', 'Cohesion & Design'],
    ['efficiency', 'Execution Efficiency'],
    ['experience', 'User Experience'],
    ['scripts', 'Script Opportunities']
  ];
  let html = `<div class="section"><div class="section-header" onclick="toggleSection(this)">`;
  html += `<span class="arrow">&#9654;</span><span class="label">Detailed Analysis</span>`;
  html += `</div><div class="section-body">`;
  dims.forEach(([key, label]) => {
    const dim = da[key];
    if (!dim) return;
    html += `<div class="analysis-section"><h4>${label}</h4>`;
    if (dim.assessment) html += `<p>${esc(dim.assessment)}</p>`;
    if (dim.dimensions) {
      html += `<table style="width:100%;font-size:0.85rem;margin:0.5rem 0;border-collapse:collapse;">`;
      html += `<tr><th style="text-align:left;padding:0.3rem;border-bottom:1px solid var(--border)">Dimension</th><th style="text-align:left;padding:0.3rem;border-bottom:1px solid var(--border)">Score</th><th style="text-align:left;padding:0.3rem;border-bottom:1px solid var(--border)">Notes</th></tr>`;
      Object.entries(dim.dimensions).forEach(([d, v]) => {
        if (v && typeof v === 'object') {
          html += `<tr><td style="padding:0.3rem;border-bottom:1px solid var(--border)">${esc(d.replace(/_/g,' '))}</td><td style="padding:0.3rem;border-bottom:1px solid var(--border)">${esc(v.score||'')}</td><td style="padding:0.3rem;border-bottom:1px solid var(--border)">${esc(v.notes||'')}</td></tr>`;
        }
      });
      html += `</table>`;
    }
    if (dim.journeys && dim.journeys.length) {
      dim.journeys.forEach(j => {
        html += `<div style="margin:0.5rem 0"><strong>${esc(j.archetype)}</strong>: ${esc(j.summary || j.journey_summary || '')}`;
        if (j.friction_points && j.friction_points.length) {
          html += `<ul style="color:var(--high);font-size:0.85rem;padding-left:1.25rem">`;
          j.friction_points.forEach(fp => { html += `<li>${esc(fp)}</li>`; });
          html += `</ul>`;
        }
        html += `</div>`;
      });
    }
    if (dim.autonomous) {
      const a = dim.autonomous;
      html += `<p><strong>Headless Potential:</strong> ${esc(a.potential||'')}`;
      if (a.notes) html += ` — ${esc(a.notes)}`;
      html += `</p>`;
    }
    (dim.findings || []).forEach(f => {
      const loc = f.file ? `${f.file}${f.line ? ':'+f.line : ''}` : '';
      html += `<div class="analysis-finding">`;
      if (f.severity) html += `<span class="badge badge-${f.severity}">${esc(f.severity)}</span> `;
      html += `${esc(f.title)}`;
      if (loc) html += ` <span class="item-file">${esc(loc)}</span>`;
      html += `</div>`;
    });
    html += `</div>`;
  });
  html += `</div></div>`;
  document.getElementById('detailed-section').innerHTML = html;
}

// --- Interactions ---
function toggleSection(el) {
  el.classList.toggle('open');
  el.nextElementSibling.classList.toggle('open');
}

function toggleFindings(idx) {
  document.getElementById('findings-'+idx).classList.toggle('open');
}

// --- Prompt Generation ---
function showThemePrompt(idx) {
  const opp = DATA.opportunities[idx];
  if (!opp) return;
  let prompt = `## Task: ${opp.name}\nSkill path: ${DATA.meta.skill_path}\n\n`;
  prompt += `### Problem\n${opp.description}\n\n`;
  prompt += `### Fix\n${opp.action}\n\n`;
  if (opp.findings && opp.findings.length) {
    prompt += `### Specific observations to address:\n\n`;
    opp.findings.forEach((f, i) => {
      const loc = f.file ? (f.line ? `${f.file}:${f.line}` : f.file) : '';
      prompt += `${i+1}. **${f.title}**`;
      if (loc) prompt += ` (${loc})`;
      if (f.detail) prompt += `\n   ${f.detail}`;
      prompt += `\n`;
    });
  }
  document.getElementById('modal-title').textContent = `Fix: ${opp.name}`;
  document.getElementById('modal-content').textContent = prompt.trim();
  document.getElementById('modal').classList.add('visible');
}

function showBrokenPrompt() {
  const items = DATA.broken || [];
  let prompt = `## Task: Fix Critical Issues\nSkill path: ${DATA.meta.skill_path}\n\n`;
  items.forEach((item, i) => {
    const loc = item.file ? (item.line ? `${item.file}:${item.line}` : item.file) : '';
    prompt += `${i+1}. **[${(item.severity||'high').toUpperCase()}] ${item.title}**\n`;
    if (loc) prompt += `   File: ${loc}\n`;
    if (item.detail) prompt += `   Context: ${item.detail}\n`;
    if (item.action) prompt += `   Fix: ${item.action}\n`;
    prompt += `\n`;
  });
  document.getElementById('modal-title').textContent = 'Fix Critical Issues';
  document.getElementById('modal-content').textContent = prompt.trim();
  document.getElementById('modal').classList.add('visible');
}

function closeModal() { document.getElementById('modal').classList.remove('visible'); }

function copyModal() {
  const text = document.getElementById('modal-content').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.modal .btn-primary');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy to Clipboard'; }, 1500);
  });
}

init();
</script>
</body>
</html>"""


def generate_html(report_data: dict) -> str:
    """Inject report data into the HTML template."""
    data_json = json.dumps(report_data, indent=None, ensure_ascii=False)
    data_tag = f'<script id="report-data" type="application/json">{data_json}</script>'
    html = HTML_TEMPLATE.replace('<script>\nconst RAW', f'{data_tag}\n<script>\nconst RAW')
    html = html.replace('SKILL_NAME', report_data.get('meta', {}).get('skill_name', 'Unknown'))
    return html


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate interactive HTML quality analysis report',
    )
    parser.add_argument(
        'report_dir',
        type=Path,
        help='Directory containing report-data.json',
    )
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open the HTML report in the default browser',
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output HTML file path (default: {report_dir}/quality-report.html)',
    )
    args = parser.parse_args()

    if not args.report_dir.is_dir():
        print(f'Error: {args.report_dir} is not a directory', file=sys.stderr)
        return 2

    report_data = load_report_data(args.report_dir)
    html = generate_html(report_data)

    output_path = args.output or (args.report_dir / 'quality-report.html')
    output_path.write_text(html, encoding='utf-8')

    # Output summary
    opp_count = len(report_data.get('opportunities', []))
    broken_count = len(report_data.get('broken', []))
    print(json.dumps({
        'html_report': str(output_path),
        'grade': report_data.get('grade', 'Unknown'),
        'opportunities': opp_count,
        'broken': broken_count,
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
