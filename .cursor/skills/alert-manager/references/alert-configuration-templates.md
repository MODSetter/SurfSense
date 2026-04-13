# Alert Configuration Templates

Detailed alert configuration templates for each alert category. Use these templates when setting up a new alert system for a domain.

---

## Ranking Alerts

### Position Drop Alerts

| Alert Name | Condition | Threshold | Priority | Action |
|------------|-----------|-----------|----------|--------|
| Critical Drop | Any top 3 keyword drops 5+ positions | Position change >=5 | Critical | Immediate investigation |
| Major Drop | Top 10 keyword drops out of top 10 | Position >10 | High | Same-day review |
| Moderate Drop | Any keyword drops 10+ positions | Position change >=10 | Medium | Weekly review |
| Competitor Overtake | Competitor passes you for key term | Comp position < yours | Medium | Analysis needed |

### Position Improvement Alerts

| Alert Name | Condition | Threshold | Priority |
|------------|-----------|-----------|----------|
| New Top 3 | Keyword enters top 3 | Position <=3 | Positive |
| Page 1 Entry | Keyword enters top 10 | Position <=10 | Positive |
| Significant Climb | Keyword improves 10+ positions | Change >=+10 | Positive |

### SERP Feature Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Snippet Lost | Lost featured snippet ownership | High |
| Snippet Won | Won new featured snippet | Positive |
| AI Overview Change | Appeared/disappeared in AI Overview | Medium |

### Keywords to Monitor

| Keyword | Current Rank | Alert Threshold | Priority |
|---------|--------------|-----------------|----------|
| [keyword 1] | [X] | Drop >=3 | Critical |
| [keyword 2] | [X] | Drop >=5 | High |
| [keyword 3] | [X] | Drop >=10 | Medium |

---

## Traffic Alerts

### Traffic Decline Alerts

| Alert Name | Condition | Threshold | Priority |
|------------|-----------|-----------|----------|
| Traffic Crash | Day-over-day decline | >=50% drop | Critical |
| Significant Drop | Week-over-week decline | >=30% drop | High |
| Moderate Decline | Month-over-month decline | >=20% drop | Medium |
| Trend Warning | 3 consecutive weeks decline | Any decline | Medium |

### Traffic Anomaly Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Traffic Spike | Unusual increase | Investigate |
| Zero Traffic | Page receiving 0 visits | High |
| Bot Traffic | Unusual traffic pattern | Medium |

### Page-Level Alerts

| Page Type | Alert Condition | Priority |
|-----------|-----------------|----------|
| Homepage | Any 20%+ decline | Critical |
| Top 10 pages | Any 30%+ decline | High |
| Conversion pages | Any 25%+ decline | High |
| Blog posts | Any 40%+ decline | Medium |

### Conversion Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Conversion Drop | Organic conversions down 30%+ | Critical |
| CVR Decline | Conversion rate drops 20%+ | High |

---

## Technical SEO Alerts

### Critical Technical Alerts

| Alert Name | Condition | Priority | Response Time |
|------------|-----------|----------|---------------|
| Site Down | HTTP 5xx errors | Critical | Immediate |
| SSL Expiry | Certificate expiring in 14 days | Critical | Same day |
| Robots.txt Block | Important pages blocked | Critical | Same day |
| Index Dropped | Pages dropping from index | Critical | Same day |

### Crawl & Index Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Crawl Errors Spike | Errors increase 50%+ | High |
| New 404 Pages | 404 errors on important pages | Medium |
| Redirect Chains | 3+ redirect hops detected | Medium |
| Duplicate Content | New duplicates detected | Medium |
| Index Coverage Drop | Indexed pages decline 10%+ | High |

### Performance Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Core Web Vitals Fail | CWV drops to "Poor" | High |
| Page Speed Drop | Load time increases 50%+ | Medium |
| Mobile Issues | Mobile usability errors | High |

### Security Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Security Issue | GSC security warning | Critical |
| Manual Action | Google manual action | Critical |
| Malware Detected | Site flagged for malware | Critical |

---

## Backlink Alerts

### Link Loss Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| High-Value Link Lost | DA 70+ link removed | High |
| Multiple Links Lost | 10+ links lost in a day | Medium |
| Referring Domain Lost | Lost entire domain's links | Medium |

### Link Gain Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| High-Value Link | New DA 70+ link | Positive |
| Suspicious Links | Many low-quality links | Review |
| Negative SEO | Spam link attack pattern | High |

### Link Profile Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Toxic Score Increase | Toxic score up 20%+ | High |
| Anchor Over-Optimization | Exact match anchors >30% | Medium |

---

## Competitor Monitoring Alerts

### Ranking Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Competitor Overtake | Competitor passes you | Medium |
| Competitor Top 3 | Competitor enters top 3 on key term | Medium |
| Competitor Content | Competitor publishes on your topic | Info |

### Activity Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| New Backlinks | Competitor gains high-DA link | Info |
| Content Update | Competitor updates ranking content | Info |
| New Content | Competitor publishes new content | Info |

### Competitors to Monitor

| Competitor | Domain | Monitor Keywords | Alert Priority |
|------------|--------|------------------|----------------|
| [Competitor 1] | [domain] | [X] keywords | High |
| [Competitor 2] | [domain] | [X] keywords | Medium |
| [Competitor 3] | [domain] | [X] keywords | Low |

---

## GEO (AI Visibility) Alerts

### AI Citation Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Citation Lost | Lost AI Overview citation | Medium |
| Citation Won | New AI Overview citation | Positive |
| Citation Position Drop | Dropped from 1st to 3rd+ source | Medium |
| New AI Overview | AI Overview appears for tracked keyword | Info |

### GEO Trend Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Citation Rate Drop | AI citation rate drops 20%+ | High |
| GEO Competitor | Competitor cited where you're not | Medium |

---

## Brand Monitoring Alerts

### Mention Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Brand Mention | New brand mention online | Info |
| Negative Mention | Negative sentiment mention | High |
| Review Alert | New review on key platforms | Medium |
| Unlinked Mention | Brand mention without link | Opportunity |

### Reputation Alerts

| Alert Name | Condition | Priority |
|------------|-----------|----------|
| Review Rating Drop | Average rating drops | High |
| Negative Press | Negative news article | High |
| Competitor Comparison | Named in competitor comparison | Medium |

---

## Alert Response Plans

### Critical Alert Response

**Response Time**: Immediate (within 1 hour)

| Alert Type | Immediate Actions |
|------------|-------------------|
| Site Down | 1. Check server status 2. Contact hosting 3. Check DNS |
| Traffic Crash | 1. Check for algorithm update 2. Review GSC errors 3. Check competitors |
| Manual Action | 1. Review GSC message 2. Identify issue 3. Begin remediation |
| Critical Rank Drop | 1. Check if page indexed 2. Review SERP 3. Analyze competitors |

### High Priority Response

**Response Time**: Same day

| Alert Type | Actions |
|------------|---------|
| Major Rank Drops | Analyze cause, create recovery plan |
| Traffic Decline | Investigate source, check technical issues |
| Backlink Loss | Attempt recovery outreach |
| CWV Failure | Diagnose and fix performance issues |

### Medium Priority Response

**Response Time**: Within 48 hours

| Alert Type | Actions |
|------------|---------|
| Moderate Rank Changes | Monitor trend, plan content updates |
| Competitor Movement | Analyze competitor changes |
| New 404s | Set up redirects, update internal links |

### Low Priority

**Response Time**: Weekly review

| Alert Type | Actions |
|------------|---------|
| Positive Changes | Document wins, understand cause |
| Info Alerts | Log for trend analysis |

---

## Alert Notification Setup

### Notification Channels

| Priority | Channels | Frequency |
|----------|----------|-----------|
| Critical | Email + SMS + Slack | Immediate |
| High | Email + Slack | Immediate |
| Medium | Email + Slack | Daily digest |
| Low | Email | Weekly digest |

### Alert Recipients

| Role | Critical | High | Medium | Low |
|------|----------|------|--------|-----|
| SEO Manager | Yes | Yes | Yes | Yes |
| Dev Team | Yes | Yes (tech only) | No | No |
| Marketing Lead | Yes | Yes | No | No |
| Executive | Yes | No | No | No |

### Alert Suppression

- Suppress duplicate alerts for 24 hours
- Don't alert on known issues (maintenance windows)
- Batch low-priority alerts into digests

### Alert Escalation

| If No Response In | Escalate To |
|-------------------|-------------|
| 1 hour (Critical) | SEO Manager -> Director |
| 4 hours (High) | Team Lead -> Manager |
| 24 hours (Medium) | Team -> Lead |
