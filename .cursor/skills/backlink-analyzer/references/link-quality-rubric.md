# Link Quality Rubric

Comprehensive reference for evaluating backlink quality. Use this rubric to assess individual links, audit entire link profiles, perform competitive link gap analysis, and prepare disavow files.

---

## 1. Individual Link Quality Evaluation

### Scoring Methodology

Evaluate each link across six factors. Multiply score (1-5) by factor weight to produce a weighted score. Sum all weighted scores for a final Link Quality Score (LQS).

**Rating Scale:**
- **LQS 4.0-5.0**: Premium link — high authority, topically relevant, editorial placement
- **LQS 2.5-3.9**: Acceptable link — provides value, typical of healthy profiles
- **LQS 1.0-2.4**: Low quality — minimal value, review for potential risk

### Factor 1: Domain Authority (25% weight)

| Score | DR / DA Range | Characteristics | Examples |
|-------|-------------|-----------------|---------|
| 5 | DR 70+ | Major publication, established authority | NYTimes, Forbes, BBC, major university sites |
| 4 | DR 50-69 | Strong domain, recognized in industry | Industry publications, large blogs, government sites |
| 3 | DR 30-49 | Moderate authority, established site | Mid-tier blogs, regional publications, niche authorities |
| 2 | DR 15-29 | Low authority, newer or smaller site | Small blogs, newer companies, personal sites |
| 1 | DR <15 | Very low authority | New sites, abandoned sites, thin content sites |

**Notes:**
- DR/DA is a proxy, not the sole indicator. A DR 30 site that is highly relevant to your niche may be more valuable than a DR 70 site in an unrelated field.
- Check if the domain's authority is organic (earned over time) or inflated (bought links, PBN).

### Factor 2: Topical Relevance (25% weight)

| Score | Relevance Level | Description |
|-------|----------------|-------------|
| 5 | Exact match | Same niche, same subtopic. A link from a CRM review site to your CRM product. |
| 4 | Closely related | Same industry, adjacent topic. A marketing blog linking to your email tool. |
| 3 | Broadly related | Same general field. A business blog linking to your SaaS product. |
| 2 | Tangentially related | Loose connection. A general news site mentioning your product in a tech roundup. |
| 1 | Unrelated | No topical connection. A cooking blog linking to your B2B software. |

**How to assess relevance:**
1. Read the linking page content. Is it about your topic?
2. Check the linking site's overall focus. Is it in your industry?
3. Look at the surrounding content. Does the link make editorial sense?
4. Check the site's other outbound links. Are they topically coherent?

### Factor 3: Traffic to Linking Page (15% weight)

| Score | Estimated Monthly Traffic | Characteristics |
|-------|--------------------------|-----------------|
| 5 | 10,000+ visits/month | High-traffic page, likely drives referral traffic |
| 4 | 1,000-9,999 visits/month | Solid traffic, some referral value |
| 3 | 100-999 visits/month | Moderate traffic, primarily SEO value |
| 2 | 10-99 visits/month | Low traffic, SEO value only |
| 1 | <10 visits/month | No meaningful traffic, minimal value |

**Why traffic matters:**
- Links from pages with real traffic are more likely to be genuine editorial placements.
- Google likely weights links from pages that receive traffic more highly.
- Referral traffic from the link provides direct business value beyond SEO.

### Factor 4: Link Position (15% weight)

| Score | Position | Description |
|-------|----------|-------------|
| 5 | In-content, editorial | Naturally placed within the article body as a citation or resource |
| 4 | In-content, contextual | Within the body text but in a "resources" or "further reading" section |
| 3 | Author bio or about section | Part of a contributor's bio or about page |
| 2 | Sidebar or dedicated links section | Widget, blogroll, or sidebar placement |
| 1 | Footer, sitewide, or hidden | Footer link, sitewide template link, or visually obscured |

**Key principle:** Editorial in-content links carry the most weight because they represent a genuine endorsement. Footer and sitewide links are devalued by search engines.

### Factor 5: Anchor Text (10% weight)

| Score | Anchor Type | Example (for a CRM product) |
|-------|------------|----------------------------|
| 5 | Descriptive, natural | "this customer relationship management platform" |
| 4 | Partial match, natural | "CRM tools for small businesses" |
| 3 | Brand name | "Acme CRM" |
| 2 | Naked URL | "https://acmecrm.com" |
| 1 | Generic | "click here", "read more", "this website" |

**Important nuance:** A natural link profile has a MIX of all anchor types. Too many exact-match anchors (score 5) can signal manipulation. The ideal distribution is:
- Brand anchors: 30-40%
- Naked URLs: 15-25%
- Generic anchors: 10-20%
- Descriptive/partial match: 15-25%
- Exact match: 5-15%

### Factor 6: Follow Status (10% weight)

| Score | Status | Description |
|-------|--------|-------------|
| 5 | Dofollow, editorial | Standard followed link from editorial content |
| 4 | Dofollow, non-editorial | Followed link from directory, profile, or user-generated content |
| 3 | Sponsored (rel="sponsored") | Properly disclosed sponsored/paid link |
| 2 | UGC (rel="ugc") | User-generated content link (forums, comments) |
| 1 | Nofollow (rel="nofollow") | Explicitly nofollowed link |

**Notes:**
- Google treats nofollow as a "hint" rather than a directive since 2019.
- Nofollow links from high-authority sites (e.g., Wikipedia) still provide brand value and referral traffic.
- A healthy profile naturally includes a mix of followed and nofollowed links. Typical ratio: 60-80% dofollow, 20-40% nofollow.

---

## 2. Example Link Profile Assessments

### Example A: Strong Link Profile

| Characteristic | Value | Assessment |
|---------------|-------|-----------|
| Total referring domains | 1,200 | Healthy for a mid-size SaaS company |
| Dofollow ratio | 72% | Natural distribution |
| Average linking domain DR | 38 | Solid average authority |
| Top anchor: brand name | 35% | Natural brand dominance |
| Exact match anchors | 8% | Within safe range |
| Topical relevance (sampled) | 75% related | Strong relevance signal |
| Link velocity | +25/month net | Steady organic growth |
| Toxic link estimate | 3% | Below 5% threshold — healthy |

**Verdict:** Healthy profile with natural link distribution. Continue current strategy.

### Example B: At-Risk Link Profile

| Characteristic | Value | Assessment |
|---------------|-------|-----------|
| Total referring domains | 800 | Adequate but thin for competitive niche |
| Dofollow ratio | 92% | Suspiciously high — may indicate link manipulation |
| Average linking domain DR | 18 | Low average authority |
| Top anchor: exact match keyword | 42% | Over-optimized — risk of penalty |
| Exact match anchors | 42% | Far above safe threshold (>15%) |
| Topical relevance (sampled) | 30% related | Many irrelevant links |
| Link velocity | +80/month net | Unnaturally high — investigate |
| Toxic link estimate | 18% | Above 10% threshold — action needed |

**Verdict:** Profile shows signs of manipulation. Immediate actions needed: disavow toxic links, diversify anchor text, slow down link acquisition pace.

### Example C: New Site Link Profile

| Characteristic | Value | Assessment |
|---------------|-------|-----------|
| Total referring domains | 45 | Expected for a 6-month-old site |
| Dofollow ratio | 65% | Natural |
| Average linking domain DR | 28 | Reasonable for early-stage outreach |
| Top anchor: brand name | 40% | Healthy |
| Exact match anchors | 5% | Conservative and safe |
| Topical relevance (sampled) | 80% related | Well-targeted outreach |
| Link velocity | +8/month net | Appropriate for new site |
| Toxic link estimate | 1% | Clean profile |

**Verdict:** Healthy foundation. Focus on scaling link acquisition while maintaining quality standards.

---

## 3. Competitive Link Gap Analysis Methodology

### Step-by-Step Process

**Step 1: Identify competitors**
Select 3-5 direct competitors who rank for your target keywords.

**Step 2: Pull referring domain data**
Export the full referring domain list for each competitor from ~~link database.

**Step 3: Create intersection matrix**

| Referring Domain | You | Comp 1 | Comp 2 | Comp 3 | Overlap Count |
|-----------------|-----|--------|--------|--------|---------------|
| example-a.com | No | Yes | Yes | Yes | 3 |
| example-b.com | No | Yes | Yes | No | 2 |
| example-c.com | No | Yes | No | No | 1 |
| example-d.com | Yes | Yes | Yes | Yes | 3 (already have) |

**Step 4: Prioritize opportunities**

| Priority | Criteria | Rationale |
|----------|---------|-----------|
| Highest | Links to 3+ competitors, DR 50+, relevant | If all competitors have it, it is likely linkable |
| High | Links to 2+ competitors, DR 30+, relevant | Strong signal of willingness to link in niche |
| Medium | Links to 1 competitor, DR 50+, relevant | May be less accessible but high value |
| Lower | Links to 1 competitor, DR <30, or low relevance | Diminishing returns |

**Step 5: Analyze link context**
For each high-priority opportunity, visit the actual linking page to understand:
- Why did they link to your competitor? (resource page, mention, guest post, etc.)
- What content on your site could replace or complement that link?
- What outreach angle would work? (broken link, better resource, relationship)

**Step 6: Create outreach plan**
Build a prioritized list with contact information, outreach angle, and template selection.

---

## 4. Disavow File Format Guide

### When to Disavow

Only disavow links when you have clear evidence of risk. Unnecessary disavow can hurt your rankings.

| Situation | Disavow? | Reasoning |
|-----------|----------|-----------|
| Obvious PBN links | Yes | Clear manipulation signal |
| Paid links you cannot get removed | Yes | After attempting removal |
| Spam attack (negative SEO) | Yes | Protect from third-party manipulation |
| Low-quality directory links | Maybe | Only if pattern is excessive |
| Foreign language spam | Yes | If clearly unnatural |
| Low-DA sites with real content | No | Low quality is not toxic |
| Nofollow links from any source | No | Already nofollowed; no risk |

### Disavow File Format

The disavow file is a plain text file (.txt) uploaded to Google Search Console.

```
# Disavow file for example.com
# Generated: [date]
# Reason: Toxic link cleanup

# Individual URLs to disavow
https://spam-site.com/page-with-link
https://another-spam.com/toxic-page

# Entire domains to disavow (use for sites with multiple toxic links)
domain:link-farm-example.com
domain:pbn-network-site.com
domain:spam-directory.net
```

### Disavow File Best Practices

| Practice | Why |
|----------|-----|
| Comment every entry or group | Future auditors need to understand why |
| Use `domain:` for sites with multiple bad links | More thorough than individual URLs |
| Use individual URLs when only one page is toxic | Avoid disavowing good links from the same domain |
| Keep a changelog | Track what was added and when |
| Review quarterly | Remove entries if domains have been cleaned up |
| Never disavow your own domain | Common mistake that causes severe damage |
| Back up before uploading | Keep previous version in case of errors |

### Disavow Review Workflow

| Step | Action | Tool |
|------|--------|------|
| 1 | Export full backlink profile | ~~link database |
| 2 | Filter for known toxic patterns | Spam score, DR <10, foreign spam |
| 3 | Manual review of flagged links | Visit each flagged domain |
| 4 | Attempt removal via email first | Contact webmasters |
| 5 | Wait 2 weeks for removal responses | Track outreach results |
| 6 | Add non-removed toxic links to disavow | Format as .txt file |
| 7 | Upload to Google Search Console | Disavow Links tool |
| 8 | Document all actions and dates | Internal records |
| 9 | Re-check in 4-6 weeks | Verify processing |

---

## 5. Link Profile Health Benchmarks

### Healthy Profile Indicators

| Metric | Healthy Range | Warning Sign | Critical |
|--------|-------------|--------------|----------|
| Dofollow ratio | 60-80% | >90% | >95% |
| Exact match anchor % | <15% | 15-25% | >25% |
| Brand anchor % | 25-45% | <15% | <5% |
| Toxic link % | <5% | 5-10% | >10% |
| Referring domain growth | Positive, steady | Flat | Declining |
| Average linking DR | 25+ | 15-25 | <15 |
| Link diversity (unique domains / total links) | >0.3 | 0.1-0.3 | <0.1 |
| Topical relevance (sampled) | >60% | 40-60% | <40% |

### Industry-Specific Benchmarks

Authority expectations vary significantly by industry vertical.

| Industry | Typical DR Range (Top 10 Sites) | Typical Referring Domains | Link Difficulty |
|----------|-------------------------------|--------------------------|----------------|
| Finance / Insurance | DR 60-90 | 5,000-50,000+ | Very High |
| Health / Medical | DR 50-85 | 3,000-30,000+ | Very High |
| Technology / SaaS | DR 40-80 | 1,000-20,000+ | High |
| E-commerce (general) | DR 35-75 | 500-15,000+ | High |
| Legal | DR 40-70 | 1,000-10,000+ | High |
| Education | DR 50-90 | 2,000-25,000+ | Medium-High |
| Local services | DR 15-45 | 50-500 | Medium |
| B2B niche | DR 25-60 | 200-5,000+ | Medium |
| Blog / Content site | DR 20-70 | 100-10,000+ | Medium |
| New startup | DR 5-25 | 10-200 | Starting point |

_Note: These are general ranges. Actual requirements depend on your specific keyword competition._
