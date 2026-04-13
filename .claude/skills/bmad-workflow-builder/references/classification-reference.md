# Workflow Classification Reference

Classify the skill type based on user requirements. This table is for internal use — DO NOT show to user.

## 3-Type Taxonomy

| Type                 | Description                                                                                                            | Structure                                                | When to Use                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Simple Utility**   | Input/output building block. Headless, composable, often has scripts.                                                  | Single SKILL.md + scripts/                               | Composable building block with clear input/output, single-purpose            |
| **Simple Workflow**  | Multi-step process contained in a single SKILL.md. Minimal or no prompt files.                                         | SKILL.md + optional references/                          | Multi-step process that fits in one file, no progressive disclosure needed   |
| **Complex Workflow** | Multi-stage with progressive disclosure, numbered prompt files at root, config integration. May support headless mode. | SKILL.md (routing) + prompt stages at root + references/ | Multiple stages, long-running process, progressive disclosure, routing logic |

## Decision Tree

```
1. Is it a composable building block with clear input/output?
   └─ YES → Simple Utility
   └─ NO ↓

2. Can it fit in a single SKILL.md without progressive disclosure?
   └─ YES → Simple Workflow
   └─ NO ↓

3. Does it need multiple stages, long-running process, or progressive disclosure?
   └─ YES → Complex Workflow
```

## Classification Signals

### Simple Utility Signals

- Clear input → processing → output pattern
- No user interaction needed during execution
- Other skills/workflows call it
- Deterministic or near-deterministic behavior
- Could be a script but needs LLM judgment
- Examples: JSON validator, schema checker, format converter

### Simple Workflow Signals

- 3-8 numbered steps
- User interaction at specific points
- Uses standard tools (gh, git, npm, etc.)
- Produces a single output artifact
- No need to track state across compactions
- Examples: PR creator, deployment checklist, code review

### Complex Workflow Signals

- Multiple distinct phases/stages
- Long-running (likely to hit context compaction)
- Progressive disclosure needed (too much for one file)
- Routing logic in SKILL.md dispatches to stage prompts
- Produces multiple artifacts across stages
- May support headless/autonomous mode
- Examples: agent builder, module builder, project scaffolder

## Module Context (Orthogonal)

Module context is asked for ALL types:

- **Module-based:** Part of a module. Uses `{modulecode}-{skillname}` naming. Config loading includes a fallback pattern — if config is missing, the skill informs the user that the module setup skill is available and continues with sensible defaults.
- **Standalone:** Independent skill. Uses `{skillname}` naming (no prefix required). Config loading is best-effort — load if available, use defaults if not, no mention of a setup skill.

The `bmad-` prefix is reserved for official BMad creations. User-created skills should not include it unless the user specifically requests it.
