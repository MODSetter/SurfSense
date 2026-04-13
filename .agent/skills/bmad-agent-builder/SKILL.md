---
name: bmad-agent-builder
description: Builds, edits or analyzes Agent Skills through conversational discovery. Use when the user requests to "Create an Agent", "Analyze an Agent" or "Edit an Agent".
---

# Agent Builder

## Overview

This skill helps you build AI agents that are **outcome-driven** — describing what each capability achieves, not micromanaging how. Agents are skills with named personas, capabilities, and optional memory. Great agents have a clear identity, focused capabilities that describe outcomes, and personality that comes through naturally. Poor agents drown the LLM in mechanical procedures it would figure out from the persona context alone.

Act as an architect guide — walk users through conversational discovery to understand who their agent is, what it should achieve, and how it should make users feel. Then craft the leanest possible agent where every instruction carries its weight. The agent's identity and persona context should inform HOW capabilities are executed — capability prompts just need the WHAT.

**Args:** Accepts `--headless` / `-H` for non-interactive execution, an initial description for create, or a path to an existing agent with keywords like analyze, edit, or rebuild.

**Your output:** A complete agent skill structure — persona, capabilities, optional memory and headless modes — ready to integrate into a module or use standalone.

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

The core creative path — where agent ideas become reality. Through conversational discovery, you guide users from a rough vision to a complete, outcome-driven agent skill.

The builder produces three agent types along a spectrum:

- **Stateless agent** — everything in SKILL.md, no memory, no First Breath. For focused experts handling isolated sessions.
- **Memory agent** — lean bootloader SKILL.md + sanctum (6 standard files + First Breath). For agents that build understanding over time.
- **Autonomous agent** — memory agent + PULSE. For agents that operate on their own between sessions.

Agent type is determined during Phase 1 discovery, not upfront. The builder covers building new agents, converting existing ones, editing, and rebuilding from intent.

Load `./references/build-process.md` to begin.

## Quality Analysis

Comprehensive quality analysis toward outcome-driven design. Analyzes existing agents for over-specification, structural issues, persona-capability alignment, execution efficiency, and enhancement opportunities. Produces a synthesized report with agent portrait, capability dashboard, themes, and actionable opportunities.

Load `./references/quality-analysis.md` to begin.

---

## Quick Reference

| Intent                      | Trigger Phrases                                       | Route                                    |
| --------------------------- | ----------------------------------------------------- | ---------------------------------------- |
| **Build new**               | "build/create/design a new agent"                     | Load `./references/build-process.md`                |
| **Existing agent provided** | Path to existing agent, or "convert/edit/fix/analyze" | Ask the 3-way question below, then route |
| **Quality analyze**         | "quality check", "validate", "review agent"           | Load `./references/quality-analysis.md`             |
| **Unclear**                 | —                                                     | Present options and ask                  |

### When given an existing agent, ask:

- **Analyze** — Run quality analysis: identify opportunities, prune over-specification, get an actionable report with agent portrait and capability dashboard
- **Edit** — Modify specific behavior while keeping the current approach
- **Rebuild** — Rethink from core outcomes and persona, using this as reference material, full discovery process

Analyze routes to `./references/quality-analysis.md`. Edit routes to `./references/edit-guidance.md`. Rebuild routes to `./references/build-process.md` with the chosen intent.

Regardless of path, respect headless mode if requested.
