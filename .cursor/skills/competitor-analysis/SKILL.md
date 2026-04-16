---
name: competitor-analysis
description: 'Analyze competitor SEO/GEO: keywords, content, backlinks, AI citations, traffic share gaps. 竞品分析/竞争对手'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when analyzing competitor SEO strategy, comparing domains, benchmarking against competitors, or finding competitor keywords and content gaps."
argument-hint: "<competitor URL or domain>"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "medium"
  tags:
    - seo
    - geo
    - competitor-analysis
    - competitive-intelligence
    - benchmarking
    - competitor-keywords
    - competitor-backlinks
    - market-analysis
    - spyfu-alternative
    - 竞品分析
    - 競合分析
    - 경쟁분석
    - analisis-competitivo
  triggers:
    # EN-formal
    - "analyze competitors"
    - "competitor SEO"
    - "competitive analysis"
    - "competitor keywords"
    - "competitor backlinks"
    - "market analysis"
    - "competitive intelligence"
    # EN-casual
    - "what are my competitors doing"
    - "what are they doing differently"
    - "why do they rank higher"
    - "spy on competitor SEO"
    - "what are they doing better"
    - "why do they outrank me"
    # EN-question
    - "who are my SEO competitors"
    - "how do I beat my competitors"
    - "why do competitors rank higher"
    # EN-competitor
    - "SpyFu alternative"
    - "Semrush competitor analysis"
    - "Ahrefs competitor tool"
    # ZH-pro
    - "竞品分析"
    - "竞争对手分析"
    - "竞品SEO"
    - "对标分析"
    - "竞争情报"
    # ZH-casual
    - "竞品怎么做的"
    - "他们排名为什么比我高"
    - "看看对手在干什么"
    - "为什么他们排名好"
    # JA
    - "競合分析"
    - "競合SEO分析"
    - "ライバル分析"
    # KO
    - "경쟁 분석"
    - "경쟁사 SEO"
    - "경쟁사 키워드"
    # ES
    - "análisis de competidores"
    - "análisis competitivo SEO"
    # PT
    - "análise de concorrentes"
    # Misspellings
    - "competitve analysis"
    - "compeditor analysis"
---

# Competitor Analysis


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This research skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


This skill provides comprehensive analysis of competitor SEO and GEO strategies, revealing what's working in your market and identifying opportunities to outperform the competition.

**System role**: Research layer skill. It turns market signals into reusable strategic inputs for the rest of the library.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs reusable market intelligence that should influence strategy, not just an ad hoc answer.

- Entering a new market or niche
- Planning content strategy based on competitor success
- Understanding why competitors rank higher
- Finding backlink and partnership opportunities
- Identifying content gaps competitors are missing
- Analyzing competitor AI citation strategies
- Benchmarking your SEO performance

## What This Skill Does

1. **Keyword Analysis**: Identifies keywords competitors rank for
2. **Content Audit**: Analyzes competitor content strategies and formats
3. **Backlink Profiling**: Reviews competitor link-building approaches
4. **Technical Assessment**: Evaluates competitor site health
5. **GEO Analysis**: Identifies how competitors appear in AI responses
6. **Gap Identification**: Finds opportunities competitors miss
7. **Strategy Extraction**: Reveals actionable insights from competitor success

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Basic Competitor Analysis

```
Analyze SEO strategy for [competitor URL]
```

```
Compare my site [URL] against [competitor 1], [competitor 2], [competitor 3]
```

### Specific Analysis

```
What content is driving the most traffic for [competitor]?
```

```
Analyze why [competitor] ranks #1 for [keyword]
```

### GEO-Focused Analysis

```
How is [competitor] getting cited in AI responses? What can I learn?
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

**With ~~SEO tool + ~~analytics + ~~AI monitor connected:**
Automatically pull competitor keyword rankings, backlink profiles, top performing content, domain authority metrics from ~~SEO tool. Compare against your site's metrics from ~~analytics and ~~search console. Check AI citation patterns for both your site and competitors using ~~AI monitor.

**With manual data only:**
Ask the user to provide:
1. Competitor URLs to analyze (2-5 recommended)
2. Your own site URL and current metrics (traffic, rankings if known)
3. Industry or niche context
4. Specific aspects to focus on (keywords, content, backlinks, etc.)
5. Any known competitor strengths or weaknesses

Proceed with the full analysis using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests competitor analysis:

1. **Identify Competitors**

   If not specified, help identify competitors:
   
   ```markdown
   ### Competitor Identification Framework
   
   **Direct Competitors** (same product/service)
   - Search "[your main keyword]" and note top 5 organic results
   - Check who's advertising for your keywords
   - Ask: Who do customers compare you to?
   
   **Indirect Competitors** (different solution, same problem)
   - Search problem-focused keywords
   - Look at alternative solutions
   
   **Content Competitors** (compete for same keywords)
   - May not sell same product
   - Rank for your target keywords
   - Include media sites, blogs, aggregators
   ```

2. **Gather Competitor Data**

   Collect for each competitor: URL, domain age, estimated traffic, domain authority, business model, target audience, and key offerings.

3. **Analyze Keyword Rankings**

   Document total keywords ranking, top 10/top 3 counts, top performing keywords (with position, volume, traffic, page URL), keyword distribution by intent, and keyword gaps.

4. **Audit Content Strategy**

   Analyze content volume by type, top performing content, content patterns (word count, frequency, formats), content themes, and success factors.

5. **Analyze Backlink Profile**

   Review total backlinks, referring domains, link quality distribution, top linking domains, link acquisition patterns, and linkable assets.

6. **Technical SEO Assessment**

   Evaluate Core Web Vitals, mobile-friendliness, site architecture, internal linking quality, URL structure, and technical strengths/weaknesses.

7. **GEO/AI Citation Analysis**

   Test competitor content in AI systems: document which queries cite them, GEO strategies observed (definitions, statistics, Q&A, authority signals), and GEO opportunities they are missing.

8. **Synthesize Competitive Intelligence**

   Produce a final report with: Executive Summary, Competitive Landscape comparison table, CITE domain authority comparison, Strengths to Learn From, Weaknesses to Exploit, Keyword Opportunities, Content Strategy Recommendations, and Action Plan (Immediate / Short-term / Long-term).

   > **Reference**: See [references/analysis-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/analysis-templates.md) for detailed templates for each step.

## Validation Checkpoints

### Input Validation
- [ ] Competitor URLs verified as relevant to your niche
- [ ] Analysis scope defined (comprehensive or specific focus area)
- [ ] Your own site metrics available for comparison
- [ ] Minimum 2-3 competitors identified for meaningful patterns

### Output Validation
- [ ] Every recommendation cites specific data points (not generic advice)
- [ ] Competitor strengths backed by measurable evidence (metrics, rankings)
- [ ] Opportunities based on identifiable gaps, not assumptions
- [ ] Action plan items are specific and actionable (not vague strategies)
- [ ] Source of each data point clearly stated (~~SEO tool data, ~~analytics data, ~~AI monitor data, user-provided, or estimated)

## Example

> **Reference**: See [references/example-report.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/example-report.md) for a complete example analyzing HubSpot's marketing keyword dominance.

## Advanced Analysis Types

### Content Gap Analysis

```
Show me content [competitor] has that I don't, sorted by traffic potential
```

### Link Intersection

```
Find sites linking to [competitor 1] AND [competitor 2] but not me
```

### SERP Feature Analysis

```
What SERP features do competitors win? (Featured snippets, PAA, etc.)
```

### Historical Tracking

```
How has [competitor]'s SEO strategy evolved over the past year?
```

## Tips for Success

1. **Analyze 3-5 competitors** for comprehensive view
2. **Include indirect competitors** - they often have innovative approaches
3. **Look beyond rankings** - analyze content quality, user experience
4. **Study their failures** - avoid their mistakes
5. **Monitor regularly** - competitor strategies evolve
6. **Focus on actionable insights** - what can you actually implement?



### Save Results

After delivering findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/research/competitor-analysis/YYYY-MM-DD-<topic>.md` containing:
- One-line headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.

## Reference Materials

- [Analysis Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/analysis-templates.md) — Detailed templates for each analysis step (profile, keywords, content, backlinks, technical, GEO, synthesis)
- [Battlecard Template](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/battlecard-template.md) — Quick-reference competitive battlecard for sales and marketing teams
- [Positioning Frameworks](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/positioning-frameworks.md) — Positioning maps, messaging matrices, narrative analysis, and differentiation frameworks
- [Example Report](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/references/example-report.md) — Complete example analyzing HubSpot's marketing keyword dominance

## Next Best Skill

- **Primary**: [content-gap-analysis](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/content-gap-analysis/SKILL.md) — turn competitor findings into a focused opportunity map.
