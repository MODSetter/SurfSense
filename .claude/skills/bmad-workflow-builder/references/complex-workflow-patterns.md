# BMad Module Workflows

Advanced patterns for BMad module workflows — long-running, multi-stage processes with progressive disclosure, config integration, and compaction survival.

---

## Workflow Persona

BMad workflows treat the human operator as the expert. The agent facilitates — asks clarifying questions, presents options with trade-offs, validates before irreversible actions. The operator knows their domain; the workflow knows the process.

---

## Config Reading and Integration

Workflows read config from `{project-root}/_bmad/config.yaml` and `config.user.yaml`.

### Config Loading Pattern

**Module-based skills** — load with fallback and setup skill awareness:

```
Load config from {project-root}/_bmad/config.yaml ({module-code} section) and config.user.yaml.
If missing: inform user that {module-setup-skill} is available, continue with sensible defaults.
```

**Standalone skills** — load best-effort:

```
Load config from {project-root}/_bmad/config.yaml and config.user.yaml if available.
If missing: continue with defaults — no mention of setup skill.
```

### Required Core Variables

Load core config (user preferences, language, output locations) with sensible defaults. If the workflow creates documents, include document output language.

**Example config line for a document-producing workflow:**

```
vars: user_name:BMad,communication_language:English,document_output_language:English,output_folder:{project-root}/_bmad-output,bmad_builder_output_folder:{project-root}/bmad-builder-creations/
```

Config variables used directly in prompts — they already contain `{project-root}` in resolved values.

---

## Long-Running Workflows: Compaction Survival

Workflows that run long may trigger context compaction. Critical state MUST survive in output files.

### The Document-Itself Pattern

**The output document is the cache.** Write directly to the file you're creating, updating progressively. The document stores both content and context:

- **YAML front matter** — paths to input files, current status
- **Draft sections** — progressive content as it's built
- **Status marker** — which stage is complete

Each stage after the first reads the output document to recover context. If compacted, re-read input files listed in the YAML front matter.

```markdown
---
title: 'Analysis: Research Topic'
status: 'analysis'
inputs:
  - '{project_root}/docs/brief.md'
created: '2025-03-02T10:00:00Z'
updated: '2025-03-02T11:30:00Z'
---
```

**When to use:** Guided flows with long documents, yolo flows with multiple turns. Single-pass yolo can wait to write final output.

**When NOT to use:** Short single-turn outputs, purely conversational workflows, multiple independent artifacts (each gets its own file).

---

## Sequential Progressive Disclosure

Use numbered prompt files at the skill root when:

- Multi-phase workflow with ordered stages
- Input of one phase affects the next
- Workflow is long-running and stages shouldn't be visible upfront

### Structure

```
my-workflow/
├── SKILL.md                    # Routing + entry logic (minimal)
├── references/
│   ├── 01-discovery.md         # Stage 1
│   ├── 02-planning.md          # Stage 2
│   ├── 03-execution.md         # Stage 3
│   └── templates.md            # Supporting reference
└── scripts/
    └── validator.sh
```

Each stage prompt specifies prerequisites, progression conditions, and next destination. SKILL.md is minimal routing logic.

**Keep inline in SKILL.md when:** Simple skill, well-known domain, single-purpose utility, all stages independent.

---

## Module Metadata Reference

BMad module workflows require extended frontmatter metadata. See `./metadata-reference.md` for the metadata template and field explanations.

---

## Workflow Architecture Checklist

Before finalizing a BMad module workflow, verify:

- [ ] Facilitator persona — treats operator as expert?
- [ ] Config integration — language, output locations read and used?
- [ ] Portable paths — artifacts use `{project_root}`?
- [ ] Compaction survival — each stage writes to output document?
- [ ] Document-as-cache — YAML front matter with status and inputs?
- [ ] Progressive disclosure — stages in `references/` with progression conditions?
- [ ] Final polish — subagent polish step at the end?
- [ ] Recovery — can resume by reading output doc front matter?
