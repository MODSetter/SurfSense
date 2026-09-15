---
name: backlink-analyzer
description: 'Analyze backlink profiles: link authority, toxic links, building opportunities, competitor link gaps. 外链分析/反向链接'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when analyzing backlink profiles, link quality, toxic links, referring domains, or anchor text distribution."
argument-hint: "<domain or URL>"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "low"
  tags:
    - seo
    - backlinks
    - link-building
    - link-profile
    - toxic-links
    - off-page-seo
    - link-audit
    - referring-domains
    - disavow
    - ahrefs-alternative
    - 外链分析
    - 被リンク
    - 백링크
    - backlinks-seo
  triggers:
    # EN-formal
    - "analyze backlinks"
    - "check link profile"
    - "find toxic links"
    - "link building opportunities"
    - "link profile analysis"
    - "backlink audit"
    - "link quality"
    # EN-casual
    - "who links to me"
    - "I have spammy links"
    - "how do I get more backlinks"
    - "how do I get more links"
    - "disavow links"
    - "link building outreach"
    - "disavow file"
    # EN-question
    - "how to build backlinks"
    - "how to find toxic backlinks"
    # ZH-pro
    - "外链分析"
    - "反向链接"
    - "有毒链接"
    - "链接建设"
    # ZH-casual
    - "外链怎么做"
    - "有垃圾外链"
    - "谁链接到我"
    - "友链"
    - "互换友链"
    - "外链建设"
    # JA
    - "被リンク分析"
    - "バックリンク"
    - "リンク構築"
    # KO
    - "백링크 분석"
    - "링크 빌딩"
    - "누가 내 사이트 링크해?"
    - "백링크 어떻게 늘려?"
    # ES
    - "análisis de backlinks"
    - "enlaces entrantes"
    # PT
    - "análise de backlinks"
    # Misspellings
    - "backlink anaylsis"
    - "backlnk analysis"
---

# Backlink Analyzer


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This monitoring skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


Analyzes, monitors, and optimizes backlink profiles. Identifies link quality, discovers opportunities, and tracks competitor link building activities.

**System role**: Monitoring layer skill. It turns performance changes into deltas, alerts, and next actions.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs time-aware change detection, escalation, or stakeholder-ready visibility.

- Auditing your current backlink profile
- Identifying toxic or harmful links
- Discovering link building opportunities
- Analyzing competitor backlink strategies
- Monitoring new and lost links
- Evaluating link quality for outreach
- Preparing for link disavow

## What This Skill Does

1. **Profile Analysis**: Comprehensive backlink profile overview
2. **Quality Assessment**: Evaluates link authority and relevance
3. **Toxic Link Detection**: Identifies harmful links
4. **Competitor Analysis**: Compares link profiles across competitors
5. **Opportunity Discovery**: Finds link building prospects
6. **Trend Monitoring**: Tracks link acquisition over time
7. **Disavow Guidance**: Helps create disavow files

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Analyze Your Profile

```
Analyze backlink profile for [domain]
```

### Find Opportunities

```
Find link building opportunities by analyzing [competitor domains]
```

### Detect Issues

```
Check for toxic backlinks on [domain]
```

### Compare Profiles

```
Compare backlink profiles: [your domain] vs [competitor domains]
```

## Skill Contract

**Expected output**: a delta summary, alert/report output, and a short handoff summary ready for `memory/monitoring/`.

- **Reads**: current metrics, previous baselines, alert thresholds, and reporting context from [CLAUDE.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CLAUDE.md) and the shared [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md) when available.
- **Writes**: a user-facing monitoring deliverable plus a reusable summary that can be stored under `memory/monitoring/`.
- **Promotes**: significant changes, confirmed anomalies, and follow-up actions to `memory/open-loops.md` and `memory/decisions.md`.
- **Next handoff**: use the `Next Best Skill` below when a change needs action.

## Data Sources

> **Note:** All integrations are optional. This skill works without any API keys — users provide data manually when no tools are connected.

> See [CONNECTORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/CONNECTORS.md) for tool category placeholders.

**With ~~link database + ~~SEO tool connected:**
Automatically pull comprehensive backlink profiles including referring domains, anchor text distribution, link quality metrics (DA/DR), link velocity, and toxic link detection from ~~link database. Competitor backlink data from ~~SEO tool for gap analysis.

**With manual data only:**
Ask the user to provide:
1. Backlink export CSV (with source domains, anchor text, link type)
2. Referring domains list with authority metrics
3. Competitor domains for comparison
4. Recent link gains/losses if tracking changes
5. Any known toxic or spammy links

Proceed with the full analysis using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests backlink analysis:

1. **Generate Profile Overview** -- Key metrics (total backlinks, referring domains, DA/DR, dofollow ratio), link velocity (30d/90d/year), authority distribution chart, profile health score.

2. **Analyze Link Quality** -- Top quality backlinks table, link type distribution, anchor text analysis (brand/exact/partial/URL/generic), geographic distribution.

3. **Identify Toxic Links** -- Toxic score, risk indicators by type (spam, PBN, link farms, irrelevant), high-risk links to review, disavow recommendations (domain-level and URL-level).

4. **Compare Against Competitors** -- Profile comparison table (referring domains, DA/DR, velocity, avg link DA), unique referring domains, link intersection analysis, competitor content attracting most links.

5. **Find Link Building Opportunities** -- Link intersection prospects, broken link opportunities, unlinked mentions, resource page opportunities, guest post prospects, priority matrix (effort vs impact).

6. **Track Link Changes** -- New and lost links for last 30 days with DA, type, anchor, dates. Net change and links to recover.

7. **Generate Backlink Report** -- Executive summary, strengths, concerns, opportunities, competitive position, recommended actions (immediate/short-term/long-term), KPIs to track.

   > **Reference**: See [references/analysis-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/backlink-analyzer/references/analysis-templates.md) for complete output templates for all 7 steps above.

### CITE Item Mapping

When running `domain-authority-auditor` after this analysis, the following data feeds directly into CITE scoring:

| Backlink Metric | CITE Item | Dimension |
|----------------|-----------|-----------|
| Referring domains count | C01 (Referring Domain Volume) | Citation |
| Authority distribution (DA breakdown) | C02 (Referring Domains Quality) | Citation |
| Link velocity | C04 (Link Velocity) | Citation |
| Geographic distribution | C10 (Link Source Diversity) | Citation |
| Dofollow/Nofollow ratio | T02 (Dofollow Ratio Normality) | Trust |
| Toxic link analysis | T01 (Link Profile Naturalness), T03 (Link-Traffic Coherence) | Trust |
| Competitive link intersection | T05 (Profile Uniqueness) | Trust |

## Validation Checkpoints

### Input Validation
- [ ] Target domain backlink data is complete and current
- [ ] Competitor domains specified for comparison analysis
- [ ] Backlink data includes necessary fields (source domain, anchor text, link type)
- [ ] Authority metrics available (DA/DR or equivalent)

### Output Validation
- [ ] Every metric cites its data source and collection date
- [ ] Toxic link assessments include risk justification
- [ ] Link opportunity recommendations are specific and actionable
- [ ] Source of each data point clearly stated (~~link database data, ~~SEO tool data, user-provided, or estimated)

## Example

**User**: "Find link building opportunities by analyzing HubSpot, Salesforce, and Mailchimp"

**Output**:

```markdown
## Link Intersection Analysis

### Sites linking to 2+ competitors (not you)

| Domain | DA | HubSpot | Salesforce | Mailchimp | Opportunity |
|--------|-----|---------|------------|-----------|-------------|
| g2.com | 91 | ✅ | ✅ | ✅ | Get listed/reviewed |
| capterra.com | 89 | ✅ | ✅ | ✅ | Submit for review |
| entrepreneur.com | 92 | ✅ | ✅ | ❌ | Pitch guest post |
| techcrunch.com | 94 | ✅ | ❌ | ✅ | PR/news pitch |

### Top 5 Immediate Opportunities

1. **G2.com** (DA 91) - All competitors listed
   - Action: Create detailed G2 profile
   - Effort: Low
   - Impact: High authority + referral traffic

2. **Entrepreneur.com** (DA 92) - 2 competitors have links
   - Action: Pitch contributed article
   - Effort: High
   - Impact: High authority + brand exposure

3. **MarketingProfs** (DA 75) - All competitors featured
   - Action: Apply for expert contribution
   - Effort: Medium
   - Impact: Relevant audience + quality link

### Estimated Impact

If you acquire links from top 10 opportunities:
- New referring domains: +10
- Average DA of new links: 82
- Estimated ranking impact: +2-5 positions for competitive keywords
```

## Tips for Success

1. **Quality over quantity** - One DA 80 link beats ten DA 20 links
2. **Monitor regularly** - Catch lost links and toxic links early
3. **Study competitors** - Learn from their link building success
4. **Diversify your profile** - Mix of link types and anchors
5. **Disavow carefully** - Only disavow clearly toxic links

## Link Quality and Strategy Reference

> **Reference**: See [references/link-quality-rubric.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/backlink-analyzer/references/link-quality-rubric.md) for the complete link quality scoring matrix (6 weighted factors), toxic link identification criteria, link profile health benchmarks, and disavow file guidance.

> **Reference**: See [references/outreach-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/backlink-analyzer/references/outreach-templates.md) for email outreach frameworks, subject line formulas, response rate benchmarks, follow-up sequences, and templates for each link building strategy.


### Save Results

After delivering monitoring data or reports to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/monitoring/YYYY-MM-DD-<topic>.md` containing:
- One-line headline finding or status change
- Top 3-5 actionable items
- Open loops or anomalies requiring follow-up
- Source data references

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.


**Gate check recommended**: If toxic link ratio exceeds 15%, recommend running domain-authority-auditor to assess overall domain trust impact.

## Reference Materials

- [Link Quality Rubric](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/backlink-analyzer/references/link-quality-rubric.md) — Quality scoring matrix with weighted factors and toxic link identification criteria
- [Outreach Templates](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/backlink-analyzer/references/outreach-templates.md) — Email frameworks, subject line formulas, and response rate benchmarks

## Next Best Skill

- **Primary**: [domain-authority-auditor](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/cross-cutting/domain-authority-auditor/SKILL.md) — translate link findings into a domain-level trust view.
