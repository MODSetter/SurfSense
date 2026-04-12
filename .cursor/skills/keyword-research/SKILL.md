---
name: keyword-research
description: 'Find high-value SEO keywords: search volume, difficulty, intent classification, topic clusters. 关键词研究/内容选题'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when starting keyword research for a new page, topic, or campaign. Also when the user asks about search volume, keyword difficulty, topic clusters, long-tail keywords, or what to write about."
argument-hint: "<topic or seed keyword> [market/language]"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "medium"
  tags:
    - seo
    - geo
    - keywords
    - keyword-research
    - search-volume
    - keyword-difficulty
    - topic-clusters
    - long-tail-keywords
    - search-intent
    - content-calendar
    - ahrefs
    - semrush
    - google-keyword-planner
    - 关键词研究
    - SEO关键词
    - キーワード調査
    - 키워드분석
    - palabras-clave
  triggers:
    # EN-formal
    - "keyword research"
    - "find keywords"
    - "keyword analysis"
    - "keyword discovery"
    - "search volume analysis"
    - "keyword difficulty"
    - "topic research"
    - "identify ranking opportunities"
    # EN-casual
    - "what should I write about"
    - "what are people searching for"
    - "what are people googling"
    - "find me topics to write"
    - "give me keyword ideas"
    - "which keywords should I target"
    - "why is my traffic low"
    - "I need content ideas"
    # EN-question
    - "how do I find good keywords"
    - "what keywords should I target"
    - "how competitive is this keyword"
    # EN-competitor
    - "Ahrefs keyword explorer alternative"
    - "Semrush keyword magic tool"
    - "Google Keyword Planner alternative"
    - "Ubersuggest alternative"
    # ZH-pro
    - "关键词研究"
    - "关键词分析"
    - "搜索量查询"
    - "关键词难度"
    - "SEO关键词"
    - "长尾关键词"
    - "词库整理"
    - "关键词布局"
    - "关键词挖掘"
    # ZH-casual
    - "写什么内容好"
    - "找选题"
    - "帮我挖词"
    - "不知道写什么"
    - "查关键词"
    - "选词"
    - "帮我找词"
    # JA
    - "キーワード調査"
    - "キーワードリサーチ"
    - "SEOキーワード分析"
    - "検索ボリューム"
    - "ロングテールキーワード"
    - "検索意図分析"
    # KO
    - "키워드 리서치"
    - "키워드 분석"
    - "검색량 분석"
    - "키워드 어떻게 찾아요?"
    - "검색어 분석"
    - "경쟁도 낮은 키워드는?"
    # ES
    - "investigación de palabras clave"
    - "análisis de palabras clave"
    - "volumen de búsqueda"
    - "posicionamiento web"
    - "cómo encontrar palabras clave"
    # PT
    - "pesquisa de palavras-chave"
    # Misspellings
    - "keywrod research"
    - "keywork research"
---

# Keyword Research


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This research skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


Discovers, analyzes, and prioritizes keywords for SEO and GEO content strategies. Identifies high-value opportunities based on search volume, competition, intent, and business relevance.

**System role**: Research layer skill. It turns market signals into reusable strategic inputs for the rest of the library.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs reusable market intelligence that should influence strategy, not just an ad hoc answer.

- Starting a new content strategy or campaign
- Expanding into new topics or markets
- Finding keywords for a specific product or service
- Identifying long-tail keyword opportunities
- Understanding search intent for your industry
- Planning content calendars
- Researching keywords for GEO optimization

## What This Skill Does

1. **Keyword Discovery**: Generates comprehensive keyword lists from seed terms
2. **Intent Classification**: Categorizes keywords by user intent (informational, navigational, commercial, transactional)
3. **Difficulty Assessment**: Evaluates competition level and ranking difficulty
4. **Opportunity Scoring**: Prioritizes keywords by potential ROI
5. **Clustering**: Groups related keywords into topic clusters
6. **GEO Relevance**: Identifies keywords likely to trigger AI responses

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Basic Keyword Research

```
Research keywords for [topic/product/service]
```

```
Find keyword opportunities for a [industry] business targeting [audience]
```

### With Specific Goals

```
Find low-competition keywords for [topic] with commercial intent
```

```
Identify question-based keywords for [topic] that AI systems might answer
```

### Competitive Research

```
What keywords is [competitor URL] ranking for that I should target?
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

**With ~~SEO tool + ~~search console connected:**
Automatically pull historical search volume data, keyword difficulty scores, SERP analysis, current rankings from ~~search console, and competitor keyword overlap. The skill will fetch seed keyword metrics, related keyword suggestions, and search trend data.

**With manual data only:**
Ask the user to provide:
1. Seed keywords or topic description
2. Target audience and geographic location
3. Business goals (traffic, leads, sales)
4. Current domain authority (if known) or site age
5. Any known keyword performance data or search volume estimates

Proceed with the full analysis using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests keyword research:

At the start of each phase, announce: **[Phase X/8: Name]** so the user can track progress.

### Phase 1/8: Scope

   Ask clarifying questions if not provided:
   - What is your product/service/topic?
   - Who is your target audience?
   - What is your business goal? (traffic, leads, sales)
   - What is your current domain authority? (new site, established, etc.)
   - Any specific geographic targeting?
   - Preferred language?

### Phase 2/8: Discover

   Start with:
   - Core product/service terms
   - Problem-focused keywords (what issues do you solve?)
   - Solution-focused keywords (how do you help?)
   - Audience-specific terms
   - Industry terminology

### Phase 3/8: Variations

   For each seed keyword, generate variations:
   
   ```markdown
   ## Keyword Expansion Patterns
   
   ### Modifiers
   - Best [keyword]
   - Top [keyword]
   - [keyword] for [audience]
   - [keyword] near me
   - [keyword] [year]
   - How to [keyword]
   - What is [keyword]
   - [keyword] vs [alternative]
   - [keyword] examples
   - [keyword] tools
   
   ### Long-tail Variations
   - [keyword] for beginners
   - [keyword] for small business
   - Free [keyword]
   - [keyword] software/tool/service
   - [keyword] template
   - [keyword] checklist
   - [keyword] guide
   ```

### Phase 4/8: Classify

   Categorize each keyword:

   | Intent | Signals | Example | Content Type |
   |--------|---------|---------|--------------|
   | Informational | what, how, why, guide, learn | "what is SEO" | Blog posts, guides |
   | Navigational | brand names, specific sites | "google analytics login" | Homepage, product pages |
   | Commercial | best, review, vs, compare | "best SEO tools [current year]" | Comparison posts, reviews |
   | Transactional | buy, price, discount, order | "buy SEO software" | Product pages, pricing |

### Phase 5/8: Score

   Score each keyword (1-100 scale):

   ```markdown
   ### Difficulty Factors
   
   **High Difficulty (70-100)**
   - Major brands ranking
   - High domain authority competitors
   - Established content (1000+ backlinks)
   - Paid ads dominating SERP
   
   **Medium Difficulty (40-69)**
   - Mix of authority and niche sites
   - Some opportunities for quality content
   - Moderate backlink requirements
   
   **Low Difficulty (1-39)**
   - Few authoritative competitors
   - Thin or outdated content ranking
   - Long-tail variations
   - New or emerging topics
   ```

#### Opportunity Score

   Formula: `Opportunity = (Volume × Intent Value) / Difficulty`

   **Intent Value** assigns a numeric weight by search intent:
   - Informational = 1
   - Navigational = 1
   - Commercial = 2
   - Transactional = 3

   ```markdown
   ### Opportunity Matrix
   
   | Scenario | Volume | Difficulty | Intent | Priority |
   |----------|--------|------------|--------|----------|
   | Quick Win | Low-Med | Low | High | ⭐⭐⭐⭐⭐ |
   | Growth | High | Medium | High | ⭐⭐⭐⭐ |
   | Long-term | High | High | High | ⭐⭐⭐ |
   | Research | Low | Low | Low | ⭐⭐ |
   ```

### Phase 6/8: GEO-Check — AI Answer Overlap

   Keywords likely to trigger AI responses:
   
   ```markdown
   ### GEO-Relevant Keywords
   
   **High GEO Potential**
   - Question formats: "What is...", "How does...", "Why is..."
   - Definition queries: "[term] meaning", "[term] definition"
   - Comparison queries: "[A] vs [B]", "difference between..."
   - List queries: "best [category]", "top [number] [items]"
   - How-to queries: "how to [action]", "steps to [goal]"
   
   **AI Answer Indicators**
   - Query is factual/definitional
   - Answer can be summarized concisely
   - Topic is well-documented online
   - Low commercial intent
   ```

### Phase 7/8: Cluster

   Group keywords into content clusters:

   ```markdown
   ## Topic Cluster: [Main Topic]
   
   **Pillar Content**: [Primary keyword]
   - Search volume: [X]
   - Difficulty: [X]
   - Content type: Comprehensive guide
   
   **Cluster Content**:
   
   ### Sub-topic 1: [Secondary keyword]
   - Volume: [X]
   - Difficulty: [X]
   - Links to: Pillar
   - Content type: [Blog post/Tutorial/etc.]
   
   ### Sub-topic 2: [Secondary keyword]
   - Volume: [X]
   - Difficulty: [X]
   - Links to: Pillar + Sub-topic 1
   - Content type: [Blog post/Tutorial/etc.]
   
   [Continue for all cluster keywords...]
   ```

### Phase 8/8: Deliver

   Produce a report containing: Executive Summary, Top Keyword Opportunities (Quick Wins, Growth, GEO), Topic Clusters, Content Calendar, and Next Steps.

   **Quality bar** — every recommendation must include at least one specific number. If it reads like the left column, rewrite it before including.

   | ❌ Generic (rewrite before including) | ✅ Actionable |
   |---|---|
   | "Target long-tail keywords for better results" | "Target 'project management for nonprofits' (vol: 320, KD: 22) — no DR>40 sites in top 10" |
   | "This keyword has good potential" | "Opportunity 8.4: vol 4,800, KD 28, transactional intent — gap analysis shows no content updated since 2023 in top 5" |
   | "Consider creating content around this topic" | "Write '[Tool A] vs [Tool B] for small teams' — 1,200/mo searches, current #1 is a 2022 article with 12 backlinks" |
   | "Optimize your page for this keyword" | "Add primary keyword to H1 (currently missing), write a 40-word direct answer in paragraph 1, add 3 internal links from your /blog/ cluster" |

   > **Reference**: See [references/example-report.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/example-report.md) for the full report template and example.

## Validation Checkpoints

### Input Validation
- [ ] Seed keywords or topic description clearly provided
- [ ] Target audience and business goals specified
- [ ] Geographic and language targeting confirmed
- [ ] Domain authority or site maturity level established

### Output Validation
- [ ] Every recommendation cites specific data points (not generic advice)
- [ ] Search volume and difficulty scores included for each keyword
- [ ] Keywords grouped by intent and mapped to content types
- [ ] Topic clusters show clear pillar-to-cluster relationships
- [ ] Source of each data point clearly stated (~~SEO tool data, user-provided, or estimated)

## Example

> **Reference**: See [references/example-report.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/example-report.md) for a complete example report for "project management software for small businesses".

### Advanced Usage

- **Intent Mapping**: `Map all keywords for [topic] by search intent and funnel stage`
- **Seasonal Analysis**: `Identify seasonal keyword trends for [industry]`
- **Competitor Gap**: `What keywords do [competitor 1], [competitor 2] rank for that I'm missing?`
- **Local Keywords**: `Research local keywords for [business type] in [city/region]`

## Tips for Success

1. **Start with seed keywords** that describe your core offering
2. **Don't ignore long-tail** - they often have highest conversion rates
3. **Match content to intent** - informational queries need guides, not sales pages
4. **Group into clusters** for topical authority
5. **Prioritize quick wins** to build momentum and credibility
6. **Include GEO keywords** in your strategy for AI visibility
7. **Review quarterly** - keyword dynamics change over time



### Save Results

After delivering findings to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/research/keyword-research/YYYY-MM-DD-<topic>.md` containing:
- One-line headline finding
- Top 3-5 actionable items
- Open loops or blockers
- Source data references

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.

## Reference Materials

- [Keyword Intent Taxonomy](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/keyword-intent-taxonomy.md) — Complete intent classification with signal words and content strategies
- [Topic Cluster Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/topic-cluster-templates.md) — Hub-and-spoke architecture templates for pillar and cluster content
- [Keyword Prioritization Framework](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/keyword-prioritization-framework.md) — Priority scoring matrix, categories, and seasonal keyword patterns
- [Example Report](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/keyword-research/references/example-report.md) — Complete example keyword research report for project management software

## Next Best Skill

- **Primary**: [competitor-analysis](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/research/competitor-analysis/SKILL.md) — turn keyword opportunities into a competitive benchmark.
