# Quality Dimensions — Quick Reference

Seven dimensions to keep in mind when building skills. The quality scanners check these automatically during quality analysis — this is a mental checklist for the build phase.

## 1. Outcome-Driven Design

Describe what to achieve, not how to get there step by step. Only add procedural detail when the LLM would genuinely fail without it.

- **The test:** Would removing this instruction cause the LLM to produce a worse outcome? If the LLM would do it anyway, the instruction is noise.
- **Pruning:** If a block teaches the LLM something it already knows — scoring algorithms for subjective judgment, calibration tables for reading the room, weighted formulas for picking relevant participants — cut it. These are things LLMs do naturally.
- **When procedure IS value:** Exact script invocations, specific file paths, API calls with precise parameters, security-critical operations. These need low freedom because there's one right way.

## 2. Informed Autonomy

The executing agent needs enough context to make judgment calls when situations don't match the script. The Overview establishes this: domain framing, theory of mind, design rationale.

- Simple utilities need minimal context — input/output is self-explanatory
- Interactive/complex workflows need domain understanding, user perspective, and rationale for non-obvious choices
- When in doubt, explain _why_ — an agent that understands the mission improvises better than one following blind steps

## 3. Intelligence Placement

Scripts handle plumbing (fetch, transform, validate). Prompts handle judgment (interpret, classify, decide).

**Test:** If a script contains an `if` that decides what content _means_, intelligence has leaked.

**Reverse test:** If a prompt validates structure, counts items, parses known formats, compares against schemas, or checks file existence — determinism has leaked into the LLM. That work belongs in a script.

## 4. Progressive Disclosure

SKILL.md stays focused. Detail goes where it belongs.

- Stage instructions → `references/`
- Reference data, schemas, large tables → `references/`
- Templates, config files → `assets/`
- Multi-branch SKILL.md under ~250 lines: fine as-is
- Single-purpose up to ~500 lines (~5000 tokens): acceptable if focused

## 5. Description Format

Two parts: `[5-8 word summary]. [Use when user says 'X' or 'Y'.]`

Default to conservative triggering. See `./standard-fields.md` for full format.

## 6. Path Construction

Use `{project-root}` for any project-scope path. Use `./` only for same-folder references; cross-directory paths are bare and relative to skill root. Config variables used directly — they already contain `{project-root}`.

See `./standard-fields.md` for correct/incorrect patterns.

## 7. Token Efficiency

Remove genuine waste (repetition, defensive padding, meta-explanation). Preserve context that enables judgment (domain framing, theory of mind, design rationale). These are different things — never trade effectiveness for efficiency. A skill that works correctly but uses extra tokens is always better than one that's lean but fails edge cases.
