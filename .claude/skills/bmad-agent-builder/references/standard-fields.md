# Standard Agent Fields

## Frontmatter Fields

Only these fields go in the YAML frontmatter block:

| Field         | Description                                       | Example                                         |
| ------------- | ------------------------------------------------- | ----------------------------------------------- |
| `name`        | Full skill name (kebab-case, same as folder name) | `agent-tech-writer`, `cis-agent-lila` |
| `description` | [What it does]. [Use when user says 'X' or 'Y'.]  | See Description Format below                    |

## Content Fields

These are used within the SKILL.md body — never in frontmatter:

| Field         | Description                              | Example                              |
| ------------- | ---------------------------------------- | ------------------------------------ |
| `displayName` | Friendly name (title heading, greetings) | `Paige`, `Lila`, `Floyd`             |
| `title`       | Role title                               | `Tech Writer`, `Holodeck Operator`   |
| `icon`        | Single emoji                             | `🔥`, `🌟`                           |
| `role`        | Functional role                          | `Technical Documentation Specialist` |
| `memory`      | Memory folder (optional)                 | `{skillName}/`                       |

### Memory Agent Fields (bootloader SKILL.md only)

These fields appear in memory agent SKILL.md files, which use a lean bootloader structure instead of the full stateless layout:

| Field              | Description                                              | Example                                                            |
| ------------------ | -------------------------------------------------------- | ------------------------------------------------------------------ |
| `identity-seed`    | 2-3 sentence personality DNA (expands in PERSONA.md)     | "Equal parts provocateur and collaborator..."                      |
| `species-mission`  | Domain-specific purpose statement                        | "Unlock your owner's creative potential..."                        |
| `agent-type`       | One of: `stateless`, `memory`, `autonomous`              | `memory`                                                           |
| `onboarding-style` | First Breath style: `calibration` or `configuration`     | `calibration`                                                      |
| `sanctum-location` | Path to sanctum folder                                   | `{project-root}/_bmad/memory/{skillName}/`                         |

### Sanctum Template Seed Fields (CREED, BOND, PERSONA templates)

These are content blocks the builder fills during Phase 5 Build. They are NOT template variables for init-script substitution — they are baked into the agent's template files as real content.

| Field                       | Destination Template    | Description                                                  |
| --------------------------- | ----------------------- | ------------------------------------------------------------ |
| `core-values`               | CREED-template.md       | 3-5 domain-specific operational values (bulleted list)       |
| `standing-orders`           | CREED-template.md       | Domain-adapted standing orders (always active, never complete) |
| `philosophy`                | CREED-template.md       | Agent's approach to its domain (principles, not steps)       |
| `boundaries`                | CREED-template.md       | Behavioral guardrails                                        |
| `anti-patterns-behavioral`  | CREED-template.md       | How NOT to interact (with concrete bad examples)             |
| `bond-domain-sections`      | BOND-template.md        | Domain-specific discovery sections for the owner             |
| `communication-style-seed`  | PERSONA-template.md     | Initial personality expression seed                          |
| `vibe-prompt`               | PERSONA-template.md     | Prompt for vibe discovery during First Breath                |

## Overview Section Format

The Overview is the first section after the title — it primes the AI for everything that follows.

**3-part formula:**

1. **What** — What this agent does
2. **How** — How it works (role, approach, modes)
3. **Why/Outcome** — Value delivered, quality standard

**Templates by agent type:**

**Companion agents:**

```markdown
This skill provides a {role} who helps users {primary outcome}. Act as {displayName} — {key quality}. With {key features}, {displayName} {primary value proposition}.
```

**Workflow agents:**

```markdown
This skill helps you {outcome} through {approach}. Act as {role}, guiding users through {key stages/phases}. Your output is {deliverable}.
```

**Utility agents:**

```markdown
This skill {what it does}. Use when {when to use}. Returns {output format} with {key feature}.
```

## SKILL.md Description Format

```
{description of what the agent does}. Use when the user asks to talk to {displayName}, requests the {title}, or {when to use}.
```

## Path Rules

### Same-Folder References

Use `./` only when referencing a file in the same directory as the file containing the reference:

- From `references/build-process.md` → `./some-guide.md` (both in references/)
- From `scripts/scan.py` → `./utils.py` (both in scripts/)

### Cross-Directory References

Use bare paths relative to the skill root — no `./` prefix:

- `references/memory-system.md`
- `scripts/calculate-metrics.py`
- `assets/template.md`

These work from any file in the skill because they're always resolved from the skill root. **Never use `./` for cross-directory paths** — `./scripts/foo.py` from a file in `references/` is misleading because `scripts/` is not next to that file.

### Memory Files

Always use `{project-root}` prefix: `{project-root}/_bmad/memory/{skillName}/`

The memory `index.md` is the single entry point to the agent's memory system — it tells the agent what else to load (boundaries, logs, references, etc.). Load it once on activation; don't duplicate load instructions for individual memory files.

### Project-Scope Paths

Use `{project-root}/...` for any path relative to the project root:

- `{project-root}/_bmad/planning/prd.md`
- `{project-root}/docs/report.md`

### Config Variables

Use directly — they already contain `{project-root}` in their resolved values:

- `{output_folder}/file.md`
- Correct: `{bmad_builder_output_folder}/agent.md`
- Wrong: `{project-root}/{bmad_builder_output_folder}/agent.md` (double-prefix)
