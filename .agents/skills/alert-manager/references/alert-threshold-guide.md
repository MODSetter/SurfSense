# Alert Threshold Guide

Complete reference for configuring SEO/GEO alert thresholds. Covers baseline establishment, threshold setting methodology, tuning process, alert routing configuration, notification channel setup, and response playbooks for each alert type.

---

## 1. Baseline Establishment Process

Before setting any alert thresholds, you must establish a baseline that represents normal metric behavior for your site. Without a baseline, you will either set thresholds too tight (causing alert fatigue) or too loose (missing real problems).

### Baseline Collection Timeline

| Metric Category | Minimum Baseline Period | Ideal Baseline Period | Why |
|----------------|------------------------|----------------------|-----|
| Organic traffic | 4 weeks | 8-12 weeks | Accounts for weekly cycles and monthly patterns |
| Keyword rankings | 2-4 weeks | 4-8 weeks | Rankings fluctuate daily; need to establish normal range |
| Backlink metrics | 4 weeks | 8 weeks | Link acquisition is lumpy; need to see natural cadence |
| Technical metrics | 2 weeks | 4 weeks | Most technical metrics are relatively stable |
| Core Web Vitals | 4 weeks (28-day rolling) | 8 weeks | CrUX data is 28-day rolling average |
| AI citations | 4 weeks | 8 weeks | AI answer composition changes frequently |

### Baseline Data Collection Steps

| Step | Action | Output |
|------|--------|--------|
| 1 | Record daily metric values for the baseline period | Raw data spreadsheet |
| 2 | Calculate mean (average) for each metric | Central tendency |
| 3 | Calculate standard deviation for each metric | Normal variation range |
| 4 | Identify outliers (values > 2 standard deviations from mean) | Anomaly list |
| 5 | Remove known outliers (holidays, outages, one-time events) | Clean baseline |
| 6 | Recalculate mean and standard deviation on clean data | Final baseline values |
| 7 | Document seasonal patterns if baseline covers enough time | Seasonal adjustment notes |

### Baseline Metrics to Record

| Metric | Daily | Weekly | Monthly |
|--------|-------|--------|---------|
| Organic sessions | Record | Calculate WoW % change | Calculate MoM % change |
| Keyword positions (top 20) | Record | Calculate average movement | Calculate net position change |
| Keywords in top 10 | Record | Calculate weekly count | Calculate monthly trend |
| Crawl errors | Record | Calculate weekly new errors | Calculate monthly trend |
| New backlinks | N/A | Record weekly count | Calculate monthly velocity |
| Lost backlinks | N/A | Record weekly count | Calculate monthly velocity |
| Core Web Vitals | N/A | Record from CrUX | Calculate monthly trend |
| AI citations | N/A | Record weekly count | Calculate monthly trend |
| Pages indexed | N/A | Record weekly count | Calculate monthly change |
| Server response time | Record | Calculate weekly average | Calculate monthly average |

---

## 2. Threshold Setting Methodology

### The Standard Deviation Method

For most metrics, set thresholds based on standard deviations from your baseline mean.

| Threshold Level | Formula | Meaning |
|----------------|---------|---------|
| **Info** | Mean +/- 1 standard deviation | Normal fluctuation range; log but do not alert |
| **Warning** | Mean +/- 1.5 standard deviations | Unusual but not necessarily problematic |
| **Critical** | Mean +/- 2 standard deviations | Statistically significant anomaly; investigate |
| **Emergency** | Mean +/- 3 standard deviations | Extreme anomaly; immediate action required |

**Example calculation:**

```
Metric: Daily organic sessions
Baseline mean: 10,000 sessions/day
Standard deviation: 800 sessions/day

Info range:      8,200 - 11,800 (normal)
Warning:         < 8,800 or > 11,200
Critical:        < 8,400 or > 11,600
Emergency:       < 7,600 or > 12,400
```

### The Percentage Method

For metrics where standard deviation is not practical, use percentage-based thresholds.

| Metric | Warning Threshold | Critical Threshold | Comparison Period |
|--------|------------------|-------------------|-------------------|
| Organic traffic | -15% vs. comparison | -30% vs. comparison | Week over week |
| Keyword positions | >3 position average drop | >5 position average drop | Week over week |
| Pages indexed | -5% change | -20% change | Week over week |
| Referring domains | -5% loss | -15% loss | Month over month |
| Crawl error rate | >2x baseline rate | >5x baseline rate | Day over day |
| Conversion rate | -20% drop | -40% drop | Week over week |

### The Absolute Value Method

For binary or count-based metrics, use absolute thresholds.

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| New crawl errors | >10 new errors/day | >50 new errors/day |
| Server 5xx errors | Any occurrence | >5 occurrences/hour |
| Security issues | N/A | Any detection |
| Manual penalties | N/A | Any notification |
| SSL certificate expiry | <30 days to expiry | <7 days to expiry |
| Robots.txt changes | Any unexpected change | Key pages blocked |

---

## 3. Threshold Configuration by Metric Category

### Traffic Thresholds

| Metric | Comparison | Warning | Critical | Emergency |
|--------|-----------|---------|----------|-----------|
| Total organic sessions | WoW | -15% | -30% | -50% |
| Total organic sessions | DoD | -25% (weekday) | -40% | Site appears down |
| Non-brand sessions | WoW | -20% | -35% | -50% |
| Organic conversions | WoW | -20% | -40% | -60% |
| Organic revenue | WoW | -15% | -30% | -50% |
| Bounce rate | WoW | +10pp | +20pp | +30pp |
| Page-level traffic (top 10 pages) | WoW | -25% | -40% | -60% |

**Note:** Day-over-day traffic thresholds need day-of-week adjustment. Monday traffic typically differs from Saturday traffic. Compare Monday to Monday, not Monday to Sunday.

### Ranking Thresholds

| Metric | Scope | Warning | Critical |
|--------|-------|---------|----------|
| Position change (Tier 1 keywords) | Individual keyword | Drop >= 3 | Drop >= 5 |
| Position change (Tier 2 keywords) | Individual keyword | Drop >= 5 | Drop >= 10 |
| Position change (Tier 3 keywords) | Individual keyword | Drop >= 10 | Drop off page 3 |
| Average position (all keywords) | Aggregate | +2.0 (worsening) | +5.0 (worsening) |
| Keywords in top 10 | Count | -10% of count | -20% of count |
| Keywords in top 3 | Count | Any decrease | -3 or more |
| Brand keyword position | Individual | Any drop from #1 | Drops below #3 |
| Featured snippet lost | Individual | Any loss | Loss of 3+ snippets |

### Technical Thresholds

| Metric | Warning | Critical | Emergency |
|--------|---------|----------|-----------|
| New 4xx errors | >5/day | >20/day | >100/day |
| New 5xx errors | >1/day | >5/day | >20/day |
| Crawl rate change | -30% vs. baseline | -60% vs. baseline | Near-zero crawl |
| Index coverage drop | -5% | -15% | -30% |
| Average server response time | >500ms | >1000ms | >2000ms |
| LCP (mobile) | Moves to "Needs Improvement" | Moves to "Poor" | >6s |
| CLS | >0.1 | >0.25 | >0.5 |
| INP | >200ms | >500ms | >1000ms |
| Robots.txt change | Any unexpected edit | Pages blocked | Entire site blocked |
| Sitemap errors | New errors | Sitemap inaccessible | Sitemap returning 5xx |

### Backlink Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Referring domains lost (weekly) | >5% of total | >15% of total |
| High-authority link lost (DR 60+) | Any loss | Loss of 3+ in one week |
| Toxic link spike | >10 new toxic links/week | >50 new toxic links/week |
| Anchor text over-optimization | Exact match reaches 20% | Exact match reaches 30% |
| Negative SEO pattern | Unusual link velocity from low-DR sites | Massive spam link spike |

### GEO / AI Visibility Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| AI citation rate | Drops 10+ percentage points | Drops below 10% |
| Key query citation lost | Any Tier 1 query | 3+ Tier 1 queries |
| Citation position degradation | Average position worsens by 2+ | Dropped from citations entirely |
| Competitor gains citation you lost | 1 instance | Pattern across queries |

---

## 4. Alert Routing Configuration

### Routing Matrix

| Alert Category | P0 (Emergency) | P1 (Urgent) | P2 (Important) | P3 (Monitor) |
|---------------|----------------|-------------|----------------|--------------|
| **Traffic** | SEO Lead + Eng Manager + VP | SEO Lead + Marketing Mgr | SEO Team | Weekly digest |
| **Rankings** | SEO Lead + Content Lead | SEO Team | SEO Team | Weekly digest |
| **Technical** | SEO Lead + Eng Lead + DevOps | SEO Lead + Eng Team | SEO Team + Eng | Weekly digest |
| **Backlinks** | SEO Lead | SEO Team | SEO Team | Weekly digest |
| **Competitor** | N/A | SEO Lead | SEO Team | Weekly digest |
| **GEO/AI** | SEO Lead + Content Lead | SEO Team | SEO Team | Weekly digest |
| **Security** | SEO Lead + Eng Manager + VP + Legal | All above | N/A | N/A |

### Role-Based Alert Filtering

| Role | Receives | Does Not Receive |
|------|---------|-----------------|
| SEO Lead | All P0, P1, P2 alerts | P3 (weekly digest only) |
| SEO Analyst | P1, P2 in their area | P0 (escalation only), other areas |
| Content Lead | P0-P1 ranking + GEO alerts | Technical alerts, backlink alerts |
| Engineering Lead | P0-P1 technical alerts | Ranking, content, backlink alerts |
| Marketing VP | P0 only | P1-P3 (receives weekly summary) |
| DevOps | P0 technical + security | All non-infrastructure alerts |

---

## 5. Notification Channel Setup

### Channel Selection by Priority

| Priority | Primary Channel | Secondary Channel | Escalation Channel |
|----------|----------------|-------------------|-------------------|
| P0 | SMS + Phone call | Slack (#seo-emergencies) | PagerDuty / on-call rotation |
| P1 | Slack (#seo-alerts) | Email | SMS (if not acknowledged in 4h) |
| P2 | Email | Slack (#seo-daily) | Auto-escalate to P1 after 1 week |
| P3 | Weekly digest email | Dashboard | Auto-escalate to P2 after 1 month |

### Notification Content Requirements

Every alert notification should include:

| Field | Required | Example |
|-------|----------|---------|
| Alert name | Yes | "Critical Ranking Drop" |
| Priority level | Yes | "P0 — Emergency" |
| Metric affected | Yes | "Position for 'project management software'" |
| Current value | Yes | "Position 12" |
| Previous value | Yes | "Position 3 (yesterday)" |
| Threshold breached | Yes | "Dropped >5 positions" |
| Timestamp | Yes | "2025-01-15 09:00 UTC" |
| Affected URL | Yes (if applicable) | "yoursite.com/blog/pm-guide" |
| Quick action link | Yes | Link to relevant tool/dashboard |
| Suggested first step | Recommended | "Check if page is still indexed: site:yoursite.com/blog/pm-guide" |

### Notification Suppression Rules

| Rule | Configuration | Reason |
|------|-------------|--------|
| Duplicate cooldown | Do not re-alert on same metric for 24 hours | Prevent alert storms |
| Maintenance window | Suppress non-security alerts during scheduled maintenance | Avoid known-cause alerts |
| Weekend adjustment | Increase traffic thresholds by 20% on weekends | Weekend traffic naturally lower |
| Holiday adjustment | Suppress traffic alerts on major holidays | Known seasonal impact |
| Recovery auto-close | Auto-close alert if metric returns to normal within 48h | Reduce stale alerts |
| Batch related alerts | Group multiple ranking drops into single "Ranking Alert" | Reduce notification volume |

---

## 6. Threshold Tuning Guide

### When to Tune Thresholds

| Signal | Action |
|--------|--------|
| Too many false positives (>30% of alerts are noise) | Widen thresholds by 0.5 standard deviations |
| Missed a real problem | Tighten the specific threshold that should have caught it |
| Seasonal change approaching | Adjust baselines for known seasonal patterns |
| Major site change (redesign, migration) | Re-establish baseline from scratch (2-4 week observation) |
| New competitor enters market | Add competitor monitoring, adjust ranking sensitivity |
| After algorithm update | Let metrics stabilize for 2-4 weeks, then recalibrate |

### Monthly Threshold Review Checklist

| Check | Action |
|-------|--------|
| Review all alerts fired in the past month | Count true positives vs. false positives |
| Calculate false positive rate | If >30%, thresholds are too tight |
| Check for missed events | If a real issue was not alerted, threshold is too loose |
| Review metric baselines | Recalculate mean and standard deviation with latest data |
| Adjust seasonal baselines | Incorporate seasonal patterns from year-over-year data |
| Update keyword tiers | Promote/demote keywords based on current business priority |
| Verify notification routing | Confirm all recipients are still in the correct roles |
| Test alert delivery | Send a test alert through each channel to verify delivery |

### Threshold Evolution Over Time

| Site Maturity | Threshold Approach | Rationale |
|-------------|-------------------|-----------|
| New site (0-6 months) | Wide thresholds, few alerts | Metrics are volatile; avoid noise |
| Growing (6-18 months) | Moderate thresholds, expand coverage | Enough data for meaningful baselines |
| Established (18+ months) | Tight thresholds, comprehensive | Stable baselines, can detect subtle changes |
| Post-migration | Reset to wide, re-tighten over 4-8 weeks | Old baselines are invalid |

---

## 7. Playbook Templates by Alert Type

### Playbook: Organic Traffic Emergency (P0)

**Trigger:** Organic traffic drops >50% day-over-day

| Step | Time | Action | Tool |
|------|------|--------|------|
| 1 | 0 min | Verify site is accessible from multiple locations | Manual browser check, uptime monitor |
| 2 | 5 min | Check Google Search Status Dashboard for outages | Google Status Dashboard |
| 3 | 10 min | Check Search Console for manual actions or security issues | ~~search console |
| 4 | 15 min | Check robots.txt for accidental blocking | Direct URL check |
| 5 | 20 min | Check for noindex tags added to key pages | Crawl or manual page inspection |
| 6 | 30 min | Review recent deployments or CMS changes | Deploy log, git history |
| 7 | 45 min | Check server logs for unusual patterns | Server access logs |
| 8 | 60 min | If unresolved, escalate to Engineering Manager | Slack/phone |

### Playbook: Security Alert (P0)

**Trigger:** Google Search Console security issue or manual action

| Step | Time | Action |
|------|------|--------|
| 1 | 0 min | Read the exact message in Search Console |
| 2 | 5 min | Notify Engineering Manager and VP Marketing |
| 3 | 15 min | Scan site for malware or injected content |
| 4 | 30 min | If compromised: take affected pages offline, rotate all credentials |
| 5 | 1 hour | Identify attack vector and patch vulnerability |
| 6 | 2 hours | Clean all affected pages, submit for re-review |
| 7 | 24 hours | Verify resolution in Search Console |
| 8 | 1 week | Post-incident review and security hardening |

### Playbook: Algorithm Update Impact (P1-P2)

**Trigger:** Confirmed Google algorithm update + ranking/traffic changes

| Step | Time | Action |
|------|------|--------|
| 1 | Day 0 | Confirm update via Google Search Status Dashboard or official channels |
| 2 | Day 0 | Document pre-update baseline metrics (rankings, traffic, visibility) |
| 3 | Day 1-3 | Monitor daily — do not make changes while update is rolling out |
| 4 | Day 7 | First analysis: which pages/keywords improved, which declined |
| 5 | Day 7 | Analyze pattern: content quality? link profile? technical? YMYL? |
| 6 | Day 14 | Develop action plan based on analysis |
| 7 | Day 14-60 | Implement improvements (content quality, E-E-A-T signals, technical fixes) |
| 8 | Next update | Re-evaluate impact after next core update |

### Playbook: Backlink Attack / Negative SEO (P1)

**Trigger:** Unusual spike in low-quality backlinks (>100 new links from spam domains in one week)

| Step | Time | Action |
|------|------|--------|
| 1 | Day 0 | Verify the spike in ~~link database |
| 2 | Day 0 | Identify the pattern (same anchor text? same link network? same country?) |
| 3 | Day 1 | Export all new toxic links |
| 4 | Day 1 | Create disavow file with identified spam domains |
| 5 | Day 2 | Upload disavow to Google Search Console |
| 6 | Day 2 | Document the attack pattern for future reference |
| 7 | Day 7 | Re-check for continued spam link activity |
| 8 | Day 14 | Verify disavow processed, monitor rankings for impact |

### Playbook: Core Web Vitals Degradation (P2)

**Trigger:** Any CWV metric moves from "Good" to "Needs Improvement" or "Poor"

| Step | Time | Action |
|------|------|--------|
| 1 | Day 0 | Identify which metric degraded and which page groups are affected |
| 2 | Day 1 | Run PageSpeed Insights on representative pages |
| 3 | Day 1 | Check recent deployments for potential cause (new scripts, images, layout changes) |
| 4 | Day 2 | Create engineering ticket with diagnosis and fix recommendations |
| 5 | Day 3-14 | Engineering implements fix |
| 6 | Day 14 | Verify improvement in lab data (PageSpeed Insights) |
| 7 | Day 42 | Verify improvement in field data (CrUX — 28-day rolling window) |

---

## 8. Alert System Maintenance

### Quarterly System Review

| Task | Frequency | Owner |
|------|-----------|-------|
| Recalculate all baselines with latest data | Quarterly | SEO Lead |
| Review and update keyword tier assignments | Quarterly | SEO Team |
| Audit notification routing (team changes, role changes) | Quarterly | SEO Lead |
| Test all notification channels (SMS, Slack, email) | Quarterly | SEO Lead |
| Review alert response times (are SLAs being met?) | Quarterly | SEO Lead |
| Archive resolved alerts older than 90 days | Quarterly | SEO Analyst |
| Update playbooks based on lessons learned | Quarterly | SEO Team |

### Alert Effectiveness Metrics

Track these metrics about your alerting system itself:

| Metric | Target | Meaning |
|--------|--------|---------|
| False positive rate | <30% | % of alerts that were not actionable |
| Mean time to acknowledge (MTTA) | P0: <15min, P1: <4h | Time from alert to first human response |
| Mean time to resolve (MTTR) | P0: <2h, P1: <24h | Time from alert to resolution |
| Missed incident rate | 0% | Real problems that were not alerted |
| Alert volume per week | Manageable for team size | If overwhelming, thresholds need tuning |
