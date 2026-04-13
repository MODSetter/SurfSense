---
name: rank-tracker
description: 'Track keyword rankings and SERP feature changes in traditional search and AI responses over time. 排名追踪/SERP监控'
version: "6.0.0"
license: Apache-2.0
compatibility: "Claude Code ≥1.0, skills.sh marketplace, ClawHub marketplace, Vercel Labs skills ecosystem. No system packages required. Optional: MCP network access for SEO tool integrations."
homepage: "https://github.com/aaron-he-zhu/seo-geo-claude-skills"
when_to_use: "Use when tracking keyword rankings, monitoring position changes, comparing ranking snapshots, or detecting ranking drops."
argument-hint: "<domain> [keyword list]"
metadata:
  author: aaron-he-zhu
  version: "6.0.0"
  geo-relevance: "medium"
  tags:
    - seo
    - geo
    - rank-tracking
    - keyword-rankings
    - serp-positions
    - ranking-changes
    - position-tracking
    - 排名追踪
    - ランキング追跡
    - 순위추적
    - seguimiento-rankings
  triggers:
    # EN-formal
    - "track rankings"
    - "check keyword positions"
    - "ranking changes"
    - "monitor SERP positions"
    - "keyword tracking"
    - "position monitoring"
    # EN-casual
    - "how am I ranking"
    - "where do I rank for this keyword"
    - "did my rankings change"
    - "where do I rank now"
    - "check my positions"
    # EN-question
    - "what position am I ranking at"
    - "how are my rankings doing"
    # ZH-pro
    - "排名追踪"
    - "关键词排名"
    - "SERP位置监控"
    - "排名变化"
    # ZH-casual
    - "查排名"
    - "排名变了吗"
    - "我排第几"
    # JA
    - "ランキング追跡"
    - "検索順位チェック"
    - "順位変動"
    - "キーワード順位確認"
    # KO
    - "순위 추적"
    - "키워드 순위"
    - "순위 확인"
    - "내 순위 어떻게 됐어?"
    # ES
    - "seguimiento de rankings"
    - "posición en buscadores"
    - "posicionamiento SEO"
    - "en qué posición estoy"
    # PT
    - "rastreamento de rankings"
    - "monitoramento de posições"
    - "posição no Google"
    # Misspellings
    - "rank trackng"
---

# Rank Tracker


> **[SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills)** · 20 skills for SEO + GEO · [ClawHub](https://clawhub.ai/u/aaron-he-zhu) · [skills.sh](https://skills.sh/aaron-he-zhu/seo-geo-claude-skills)
> **System Mode**: This monitoring skill follows the shared [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md) and [State Model](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/state-model.md).


Tracks, analyzes, and reports on keyword ranking positions over time. Monitors both traditional SERP rankings and AI/GEO visibility to provide comprehensive search performance insights.

**System role**: Monitoring layer skill. It turns performance changes into deltas, alerts, and next actions.

## When This Must Trigger

Use this when the conversation involves any of these situations — even if the user does not use SEO terminology:

Use this whenever the task needs time-aware change detection, escalation, or stakeholder-ready visibility.

- Setting up ranking tracking for new campaigns
- Monitoring keyword position changes
- Analyzing ranking trends over time
- Comparing rankings against competitors
- Tracking SERP feature appearances
- Monitoring AI Overview inclusions
- Creating ranking reports for stakeholders

## What This Skill Does

1. **Position Tracking**: Records and tracks keyword rankings
2. **Trend Analysis**: Identifies ranking patterns over time
3. **Movement Detection**: Flags significant position changes
4. **Competitor Comparison**: Benchmarks against competitors
5. **SERP Feature Tracking**: Monitors featured snippets, PAA
6. **GEO Visibility Tracking**: Tracks AI citation appearances
7. **Report Generation**: Creates ranking performance reports

## Quick Start

Start with one of these prompts. Finish with a short handoff summary using the repository format in [Skill Contract](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/skill-contract.md).

### Set Up Tracking

```
Set up rank tracking for [domain] targeting these keywords: [keyword list]
```

### Analyze Rankings

```
Analyze ranking changes for [domain] over the past [time period]
```

### Compare to Competitors

```
Compare my rankings to [competitor] for [keywords]
```

### Generate Reports

```
Create a ranking report for [domain/campaign]
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

**With ~~SEO tool + ~~search console + ~~analytics + ~~AI monitor connected:**
Automatically pull ranking positions from ~~SEO tool, search impressions/clicks from ~~search console, traffic data from ~~analytics, and AI Overview citation tracking from ~~AI monitor. Daily automated rank checks with historical trend data.

**With manual data only:**
Ask the user to provide:
1. Keyword ranking positions (current and historical if available)
2. Target keyword list with search volumes
3. Competitor domains and their ranking positions for key terms
4. SERP feature status (featured snippets, PAA appearances)
5. AI Overview citation data (if tracking GEO metrics)

Proceed with the full analysis using provided data. Note in the output which metrics are from automated collection vs. user-provided data.

## Instructions

When a user requests rank tracking or analysis:

1. **Set Up Keyword Tracking** -- Configure domain, location, device, language, update frequency. Add keywords with volume, current rank, type, and priority. Set up competitor tracking and keyword categories (brand/product/informational/commercial).

2. **Record Current Rankings** -- Ranking overview by position range (#1, #2-3, #4-10, #11-20, etc.), position distribution visualization, detailed rankings with URL, SERP features, and change.

3. **Analyze Ranking Changes** -- Overall movement metrics, biggest improvements and declines with hypothesized causes, recommended recovery actions, stable keywords, new rankings, lost rankings.

4. **Track SERP Features** -- Feature ownership comparison vs competitors (snippets, PAA, image/video pack, local pack), featured snippet status, PAA appearances.

5. **Track GEO/AI Visibility** -- AI Overview presence per keyword, citation rate and position, GEO performance trend over time, improvement opportunities.

6. **Compare Against Competitors** -- Share of voice table, head-to-head comparison per keyword, competitor movement alerts with threat level.

7. **Generate Ranking Report** -- Executive summary with overall trend, position distribution, key highlights (wins/concerns/opportunities), detailed analysis, SERP feature report, GEO visibility, competitive position, recommendations.

   > **Reference**: See [references/ranking-analysis-templates.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/rank-tracker/references/ranking-analysis-templates.md) for complete output templates for all 7 steps.

## Validation Checkpoints

### Input Validation
- [ ] Keywords list is complete with search volumes
- [ ] Target domain and tracking location are specified
- [ ] Competitor domains identified for comparison
- [ ] Historical baseline data available or initial tracking period set

### Output Validation
- [ ] Every metric cites its data source and collection date
- [ ] Ranking changes include context (vs. previous period)
- [ ] Significant movements have explanations or investigation notes
- [ ] Source of each data point clearly stated (~~SEO tool data, ~~search console data, user-provided, or estimated)

## Example

**User**: "Analyze my ranking changes for the past month"

**Output**:

```markdown
# Ranking Analysis: [current month, year]

## Summary

Your average position improved from 15.3 to 12.8 (-2.5 positions = better)
Keywords in top 10 increased from 12 to 17 (+5)

## Biggest Wins

| Keyword | Old | New | Change | Possible Cause |
|---------|-----|-----|--------|----------------|
| email marketing tips | 18 | 5 | +13 | Likely driven by content refresh |
| best crm software | 24 | 11 | +13 | Correlates with new backlinks acquired |
| sales automation | 15 | 7 | +8 | Correlates with schema markup addition |

## Needs Attention

| Keyword | Old | New | Change | Action |
|---------|-----|-----|--------|--------|
| marketing automation | 4 | 12 | -8 | Likely displaced by new HubSpot guide |

**Recommended**: Update your marketing automation guide with [current year] statistics and examples.
```

## Tips for Success

1. **Track consistently** - Same time, same device, same location
2. **Include enough keywords** - 50-200 for meaningful data
3. **Segment by intent** - Track brand, commercial, informational separately
4. **Monitor competitors** - Context makes your data meaningful
5. **Track SERP features** - Position 1 without snippet may lose to position 4 with snippet
6. **Include GEO metrics** - AI visibility increasingly important

## Rank Change Quick Reference

### Response Protocol

| Change | Timeframe | Action |
|--------|-----------|--------|
| Drop 1-3 positions | Wait 1-2 weeks | Monitor -- may be normal fluctuation |
| Drop 3-5 positions | Investigate within 1 week | Check for technical issues, competitor changes |
| Drop 5-10 positions | Investigate immediately | Full diagnostic: technical, content, links |
| Drop off page 1 | Emergency response | Comprehensive audit + recovery plan |
| Position gained | Document and learn | What worked? Can you replicate? |

> **Reference**: See [references/tracking-setup-guide.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/rank-tracker/references/tracking-setup-guide.md) for root cause taxonomy, CTR benchmarks by position, SERP feature CTR impact, algorithm update assessment, tracking configuration best practices, keyword selection and grouping strategies, and data interpretation guidelines.


### Save Results

After delivering monitoring data or reports to the user, ask:

> "Save these results for future sessions?"

If yes, write a dated summary to `memory/monitoring/YYYY-MM-DD-<topic>.md` containing:
- One-line headline finding or status change
- Top 3-5 actionable items
- Open loops or anomalies requiring follow-up
- Source data references

If any findings should influence ongoing strategy, recommend promoting key conclusions to `memory/hot-cache.md`.

## Reference Materials

- [Tracking Setup Guide](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/rank-tracker/references/tracking-setup-guide.md) — Configuration best practices, device/location settings, and SERP feature tracking setup

## Next Best Skill

- **Primary**: [alert-manager](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/monitor/alert-manager/SKILL.md) — operationalize rank changes into thresholds and follow-ups.
