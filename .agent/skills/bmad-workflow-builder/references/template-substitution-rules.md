# Template Substitution Rules

The SKILL-template provides a minimal skeleton: frontmatter, overview, and activation with config loading. Everything beyond that is crafted by the builder based on what was learned during discovery and requirements phases.

## Frontmatter

- `{module-code-or-empty}` → Module code prefix with hyphen (e.g., `bmb-`) or empty for standalone. The `bmad-` prefix is reserved for official BMad creations; user skills should not include it.
- `{skill-name}` → Skill functional name (kebab-case)
- `{skill-description}` → Two parts: [5-8 word summary]. [trigger phrases]

## Module Conditionals

### For Module-Based Skills

- `{if-module}` ... `{/if-module}` → Keep the content inside
- `{if-standalone}` ... `{/if-standalone}` → Remove the entire block including markers
- `{module-code}` → Module code without trailing hyphen (e.g., `bmb`)
- `{module-setup-skill}` → Name of the module's setup skill (e.g., `mymod-setup`)

### For Standalone Skills

- `{if-module}` ... `{/if-module}` → Remove the entire block including markers
- `{if-standalone}` ... `{/if-standalone}` → Keep the content inside

## Beyond the Template

The builder determines the rest of the skill structure — body sections, phases, stages, scripts, external skills, headless mode, role guidance — based on the skill type classification and requirements gathered during the build process. The template intentionally does not prescribe these; the builder has the context to craft them.

## Path References

All generated skills use paths relative to skill root (cross-directory) or `./` (same-folder):

- `references/{reference}.md` — Reference documents loaded on demand
- `references/{stage}.md` — Stage prompts (complex workflows)
- `scripts/` — Python/shell scripts for deterministic operations
