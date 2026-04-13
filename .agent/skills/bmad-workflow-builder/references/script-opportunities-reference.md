# Script Opportunities Reference — Workflow Builder

**Reference: `./script-standards.md` for script creation guidelines.**

## Core Principle

Scripts handle deterministic operations (validate, transform, count). Prompts handle judgment (interpret, classify, decide). If a check has clear pass/fail criteria, it belongs in a script.

---

## How to Spot Script Opportunities

### The Determinism Test

1. **Given identical input, will it always produce identical output?** → Script candidate.
2. **Could you write a unit test with expected output?** → Definitely a script.
3. **Requires interpreting meaning, tone, or context?** → Keep as prompt.

### The Judgment Boundary

| Scripts Handle                   | Prompts Handle                       |
| -------------------------------- | ------------------------------------ |
| Fetch, Transform, Validate       | Interpret, Classify (ambiguous)      |
| Count, Parse, Compare            | Create, Decide (incomplete info)     |
| Extract, Format, Check structure | Evaluate quality, Synthesize meaning |

### Signal Verbs in Prompts

When you see these in a workflow's requirements, think scripts first: "validate", "count", "extract", "convert/transform", "compare", "scan for", "check structure", "against schema", "graph/map dependencies", "list all", "detect pattern", "diff/changes between"

### Script Opportunity Categories

| Category            | What It Does                                                | Example                                            |
| ------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| Validation          | Check structure, format, schema, naming                     | Validate frontmatter fields exist                  |
| Data Extraction     | Pull structured data without interpreting meaning           | Extract all `{variable}` references from markdown  |
| Transformation      | Convert between known formats                               | Markdown table to JSON                             |
| Metrics             | Count, tally, aggregate statistics                          | Token count per file                               |
| Comparison          | Diff, cross-reference, verify consistency                   | Cross-ref prompt names against SKILL.md references |
| Structure Checks    | Verify directory layout, file existence                     | Skill folder has required files                    |
| Dependency Analysis | Trace references, imports, relationships                    | Build skill dependency graph                       |
| Pre-Processing      | Extract compact data from large files BEFORE LLM reads them | Pre-extract file metrics into JSON for LLM scanner |
| Post-Processing     | Verify LLM output meets structural requirements             | Validate generated YAML parses correctly           |

### Your Toolbox

**Python is the default** for all script logic (cross-platform: macOS, Linux, Windows/WSL). See `./script-standards.md` for full rationale and safe bash commands.

- **Python:** Full standard library (`json`, `pathlib`, `re`, `argparse`, `collections`, `difflib`, `ast`, `csv`, `xml`, etc.) plus PEP 723 inline-declared dependencies (`tiktoken`, `jsonschema`, `pyyaml`, etc.)
- **Safe shell commands:** `git`, `gh`, `uv run`, `npm`/`npx`/`pnpm`, `mkdir -p`
- **Avoid bash for logic** — no piping, `jq`, `grep`, `sed`, `awk`, `find`, `diff`, `wc` in scripts. Use Python equivalents instead.

### The --help Pattern

All scripts use PEP 723 metadata and implement `--help`. Prompts can reference `scripts/foo.py --help` instead of inlining interface details — single source of truth, saves prompt tokens.

---

## Script Output Standard

All scripts MUST output structured JSON:

```json
{
  "script": "script-name",
  "version": "1.0.0",
  "skill_path": "/path/to/skill",
  "timestamp": "2025-03-08T10:30:00Z",
  "status": "pass|fail|warning",
  "findings": [
    {
      "severity": "critical|high|medium|low|info",
      "category": "structure|security|performance|consistency",
      "location": { "file": "SKILL.md", "line": 42 },
      "issue": "Clear description",
      "fix": "Specific action to resolve"
    }
  ],
  "summary": {
    "total": 0,
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  }
}
```

### Implementation Checklist

- [ ] `--help` with PEP 723 metadata
- [ ] Accepts skill path as argument
- [ ] `-o` flag for output file (defaults to stdout)
- [ ] Diagnostics to stderr
- [ ] Exit codes: 0=pass, 1=fail, 2=error
- [ ] `--verbose` flag for debugging
- [ ] Self-contained (PEP 723 for dependencies)
- [ ] No interactive prompts, no network dependencies
- [ ] Valid JSON to stdout
- [ ] Tests in `scripts/tests/`
