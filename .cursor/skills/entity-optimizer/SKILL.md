---
name: entity-optimizer
description: 'Build entity presence in Knowledge Graph, Wikidata, AI systems for brand recognition and citations. 实体优化/知识图谱'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when optimizing entity presence for Knowledge Graph, Wikidata, or AI engine disambiguation. Also for brand entity canonicalization."
argument-hint: "<entity name or brand>"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "high"
  tags:
    - seo
    - geo
    - entity-optimization
    - knowledge-graph
    - knowledge-panel
    - brand-entity
    - wikidata
    - entity-disambiguation
    - 实体优化
    - エンティティ
    - 엔티티
    - entidad-seo
  triggers:
    # EN-formal
    - "optimize entity presence"
    - "build knowledge graph"
    - "improve knowledge panel"
    - "entity audit"
    - "establish brand entity"
    - "entity disambiguation"
    # EN-casual
    - "Google doesn't know my brand"
    - "no knowledge panel"
    - "establish my brand"
    - "establish my brand as an entity"
    - "get a Google knowledge card"
    - "no Wikipedia entry"
    # EN-question
    - "how to get a knowledge panel"
    - "how to build brand entity"
    # ZH-pro
    - "实体优化"
    - "知识图谱"
    - "品牌实体"
    - "知识面板"
    - "品牌词"
    - "品牌词优化"
    # ZH-casual
    - "品牌搜不到"
    - "没有知识面板"
    - "Google不认识我的品牌"
    # JA
    - "エンティティ最適化"
    - "ナレッジパネル"
    # KO
    - "엔티티 최적화"
    - "지식 패널"
    - "구글이 내 브랜드 모르는데?"
    - "지식 패널 만들려면?"
    # ES
    - "optimización de entidad"
    - "panel de conocimiento"
    # PT
    - "otimização de entidade"
    # Misspellings
    - "knowlege panel"
    - "enity optimization"
---

# Entity Optimizer


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This cross-cutting skill is part of the protocol layer and follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


Audits, builds, and maintains entity identity across search engines and AI systems. Entities — the people, organizations, products, and concepts that search engines and AI systems recognize as distinct things — are the foundation of how both Google and LLMs decide *what a brand is* and *whether to cite it*.

**Why entities matter for SEO + GEO:**

- **SEO**: Google's Knowledge Graph powers Knowledge Panels, rich results, and entity-based ranking signals. A well-defined entity earns SERP real estate.
- **GEO**: AI systems resolve queries to entities before generating answers. If an AI cannot identify an entity, it cannot cite it — no matter how good the content is.

**System role**: Canonical Entity Profile. It acts as the source of truth for entity identity, associations, and disambiguation across the library.

## When This Must Trigger

Use this when brand or entity identity needs to be established or verified — even if the user doesn't use entity terminology:

- User says "Google doesn't know my brand" or "no knowledge panel"
- Auto-recommended when `memory/entities/candidates.md` accumulates 3 or more uncanonized entity candidates from other skills
- Establishing a new brand/person/product as a recognized entity
- Auditing current entity presence across Knowledge Graph, Wikidata, and AI systems
- Improving or correcting a Knowledge Panel
- Building entity associations (entity ↔ topic, entity ↔ industry)
- Resolving entity disambiguation issues (your entity confused with another)
- Strengthening entity signals for AI citation
- After launching a new brand, product, or organization
- Preparing for a site migration (preserving entity identity)
- Running periodic entity health checks

## What This Skill Does

1. **Entity Audit**: Evaluates current entity presence across search and AI systems
2. **Knowledge Graph Analysis**: Checks Google Knowledge Graph, Wikidata, and Wikipedia status
3. **AI Entity Resolution Test**: Queries AI systems to see how they identify and describe the entity
4. **Entity Signal Mapping**: Identifies all signals that establish entity identity
5. **Gap Analysis**: Finds missing or weak entity signals
6. **Entity Building Plan**: Creates actionable plan to establish or strengthen entity presence
7. **Disambiguation Strategy**: Resolves confusion with similarly-named entities

## Quick Start

Start with one of these prompts. Finish with a canonical entity profile and a handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Entity Audit

```
Audit entity presence for [brand/person/organization]
```

```
How well do search engines and AI systems recognize [entity name]?
```

### Build Entity Presence

```
Build entity presence for [new brand] in the [industry] space
```

```
Establish [person name] as a recognized expert in [topic]
```

### Fix Entity Issues

```
My Knowledge Panel shows incorrect information — fix entity signals for [entity]
```

```
AI systems confuse [my entity] with [other entity] — help me disambiguate
```

## Skill Contract

**Expected output**: an entity audit, a canonical entity profile, and a short handoff summary ready for `memory/entities/`.

- **Reads**: the entity name, primary domain, known profiles, topic associations, and prior brand context from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing entity report plus a reusable profile that can be stored under `memory/entities/`.
- **Promotes**: canonical names, sameAs links, disambiguation notes, and entity gaps to `CLAUDE.md`, `memory/entities/`, and `memory/open-loops.md`.

This skill is the sole writer of canonical entity profiles at `memory/entities/<name>.md`. Other skills write entity candidates to `memory/entities/candidates.md` only. When 3+ candidates accumulate, this skill should be recommended.

- **Next handoff**: use the `Next Best Skill` below once the entity truth is clear.

## Data Sources

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~knowledge graph + ~~SEO tool + ~~AI monitor + ~~brand monitor connected:**
Query Knowledge Graph API for entity status, pull branded search data from ~~SEO tool, test AI citation with ~~AI monitor, track brand mentions with ~~brand monitor.

**With manual data only:**
Ask the user to provide:
1. Entity name, type (Person, Organization, Brand, Product, Creative Work, Event)
2. Primary website / domain
3. Known existing profiles (Wikipedia, Wikidata, social media, industry directories)
4. Top 3-5 topics/industries the entity should be associated with
5. Any known disambiguation issues (other entities with same/similar name)

Without tools, Claude provides entity optimization strategy and recommendations based on information the user provides. The user must run search queries, check Knowledge Panels, and test AI responses to supply the raw data for analysis.

Proceed with the audit using public search results, AI query testing, and SERP analysis. Note which items require tool access for full evaluation.

## Instructions

When a user requests entity optimization:

### Step 1: Entity Discovery

Establish the entity's current state across all systems.

```markdown
### Entity Profile

**Entity Name**: [name]
**Entity Type**: [Person / Organization / Brand / Product / Creative Work / Event]
**Primary Domain**: [URL]
**Target Topics**: [topic 1, topic 2, topic 3]

#### Current Entity Presence

| Platform | Status | Details |
|----------|--------|---------|
| Google Knowledge Panel | ✅ Present / ❌ Absent / ⚠️ Incorrect | [details] |
| Wikidata | ✅ Listed / ❌ Not listed | [QID if exists] |
| Wikipedia | ✅ Article / ⚠️ Mentioned only / ❌ Absent | [notability assessment] |
| Google Knowledge Graph API | ✅ Entity found / ❌ Not found | [entity ID, types, score] |
| Schema.org on site | ✅ Complete / ⚠️ Partial / ❌ Missing | [Organization/Person/Product schema] |

#### AI Entity Resolution Test

**Note**: Claude cannot directly query other AI systems or perform real-time web searches without tool access. When running without ~~AI monitor or ~~knowledge graph tools, ask the user to run these test queries and report the results, or use the user-provided information to assess entity presence.

Test how AI systems identify this entity by querying:
- "What is [entity name]?"
- "Who founded [entity name]?" (for organizations)
- "What does [entity name] do?"
- "[entity name] vs [competitor]"

| AI System | Recognizes Entity? | Description Accuracy | Cites Entity's Content? |
|-----------|-------------------|---------------------|------------------------|
| ChatGPT | ✅ / ⚠️ / ❌ | [accuracy notes] | [yes/no/partially] |
| Claude | ✅ / ⚠️ / ❌ | [accuracy notes] | [yes/no/partially] |
| Perplexity | ✅ / ⚠️ / ❌ | [accuracy notes] | [yes/no/partially] |
| Google AI Overview | ✅ / ⚠️ / ❌ | [accuracy notes] | [yes/no/partially] |
```

### Step 2: Entity Signal Audit

Evaluate entity signals across 6 categories. For the detailed 47-signal checklist with verification methods, see [references/entity-signal-checklist.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/entity-signal-checklist.md).

Evaluate each signal as Pass / Fail / Partial with a specific action for each gap. The 6 categories are:

1. **Structured Data Signals** -- Organization/Person schema, sameAs links, @id consistency, author schema
2. **Knowledge Base Signals** -- Wikidata, Wikipedia, CrunchBase, industry directories
3. **Consistent NAP+E Signals** -- Name/description/logo/social consistency across platforms
4. **Content-Based Entity Signals** -- About page, author pages, topical authority, branded backlinks
5. **Third-Party Entity Signals** -- Authoritative mentions, co-citation, reviews, press coverage
6. **AI-Specific Entity Signals** -- Clear definitions, disambiguation, verifiable claims, crawlability

> **Reference**: Use the audit template in [references/entity-signal-checklist.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/entity-signal-checklist.md) for the full 47-signal checklist with verification methods for each category.

### Step 3: Report & Action Plan

```markdown
## Entity Optimization Report

### Overview

- **Entity**: [name]
- **Entity Type**: [type]
- **Audit Date**: [date]

### Signal Category Summary

| Category | Status | Key Findings |
|----------|--------|-------------|
| Structured Data | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |
| Knowledge Base | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |
| Consistency (NAP+E) | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |
| Content-Based | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |
| Third-Party | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |
| AI-Specific | ✅ Strong / ⚠️ Gaps / ❌ Missing | [key findings] |

### Critical Issues

[List any issues that severely impact entity recognition — disambiguation problems, incorrect Knowledge Panel, missing from Knowledge Graph entirely]

### Top 5 Priority Actions

Sorted by: impact on entity recognition × effort required

1. **[Signal]** — [specific action]
   - Impact: [High/Medium] | Effort: [Low/Medium/High]
   - Why: [explanation of how this improves entity recognition]

2. **[Signal]** — [specific action]
   - Impact: [High/Medium] | Effort: [Low/Medium/High]
   - Why: [explanation]

3–5. [Same format]

### Entity Building Roadmap

#### Week 1-2: Foundation (Structured Data + Consistency)
- [ ] Implement/fix Organization or Person schema with full properties
- [ ] Add sameAs links to all authoritative profiles
- [ ] Audit and fix NAP+E consistency across all platforms
- [ ] Ensure About page is entity-rich and well-structured

#### Month 1: Knowledge Bases
- [ ] Create or update Wikidata entry with complete properties
- [ ] Ensure CrunchBase / industry directory profiles are complete
- [ ] Build Wikipedia notability (or plan path to notability)
- [ ] Submit to relevant authoritative directories

#### Month 2-3: Authority Building
- [ ] Secure mentions on authoritative industry sites
- [ ] Build co-citation signals with established entities
- [ ] Create topical content clusters that reinforce entity-topic associations
- [ ] Pursue PR opportunities that generate entity mentions

#### Ongoing: AI-Specific Optimization
- [ ] Test AI entity resolution quarterly
- [ ] Update factual claims to remain current and verifiable
- [ ] Monitor AI systems for incorrect entity information
- [ ] Ensure new content reinforces entity identity signals

### Cross-Reference

- **CORE-EEAT relevance**: Items A07 (Knowledge Graph Presence) and A08 (Entity Consistency) directly overlap — entity optimization strengthens Authority dimension
- **CITE relevance**: CITE I01-I10 (Identity dimension) measures entity signals at domain level — entity optimization feeds these scores
- For content-level audit: `content-quality-auditor`
- For domain-level audit: `domain-authority-auditor`
```

### Save Results

After delivering findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to the appropriate `memory/` path using filename `YYYY-MM-DD-<topic>.md` containing:
- One-line verdict or headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any veto-level issue was found (CORE-EEAT T04, C01, R10 or CITE T03, T05, T09), also append a one-liner to `memory/hot-cache.md` without asking.

## Validation Checkpoints

### Input Validation
- [ ] Entity name and type identified
- [ ] Primary domain/website confirmed
- [ ] Target topics/industries specified
- [ ] Disambiguation context provided (if entity name is common)

### Output Validation
- [ ] All 6 signal categories evaluated
- [ ] AI entity resolution tested with at least 3 queries
- [ ] Knowledge Panel status checked
- [ ] Wikidata/Wikipedia status verified
- [ ] Schema.org markup on primary site audited
- [ ] Every recommendation is specific and actionable
- [ ] Roadmap includes concrete steps with timeframes
- [ ] Cross-reference with CORE-EEAT A07/A08 and CITE I01-I10 noted

## Example

> **Reference**: See [references/example-audit-report.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/example-audit-report.md) for a complete example entity audit report for a B2B SaaS company (CloudMetrics), including AI entity resolution test results, entity health summary, top 3 priority actions, and CORE-EEAT/CITE cross-references.

## Tips for Success

1. **Start with Wikidata** — It's the single most influential editable knowledge base; a complete Wikidata entry with references often triggers Knowledge Panel creation within weeks
2. **sameAs is your most powerful Schema.org property** — It directly tells search engines "I am this entity in the Knowledge Graph"; always include Wikidata URL first
3. **Test AI recognition before and after** — Query ChatGPT, Claude, Perplexity, and Google AI Overview before optimizing, then again after; this is the most direct GEO metric
4. **Entity signals compound** — Unlike content SEO, entity signals from different sources reinforce each other; 5 weak signals together are stronger than 1 strong signal alone
5. **Consistency beats completeness** — A consistent entity name and description across 10 platforms beats a perfect profile on just 2
6. **Don't neglect disambiguation** — If your entity name is shared with anything else, disambiguation is the first priority; all other signals are wasted if they're attributed to the wrong entity
7. **Pair with CITE I-dimension for domain context** — Entity audit tells you how well the entity is recognized; CITE Identity (I01-I10) tells you how well the domain represents that entity; use both together

## Entity Type Reference

> **Reference**: See [references/entity-type-reference.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/entity-type-reference.md) for entity types with key signals, schemas, and disambiguation strategies by situation.

## Knowledge Panel & Wikidata Optimization

> **Reference**: See [references/knowledge-panel-wikidata-guide.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/knowledge-panel-wikidata-guide.md) for Knowledge Panel claiming/editing, common issues and fixes, Wikidata entry creation, key properties by entity type, and AI entity resolution optimization.

## Reference Materials

Detailed guides for entity optimization:
- [references/entity-signal-checklist.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/entity-signal-checklist.md) — Complete signal checklist with verification methods
- [references/knowledge-graph-guide.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/entity-optimizer/references/knowledge-graph-guide.md) — Wikidata, Wikipedia, and Knowledge Graph optimization playbook

## Next Best Skill

- **Primary**: [schema-markup-generator](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/schema-markup-generator/SKILL.md) — turn entity truth into machine-readable implementation.
