---
name: convert-process
description: Automated skill conversion workflow. Analyzes an existing skill, rebuilds it outcome-driven, and generates a before/after HTML comparison report.
---

**Language:** Use `{communication_language}` for all output.

# Convert Process

Convert any existing skill into a BMad-compliant, outcome-driven equivalent. Whether the input is bloated, poorly structured, or simply non-conformant, this process extracts intent, rebuilds following BMad best practices, and produces a before/after comparison report.

This process is always headless — no interactive questions. The original skill provides all the context needed.

## Step 1: Capture the Original

1. **Fetch/read the original skill.** If a URL was provided, fetch the raw content. If a local path, read all files in the skill directory.

2. **Save the original.** Write the complete original content to `{bmad_builder_reports}/convert-{skill-name}/original/SKILL.md` (and any additional files if the original is a multi-file skill). This preserved copy is needed for the comparison script.

3. **Note the source** (URL or path) for the report metadata.

## Step 2: Rebuild from Intent

Load and follow `build-process.md` with these parameters pre-set:

- **Intent:** Rebuild — rethink from core outcomes, the original is reference material only
- **Headless mode:** Active — skip all interactive questions, use sensible defaults
- **Discovery questions:** Answer them yourself by analyzing the original skill's intent
- **Classification:** Determine from the original's structure and purpose
- **Requirements:** Derive from the original, applying aggressive pruning

**Critical:** Do not inherit the original's verbosity, structure, or mechanical procedures. Extract *what it achieves*, then build the leanest skill that delivers the same outcome.

When the build process reaches Phase 6 (Summary), skip the quality analysis offer and continue to Step 3 below.

## Step 3: Generate Comparison Report

After the rebuilt skill is complete:

1. **Create the analysis file.** Write `{bmad_builder_reports}/convert-{skill-name}/convert-analysis.json`:

```json
{
  "skill_name": "{skill-name}",
  "original_source": "{url-or-path-provided-by-user}",
  "cuts": [
    {
      "category": "Category Name",
      "description": "Why this content was cut",
      "examples": ["Specific example 1", "Specific example 2"],
      "severity": "high|medium|low"
    }
  ],
  "retained": [
    {
      "category": "Category Name",
      "description": "Why this content was kept — what behavioral impact it has"
    }
  ],
  "verdict": "One sharp sentence summarizing the conversion"
}
```

### Categorizing Changes

Not every conversion is about bloat — some skills are well-intentioned but non-conformant. Categorize what changed and why, drawing from these common patterns:

**Content removal** (when applicable):

| Category | Signal |
|----------|--------|
| **Training Data Redundancy** | Facts, biographies, domain knowledge the LLM already has |
| **Prescriptive Procedures** | Step-by-step instructions for things the LLM reasons through naturally |
| **Mechanical Frameworks** | Scoring rubrics, decision matrices, evaluation checklists for subjective judgment |
| **Generic Boilerplate** | "Best Practices", "Common Pitfalls", "When to Use/Not Use" filler |
| **Template Bloat** | Response format templates, greeting scripts, output structure prescriptions |
| **Redundant Examples** | Examples that repeat what the instructions already say |
| **Per-Platform Duplication** | Separate instructions per platform when one adaptive instruction works |

**Structural changes** (conformance to BMad best practices):

| Category | Signal |
|----------|--------|
| **Progressive Disclosure** | Monolithic content split into SKILL.md routing + references |
| **Outcome-Driven Rewrite** | Prescriptive instructions reframed as outcomes |
| **Frontmatter/Description** | Added or fixed BMad-compliant frontmatter and trigger phrases |
| **Path Convention Fixes** | Corrected file references to use `./` for skill-internal, `{project-root}/` for project-scope |

Severity: **high** = significant impact on quality or compliance, **medium** = notable improvement, **low** = minor or stylistic.

### Categorizing Retained Content

Focus on what the LLM *wouldn't* do correctly without being told. The retained categories should explain why each piece earns its place.

2. **Generate the HTML report:**

```bash
python3 ./scripts/generate-convert-report.py \
  "{bmad_builder_reports}/convert-{skill-name}/original" \
  "{rebuilt-skill-path}" \
  "{bmad_builder_reports}/convert-{skill-name}/convert-analysis.json" \
  -o "{bmad_builder_reports}/convert-{skill-name}/convert-report.html" \
  --open
```

3. **Present the summary** — key metrics, reduction percentages, report file location. The HTML report opens automatically.
