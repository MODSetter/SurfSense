---
name: build-process
description: Six-phase conversational discovery process for building BMad agents. Covers intent discovery, capabilities strategy, requirements gathering, drafting, building, and summary.
---

**Language:** Use `{communication_language}` for all output.

# Build Process

Build AI agents through conversational discovery. Your north star: **outcome-driven design**. Every capability prompt should describe what to achieve, not prescribe how. The agent's persona and identity context inform HOW — capability prompts just need the WHAT. Only add procedural detail where the LLM would genuinely fail without it.

## Phase 1: Discover Intent

Understand their vision before diving into specifics. Ask what they want to build and encourage detail.

### When given an existing agent

**Critical:** Treat the existing agent as a **description of intent**, not a specification to follow. Extract _who_ this agent is and _what_ it achieves. Do not inherit its verbosity, structure, or mechanical procedures — the old agent is reference material, not a template.

If the SKILL.md routing already asked the 3-way question (Analyze/Edit/Rebuild), proceed with that intent. Otherwise ask now:

- **Edit** — changing specific behavior while keeping the current approach
- **Rebuild** — rethinking from core outcomes and persona, full discovery using the old agent as context

For **Edit**: identify what to change, preserve what works, apply outcome-driven principles to the changed portions.

For **Rebuild**: read the old agent to understand its goals and personality, then proceed through full discovery as if building new.

### Discovery questions (don't skip these, even with existing input)

The best agents come from understanding the human's vision directly. Walk through these conversationally — adapt based on what the user has already shared:

- **Who IS this agent?** What personality should come through? What's their voice?
- **How should they make the user feel?** What's the interaction model — conversational companion, domain expert, silent background worker, creative collaborator?
- **What's the core outcome?** What does this agent help the user accomplish? What does success look like?
- **What capabilities serve that core outcome?** Not "what features sound cool" — what does the user actually need?
- **What's the one thing this agent must get right?** The non-negotiable.
- **If persistent memory:** What's worth remembering across sessions? What should the agent track over time?

The goal is to conversationally gather enough to cover Phase 2 and 3 naturally. Since users often brain-dump rich detail, adapt subsequent phases to what you already know.

### Agent Type Detection

After understanding who the agent is and what it does, determine the agent type. Load `./references/agent-type-guidance.md` for decision framework. Surface these as natural questions, not a menu:

1. **"Does this agent need to remember between sessions?"** No = stateless agent. Yes = memory agent.
2. **"Does this agent operate autonomously — checking in, maintaining things, creating value when no one's watching?"** If yes, include PULSE (making it an autonomous agent).

Confirm the assessment: "It sounds like this is a [stateless agent / memory agent / autonomous agent] — does that feel right?"

### Relationship Depth (memory agents only)

Determines which First Breath onboarding style to use:

- **Deep relationship** (calibration-style First Breath): The agent is a long-term creative partner, coach, or companion. The relationship IS the product.
- **Focused relationship** (configuration-style First Breath): The agent is a domain expert the user works with regularly. The relationship serves the work.

Confirm: "This feels more like a [long-term partnership / focused domain tool] — should First Breath be a deep calibration conversation, or a warmer but quicker guided setup?"

## Phase 2: Capabilities Strategy

Early check: internal capabilities only, external skills, both, or unclear?

**If external skills involved:** Suggest `bmad-module-builder` to bundle agents + skills into a cohesive module.

**Script Opportunity Discovery** (active probing — do not skip):

Identify deterministic operations that should be scripts. Load `./references/script-opportunities-reference.md` for guidance. Confirm the script-vs-prompt plan with the user before proceeding. If any scripts require external dependencies (anything beyond Python's standard library), explicitly list each dependency and get user approval — dependencies add install-time cost and require `uv` to be available.

**Evolvable Capabilities (memory agents only):**

Ask: "Should the user be able to teach this agent new things over time?" If yes, the agent gets:
- `capability-authoring.md` in its references (teaches the agent how to create new capabilities)
- A "Learned" section in CAPABILITIES.md (registry for user-taught capabilities)

This is separate from the built-in capabilities you're designing now. Evolvable means the owner can extend the agent after it's built.

## Phase 3: Gather Requirements

Gather through conversation: identity, capabilities, activation modes, memory needs, access boundaries. Refer to `./references/standard-fields.md` for conventions.

Key structural context:

- **Naming:** Standalone: `agent-{name}`. Module: `{modulecode}-agent-{name}`. The `bmad-` prefix is reserved for official BMad creations only.
- **Activation modes:** Interactive only, or Interactive + Headless (schedule/cron for background tasks)
- **Memory architecture:** Agent memory at `{project-root}/_bmad/memory/{skillName}/`
- **Access boundaries:** Read/write/deny zones stored in memory

**If headless mode enabled, also gather:**

- Default wake behavior (`--headless` | `-H` with no specific task)
- Named tasks (`--headless:{task-name}` or `-H:{task-name}`)

### Memory Agent Requirements (if memory agent or autonomous agent)

Gather these additional requirements through conversation. These seed the sanctum templates and First Breath.

**Identity seed** — condensed to 2-3 sentences for the bootloader SKILL.md. This is the agent's personality DNA: the essence that expands into PERSONA.md during First Breath. Not a full bio — just the core personality.

**Species-level mission** — domain-specific purpose statement. Load `./references/mission-writing-guidance.md` for guidance and examples. The mission must be specific to this agent type ("Catch the bugs the author's familiarity makes invisible") not generic ("Assist your owner").

**CREED seeds** — these go into CREED-template.md with real content, not empty placeholders:

- **Core values** (3-5): Domain-specific operational values, not platitudes. Load `./references/standing-order-guidance.md` for context.
- **Standing orders**: Surprise-and-delight and self-improvement are defaults — adapt each to the agent's domain with concrete examples. Discover any domain-specific standing orders by asking: "Is there something this agent should always be watching for across every interaction?"
- **Philosophy**: The agent's approach to its domain. Not steps — principles. How does this agent think about its work?
- **Boundaries**: Behavioral guardrails — what the agent must always do or never do.
- **Anti-patterns**: Behavioral (how NOT to interact) and operational (how NOT to use idle time). Be concrete — include bad examples.
- **Dominion**: Read/write/deny access zones. Defaults: read `{project-root}/`, write sanctum, deny `.env`/credentials/secrets.

**BOND territories** — what should the agent discover about its owner during First Breath and ongoing sessions? These become the domain-specific sections of BOND-template.md. Examples: "How They Think Creatively", "Their Codebase and Languages", "Their Writing Style".

**First Breath territories** — domain-specific discovery areas beyond the universal ones. Load `./references/first-breath-adaptation-guidance.md` for guidance. Ask: "What does this agent need to learn about its owner that a generic assistant wouldn't?"

**PULSE behaviors (if autonomous):**

- Default wake behavior: What should the agent do on `--headless` with no task? Memory curation is always first priority.
- Domain-specific autonomous tasks: e.g., creative spark generation, pattern review, research
- Named task routing: task names mapped to actions
- Frequency and quiet hours

**Path conventions (CRITICAL):**

- Memory: `{project-root}/_bmad/memory/{skillName}/`
- Project-scope paths: `{project-root}/...` (any path relative to project root)
- Skill-internal: `./references/`, `./scripts/`
- Config variables used directly — they already contain full paths (no `{project-root}` prefix)

## Phase 4: Draft & Refine

Think one level deeper. Present a draft outline. Point out vague areas. Iterate until ready.

**Pruning check (apply before building):**

For every planned instruction — especially in capability prompts — ask: **would the LLM do this correctly given just the agent's persona and the desired outcome?** If yes, cut it.

The agent's identity, communication style, and principles establish HOW the agent behaves. Capability prompts should describe WHAT to achieve. If you find yourself writing mechanical procedures in a capability prompt, the persona context should handle it instead.

Watch especially for:

- Step-by-step procedures in capabilities that the LLM would figure out from the outcome description
- Capability prompts that repeat identity/style guidance already in SKILL.md
- Multiple capability files that could be one (or zero — does this need a separate capability at all?)
- Templates or reference files that explain things the LLM already knows

**Memory agent pruning checks (apply in addition to the above):**

Load `./references/sample-capability-prompt.md` as a quality reference for capability prompt review.

- **Bootloader weight:** Is SKILL.md lean (~30 lines of content)? It should contain ONLY identity seed, Three Laws, Sacred Truth, mission, and activation routing. If it has communication style, detailed principles, capability menus, or session close, move that content to sanctum templates.
- **Species-level mission specificity:** Is the mission specific to this agent type? "Assist your owner" fails. It should be something only this type of agent would say.
- **CREED seed quality:** Do core values and standing orders have real content? Empty placeholders like "{to be determined}" are not seeds — seeds have initial values that First Breath refines.
- **Capability prompt pattern:** Are prompts outcome-focused with "What Success Looks Like" sections? Do memory agent prompts include "Memory Integration" and "After the Session" sections?
- **First Breath territory check:** Are there domain-specific territories beyond the universal ones? A creative muse and a code review agent should have different discovery conversations.

## Phase 5: Build

**Load these before building:**

- `./references/standard-fields.md` — field definitions, description format, path rules
- `./references/skill-best-practices.md` — outcome-driven authoring, patterns, anti-patterns
- `./references/quality-dimensions.md` — build quality checklist

Build the agent using templates from `./assets/` and rules from `./references/template-substitution-rules.md`. Output to `{bmad_builder_output_folder}`.

**Capability prompts are outcome-driven:** Each `./references/{capability}.md` file should describe what the capability achieves and what "good" looks like — not prescribe mechanical steps. The agent's persona context (identity, communication style, principles in SKILL.md) informs how each capability is executed. Don't repeat that context in every capability prompt.

### Stateless Agent Output

Use `./assets/SKILL-template.md` (the full identity template). No Three Laws, no Sacred Truth, no sanctum files. Include the species-level mission in the Overview section.

```
{skill-name}/
├── SKILL.md               # Full identity + mission + capabilities (no Three Laws or Sacred Truth)
├── references/            # Progressive disclosure content
│   └── {capability}.md    # Each internal capability prompt (outcome-focused)
├── assets/                # Templates, starter files (if needed)
└── scripts/               # Deterministic code with tests (if needed)
```

### Memory Agent Output

Load these samples before generating memory agent files:
- `./references/sample-first-breath.md` — quality bar for first-breath.md
- `./references/sample-memory-guidance.md` — quality bar for memory-guidance.md
- `./references/sample-capability-prompt.md` — quality bar for capability prompts
- `./references/sample-init-sanctum.py` — structure reference for init script

{if-evolvable}Also load `./references/sample-capability-authoring.md` for capability-authoring.md quality reference.{/if-evolvable}

Use `./assets/SKILL-template-bootloader.md` for the lean bootloader. Generate the full sanctum architecture:

```
{skill-name}/
├── SKILL.md                    # From SKILL-template-bootloader.md (lean ~30 lines)
├── references/
│   ├── first-breath.md         # Generated from first-breath-template.md + domain territories
│   ├── memory-guidance.md      # From memory-guidance-template.md
│   ├── capability-authoring.md # From capability-authoring-template.md (if evolvable)
│   └── {capability}.md         # Core capability prompts (outcome-focused)
├── assets/
│   ├── INDEX-template.md       # From builder's INDEX-template.md
│   ├── PERSONA-template.md     # From builder's PERSONA-template.md, seeded
│   ├── CREED-template.md       # From builder's CREED-template.md, seeded with gathered values
│   ├── BOND-template.md        # From builder's BOND-template.md, seeded with domain sections
│   ├── MEMORY-template.md      # From builder's MEMORY-template.md
│   ├── CAPABILITIES-template.md # From builder's CAPABILITIES-template.md (fallback)
│   └── PULSE-template.md       # From builder's PULSE-template.md (if autonomous)
└── scripts/
    └── init-sanctum.py         # From builder's init-sanctum-template.py, parameterized
```

**Critical: Seed the templates.** Copy each builder asset template and fill in the content gathered during Phases 1-3:

- **CREED-template.md**: Real core values, real standing orders with domain examples, real philosophy, real boundaries, real anti-patterns. Not empty placeholders.
- **BOND-template.md**: Domain-specific sections pre-filled (e.g., "How They Think Creatively", "Their Codebase").
- **PERSONA-template.md**: Agent title, communication style seed, vibe prompt.
- **INDEX-template.md**: Bond summary, pulse summary (if autonomous).
- **PULSE-template.md** (if autonomous): Domain-specific autonomous tasks, task routing, frequency, quiet hours.
- **CAPABILITIES-template.md**: Built-in capability table pre-filled. Evolvable sections included only if evolvable capabilities enabled.

**Generate first-breath.md** from the appropriate template:
- Calibration-style: Use `./assets/first-breath-template.md`. Fill in identity-nature, owner-discovery-territories, mission context, pulse explanation (if autonomous), example-learned-capabilities (if evolvable).
- Configuration-style: Use `./assets/first-breath-config-template.md`. Fill in config-discovery-questions (3-7 domain-specific questions).

**Parameterize init-sanctum.py** from `./assets/init-sanctum-template.py`:
- Set `SKILL_NAME` to the agent's skill name
- Set `SKILL_ONLY_FILES` (always includes `first-breath.md`)
- Set `TEMPLATE_FILES` to match the actual templates in `./assets/`
- Set `EVOLVABLE` based on evolvable capabilities decision

| Location            | Contains                           | LLM relationship                     |
| ------------------- | ---------------------------------- | ------------------------------------ |
| **SKILL.md**        | Persona/identity/routing           | LLM identity and router              |
| **`./references/`** | Capability prompts, guidance       | Loaded on demand                     |
| **`./assets/`**     | Sanctum templates (memory agents)  | Copied into sanctum by init script   |
| **`./scripts/`**    | Init script, other scripts + tests | Invoked for deterministic operations |

**Activation guidance for built agents:**

**Stateless agents:** Single flow — load config, greet user, present capabilities.

**Memory agents:** Three-path activation (already in bootloader template):
1. No sanctum → run init script, then load first-breath.md
2. `--headless` → load PULSE.md from sanctum, execute, exit
3. Normal → batch-load sanctum files (PERSONA, CREED, BOND, MEMORY, CAPABILITIES), become yourself, greet owner

**If the built agent includes scripts**, also load `./references/script-standards.md` — ensures PEP 723 metadata, correct shebangs, and `uv run` invocation from the start.

**Lint gate** — after building, validate and auto-fix:

If subagents available, delegate lint-fix to a subagent. Otherwise run inline.

1. Run both lint scripts in parallel:
   ```bash
   python3 ./scripts/scan-path-standards.py {skill-path}
   python3 ./scripts/scan-scripts.py {skill-path}
   ```
2. Fix high/critical findings and re-run (up to 3 attempts per script)
3. Run unit tests if scripts exist in the built skill

## Phase 6: Summary

Present what was built: location, structure, first-run behavior, capabilities.

Run unit tests if scripts exist. Remind user to commit before quality analysis.

**For memory agents, also explain:**

- The First Breath experience — what the owner will encounter on first activation. Briefly describe the onboarding style (calibration or configuration) and what the conversation will explore.
- Which files are seeds vs. fully populated — sanctum templates have seeded values that First Breath refines; MEMORY.md starts empty.
- The capabilities that were registered — list the built-in capabilities by code and name.
- If autonomous mode: explain PULSE behavior (what it does on `--headless`, task routing, frequency) and how to set up cron/scheduling.
- The init script: explain that `uv run ./scripts/init-sanctum.py <project-root> <skill-path>` runs before the first conversation to create the sanctum structure.

**Offer quality analysis:** Ask if they'd like a Quality Analysis to identify opportunities. If yes, load `quality-analysis.md` with the agent path.
