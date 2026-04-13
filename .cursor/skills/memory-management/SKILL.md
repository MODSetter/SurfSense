---
name: memory-management
description: 'Persist SEO/GEO campaign context across Claude sessions with automatic hot-list, active work, and archive tiers. 项目记忆/跨会话'
version: "7.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when reviewing, archiving, or cleaning up campaign memory. Also when the user asks to check saved findings, manage hot cache, or archive old data."
argument-hint: "[review|archive|cleanup]"
metadata:
  author: aaron-he-zhu
  version: "7.0.0"
  geo-relevance: "low"
  tags:
    - seo
    - geo
    - project-memory
    - context-management
    - campaign-tracking
    - session-context
    - hot-cache
    - 项目记忆
    - プロジェクト記憶
    - 프로젝트메모리
    - memoria-proyecto
  triggers:
    # EN-formal
    - "remember project context"
    - "save SEO data"
    - "track campaign progress"
    - "store keyword data"
    - "manage project memory"
    - "project context"
    - "refresh wiki index"
    - "build wiki index"
    - "wiki lint"
    # EN-casual
    - "remember this for next time"
    - "save my keyword data"
    - "keep track of this campaign"
    - "what did we decide last time"
    - "what do we know so far"
    - "project status"
    # EN-question
    - "how to save project progress"
    # ZH-pro
    - "项目记忆管理"
    - "SEO数据保存"
    - "跨会话记忆"
    - "刷新wiki索引"
    - "项目状况"
    # ZH-casual
    - "保存进度"
    - "上次说了什么"
    - "记住这个"
    # JA
    - "プロジェクト記憶"
    - "SEOデータ保存"
    # KO
    - "프로젝트 메모리"
    - "데이터 저장"
    # ES
    - "memoria del proyecto"
    - "guardar progreso"
    # PT
    - "memória do projeto"
---

# Memory Management

> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This cross-cutting skill is part of the protocol layer and follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).

This skill implements a three-tier memory system (HOT/WARM/COLD) for SEO and GEO projects. HOT memory (80 lines max) loads automatically every session via the SessionStart hook. WARM memory loads on demand per skill. COLD memory is archived data queried only when explicitly requested. The skill manages the full lifecycle: capture, promote, demote, and archive.

**System role**: Campaign Memory Loop. It defines how project context is captured, promoted, archived, and handed off across sessions. It is the sole executor of WARM-to-COLD archival and the aggregator for cross-skill project status queries.

## When This Must Trigger

Use this whenever project state should survive the current session — even if the user doesn't use memory terminology:

- User says "remember this", "save this", "keep track of this"
- User asks "what did we decide", "what do we know", "project status"
- Setting up memory structure for a new SEO project
- After completing audits, ranking checks, or performance reports (Stop hook reminds automatically)
- When project context needs updating (new keywords, competitors, priorities)
- When you need to look up historical data or project-specific terminology
- After 30+ days of work to clean up and archive stale data
- When open-loops.md has items older than 7 days (SessionStart hook reminds automatically)

## What This Skill Does

1. **HOT Cache Management**: Maintains `memory/hot-cache.md` (80 lines max) — loaded automatically every session by SessionStart hook
2. **WARM Storage**: Organizes dated findings in `memory/` subdirectories — loaded on demand by relevant skills
3. **COLD Archive**: Moves stale data (90+ days unreferenced) to `memory/archive/` with date prefix
4. **Promotion**: Elevates frequently-referenced findings from WARM to HOT (3+ refs in 7 days, or 2+ skill refs)
5. **Demotion**: Moves unreferenced HOT items to WARM (30 days), WARM to COLD (90 days)
6. **Cross-Skill Aggregation**: When user asks "what do we know", aggregates from all `memory/` subdirectories
7. **Open Loop Tracking**: Maintains `memory/open-loops.md`, reminds user of stale items via SessionStart hook
8. **Wiki Index Maintenance**: Compiles `memory/wiki/index.md` — a structured, auto-refreshed index of all WARM files with precise fields (score, 健康度, status, next_action, mtime) and best-effort summaries. Supports project isolation via `memory/wiki/<project>/index.md`. Auto-refreshed on PostToolUse; user confirmation not required (index is a fully rebuildable derived artifact). Delete `memory/wiki/` at any time to revert to pre-wiki behavior.
9. **Wiki Compiled Pages** (Phase 2): Generates interlinked entity, keyword, and topic pages from WARM files with source hash tracking, contradiction detection, and confidence-labeled reconciliation. Requires user confirmation before writing.
10. **Wiki Lint** (Phase 2): Detects contradictions, orphan pages, stale claims, missing pages, and source hash mismatches across wiki and WARM files via `/seo:wiki-lint`.
11. **WARM Retirement Preview** (Phase 3): `wiki-lint --retire-preview` lists WARM files fully covered by wiki compiled pages as retirement candidates. Actual archival to COLD requires explicit user confirmation.

## Quick Start

Start with one of these prompts. Finish with a hot-cache update plan and a handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Initialize Wiki Index

```
Refresh wiki index
```

```
Build wiki index for [project name]
```

Generates `memory/wiki/index.md` from existing WARM files. Required once to enable wiki features; subsequent refreshes happen automatically.

### Initialize Memory Structure

```
Set up SEO memory for [project name]
```

```
Initialize memory structure for a new [industry] website optimization project
```

### Update After Analysis

```
Update memory after ranking check for [keyword group]
```

```
Refresh hot cache with latest competitor analysis findings
```

### Query Stored Context

```
What are our hero keywords?
```

```
Show me the last ranking update date for [keyword category]
```

```
Look up our primary competitors and their domain authority
```

### Promotion and Demotion

```
Promote [keyword] to hot cache
```

```
Archive stale data that hasn't been referenced in 30+ days
```

### Glossary Management

```
Add [term] to project glossary: [definition]
```

```
What does [internal jargon] mean in this project?
```

## Skill Contract

**Expected output**: a memory update plan, hot-cache changes, and a short handoff summary.

- **Reads**: current campaign facts, new findings from other skills, approved decisions, and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).
- **Writes**: updates to `memory/hot-cache.md`, `memory/open-loops.md`, `memory/decisions.md`, and related `memory/` folders. Manages WARM-to-COLD archival in `memory/archive/`. Compiles `memory/wiki/index.md` (auto-refreshed) and wiki compiled pages (user-confirmed).
- **Promotes**: durable strategy, blockers, terminology, entity candidates, and major deltas. Applies temperature lifecycle rules: promote to HOT on high reference frequency, demote on staleness.
- **Next handoff**: use the `Next Best Skill` below when the project memory baseline is ready for active work.

### Temperature Lifecycle Rules

> See [references/promotion-demotion-rules.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/promotion-demotion-rules.md) for the full promotion/demotion table and action procedures.

### Hook Integration

This skill's behavior is reinforced by the library's prompt-based hooks:
- **SessionStart**: loads `memory/hot-cache.md`, reminds of stale open loops; loads `memory/wiki/<project>/index.md` (or global `index.md`) if it exists; provides light-user guidance based on Quick Status when `next_action` items are available
- **PostToolUse**: after any WARM file write, silently refreshes `memory/wiki/index.md` (Phase 1); prompts to update compiled pages (Phase 2)
- **Stop**: prompts to save session findings, auto-saves veto issues to hot-cache; appends changelog entry to index.md bottom

## Data Sources

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~SEO tool + ~~analytics + ~~search console connected:**
Automatically populate memory from historical data: keyword rankings over time, competitor domain authority changes, traffic metrics, conversion data, backlink profile evolution. The skill will fetch current rankings, alert on significant changes, and update both hot cache and cold storage.

**With manual data only:**
Ask the user to provide:
1. Current target keywords with priority levels
2. Primary competitors (3-5 domains)
3. Key performance metrics and last update date
4. Active campaigns and their status
5. Any project-specific terminology or abbreviations

Proceed with memory structure creation using provided data. Note in CLAUDE.md which data requires manual updates vs. automated refresh.

## Instructions

When a user requests SEO memory management:

### 1. Initialize Memory Structure

For new projects, create the directory structure defined in the [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md). Key directories: `memory/` (decisions, open-loops, glossary, entities, research, content, audits, monitoring) plus `memory/wiki/` (auto-managed compiled index with optional per-project subdirectories).

> **Templates**: [hot-cache-template.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/hot-cache-template.md) · [glossary-template.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/glossary-template.md) · [Wiki spec](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/proposal-wiki-layer-v3.md)

### 2. Context Lookup Flow

When a user references something unclear, follow this lookup sequence:

**Step 1: Check CLAUDE.md (Hot Cache)**
- Is it in active keywords?
- Is it in primary competitors?
- Is it in current priorities or campaigns?

**Step 2: Check Wiki Index** (`memory/wiki/index.md` or project-level) — locate relevant WARM files

**Step 3: Check memory/glossary.md**
- Is it defined as project terminology?
- Is it a custom segment or shorthand?

**Step 4: Check Cold Storage**
- Search memory/research/keywords/ for historical keyword context
- Search memory/research/competitors/ for past analyses
- Search memory/monitoring/reports/ for archived mentions

**Step 5: Ask User**
- If not found in any layer, ask for clarification
- Log the new term in glossary if it's project-specific

Example lookup:

```markdown
User: "Update rankings for our hero KWs"

Step 1: Check CLAUDE.md → Found "Hero Keywords (Priority 1)" section
Step 2: Extract keyword list from hot cache
Step 3: Execute ranking check
Step 4: Update both CLAUDE.md and memory/monitoring/rank-history/YYYY-MM-DD-ranks.csv
```

### 3. Promotion & Demotion Logic

> **Reference**: See [references/promotion-demotion-rules.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/promotion-demotion-rules.md) for detailed promotion/demotion triggers (keywords, competitors, metrics, campaigns) and the action procedures for each.

### 4. Update Triggers, Archive Management & Cross-Skill Integration

> **Reference**: See [references/update-triggers-integration.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/update-triggers-integration.md) for the complete update procedures after ranking checks, competitor analyses, audits, and reports; monthly/quarterly archive routines; and integration points with all 8 connected skills (keyword-research, rank-tracker, competitor-analysis, content-gap-analysis, seo-content-writer, content-quality-auditor, domain-authority-auditor).

### 5. Memory Hygiene Checks

When invoked for review or cleanup:

1. **Line count check**: Count lines in `memory/hot-cache.md`. If >80, list oldest entries for archival.
2. **Byte check**: If hot-cache exceeds 25KB, warn and recommend trimming long entries.
3. **Staleness scan**: List memory files older than 30 days that have not been referenced. Recommend archival for files >90 days.
4. **Frontmatter audit**: Check that all memory files (except hot-cache.md) have `name`, `description`, and `type` in their frontmatter. Report any missing fields.

### 6. Save Results

After delivering any memory update or aggregation to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to the appropriate `memory/` path using filename `YYYY-MM-DD-<topic>.md` containing:
- One-line verdict or headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any veto-level issue was found (CORE-EEAT T04, C01, R10 or CITE T03, T05, T09), also append a one-liner to `memory/hot-cache.md` without asking.

## Validation Checkpoints

### Structure Validation
- [ ] memory/hot-cache.md exists and is under 80 lines
- [ ] memory/ directory structure matches the shared state model
- [ ] glossary.md exists and is populated with project basics
- [ ] All historical data files include timestamps in filename or metadata

### Content Validation
- [ ] CLAUDE.md "Last Updated" date is current
- [ ] Every keyword in hot cache has current rank, target rank, and status
- [ ] Every competitor has domain authority and position assessment
- [ ] Every active campaign has status percentage and expected completion date
- [ ] Key Metrics Snapshot shows "Previous" values for comparison

### Lookup Validation
- [ ] Test lookup flow: reference a term → verify it finds it in correct layer
- [ ] Test promotion: manually promote item → verify it appears in CLAUDE.md
- [ ] Test demotion: manually archive item → verify removed from CLAUDE.md
- [ ] Glossary contains all custom segments and shorthand used in CLAUDE.md

### Update Validation
- [ ] After ranking check, `memory/monitoring/rank-history/` has a dated snapshot or export
- [ ] After competitor analysis, `memory/research/competitors/` has a dated file
- [ ] After audit, top action items appear in CLAUDE.md priorities
- [ ] After monthly report, metrics snapshot reflects new data

## Examples

> **Reference**: See [references/examples.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/memory-management/references/examples.md) for three complete examples: (1) updating hero keyword rankings with memory refresh, (2) glossary lookup flow, and (3) initializing memory for a new e-commerce project.

## Advanced Features

- **Smart Context Loading**: `Load full context for [campaign name]` — retrieves hot cache + all cold storage files for a campaign
- **Memory Health Check**: `Run memory health check` — finds orphaned files, missing timestamps, stale items, broken references
- **Bulk Promotion/Demotion**: `Promote all keywords ranking in top 10 to hot cache` / `Demote all completed campaigns from Q3`
- **Memory Snapshot**: `Create memory snapshot for [date/milestone]` — point-in-time copy for major milestones
- **Cross-Project Memory**: `Compare memory with [other project]` — keyword overlaps, competitor intersections across projects
- **Wiki Lint**: `/seo:wiki-lint [--fix] [--project name] [--retire-preview]` — contradictions, orphans, stale claims, hash mismatches. See [commands/wiki-lint.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/commands/wiki-lint.md)

## Practical Limitations

- **Concurrent access**: Use timestamped filenames to avoid overwrites from parallel sessions.
- **Cold storage retrieval**: WARM/COLD files only load on demand. Hot cache is the primary cross-session mechanism.
- **Data freshness**: Stale data (>90 days) should be flagged for refresh. Wiki index `mtime` field helps detect staleness.
- **Wiki compilation**: Index is best-effort for summaries; precise fields (score, status, mtime) are deterministic. Delete `memory/wiki/` anytime to revert.

## Reference Materials

- [CORE-EEAT Content Benchmark](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/core-eeat-benchmark.md) — Content quality scoring stored in memory
- [CITE Domain Rating](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/cite-domain-rating.md) — Domain authority scoring stored in memory

## Next Best Skill

- **Primary**: [keyword-research](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/SKILL.md) — seed or refresh campaign strategy with current demand signals.
