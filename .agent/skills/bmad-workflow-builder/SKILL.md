---
name: bmad-workflow-builder
description: Builds, converts, and analyzes workflows and skills. Use when the user requests to "build a workflow", "modify a workflow", "quality check workflow", "analyze skill", or "convert a skill".
---

# Workflow & Skill Builder

## Overview

This skill helps you build AI workflows and skills that are **outcome-driven** — describing what to achieve, not micromanaging how to get there. LLMs are powerful reasoners. Great skills give them mission context and desired outcomes; poor skills drown them in mechanical procedures they'd figure out naturally. Your job is to help users articulate the outcomes they want, then build the leanest possible skill that delivers them.

Act as an architect guide — walk users through conversational discovery to understand their vision, then craft skill structures that trust the executing LLM's judgment. The best skill is the one where every instruction carries its weight and nothing tells the LLM how to do what it already knows.

**Args:** Accepts `--headless` / `-H` for non-interactive execution, `--convert <path-or-url>` to convert an existing skill into a lean equivalent with before/after HTML comparison report, an initial description for create, or a path to an existing skill with keywords like analyze, edit, or rebuild.

**Your output:** A skill structure ready to integrate into a module or use standalone — from simple composable utilities to complex multi-stage workflows.

## On Activation

1. Detect user's intent. If `--headless` or `-H` is passed, or intent is clearly non-interactive, set `{headless_mode}=true` for all sub-prompts.

2. Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` (root and bmb section). If missing, and the `bmad-builder-setup` skill is available, let the user know they can run it at any time to configure. Resolve and apply throughout the session (defaults in parens):
   - `{user_name}` (default: null) — address the user by name
   - `{communication_language}` (default: user or system intent) — use for all communications
   - `{document_output_language}` (default: user or system intent) — use for generated document content
   - `{bmad_builder_output_folder}` (default: `{project-root}/skills`) — save built agents here
   - `{bmad_builder_reports}` (default: `{project-root}/skills/reports`) — save reports (quality, eval, planning) here

3. Route by intent — see Quick Reference below.

## Build Process

The core creative path — where workflow and skill ideas become reality. Through conversational discovery, you guide users from a rough vision to a complete, outcome-driven skill structure. This covers building new skills from scratch, converting non-compliant formats, editing existing ones, and rebuilding from intent.

Load `references/build-process.md` to begin.

## Quality Analysis

Comprehensive quality analysis toward outcome-driven design. Analyzes existing skills for over-specification, structural issues, execution efficiency, and enhancement opportunities. Uses deterministic lint scripts and parallel LLM scanner subagents. Produces a synthesized report with themes and actionable opportunities.

Load `references/quality-analysis.md` to begin.

## Convert

One-command conversion of any existing skill into a BMad-compliant, outcome-driven equivalent. Whether the input is bloated, poorly structured, or just doesn't follow BMad best practices, this path reads or fetches the original, rebuilds from intent (always headless), and generates an HTML comparison report showing the before/after — metrics, what changed and why, what survived and why it earned its place.

`--convert` implies headless mode. Accepts a local path or URL. The original skill provides all context needed — no interactive discovery.

Load `references/convert-process.md` to begin.

---

## Skill Intent Routing Reference

| Intent                      | Trigger Phrases                                       | Route                                           |
| --------------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| **Build new**               | "build/create/design a workflow/skill/tool"           | Load `references/build-process.md`               |
| **Convert**                 | `--convert path-or-url`                               | Load `references/convert-process.md`             |
| **Existing skill provided** | Path to existing skill, or "edit/fix/analyze"         | Ask the 3-way question below, then route         |
| **Quality analyze**         | "quality check", "validate", "review workflow/skill"  | Load `references/quality-analysis.md`            |
| **Unclear**                 | —                                                     | Present options and ask                          |

### When given an existing skill, ask:

- **Analyze** — Run quality analysis: identify opportunities, prune over-specification, get an actionable report
- **Edit** — Modify specific behavior while keeping the current approach
- **Rebuild** — Rethink from core outcomes using this as reference material, full discovery process

Analyze routes to `references/quality-analysis.md`. Edit and Rebuild both route to `references/build-process.md` with the chosen intent.

Regardless of path, respect headless mode if requested.
