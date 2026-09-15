---
name: serp-analysis
description: 'Analyze SERPs: ranking factors, features, intent patterns, AI overviews, featured snippets. SERP分析/搜索结果'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
allowed-tools: WebFetch
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when analyzing search engine results pages, SERP features, featured snippets, People Also Ask, or understanding ranking patterns for a query."
argument-hint: "<keyword or query>"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "high"
  tags:
    - seo
    - geo
    - serp-analysis
    - serp-features
    - featured-snippet
    - ai-overview
    - people-also-ask
    - search-intent
    - SERP分析
    - 検索結果分析
    - 검색결과
    - analisis-serp
  triggers:
    # EN-formal
    - "analyze search results"
    - "SERP analysis"
    - "what ranks for"
    - "SERP features"
    - "why does this page rank"
    - "featured snippets"
    - "AI overviews"
    # EN-casual
    - "what's on page one for this query"
    - "who ranks for this keyword"
    - "what does Google show for"
    - "what shows up for this search"
    - "who is on page one"
    # EN-question
    - "why does this page rank first"
    - "what SERP features appear for"
    # ZH-pro
    - "SERP分析"
    - "搜索结果分析"
    - "精选摘要"
    - "AI概览"
    # ZH-casual
    - "谁排第一"
    - "搜索结果长什么样"
    - "谁排在前面"
    # JA
    - "検索結果ページ分析"
    - "検索結果分析"
    - "強調スニペット"
    # KO
    - "검색 결과 분석"
    - "SERP 분석"
    # ES
    - "análisis SERP"
    - "análisis de resultados de búsqueda"
    # PT
    - "análise de SERP"
    # Misspellings
    - "serp anaylsis"
---

# SERP Analysis


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This research skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


This skill analyzes Search Engine Results Pages to reveal what's working for ranking content, which SERP features appear, and what triggers AI-generated answers. Understand the battlefield before creating content.

**System role**: Research layer skill. It turns market signals into reusable strategic inputs for the rest of the library.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs reusable market intelligence that should influence strategy, not just an ad hoc answer.

- Before creating content for a target keyword
- Understanding why certain pages rank #1
- Identifying SERP feature opportunities (featured snippets, PAA)
- Analyzing AI Overview/SGE patterns
- Evaluating keyword difficulty more accurately
- Planning content format based on what ranks
- Identifying ranking factors for specific queries

## What This Skill Does

1. **SERP Composition Analysis**: Maps what appears on the results page
2. **Ranking Factor Identification**: Reveals why top results rank
3. **SERP Feature Mapping**: Identifies featured snippets, PAA, knowledge panels
4. **AI Overview Analysis**: Examines when and how AI answers appear
5. **Intent Signal Detection**: Confirms user intent from SERP composition
6. **Content Format Recommendations**: Suggests optimal format based on SERP
7. **Difficulty Assessment**: Evaluates realistic ranking potential

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Basic SERP Analysis

```
Analyze the SERP for [keyword]
```

```
What does it take to rank for [keyword]?
```

### Feature-Specific Analysis

```
Analyze featured snippet opportunities for [keyword list]
```

```
Which of these keywords trigger AI Overviews? [keyword list]
```

### Competitive SERP Analysis

```
Why does [URL] rank #1 for [keyword]?
```

## Skill Contract

**Expected output**: a prioritized research brief, evidence-backed findings, and a short handoff summary ready for `memory/research/`.

- **Reads**: user goals, target market inputs, available tool data, and prior strategy from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing research deliverable plus a reusable summary that can be stored under `memory/research/`.
- **Promotes**: durable keyword priorities, competitor facts, entity candidates, and strategic decisions to `CLAUDE.md`, `memory/decisions.md`, and `memory/research/`; hand canonical entity work to `entity-optimizer`.
- **Next handoff**: use the `Next Best Skill` below when the findings are ready to drive action.

## Data Sources

> **Note:** All integrations are optional. This skill works without any API keys — users provide data manually when no tools are connected.

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~SEO tool + ~~search console + ~~AI monitor connected:**
Automatically fetch SERP snapshots for target keywords, extract ranking page metrics (domain authority, backlinks, content length), pull SERP feature data, and check AI Overview presence using ~~AI monitor. Historical SERP change data and mobile vs. desktop variations can be retrieved automatically.

**With manual data only:**
Ask the user to provide:
1. Target keyword(s) to analyze
2. SERP screenshots or detailed descriptions of search results
3. URLs of top 10 ranking pages
4. Search location and device type (mobile/desktop)
5. Any observations about SERP features (featured snippets, PAA, AI Overviews)

Proceed with the full analysis using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests SERP analysis:

1. **Understand the Query**

   Clarify if needed:
   - Target keyword(s) to analyze
   - Search location/language
   - Device type (mobile/desktop)
   - Specific questions about the SERP

2. **Map SERP Composition**

   Document all elements appearing on the results page: AI Overview, ads, featured snippet, organic results, PAA, knowledge panel, image pack, video results, local pack, shopping results, news results, sitelinks, and related searches.

3. **Analyze Top Ranking Pages**

   For each of the top 10 results, document: URL, domain, domain authority, content type, word count, publish/update dates, on-page factors (title, meta description, H1, URL structure), content structure (headings, media, tables, FAQ), estimated metrics (backlinks, referring domains), and why it ranks.

4. **Identify Ranking Patterns**

   Analyze common characteristics across top 5 results: word count, domain authority, backlinks, content freshness, HTTPS, mobile optimization. Document content format distribution, domain type distribution, and key success factors.

5. **Analyze SERP Features**

   For each present SERP feature: analyze the current holder, content format, and strategy to win. Cover Featured Snippet (type, content, winning strategy), PAA (questions, current answers, optimization approach), and AI Overview (sources cited, content patterns, citation strategy).

6. **Determine Search Intent**

   Confirm primary intent from SERP composition. Document evidence, intent breakdown percentages, and content format implications (format, tone, CTA).

7. **Calculate True Difficulty**

   Score overall difficulty (1-100) based on: top 10 domain authority, page authority, backlinks required, content quality bar, and SERP stability. Provide realistic assessments for new, growing, and established sites, plus easier alternatives.

8. **Generate Recommendations**

   Produce a summary with: Key Findings, Content Requirements to Rank (minimum requirements + differentiators), SERP Feature Strategy, Recommended Content Outline, and Next Steps.

   > **Reference**: See [references/analysis-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/serp-analysis/references/analysis-templates.md) for detailed templates for each step.

## Validation Checkpoints

### Input Validation
- [ ] Target keyword(s) clearly specified
- [ ] Search location and device type confirmed
- [ ] SERP data is current (date confirmed)
- [ ] Top 10 ranking URLs identified or provided

### Output Validation
- [ ] Every recommendation cites specific data points (not generic advice)
- [ ] SERP composition mapped with all features documented
- [ ] Ranking factors identified from actual top 10 analysis (not assumptions)
- [ ] Content requirements based on observed patterns in current SERP
- [ ] Source of each data point clearly stated (~~SEO tool data, ~~AI monitor data, user-provided, or manual observation)

## Example

> **Reference**: See [references/example-report.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/serp-analysis/references/example-report.md) for a complete example analyzing the SERP for "how to start a podcast".

## Advanced Analysis

### Multi-Keyword SERP Comparison

```
Compare SERPs for [keyword 1], [keyword 2], [keyword 3]
```

### Historical SERP Changes

```
How has the SERP for [keyword] changed over time?
```

### Local SERP Variations

```
Compare SERP for [keyword] in [location 1] vs [location 2]
```

### Mobile vs Desktop SERP

```
Analyze mobile vs desktop SERP differences for [keyword]
```

## Tips for Success

1. **Always check SERP before writing** - Don't assume, verify
2. **Match content format to SERP** - If lists rank, write lists
3. **Identify SERP feature opportunities** - Lower competition than #1
4. **Note SERP volatility** - Stable SERPs are harder to break into
5. **Study the outliers** - Why does a weaker site rank? Opportunity!
6. **Consider AI Overview optimization** - Growing importance



### Save Results

After delivering findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/research/serp-analysis/YYYY-MM-DD-<topic>.md` containing:
- One-line headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.

## Reference Materials

- [Analysis Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/serp-analysis/references/analysis-templates.md) — Detailed templates for each analysis step (SERP composition, top results, ranking patterns, features, intent, difficulty, recommendations)
- [SERP Feature Taxonomy](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/serp-analysis/references/serp-feature-taxonomy.md) — Complete taxonomy of SERP features with trigger conditions, AI overview framework, intent signals, and volatility assessment
- [Example Report](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/serp-analysis/references/example-report.md) — Complete example analyzing the SERP for "how to start a podcast"

## Next Best Skill

- **Primary**: [seo-content-writer](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/build/seo-content-writer/SKILL.md) — turn SERP patterns into a content brief or page structure.
