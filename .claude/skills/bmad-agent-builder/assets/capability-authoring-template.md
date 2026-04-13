---
name: capability-authoring
description: Guide for creating and evolving learned capabilities
---

# Capability Authoring

When your owner wants you to learn a new ability, you create a capability together. This guide tells you how to write, format, and register it.

## Capability Types

A capability can take several forms:

### Prompt (default)
A markdown file with guidance on what to achieve. Best for judgment-based tasks where you need flexibility.

```
capabilities/
└── {example-capability}.md
```

### Script
A Python or bash script for deterministic tasks — calculations, file processing, data transformation, API calls. Create the script alongside a short markdown file that describes when and how to use it.

```
capabilities/
├── {example-script}.md          # When to run, what to do with results
└── {example-script}.py          # The actual computation
```

### Multi-file
A folder with multiple files for complex capabilities — mini-workflows with multiple steps, reference materials, templates.

```
capabilities/
└── {example-complex}/
    ├── {example-complex}.md     # Main guidance
    ├── structure.md             # Reference material
    └── examples.md              # Examples for tone/format
```

### External Skill Reference
Point to an existing installed skill rather than reinventing it. If you discover a skill that would serve your owner well, suggest it — but always ask before installing.

```markdown
## Learned
| Code | Name | Description | Source | Added |
|------|------|-------------|--------|-------|
| [XX] | Skill Name | What it does | External: `skill-name` | YYYY-MM-DD |
```

## Prompt File Format

Every capability prompt file should have this frontmatter:

```markdown
---
name: {kebab-case-name}
description: {one line — what this does}
code: {2-letter menu code, unique across all capabilities}
added: {YYYY-MM-DD}
type: prompt | script | multi-file | external
---
```

The body should be **outcome-focused** — describe what success looks like, not step-by-step instructions. Include:

- **What Success Looks Like** — the outcome, not the process
- **Context** — constraints, preferences, domain knowledge
- **Memory Integration** — how to use MEMORY.md and BOND.md to personalize
- **After Use** — what to capture in the session log

## Creating a Capability (The Flow)

1. Owner says they want you to do something new
2. Explore what they need through conversation — don't rush to write
3. Draft the capability prompt and show it to them
4. Refine based on feedback
5. Save to `capabilities/` (file or folder depending on type)
6. Update CAPABILITIES.md — add a row to the Learned table
7. Update INDEX.md — note the new file under "My Files"
8. Confirm: "I'll remember how to do this next session. You can trigger it with [{code}]."

## Scripts

When a capability needs deterministic logic (math, file parsing, API calls), write a script:

- **Python** preferred for portability
- Keep scripts focused — one job per script
- The companion markdown file says WHEN to run the script and WHAT to do with results
- Scripts should read from and write to files in the sanctum
- Never hardcode paths — accept sanctum path as argument

## Refining Capabilities

Capabilities evolve. After use, if the owner gives feedback:

- Update the capability prompt with refined context
- Add to the "Owner Preferences" section if one exists
- Log the refinement in the session log

A capability that's been refined 3-4 times is usually excellent. The first draft is rarely the best.

## Retiring Capabilities

If a capability is no longer useful:

- Remove its row from CAPABILITIES.md
- Keep the file (don't delete — the owner might want it back)
- Note the retirement in the session log
