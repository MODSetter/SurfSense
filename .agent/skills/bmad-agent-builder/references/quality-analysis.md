---
name: quality-analysis
description: Comprehensive quality analysis for BMad agents. Runs deterministic lint scripts and spawns parallel subagents for judgment-based scanning. Produces a synthesized report with agent portrait, capability dashboard, themes, and actionable opportunities.
---

**Language:** Use `{communication_language}` for all output.

# BMad Method · Quality Analysis

You orchestrate quality analysis on a BMad agent. Deterministic checks run as scripts (fast, zero tokens). Judgment-based analysis runs as LLM subagents. A report creator synthesizes everything into a unified, theme-based report with agent portrait and capability dashboard.

## Your Role

**DO NOT read the target agent's files yourself.** Scripts and subagents do all analysis. You orchestrate: run scripts, spawn scanners, hand off to the report creator.

## Headless Mode

If `{headless_mode}=true`, skip all user interaction, use safe defaults, note warnings, and output structured JSON as specified in Present to User.

## Pre-Scan Checks

Check for uncommitted changes. In headless mode, note warnings and proceed. In interactive mode, inform the user and confirm. Also confirm the agent is currently functioning.

## Analysis Principles

**Effectiveness over efficiency.** Agent personality is investment, not waste. The report presents opportunities — the user applies judgment. Never suggest flattening an agent's voice unless explicitly asked.

## Scanners

### Lint Scripts (Deterministic — Run First)

| #   | Script                           | Focus                                   | Output File                |
| --- | -------------------------------- | --------------------------------------- | -------------------------- |
| S1  | `./scripts/scan-path-standards.py` | Path conventions                        | `path-standards-temp.json` |
| S2  | `./scripts/scan-scripts.py`        | Script portability, PEP 723, unit tests | `scripts-temp.json`        |

### Pre-Pass Scripts (Feed LLM Scanners)

| #   | Script                                      | Feeds                        | Output File                           |
| --- | ------------------------------------------- | ---------------------------- | ------------------------------------- |
| P1  | `./scripts/prepass-structure-capabilities.py` | structure scanner            | `structure-capabilities-prepass.json` |
| P2  | `./scripts/prepass-prompt-metrics.py`         | prompt-craft scanner         | `prompt-metrics-prepass.json`         |
| P3  | `./scripts/prepass-execution-deps.py`         | execution-efficiency scanner | `execution-deps-prepass.json`         |
| P4  | `./scripts/prepass-sanctum-architecture.py`   | sanctum architecture scanner | `sanctum-architecture-prepass.json`   |

### LLM Scanners (Judgment-Based — Run After Scripts)

Each scanner writes a free-form analysis document:

| #   | Scanner                                     | Focus                                                                     | Pre-Pass? | Output File                             |
| --- | ------------------------------------------- | ------------------------------------------------------------------------- | --------- | --------------------------------------- |
| L1  | `quality-scan-structure.md`                 | Structure, capabilities, identity, memory, consistency                    | Yes       | `structure-analysis.md`                 |
| L2  | `quality-scan-prompt-craft.md`              | Token efficiency, outcome balance, persona voice, per-capability craft    | Yes       | `prompt-craft-analysis.md`              |
| L3  | `quality-scan-execution-efficiency.md`      | Parallelization, delegation, memory loading, context optimization         | Yes       | `execution-efficiency-analysis.md`      |
| L4  | `quality-scan-agent-cohesion.md`            | Persona-capability alignment, identity coherence, per-capability cohesion | No        | `agent-cohesion-analysis.md`            |
| L5  | `quality-scan-enhancement-opportunities.md` | Edge cases, experience gaps, user journeys, headless potential            | No        | `enhancement-opportunities-analysis.md` |
| L6  | `quality-scan-script-opportunities.md`      | Deterministic operations that should be scripts                           | No        | `script-opportunities-analysis.md`      |
| L7  | `quality-scan-sanctum-architecture.md`      | Sanctum architecture (memory agents only)                                 | Yes       | `sanctum-architecture-analysis.md`      |

**L7 only runs for memory agents.** The prepass (P4) detects whether the agent is a memory agent. If the prepass reports `is_memory_agent: false`, skip L7 entirely.

## Execution

First create output directory: `{bmad_builder_reports}/{skill-name}/quality-analysis/{date-time-stamp}/`

### Step 1: Run All Scripts (Parallel)

```bash
uv run ./scripts/scan-path-standards.py {skill-path} -o {report-dir}/path-standards-temp.json
uv run ./scripts/scan-scripts.py {skill-path} -o {report-dir}/scripts-temp.json
uv run ./scripts/prepass-structure-capabilities.py {skill-path} -o {report-dir}/structure-capabilities-prepass.json
uv run ./scripts/prepass-prompt-metrics.py {skill-path} -o {report-dir}/prompt-metrics-prepass.json
uv run ./scripts/prepass-execution-deps.py {skill-path} -o {report-dir}/execution-deps-prepass.json
uv run ./scripts/prepass-sanctum-architecture.py {skill-path} -o {report-dir}/sanctum-architecture-prepass.json
```

### Step 2: Spawn LLM Scanners (Parallel)

After scripts complete, spawn all scanners as parallel subagents.

**With pre-pass (L1, L2, L3, L7):** provide pre-pass JSON path.
**Without pre-pass (L4, L5, L6):** provide skill path and output directory.

**Memory agent check:** Read `sanctum-architecture-prepass.json`. If `is_memory_agent` is `true`, include L7 in the parallel spawn. If `false`, skip L7.

Each subagent loads the scanner file, analyzes the agent, writes analysis to the output directory, returns the filename.

### Step 3: Synthesize Report

Spawn a subagent with `report-quality-scan-creator.md`.

Provide:

- `{skill-path}` — The agent being analyzed
- `{quality-report-dir}` — Directory with all scanner output

The report creator reads everything, synthesizes agent portrait + capability dashboard + themes, writes:

1. `quality-report.md` — Narrative markdown with BMad Method branding
2. `report-data.json` — Structured data for HTML

### Step 4: Generate HTML Report

```bash
uv run ./scripts/generate-html-report.py {report-dir} --open
```

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
  "grade": "Excellent|Good|Fair|Poor",
  "opportunities": 0,
  "broken": 0
}
```

**IF interactive:**

Read `report-data.json` and present:

1. Agent portrait — icon, name, title
2. Grade and narrative
3. Capability dashboard summary
4. Top opportunities
5. Reports — paths and "HTML opened in browser"
6. Offer: apply fixes, use HTML to select items, discuss findings
