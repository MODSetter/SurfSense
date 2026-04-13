# Template Substitution Rules

The SKILL-template provides a minimal skeleton: frontmatter, overview, agent identity sections, memory, and activation with config loading. Everything beyond that is crafted by the builder based on what was learned during discovery and requirements phases.

## Frontmatter

- `{module-code-or-empty}` → Module code prefix with hyphen (e.g., `cis-`) or empty for standalone. The `bmad-` prefix is reserved for official BMad creations; user agents should not include it.
- `{agent-name}` → Agent functional name (kebab-case)
- `{skill-description}` → Two parts: [4-6 word summary]. [trigger phrases]
- `{displayName}` → Friendly display name
- `{skillName}` → Full skill name with module prefix

## Module Conditionals

### For Module-Based Agents

- `{if-module}` ... `{/if-module}` → Keep the content inside
- `{if-standalone}` ... `{/if-standalone}` → Remove the entire block including markers
- `{module-code}` → Module code without trailing hyphen (e.g., `cis`)
- `{module-setup-skill}` → Name of the module's setup skill (e.g., `cis-setup`)

### For Standalone Agents

- `{if-module}` ... `{/if-module}` → Remove the entire block including markers
- `{if-standalone}` ... `{/if-standalone}` → Keep the content inside

## Memory Conditionals (legacy — stateless agents)

- `{if-memory}` ... `{/if-memory}` → Keep if agent has persistent memory, otherwise remove
- `{if-no-memory}` ... `{/if-no-memory}` → Inverse of above

## Headless Conditional (legacy — stateless agents)

- `{if-headless}` ... `{/if-headless}` → Keep if agent supports headless mode, otherwise remove

## Agent Type Conditionals

These replace the legacy memory/headless conditionals for the new agent type system:

- `{if-memory-agent}` ... `{/if-memory-agent}` → Keep for memory and autonomous agents, remove for stateless
- `{if-stateless-agent}` ... `{/if-stateless-agent}` → Keep for stateless agents, remove for memory/autonomous
- `{if-evolvable}` ... `{/if-evolvable}` → Keep if agent has evolvable capabilities (owner can teach new capabilities)
- `{if-pulse}` ... `{/if-pulse}` → Keep if agent has autonomous mode (PULSE enabled)

**Mapping from legacy conditionals:**
- `{if-memory}` is equivalent to `{if-memory-agent}` — both mean the agent has persistent state
- `{if-headless}` maps to `{if-pulse}` — both mean the agent can operate autonomously

## Template Selection

The builder selects the appropriate SKILL.md template based on agent type:

- **Stateless agent:** Use `./assets/SKILL-template.md` (full identity, no Three Laws/Sacred Truth)
- **Memory/autonomous agent:** Use `./assets/SKILL-template-bootloader.md` (lean bootloader with Three Laws, Sacred Truth, 3-path activation)

## Beyond the Template

The builder determines the rest of the agent structure — capabilities, activation flow, sanctum templates, init script, First Breath, capability routing, external skills, scripts — based on the agent's requirements. The template intentionally does not prescribe these.

## Path References

All generated agents use `./` prefix for skill-internal paths:

**Stateless agents:**
- `./references/{capability}.md` — Individual capability prompts
- `./scripts/` — Python/shell scripts for deterministic operations

**Memory agents:**
- `./references/first-breath.md` — First Breath onboarding (loaded when no sanctum exists)
- `./references/memory-guidance.md` — Memory philosophy
- `./references/capability-authoring.md` — Capability evolution framework (if evolvable)
- `./references/{capability}.md` — Individual capability prompts
- `./assets/{FILE}-template.md` — Sanctum templates (copied by init script)
- `./scripts/init-sanctum.py` — Deterministic sanctum scaffolding
