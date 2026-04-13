---
name: edit-guidance
description: Guides targeted edits to existing agents. Loaded when the user chooses "Edit" from the 3-way routing question. Covers intent clarification, cascade assessment, type-aware editing, and post-edit validation.
---

**Language:** Use `{communication_language}` for all output.

# Edit Guidance

Edit means: change specific behavior while preserving the agent's existing identity and design. You are a surgeon, not an architect. Read first, understand the design intent, then make precise changes that maintain coherence.

## 1. Understand What They Want to Change

Start by reading the agent's full structure. For memory/autonomous agents, read SKILL.md and all sanctum templates. For stateless agents, read SKILL.md and all references.

Then ask: **"What's not working the way you want?"** Let the user describe the problem in their own words. Common edit categories:

- **Persona tweaks** -- voice, tone, communication style, how the agent feels to interact with
- **Capability changes** -- add, remove, rename, or rework what the agent can do
- **Memory structure** -- what the agent tracks, BOND territories, memory guidance
- **Standing orders / CREED** -- values, boundaries, anti-patterns, philosophy
- **Activation behavior** -- how the agent starts up, greets, routes
- **PULSE adjustments** (autonomous only) -- wake behavior, task routing, frequency

Do not assume the edit is small. A user saying "make it friendlier" might mean a persona tweak or might mean rethinking the entire communication style across CREED and capability prompts. Clarify scope before touching anything.

## 2. Assess Cascade

Some edits are local. Others ripple. Before making changes, map the impact:

**Local edits (single file, no cascade):**
- Fixing wording in a capability prompt
- Adjusting a standing order's examples
- Updating BOND territory labels
- Tweaking the greeting or session close

**Cascading edits (touch multiple files):**
- Adding a capability: new reference file + CAPABILITIES-template entry + possibly CREED update if it changes what the agent watches for
- Changing the agent's core identity: SKILL.md seed + PERSONA-template + possibly CREED philosophy + capability prompts that reference the old identity
- Switching agent type (e.g., stateless to memory): this is a rebuild, not an edit. Redirect to the build process.
- Adding/removing autonomous mode: adding or removing PULSE-template, updating SKILL.md activation routing, updating init-sanctum.py

When the cascade is non-obvious, explain it: "Adding this capability also means updating the capabilities registry and possibly seeding a new standing order. Want me to walk through what changes?"

## 3. Edit by Agent Type

### Stateless Agents

Everything lives in SKILL.md and `./references/`. Edits are straightforward. The main risk is breaking the balance between persona context and capability prompts. Remember: persona informs HOW, capabilities describe WHAT. If the edit blurs this line, correct it.

### Memory Agents

The bootloader SKILL.md is intentionally lean (~30 lines of content). Resist the urge to add detail there. Most edits belong in sanctum templates:

- Persona changes go in PERSONA-template.md, not SKILL.md (the bootloader carries only the identity seed)
- Values and behavioral rules go in CREED-template.md
- Relationship tracking goes in BOND-template.md
- Capability registration goes in CAPABILITIES-template.md

If the agent has already been initialized (sanctum exists), edits to templates only affect future initializations. Note this for the user and suggest whether they should also edit the live sanctum files directly.

### Autonomous Agents

Same as memory agents, plus PULSE-template.md. Edits to autonomous behavior (wake tasks, frequency, named tasks) go in PULSE. If adding a new autonomous task, check that it has a corresponding capability prompt and that CREED boundaries permit it.

## 4. Make the Edit

Read the target file(s) completely before changing anything. Understand why each section exists. Then:

- **Preserve voice.** Match the existing writing style. If the agent speaks in clipped technical language, don't introduce flowery prose. If it's warm and conversational, don't inject formality.
- **Preserve structure.** Follow the conventions already in the file. If capabilities use "What Success Looks Like" sections, new capabilities should too. If standing orders follow a specific format, match it.
- **Apply outcome-driven principles.** Even in edits, check: would the LLM do this correctly given just the persona and desired outcome? If yes, don't add procedural detail.
- **Update cross-references.** If you renamed a capability, check SKILL.md routing, CAPABILITIES-template, and any references between capability prompts.

For memory agents with live sanctums: confirm with the user whether to edit the templates (affects future init), the live sanctum files (affects current sessions), or both.

## 5. Validate After Edit

After completing edits, run a lightweight coherence check:

- **Read the modified files end-to-end.** Does the edit feel integrated, or does it stick out?
- **Check identity alignment.** Does the change still sound like this agent? If you added a capability, does it fit the agent's stated mission and personality?
- **Check structural integrity.** Are all cross-references valid? Does SKILL.md routing still point to real files? Does CAPABILITIES-template list match actual capability reference files?
- **Run the lint gate.** Execute `scan-path-standards.py` and `scan-scripts.py` against the skill path to catch path convention or script issues introduced by the edit.

If the edit was significant (new capability, persona rework, CREED changes), suggest a full Quality Analysis to verify nothing drifted. Offer it; don't force it.

Present a summary: what changed, which files were touched, and any recommendations for the user to verify in a live session.
