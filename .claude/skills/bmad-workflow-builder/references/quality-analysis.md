---
name: quality-analysis
description: Comprehensive quality analysis for BMad workflows and skills. Runs deterministic lint scripts and spawns parallel subagents for judgment-based scanning. Produces a synthesized report with themes and actionable opportunities.
menu-code: QA
---

# Quality Analysis

Communicate with user in `{communication_language}`. Write report content in `{document_output_language}`.

You orchestrate quality analysis on a BMad workflow or skill. Deterministic checks run as scripts (fast, zero tokens). Judgment-based analysis runs as LLM subagents. A report creator synthesizes everything into a unified, theme-based report.

## Your Role: Coordination, Not File Reading

**DO NOT read the target skill's files yourself.** Scripts and subagents do all analysis.

You orchestrate: run deterministic scripts and pre-pass extractors, spawn LLM scanner subagents in parallel, then hand off to the report creator for synthesis.

## Headless Mode

If `{headless_mode}=true`, skip all user interaction, use safe defaults, note any warnings, and output structured JSON as specified in the Present Findings section.

## Pre-Scan Checks

Check for uncommitted changes. In headless mode, note warnings and proceed. In interactive mode, inform the user and confirm before proceeding. In interactive mode, also confirm the workflow is currently functioning.

## Analysis Principles

**Effectiveness over efficiency.** The analysis may suggest leaner phrasing, but if the current phrasing captures the right guidance, it should be kept. Over-optimization can make skills lose their effectiveness. The report presents opportunities — the user applies judgment.

## Scanners

### Lint Scripts (Deterministic — Run First)

These run instantly, cost zero tokens, and produce structured JSON:

| #   | Script                           | Focus                                   | Output File                |
| --- | -------------------------------- | --------------------------------------- | -------------------------- |
| S1  | `scripts/scan-path-standards.py` | Path conventions                        | `path-standards-temp.json` |
| S2  | `scripts/scan-scripts.py`        | Script portability, PEP 723, unit tests | `scripts-temp.json`        |

### Pre-Pass Scripts (Feed LLM Scanners)

Extract metrics so LLM scanners work from compact data instead of raw files:

| #   | Script                                  | Feeds                        | Output File                       |
| --- | --------------------------------------- | ---------------------------- | --------------------------------- |
| P1  | `scripts/prepass-workflow-integrity.py` | workflow-integrity scanner   | `workflow-integrity-prepass.json` |
| P2  | `scripts/prepass-prompt-metrics.py`     | prompt-craft scanner         | `prompt-metrics-prepass.json`     |
| P3  | `scripts/prepass-execution-deps.py`     | execution-efficiency scanner | `execution-deps-prepass.json`     |

### LLM Scanners (Judgment-Based — Run After Scripts)

Each scanner writes a free-form analysis document (not JSON):

| #   | Scanner                                     | Focus                                                                     | Pre-Pass? | Output File                             |
| --- | ------------------------------------------- | ------------------------------------------------------------------------- | --------- | --------------------------------------- |
| L1  | `quality-scan-workflow-integrity.md`        | Structural completeness, naming, type-appropriate requirements            | Yes       | `workflow-integrity-analysis.md`        |
| L2  | `quality-scan-prompt-craft.md`              | Token efficiency, outcome-driven balance, progressive disclosure, pruning | Yes       | `prompt-craft-analysis.md`              |
| L3  | `quality-scan-execution-efficiency.md`      | Parallelization, subagent delegation, context optimization                | Yes       | `execution-efficiency-analysis.md`      |
| L4  | `quality-scan-skill-cohesion.md`            | Stage flow, purpose alignment, complexity appropriateness                 | No        | `skill-cohesion-analysis.md`            |
| L5  | `quality-scan-enhancement-opportunities.md` | Edge cases, UX gaps, user journeys, headless potential                    | No        | `enhancement-opportunities-analysis.md` |
| L6  | `quality-scan-script-opportunities.md`      | Deterministic operations that should be scripts                           | No        | `script-opportunities-analysis.md`      |

## Execution

First create output directory: `{bmad_builder_reports}/{skill-name}/quality-analysis/{date-time-stamp}/`

### Step 1: Run All Scripts (Parallel)

Run all lint scripts and pre-pass scripts in parallel:

```bash
python3 scripts/scan-path-standards.py {skill-path} -o {report-dir}/path-standards-temp.json
python3 scripts/scan-scripts.py {skill-path} -o {report-dir}/scripts-temp.json
uv run scripts/prepass-workflow-integrity.py {skill-path} -o {report-dir}/workflow-integrity-prepass.json
python3 scripts/prepass-prompt-metrics.py {skill-path} -o {report-dir}/prompt-metrics-prepass.json
uv run scripts/prepass-execution-deps.py {skill-path} -o {report-dir}/execution-deps-prepass.json
```

### Step 2: Spawn LLM Scanners (Parallel)

After scripts complete, spawn all applicable LLM scanners as parallel subagents.

**For scanners WITH pre-pass (L1, L2, L3):** provide the pre-pass JSON file path so the scanner reads compact metrics first, then reads raw files only as needed for judgment calls.

**For scanners WITHOUT pre-pass (L4, L5, L6):** provide just the skill path and output directory.

Each subagent receives:

- Scanner file to load
- Skill path: `{skill-path}`
- Output directory: `{report-dir}`
- Pre-pass file path (if applicable)

The subagent loads the scanner file, analyzes the skill, writes its analysis to the output directory, and returns the filename.

### Step 3: Synthesize Report

After all scanners complete, spawn a subagent with `./report-quality-scan-creator.md`.

Provide:

- `{skill-path}` — The skill being analyzed
- `{quality-report-dir}` — Directory containing all scanner output

The report creator reads everything, synthesizes themes, and writes:

1. `quality-report.md` — Narrative markdown report
2. `report-data.json` — Structured data for HTML

### Step 4: Generate HTML Report

After the report creator finishes, generate the interactive HTML:

```bash
python3 scripts/generate-html-report.py {report-dir} --open
```

This reads `report-data.json` and produces `quality-report.html` — a self-contained interactive report with opportunity themes, "Fix This Theme" prompt generation, and expandable detailed analysis.

## Present to User

**IF `{headless_mode}=true`:**

Read `report-data.json` and output:

```json
{
  "headless_mode": true,
  "scan_completed": true,
  "report_file": "{path}/quality-report.md",
  "html_report": "{path}/quality-report.html",
  "data_file": "{path}/report-data.json",
  "warnings": [],
  "grade": "Excellent|Good|Fair|Poor",
  "opportunities": 0,
  "broken": 0
}
```

**IF interactive:**

Read `report-data.json` and present:

1. Grade and narrative — the 2-3 sentence synthesis
2. Broken items (if any) — critical/high issues prominently
3. Top opportunities — theme names with finding counts and impact
4. Reports — "Full report: quality-report.md" and "Interactive HTML opened in browser"
5. Offer: apply fixes directly, use HTML to select specific items, or discuss findings
