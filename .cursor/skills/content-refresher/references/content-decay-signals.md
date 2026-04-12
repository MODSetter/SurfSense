# Content Decay Signals

Comprehensive decay detection system with automated monitoring setup, severity scoring, refresh playbooks by content type, and ROI estimation for content refresh investments.

## Decay Signal Detection System

### Primary Signals (High Reliability)

These signals directly indicate content performance decline and should trigger immediate investigation.

#### 1. Organic Traffic Decline

| Severity | Threshold | Detection Window | Action |
|----------|-----------|-----------------|--------|
| Watch | 10-20% decline | Month-over-month | Add to monitoring list |
| Warning | 20-40% decline | Month-over-month | Schedule refresh within 2 weeks |
| Critical | 40-60% decline | Month-over-month | Refresh this week |
| Emergency | >60% decline | Month-over-month | Investigate immediately (may be technical issue) |

**Detection method**: Compare current month's organic sessions to same month previous year (to account for seasonality) and to previous month (for trend detection).

**False positive check**: Before attributing traffic decline to content decay, rule out:
- Seasonal variations (compare year-over-year, not just month-over-month)
- Algorithm updates (check if decline coincides with known Google updates)
- Technical issues (crawl errors, indexation problems, site speed regression)
- Tracking code changes (analytics misconfiguration)

#### 2. Ranking Position Drops

| Severity | Threshold | Detection Window | Action |
|----------|-----------|-----------------|--------|
| Watch | 1-3 positions lost | 2-week average | Monitor |
| Warning | 3-5 positions lost | 2-week average | Investigate cause |
| Critical | 5-10 positions lost | 2-week average | Schedule immediate refresh |
| Emergency | Dropped off page 1 to page 3+ | Any timeframe | Priority refresh or rewrite |

**Detection method**: Track primary keyword positions weekly. Use 2-week rolling averages to smooth daily fluctuations.

#### 3. Click-Through Rate Decline

| Severity | Threshold | Context | Action |
|----------|-----------|---------|--------|
| Watch | CTR below expected for position | Position stable, CTR dropping | Review title and meta description |
| Warning | CTR dropped 20%+ vs. baseline | With stable impressions | Rewrite title tag and meta description |
| Critical | CTR dropped 40%+ vs. baseline | May indicate stale SERP appearance | Full refresh of title, description, and structured data |

**Expected CTR by position** (organic, desktop, approximate):

| Position | Expected CTR Range | Below This = Investigate |
|----------|--------------------|-------------------------|
| 1 | 25-35% | <20% |
| 2 | 12-18% | <10% |
| 3 | 8-12% | <6% |
| 4-5 | 5-8% | <4% |
| 6-10 | 2-5% | <2% |

---

### Secondary Signals (Moderate Reliability)

These signals suggest potential decay but may have other causes. Use them to corroborate primary signals.

#### 4. Engagement Metric Decline

| Metric | Decay Indicator | Possible Cause |
|--------|----------------|---------------|
| Bounce rate increase >15% | Content no longer satisfies intent | Outdated information, better competitor content |
| Time on page decrease >20% | Users leaving faster | Content not comprehensive enough |
| Scroll depth decrease | Users not reading full content | Front-loading outdated info, losing interest |
| Pages per session decrease | Users not exploring further | Poor internal linking, irrelevant content |

#### 5. Content Freshness Indicators

| Indicator | Decay Risk | Detection |
|-----------|-----------|-----------|
| Published >12 months ago, never updated | High | CMS date audit |
| Contains year references 2+ years old | High | Text search for year patterns |
| Statistics from 3+ years ago | Medium | Manual review or text search for "20XX" |
| Broken external links (>10% of total) | Medium | Monthly crawl report |
| Screenshots of outdated UI | Medium | Manual visual review |
| References to discontinued products/tools | High | Manual review |

#### 6. Competitive Displacement Signals

| Signal | Detection Method | Severity |
|--------|-----------------|----------|
| New competitor content ranking above you | SERP monitoring | High |
| Competitor content is longer and more comprehensive | Manual comparison | Medium |
| Competitor has more recent publication date displayed in SERP | SERP monitoring | Medium |
| Featured snippet lost to competitor | SERP monitoring | High |
| AI overview now answers query without click | SERP monitoring | High |

---

### Tertiary Signals (Low Reliability, Supporting Evidence)

These signals alone do not indicate decay but strengthen the case when combined with primary or secondary signals.

| Signal | What It Suggests |
|--------|-----------------|
| Fewer social shares over time | Content less share-worthy (may be stale) |
| Decrease in backlink acquisition | Content no longer being cited as a resource |
| Fewer comments or engagement | Community interest waning |
| Content not appearing in AI responses | Not structured for GEO or information is outdated |

---

## Automated Monitoring Setup

### Monitoring Dashboard Configuration

Set up these automated checks to catch decay early.

#### Weekly Checks

| Check | Data Source | Alert Threshold |
|-------|-----------|----------------|
| Keyword position changes | Rank tracker | Any target keyword drops >3 positions |
| Crawl errors on key pages | Search Console | Any new crawl error on monitored pages |
| Index coverage changes | Search Console | Any page drops from index |

#### Monthly Checks

| Check | Data Source | Alert Threshold |
|-------|-----------|----------------|
| Traffic comparison (MoM) | Analytics | >15% decline on any monitored page |
| CTR comparison | Search Console | >20% CTR decline for any target keyword |
| Broken link scan | Crawler | Any new broken links on monitored pages |
| Competitor SERP changes | SERP tracker | New competitor enters top 5 |

#### Quarterly Checks

| Check | Data Source | Process |
|-------|-----------|---------|
| Content freshness audit | CMS + manual | Review all content older than 6 months |
| Statistics accuracy check | Manual | Verify top 20 pages have current data |
| Engagement trend review | Analytics | Compare engagement metrics across quarters |
| Full competitive content gap | SEO tool | Identify new competitor content opportunities |

### Alert Priority Matrix

When multiple signals fire simultaneously, use this matrix to determine response urgency.

| Primary Signal + Secondary Signal | Priority | Response |
|----------------------------------|----------|----------|
| Traffic decline + Position drop | P1 (Critical) | Refresh within 48 hours |
| Traffic decline + CTR decline | P1 (Critical) | Rewrite title/description immediately, schedule content refresh |
| Position drop + Competitor displacement | P2 (High) | Refresh within 1 week |
| Traffic decline + Engagement decline | P2 (High) | Refresh within 1 week |
| CTR decline only | P3 (Medium) | Rewrite title and meta description this week |
| Freshness indicators only | P3 (Medium) | Schedule refresh within 2 weeks |
| Engagement decline only | P4 (Low) | Investigate and schedule if confirmed |

---

## Decay Severity Scoring

### Composite Decay Score

Calculate a 0-100 decay severity score by summing weighted signal scores.

| Signal Category | Weight | Score Range |
|----------------|--------|-------------|
| Traffic decline | 30% | 0 = no decline, 100 = >60% decline |
| Position drops | 25% | 0 = stable, 100 = dropped off page 1 |
| CTR decline | 15% | 0 = stable, 100 = >40% decline |
| Content freshness | 15% | 0 = updated this quarter, 100 = >2 years stale |
| Competitive displacement | 15% | 0 = no new competitors, 100 = displaced from top 3 |

### Score Interpretation

| Composite Score | Decay Stage | Action |
|----------------|-------------|--------|
| 0-20 | Healthy | Continue monitoring |
| 21-40 | Early decay | Add to refresh queue (next month) |
| 41-60 | Active decay | Schedule refresh (this week) |
| 61-80 | Significant decay | Immediate refresh or rewrite decision |
| 81-100 | Terminal decay | Rewrite, redirect, or retire |

---

## Refresh Playbooks by Content Type

### Blog Post / Article Refresh Playbook

| Step | Action | Time Estimate |
|------|--------|--------------|
| 1 | Update title with current year or hook | 10 min |
| 2 | Rewrite introduction with fresh angle | 20 min |
| 3 | Update all statistics with current sources | 30-60 min |
| 4 | Add 1-2 new sections covering gaps | 60-90 min |
| 5 | Update screenshots and images | 30 min |
| 6 | Add or update FAQ section | 20 min |
| 7 | Refresh internal links | 15 min |
| 8 | Update meta description | 5 min |
| 9 | Add/update schema markup | 10 min |
| 10 | Update dateModified and republish | 5 min |
| **Total** | | **3-4 hours** |

### Product/Service Page Refresh Playbook

| Step | Action | Time Estimate |
|------|--------|--------------|
| 1 | Update pricing, features, specifications | 30 min |
| 2 | Add new customer testimonials/reviews | 20 min |
| 3 | Update product images | 30 min |
| 4 | Refresh comparison tables | 20 min |
| 5 | Update internal links to related products | 15 min |
| 6 | Verify and update schema markup | 10 min |
| **Total** | | **2-2.5 hours** |

### Statistics/Data Roundup Refresh Playbook

| Step | Action | Time Estimate |
|------|--------|--------------|
| 1 | Verify every statistic is still current | 60-90 min |
| 2 | Replace outdated stats with current data | 60 min |
| 3 | Add new statistics from recent studies | 30 min |
| 4 | Update source links and citations | 30 min |
| 5 | Update year references throughout | 15 min |
| 6 | Add new visualization if data changed significantly | 30 min |
| 7 | Update title, meta description with year | 10 min |
| **Total** | | **4-5 hours** |

### How-To Guide Refresh Playbook

| Step | Action | Time Estimate |
|------|--------|--------------|
| 1 | Verify all steps are still accurate | 30 min |
| 2 | Update screenshots for UI changes | 60 min |
| 3 | Add new methods or alternative approaches | 30 min |
| 4 | Update tool recommendations | 15 min |
| 5 | Add troubleshooting section if missing | 20 min |
| 6 | Update FAQ with new common questions | 15 min |
| 7 | Test all links and embedded resources | 15 min |
| **Total** | | **3-3.5 hours** |

---

## ROI Estimation for Content Refresh

### Cost-Benefit Framework

| Factor | Measurement |
|--------|------------|
| **Cost of refresh** | Writer hours x hourly rate + tool costs |
| **Current monthly traffic value** | Organic sessions x conversion rate x avg order value |
| **Projected traffic recovery** | Based on decay stage and content potential |
| **Time to recover** | Typically 4-8 weeks for rankings to respond |

### Traffic Recovery Benchmarks

Based on industry data for content refreshes (not rewrites):

| Decay Stage at Refresh | Typical Traffic Recovery | Recovery Timeline |
|------------------------|------------------------|-------------------|
| Early decay | 90-110% of peak (often exceeds) | 2-4 weeks |
| Active decay | 70-90% of peak | 4-8 weeks |
| Significant decay | 40-70% of peak | 6-12 weeks |
| Terminal decay | 10-40% of peak (rewrite may be better) | 8-16 weeks |

### ROI Calculation Template

```
Refresh Cost:
  Writer time: [X hours] x [$Y/hour] = $[Z]
  Tool costs: $[A] (one-time crawl, research tools)
  Total cost: $[Z + A]

Monthly Traffic Value (before decay):
  Peak monthly organic sessions: [N]
  Conversion rate: [X]%
  Average conversion value: $[Y]
  Peak monthly value: [N] x [X]% x $[Y] = $[V]

Expected Recovery:
  Projected recovery: [%] of peak = $[V x %] per month
  Current monthly value: $[current]
  Monthly value increase: $[V x % - current]

ROI:
  Payback period: $[total cost] / $[monthly value increase] = [months]
  12-month ROI: ($[monthly value increase] x 12 - $[total cost]) / $[total cost] x 100 = [X]%
```

### Refresh Priority Scoring

When choosing which content to refresh first, score each candidate:

| Factor | Weight | Score (1-10) |
|--------|--------|-------------|
| Current traffic value | 25% | Higher traffic = higher score |
| Decay severity | 20% | More decay = more urgency |
| Competitive opportunity | 20% | Weaker competition = higher score |
| Refresh difficulty | 15% | Easier refresh = higher score |
| Strategic importance | 10% | Aligns with business goals = higher score |
| Backlink equity | 10% | More backlinks = more worth preserving |

**Priority formula**: Weighted score total. Refresh highest-scoring content first.

---

## Content Retirement Decision

Not all decaying content should be refreshed. Use this checklist to decide when to retire content instead.

### Retire When

- [ ] Content targets a keyword with zero search volume
- [ ] Topic is no longer relevant to your business
- [ ] No backlinks worth preserving
- [ ] Content never ranked well even when fresh
- [ ] Cost to refresh exceeds projected 12-month value recovery
- [ ] Content cannibalizes a better-performing page on the same topic

### Retirement Options

| Option | When to Use | Implementation |
|--------|------------|---------------|
| 301 redirect | Content has backlinks or residual traffic | Redirect to best related page |
| Consolidate | Multiple weak pages on same topic | Merge into one strong page, redirect others |
| Noindex | Page has internal utility but should not rank | Add noindex, keep page accessible |
| Delete (410) | Content has no value, no links, no traffic | Return 410 Gone status |

### Post-Retirement Monitoring

After retiring content, monitor for 4 weeks:
- Verify redirects are working (no 404 errors)
- Check that target pages are receiving redirected traffic
- Monitor rankings of consolidated/target pages
- Ensure no orphan pages were created by removing internal links

---

## Content Decay Signal Taxonomy

### Decay Indicators

| Signal | Source | Severity | Detection Method |
|--------|--------|----------|-----------------|
| Traffic decline >20% MoM | Analytics | High | Monthly traffic comparison |
| Position drop >5 positions | Rank tracker | High | Weekly rank monitoring |
| Outdated statistics/dates | Manual review | Medium | Annual content audit |
| Broken external links | Crawler | Medium | Monthly crawl reports |
| Decreased CTR | Search Console | Medium | Quarterly CTR analysis |
| Competitor new content | SERP monitoring | Medium | Monthly SERP checks |
| User engagement drop | Analytics | Low | Quarterly engagement review |
| Index coverage issues | Search Console | High | Weekly coverage monitoring |

### Content Decay Stages

| Stage | Symptoms | Urgency | Recommended Action |
|-------|---------|---------|-------------------|
| **Early decay** | Slight traffic/position dip | Low | Monitor for 2-4 weeks |
| **Active decay** | Consistent decline across 2+ months | Medium | Schedule refresh within 2 weeks |
| **Significant decay** | 50%+ traffic loss, page 2+ | High | Immediate refresh or rewrite |
| **Terminal decay** | No organic traffic, deindexed | Critical | Rewrite, redirect, or retire |

## Refresh vs. Rewrite Decision Framework

| Factor | Refresh (Update) | Rewrite (New version) |
|--------|-----------------|---------------------|
| Content quality | Good foundation, needs updating | Fundamentally flawed or outdated approach |
| Position | Was ranking well, now dropping | Never ranked well despite optimization |
| URL age | 1+ years, has earned backlinks | Young URL with no backlink equity |
| Backlinks | Has external links pointing to it | No backlinks worth preserving |
| Scope of changes needed | <50% of content changing | >50% needs rewriting |
| Search intent | Intent hasn't changed | Search intent has evolved |

**Decision rule:** If the URL has backlinks and was ranking, REFRESH. If not, consider REWRITE at a new URL (with 301 redirect if old URL has any equity).

## Content Lifecycle Model

```
CREATE → PROMOTE → MAINTAIN → REFRESH → [REFRESH again] or RETIRE
  │         │          │          │                          │
  │      Month 1    Month 2-6   Month 6-12              When terminal
  │    Social,      Monitor     Update facts,            301 redirect
  │    outreach,    rankings,   add new sections,         to related
  │    email        fix issues  improve depth              content
```

### Lifecycle Actions by Phase

| Phase | Duration | Key Actions | Metrics to Track |
|-------|----------|------------|-----------------|
| Create | Week 1 | Publish, submit to Search Console | Indexation |
| Promote | Month 1 | Social shares, email, outreach | Referral traffic, backlinks |
| Maintain | Months 2-6 | Monitor, fix broken links, respond to comments | Rankings, traffic trend |
| Refresh | Months 6-12+ | Update data, add sections, improve structure | Traffic recovery, new keywords |
| Retire | When terminal | 301 redirect to best alternative | Redirect traffic recovery |

## Update Strategy by Content Type

| Content Type | Refresh Frequency | Key Updates | Shelf Life |
|-------------|-------------------|------------|-----------|
| Statistics roundups | Every 6 months | Replace old stats, add new sources | 6-12 months |
| Tool comparisons | Every 3-6 months | Update pricing, features, screenshots | 3-6 months |
| How-to guides | Annually | Update steps, screenshots, links | 12-18 months |
| Evergreen guides | Every 12-18 months | Add new sections, update examples | 18-24 months |
| News/trend content | Don't refresh | Archive or redirect | 1-3 months |
| Case studies | Rarely | Update results if available | 2-3 years |
| Glossary/definitions | As needed | Update when definitions evolve | 2-5 years |

