# Quality Dimensions — Quick Reference

Seven dimensions to keep in mind when building agent skills. The quality scanners check these automatically during quality analysis — this is a mental checklist for the build phase.

## 1. Outcome-Driven Design

Describe what each capability achieves, not how to do it step by step. The agent's persona context (identity, communication style, principles) informs HOW — capability prompts just need the WHAT.

- **The test:** Would removing this instruction cause the agent to produce a worse outcome? If the agent would do it anyway given its persona and the desired outcome, the instruction is noise.
- **Pruning:** If a capability prompt teaches the LLM something it already knows — or repeats guidance already in the agent's identity/style — cut it.
- **When procedure IS value:** Exact script invocations, specific file paths, API calls, security-critical operations. These need low freedom.

## 2. Informed Autonomy

The executing agent needs enough context to make judgment calls when situations don't match the script. The Overview section establishes this: domain framing, theory of mind, design rationale.

- Simple agents with 1-2 capabilities need minimal context
- Agents with memory, autonomous mode, or complex capabilities need domain understanding, user perspective, and rationale for non-obvious choices
- When in doubt, explain _why_ — an agent that understands the mission improvises better than one following blind steps

## 3. Intelligence Placement

Scripts handle plumbing (fetch, transform, validate). Prompts handle judgment (interpret, classify, decide).

**Test:** If a script contains an `if` that decides what content _means_, intelligence has leaked.

**Reverse test:** If a prompt validates structure, counts items, parses known formats, compares against schemas, or checks file existence — determinism has leaked into the LLM. That work belongs in a script.

## 4. Progressive Disclosure

SKILL.md stays focused. Detail goes where it belongs.

- Capability instructions → `./references/`
- Reference data, schemas, large tables → `./references/`
- Templates, starter files → `./assets/`
- Memory discipline → `./references/memory-system.md`
- Multi-capability SKILL.md under ~250 lines: fine as-is
- Single-purpose up to ~500 lines: acceptable if focused

## 5. Description Format

Two parts: `[5-8 word summary]. [Use when user says 'X' or 'Y'.]`

Default to conservative triggering. See `./references/standard-fields.md` for full format.

## 6. Path Construction

Use `{project-root}` for any project-scope path. Use `./` for skill-internal paths. Config variables used directly — they already contain `{project-root}`.

See `./references/standard-fields.md` for correct/incorrect patterns.

## 7. Token Efficiency

Remove genuine waste (repetition, defensive padding, meta-explanation). Preserve context that enables judgment (persona voice, domain framing, theory of mind, design rationale). These are different things — never trade effectiveness for efficiency. A capability that works correctly but uses extra tokens is always better than one that's lean but fails edge cases.

## 8. Sanctum Architecture (memory agents only)

Memory agents have additional quality dimensions beyond the general seven:

- **Bootloader weight:** SKILL.md should be ~30 lines of content. If it's heavier, content belongs in sanctum templates instead.
- **Template seed quality:** All 6 standard sanctum templates (INDEX, PERSONA, CREED, BOND, MEMORY, CAPABILITIES) must exist. CREED, BOND, and PERSONA should have meaningful seed values, not empty placeholders. MEMORY starts empty (correct).
- **First Breath completeness:** first-breath.md must exist with all universal mechanics (for calibration: pacing, mirroring, hypotheses, silence-as-signal, save-as-you-go; for configuration: discovery questions, urgency detection). Must have domain-specific territories beyond universal ones. Birthday ceremony must be present.
- **Standing orders:** CREED template must include surprise-and-delight and self-improvement, domain-adapted with concrete examples.
- **Init script validity:** init-sanctum.py must exist, SKILL_NAME must match the skill name, TEMPLATE_FILES must match actual templates in ./assets/.
- **Self-containment:** After init script runs, the sanctum must be fully self-contained. The agent should not depend on the skill bundle for normal operation (only for First Breath and init).
