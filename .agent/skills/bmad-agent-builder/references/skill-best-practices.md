# Skill Authoring Best Practices

For field definitions and description format, see `./standard-fields.md`. For quality dimensions, see `./quality-dimensions.md`.

## Core Philosophy: Outcome-Based Authoring

Skills should describe **what to achieve**, not **how to achieve it**. The LLM is capable of figuring out the approach — it needs to know the goal, the constraints, and the why.

**The test for every instruction:** Would removing this cause the LLM to produce a worse outcome? If the LLM would do it anyway — or if it's just spelling out mechanical steps — cut it.

### Outcome vs Prescriptive

| Prescriptive (avoid)                                                                                  | Outcome-based (prefer)                                                                                 |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "Step 1: Ask about goals. Step 2: Ask about constraints. Step 3: Summarize and confirm."              | "Ensure the user's vision is fully captured — goals, constraints, and edge cases — before proceeding." |
| "Load config. Read user_name. Read communication_language. Greet the user by name in their language." | "Load available config and greet the user appropriately."                                              |
| "Create a file. Write the header. Write section 1. Write section 2. Save."                            | "Produce a report covering X, Y, and Z."                                                               |

The prescriptive versions miss requirements the author didn't think of. The outcome-based versions let the LLM adapt to the actual situation.

### Why This Works

- **Why over what** — When you explain why something matters, the LLM adapts to novel situations. When you just say what to do, it follows blindly even when it shouldn't.
- **Context enables judgment** — Give domain knowledge, constraints, and goals. The LLM figures out the approach. It's better at adapting to messy reality than any script you could write.
- **Prescriptive steps create brittleness** — When reality doesn't match the script, the LLM either follows the wrong script or gets confused. Outcomes let it adapt.
- **Every instruction should carry its weight** — If the LLM would do it anyway, the instruction is noise. If the LLM wouldn't know to do it without being told, that's signal.

### When Prescriptive Is Right

Reserve exact steps for **fragile operations** where getting it wrong has consequences — script invocations, exact file paths, specific CLI commands, API calls with precise parameters. These need low freedom because there's one right way to do them.

| Freedom             | When                                               | Example                                                             |
| ------------------- | -------------------------------------------------- | ------------------------------------------------------------------- |
| **High** (outcomes) | Multiple valid approaches, LLM judgment adds value | "Ensure the user's requirements are complete"                       |
| **Medium** (guided) | Preferred approach exists, some variation OK       | "Present findings in a structured report with an executive summary" |
| **Low** (exact)     | Fragile, one right way, consequences for deviation | `uv run ./scripts/scan-path-standards.py {skill-path}`             |

## Patterns

These are patterns that naturally emerge from outcome-based thinking. Apply them when they fit — they're not a checklist.

### Soft Gate Elicitation

At natural transitions, invite contribution without demanding it: "Anything else, or shall we move on?" Users almost always remember one more thing when given a graceful exit ramp. This produces richer artifacts than rigid section-by-section questioning.

### Intent-Before-Ingestion

Understand why the user is here before scanning documents or project context. Intent gives you the relevance filter — without it, scanning is noise.

### Capture-Don't-Interrupt

When users provide information beyond the current scope, capture it for later rather than redirecting. Users in creative flow share their best insights unprompted — interrupting loses them.

### Dual-Output: Human Artifact + LLM Distillate

Artifact-producing skills can output both a polished human-facing document and a token-efficient distillate for downstream LLM consumption. The distillate captures overflow, rejected ideas, and detail that doesn't belong in the human doc but has value for the next workflow. Always optional.

### Parallel Review Lenses

Before finalizing significant artifacts, fan out reviewers with different perspectives — skeptic, opportunity spotter, domain-specific lens. If subagents aren't available, do a single critical self-review pass. Multiple perspectives catch blind spots no single reviewer would.

### Three-Mode Architecture (Guided / Yolo / Headless)

Consider whether the skill benefits from multiple execution modes:

| Mode         | When                | Behavior                                                      |
| ------------ | ------------------- | ------------------------------------------------------------- |
| **Guided**   | Default             | Conversational discovery with soft gates                      |
| **Yolo**     | "just draft it"     | Ingest everything, draft complete artifact, then refine       |
| **Headless** | `--headless` / `-H` | Complete the task without user input, using sensible defaults |

Not all skills need all three. But considering them during design prevents locking into a single interaction model.

### Graceful Degradation

Every subagent-dependent feature should have a fallback path. A skill that hard-fails without subagents is fragile — one that falls back to sequential processing works everywhere.

### Verifiable Intermediate Outputs

For complex tasks with consequences: plan → validate → execute → verify. Create a verifiable plan before executing, validate with scripts where possible. Catches errors early and makes the work reversible.

## Writing Guidelines

- **Consistent terminology** — one term per concept, stick to it
- **Third person** in descriptions — "Processes files" not "I help process files"
- **Descriptive file names** — `form_validation_rules.md` not `doc2.md`
- **Forward slashes** in all paths — cross-platform
- **One level deep** for reference files — SKILL.md → reference.md, never chains
- **TOC for long files** — >100 lines

## Anti-Patterns

| Anti-Pattern                                       | Fix                                                   |
| -------------------------------------------------- | ----------------------------------------------------- |
| Numbered steps for things the LLM would figure out | Describe the outcome and why it matters               |
| Explaining how to load config (the mechanic)       | List the config keys and their defaults (the outcome) |
| Prescribing exact greeting/menu format             | "Greet the user and present capabilities"             |
| Spelling out headless mode in detail               | "If headless, complete without user input"            |
| Too many options upfront                           | One default with escape hatch                         |
| Deep reference nesting (A→B→C)                     | Keep references 1 level from SKILL.md                 |
| Inconsistent terminology                           | Choose one term per concept                           |
| Scripts that classify meaning via regex            | Intelligence belongs in prompts, not scripts          |

## Bootloader SKILL.md (Memory Agents)

Memory agents use a lean bootloader SKILL.md that carries ONLY the essential DNA. Everything else lives in the sanctum (loaded on rebirth) or references (loaded on demand).

**What belongs in the bootloader (~30 lines of content):**
- Identity seed (2-3 sentences of personality DNA)
- The Three Laws
- Sacred Truth
- Species-level mission
- Activation routing (3 paths: no sanctum, headless, rebirth)
- Sanctum location

**What does NOT belong in the bootloader:**
- Communication style (goes in PERSONA-template.md)
- Detailed principles (go in CREED-template.md)
- Capability menus/tables (go in CAPABILITIES-template.md, auto-generated by init script)
- Session close behavior (emerges from persona)
- Overview section (the bootloader IS the overview)
- Extensive activation instructions (the three paths are enough)

**The test:** If the bootloader is over 40 lines of content, something belongs in a sanctum template instead.

## Capability Prompts for Memory Agents

Memory agent capability prompts follow the same outcome-focused philosophy but include memory integration. The pattern:

- **What Success Looks Like** — the outcome, not the process
- **Your Approach** — philosophy and principles, not step-by-step. Reference technique libraries if they exist.
- **Memory Integration** — how to use MEMORY.md and BOND.md to personalize the interaction. Surface past work, reference preferences.
- **After the Session** — what to capture in the session log. What patterns to note for BOND.md. What to flag for PULSE curation.

Stateless agent prompts omit Memory Integration and After the Session sections.

When a capability has substantial domain knowledge (frameworks, methodologies, technique catalogs), separate it into a lean capability prompt + a technique library loaded on demand. This keeps prompts focused while making deep knowledge available.

## Scripts in Skills

- **Execute vs reference** — "Run `analyze.py`" (execute) vs "See `analyze.py` for the algorithm" (read)
- **Document constants** — explain why `TIMEOUT = 30`, not just what
- **PEP 723 for Python** — self-contained with inline dependency declarations
- **MCP tools** — use fully qualified names: `ServerName:tool_name`
