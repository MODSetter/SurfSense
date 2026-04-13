---
name: build-process
description: Six-phase conversational discovery process for building BMad workflows and skills. Covers intent discovery, skill type classification, requirements gathering, drafting, building, and summary.
---

**Language:** Use `{communication_language}` for all output.

# Build Process

Build workflows and skills through conversational discovery. Your north star: **outcome-driven design**. Every instruction in the final skill should describe what to achieve, not prescribe how to do it step by step. Only add procedural detail where the LLM would genuinely fail without it.

## Phase 1: Discover Intent

Understand their vision before diving into specifics. Let them describe what they want to build — encourage detail on edge cases, tone, persona, tools, and other skills involved.

**Input flexibility:** Accept input in any format:

- Existing BMad workflow/skill path → read and extract intent (see below)
- Rough idea or description → guide through discovery
- Code, documentation, API specs → extract intent and requirements
- Non-BMad skill/tool → extract intent for conversion

### When given an existing skill

**Critical:** Treat the existing skill as a **description of intent**, not a specification to follow. Extract _what_ it's trying to achieve. Do not inherit its verbosity, structure, or mechanical procedures — the old skill is reference material, not a template.

If the SKILL.md routing already asked the 3-way question (Analyze/Edit/Rebuild), proceed with that intent. Otherwise ask now:

- **Edit** — changing specific behavior while keeping the current approach
- **Rebuild** — rethinking from core outcomes, full discovery using the old skill as context

For **Edit**: use the edit fast-track — full Phase 1-6 is for Rebuild and new builds only.

**Edit fast-track:**

1. Read the relevant files in the existing skill
2. Understand the specific change requested and its scope
3. Apply the change following outcome-driven principles — preserve what works, improve what's targeted
4. Run lint gate (Phase 5 lint steps) and fix any findings
5. Present the change and lint results

If the edit touches the skill's core architecture, classification, or requires rethinking multiple stages, recommend Rebuild instead.

For **Rebuild**: read the old skill to understand its goals, then proceed through full discovery as if building new — the old skill informs your questions but doesn't constrain the design.

### Discovery questions (don't skip these, even with existing input)

The best skills come from understanding the human's intent, not reverse-engineering it from code. Walk through these conversationally — adapt based on what the user has already shared:

- What is the **core outcome** this skill delivers? What does success look like?
- **Who is the user** and how should the experience feel? What's the interaction model — collaborative discovery, rapid execution, guided interview?
- What **judgment calls** does the LLM need to make vs. just do mechanically?
- What's the **one thing** this skill must get right?
- Are there things the user might not know or might get wrong? How should the skill handle that?

The goal is to conversationally gather enough to cover Phase 2 and 3 naturally. Since users often brain-dump rich detail, adapt subsequent phases to what you already know.

## Phase 2: Classify Skill Type

Ask upfront:

- Will this be part of a module? If yes:
  - What's the module code?
  - What other skills will it use from the core or module? (need name, inputs, outputs for integration)
  - What config variables does it need access to?

Load `./classification-reference.md` and classify. Present classification with reasoning.

For Simple Workflows and Complex Workflows, also ask:

- **Headless mode?** Should this support `--headless`? (If it produces an artifact, headless is often valuable)

## Phase 3: Gather Requirements

Work through conversationally, adapted per skill type. Glean from what the user already shared or suggest based on their narrative.

**All types — Common fields:**

- **Name:** kebab-case. Module: `{modulecode}-{skillname}`. Standalone: `{skillname}`. The `bmad-` prefix is reserved for official BMad creations only.
- **Description:** Two parts: [5-8 word summary]. [Use when user says 'specific phrase'.] — Default to conservative triggering. See `./standard-fields.md` for format.
- **Overview:** What/How/Why-Outcome. For interactive or complex skills, include domain framing and theory of mind — these give the executing agent context for judgment calls.
- **Role guidance:** Brief "Act as a [role/expert]" primer
- **Design rationale:** Non-obvious choices the executing agent should understand
- **External skills used:** Which skills does this invoke?
- **Script Opportunity Discovery** — Walk through planned steps with the user. Identify deterministic operations that should be scripts not prompts. Load `./script-opportunities-reference.md` for guidance. Confirm the script-vs-prompt plan. If any scripts require external dependencies (anything beyond Python's standard library), explicitly list each dependency and get user approval before proceeding — dependencies add install-time cost and require `uv` to be available.
- **Creates output documents?** If yes, will use `{document_output_language}`

**Simple Utility additional:**

- Input/output format, standalone?, composability

**Simple Workflow additional:**

- Steps (inline in SKILL.md), config variables

**Complex Workflow additional:**

- Stages with purposes, progression conditions, headless behavior, config variables

**Module capability metadata (if part of a module):**
Confirm with user: phase-name, after (dependencies), before (downstream), is-required, description (short — what it produces, not how).

**Path conventions (CRITICAL):**

- Skill-internal: `references/`, `scripts/` (relative to skill root)
- Project-scope paths: `{project-root}/...` (any path relative to project root)
- Config variables used directly — they already contain `{project-root}`

## Phase 4: Draft & Refine

Think one level deeper. Clarify gaps in logic or understanding. Create and present a plan. Point out vague areas. Iterate until ready.

**Pruning check (apply before building):**

For every planned instruction, ask: **would the LLM do this correctly without being told?** If yes, cut it. Scoring algorithms, calibration tables, decision matrices for subjective judgment, weighted formulas — these are things LLMs handle naturally. The instruction must earn its place by preventing a failure that would otherwise happen.

Watch especially for:

- Mechanical procedures for tasks the LLM does through general capability
- Per-platform instructions when a single adaptive instruction works
- Templates that explain things the LLM already knows (how to format output, how to greet users)
- Multiple files that could be a single instruction

## Phase 5: Build

**Load these before building:**

- `./standard-fields.md` — field definitions, description format, path rules
- `./skill-best-practices.md` — outcome-driven authoring, patterns, anti-patterns
- `./quality-dimensions.md` — build quality checklist

**Load based on skill type:**

- **If Complex Workflow:** `./complex-workflow-patterns.md` — compaction survival, config integration, progressive disclosure

Load the template from `assets/SKILL-template.md` and `./template-substitution-rules.md`. Build the skill with progressive disclosure (SKILL.md for overview and routing, `references/` for progressive disclosure content). Output to `{bmad_builder_output_folder}`.

**Skill Source Tree** (only create subfolders that are needed):

```
{skill-name}/
├── SKILL.md           # Frontmatter, overview, activation, routing
├── references/        # Progressive disclosure content — prompts, guides, schemas
├── assets/            # Templates, starter files
├── scripts/           # Deterministic code with tests
│   └── tests/
```

| Location            | Contains                           | LLM relationship                     |
| ------------------- | ---------------------------------- | ------------------------------------ |
| **SKILL.md**        | Overview, activation, routing      | LLM identity and router              |
| **`references/`**   | Capability prompts, reference data | Loaded on demand                     |
| **`assets/`**       | Templates, starter files           | Copied/transformed into output       |
| **`scripts/`**      | Python, shell scripts with tests   | Invoked for deterministic operations |

**If the built skill includes scripts**, also load `./script-standards.md` — ensures PEP 723 metadata, correct shebangs, and `uv run` invocation from the start.

**Lint gate** — after building, validate and auto-fix:

If subagents available, delegate lint-fix to a subagent. Otherwise run inline.

1. Run both lint scripts in parallel:
   ```bash
   python3 scripts/scan-path-standards.py {skill-path}
   python3 scripts/scan-scripts.py {skill-path}
   ```
2. Fix high/critical findings and re-run (up to 3 attempts per script)
3. Run unit tests if scripts exist in the built skill

## Phase 6: Summary

Present what was built: location, structure, capabilities. Include lint results.

Run unit tests if scripts exist. Remind user to commit before quality analysis.

**Offer quality analysis:** Ask if they'd like a Quality Analysis to identify opportunities. If yes, load `./quality-analysis.md` with the skill path.
