# SEO/GEO KPI Definitions

Complete glossary of SEO and GEO key performance indicators with calculation formulas, data sources, benchmark ranges by industry, and interpretation guidance.

---

## 1. Organic Search KPIs

### Organic Sessions

| Attribute | Detail |
|-----------|--------|
| **Definition** | Number of visits to your site originating from organic (unpaid) search engine results |
| **Formula** | Count of sessions where medium = "organic" |
| **Data Source** | ~~analytics (Google Analytics, Adobe Analytics, or equivalent) |
| **Good Range** | Growing month-over-month; 3-10% MoM growth is healthy |
| **Warning** | Decline >10% MoM without known seasonal cause |
| **Segmentation** | Always separate brand vs. non-brand organic sessions |

**Interpretation:**
- Growing organic sessions with stable conversion rate = SEO strategy is working.
- Growing sessions but declining conversions = traffic quality issue; check keyword targeting.
- Flat sessions despite new content = content not ranking or cannibalizing existing pages.

---

### Organic Click-Through Rate (CTR)

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of search impressions that result in a click to your site |
| **Formula** | (Organic Clicks / Organic Impressions) x 100 |
| **Data Source** | ~~search console |
| **Good Range** | >3% overall; varies significantly by position and query type |
| **Warning** | <1.5% overall or declining trend |
| **Segmentation** | By query type (brand vs. non-brand), by page, by position range |

**Benchmarks by Position:**

| Position | Expected CTR Range |
|----------|-------------------|
| #1 | 25-35% |
| #2 | 12-18% |
| #3 | 8-13% |
| #4-5 | 4-8% |
| #6-10 | 2-5% |
| #11-20 | 0.5-2% |

**Interpretation:**
- High impressions but low CTR = title tags and meta descriptions need optimization.
- CTR declining for stable positions = SERP features (AI Overview, PAA) stealing clicks.
- CTR higher than position benchmarks = strong brand recognition or compelling snippets.

---

### Average Position

| Attribute | Detail |
|-----------|--------|
| **Definition** | Mean ranking position across all tracked keywords or queries |
| **Formula** | Sum of all positions / count of keywords |
| **Data Source** | ~~search console (query-level), ~~SEO tool (keyword-level) |
| **Good Range** | <20 for tracked keywords; improving trend |
| **Warning** | >30 or rising (worsening) trend |
| **Segmentation** | By keyword group, by page, by intent type |

**Interpretation:**
- Average position is a directional indicator, not an absolute measure. A few very low-ranking keywords can drag the average down significantly.
- Always pair with keyword distribution (how many keywords in top 10, top 20, etc.) for a complete picture.

---

### Keyword Visibility Score

| Attribute | Detail |
|-----------|--------|
| **Definition** | Weighted score combining keyword positions and search volumes into a single index |
| **Formula** | Sum of (estimated CTR at position x monthly search volume) for each keyword |
| **Data Source** | ~~SEO tool |
| **Good Range** | Growing over time; absolute value depends on niche |
| **Warning** | Declining trend for 3+ consecutive weeks |
| **Segmentation** | By topic cluster, by competitor |

**Interpretation:**
- Visibility score accounts for both ranking position and keyword importance (volume).
- A single high-volume keyword moving from #1 to #5 can cause a larger visibility drop than 20 low-volume keywords dropping off page 1.

---

### Pages Indexed

| Attribute | Detail |
|-----------|--------|
| **Definition** | Number of your pages included in Google's search index |
| **Formula** | Count of valid indexed pages in Index Coverage report |
| **Data Source** | ~~search console (Index Coverage / Pages report) |
| **Good Range** | Indexed count close to total intended indexable pages; growing with new content |
| **Warning** | Indexed count dropping without intentional removal; large gap between submitted and indexed |
| **Segmentation** | By sitemap, by content type, by subdirectory |

**Interpretation:**
- Indexed < submitted = quality or technical issues preventing indexing.
- Sudden drop in indexed pages = possible noindex tag, robots.txt change, or manual action.
- Indexed > intended = duplicate content, parameter URLs, or faceted navigation issues.

---

### Organic Conversion Rate

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of organic sessions that complete a defined conversion goal |
| **Formula** | (Organic Conversions / Organic Sessions) x 100 |
| **Data Source** | ~~analytics |
| **Good Range** | >2% for lead generation; >1% for e-commerce (varies by industry) |
| **Warning** | <0.5% or declining while traffic grows |
| **Segmentation** | By landing page, by keyword intent, by device |

**Industry Benchmarks:**

| Industry | Typical Organic CVR |
|----------|-------------------|
| SaaS / Software | 2-5% |
| E-commerce | 1-3% |
| Finance | 3-6% |
| Healthcare | 2-4% |
| B2B Services | 2-5% |
| Media / Publishing | 0.5-2% (ad-supported) |
| Education | 2-5% |

---

### Non-Brand Organic Traffic Share

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of organic traffic coming from non-branded search queries |
| **Formula** | (Organic sessions - brand query sessions) / Organic sessions x 100 |
| **Data Source** | ~~search console + ~~analytics |
| **Good Range** | >50% of total organic; growing |
| **Warning** | <30% (over-reliance on brand awareness, not SEO) |
| **Segmentation** | Trend over time |

**Interpretation:**
- High non-brand share = SEO is driving new audience discovery.
- Low non-brand share = organic traffic is mostly people who already know your brand; SEO is underperforming for acquisition.

---

## 2. GEO / AI Visibility KPIs

### AI Citation Rate

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of monitored queries where your content is cited in AI-generated answers |
| **Formula** | (Queries where you are cited / Total monitored queries with AI answers) x 100 |
| **Data Source** | ~~AI monitor |
| **Good Range** | >20% of monitored queries |
| **Warning** | <5% or declining trend |
| **Segmentation** | By topic cluster, by content type |

---

### AI Citation Position

| Attribute | Detail |
|-----------|--------|
| **Definition** | Your average position among cited sources in AI-generated responses |
| **Formula** | Sum of citation positions / count of citations |
| **Data Source** | ~~AI monitor |
| **Good Range** | Top 3 sources on average |
| **Warning** | Not cited or consistently cited in position 5+ |
| **Segmentation** | By query, by topic |

---

### AI Answer Coverage

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of your target topics that appear in AI-generated answers |
| **Formula** | (Topics with AI answers / Total target topics) x 100 |
| **Data Source** | ~~AI monitor |
| **Good Range** | Growing over time as AI answers expand |
| **Warning** | Declining coverage may indicate content quality issues |
| **Segmentation** | By topic cluster |

---

### Brand Mention in AI Responses

| Attribute | Detail |
|-----------|--------|
| **Definition** | Number of times your brand is mentioned in AI-generated responses across monitored queries |
| **Formula** | Count of AI responses containing your brand name |
| **Data Source** | ~~AI monitor |
| **Good Range** | Growing; present in responses for your key topics |
| **Warning** | Zero mentions for topics where you are an authority |
| **Segmentation** | By query category |

---

## 3. Domain Authority KPIs

### Domain Rating / Domain Authority

| Attribute | Detail |
|-----------|--------|
| **Definition** | Proprietary metric estimating the overall strength of a domain's backlink profile (0-100 scale) |
| **Formula** | Varies by tool (logarithmic scale based on backlink quantity and quality) |
| **Data Source** | ~~SEO tool (Ahrefs DR, Moz DA, or equivalent) |
| **Good Range** | Growing; competitive with top-ranking sites in your niche |
| **Warning** | Declining or significantly below competitors |
| **Segmentation** | Compare against competitors |

**Benchmarks by Site Stage:**

| Site Stage | Typical DR/DA |
|-----------|--------------|
| Brand new (0-6 months) | 0-15 |
| Early growth (6-18 months) | 15-30 |
| Established (18-36 months) | 25-50 |
| Mature (3+ years) | 40-70+ |
| Industry leader | 70-90+ |

---

### Referring Domains

| Attribute | Detail |
|-----------|--------|
| **Definition** | Count of unique domains that link to your site |
| **Formula** | Count of distinct root domains with at least one dofollow or nofollow link |
| **Data Source** | ~~link database |
| **Good Range** | Growing MoM; higher than primary competitors |
| **Warning** | Net loss of referring domains for 2+ consecutive months |
| **Segmentation** | By authority tier (DR 0-20, 20-40, 40-60, 60+) |

---

### Backlink Growth Rate

| Attribute | Detail |
|-----------|--------|
| **Definition** | Net new backlinks acquired per month |
| **Formula** | New backlinks gained - backlinks lost in the period |
| **Data Source** | ~~link database |
| **Good Range** | Positive and steady; proportional to content output |
| **Warning** | Negative for 2+ months; sudden spikes (may indicate spam) |
| **Segmentation** | By link quality tier |

---

### Toxic Link Ratio

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of your backlinks classified as toxic or spammy |
| **Formula** | (Toxic backlinks / Total backlinks) x 100 |
| **Data Source** | ~~link database (toxic score/spam score) |
| **Good Range** | <5% |
| **Warning** | 5-10% (monitor and clean up) |
| **Critical** | >10% (immediate disavow action needed) |
| **Segmentation** | By toxic type (PBN, spam, irrelevant) |

---

## 4. Technical SEO KPIs

### Core Web Vitals

| Metric | Definition | Good | Needs Improvement | Poor |
|--------|-----------|------|-------------------|------|
| **LCP** (Largest Contentful Paint) | Time to render largest content element | <=2.5s | 2.5-4.0s | >4.0s |
| **CLS** (Cumulative Layout Shift) | Visual stability during page load | <=0.1 | 0.1-0.25 | >0.25 |
| **INP** (Interaction to Next Paint) | Responsiveness to user interactions | <=200ms | 200-500ms | >500ms |

**Data Source:** ~~search console (Core Web Vitals report), Chrome UX Report, PageSpeed Insights

---

### Crawl Budget Utilization

| Attribute | Detail |
|-----------|--------|
| **Definition** | How efficiently search engine crawlers are spending their crawl budget on your site |
| **Formula** | (Useful pages crawled / Total pages crawled) x 100 |
| **Data Source** | ~~search console (Crawl Stats), server logs |
| **Good Range** | >80% of crawled pages are indexable, valuable pages |
| **Warning** | High crawl of non-indexable or low-value pages |
| **Segmentation** | By content type, by HTTP status code |

---

### Index Coverage Rate

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of submitted pages that are successfully indexed |
| **Formula** | (Indexed pages / Submitted pages) x 100 |
| **Data Source** | ~~search console |
| **Good Range** | >90% for sites with curated sitemaps |
| **Warning** | <80% or declining |
| **Segmentation** | By sitemap, by exclusion reason |

---

## 5. Content Performance KPIs

### Content Efficiency Score

| Attribute | Detail |
|-----------|--------|
| **Definition** | Ratio of content investment to organic traffic generated |
| **Formula** | Organic sessions per content piece / cost per content piece |
| **Data Source** | ~~analytics + internal cost tracking |
| **Good Range** | Improving over time; varies by content type |
| **Warning** | Declining efficiency despite continued investment |
| **Segmentation** | By content type, by topic, by author |

---

### Content Decay Rate

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of existing content losing organic traffic over a defined period |
| **Formula** | (Pages with >20% traffic decline over 6 months / Total pages with traffic) x 100 |
| **Data Source** | ~~analytics |
| **Good Range** | <20% of pages decaying per 6-month period |
| **Warning** | >30% of pages decaying |
| **Segmentation** | By content age, by topic, by content type |

---

### Organic Revenue Per Session

| Attribute | Detail |
|-----------|--------|
| **Definition** | Average revenue generated per organic search session |
| **Formula** | Total organic revenue / Total organic sessions |
| **Data Source** | ~~analytics (e-commerce tracking or goal values) |
| **Good Range** | Stable or growing; varies hugely by industry |
| **Warning** | Declining while traffic grows (traffic quality deteriorating) |
| **Segmentation** | By landing page, by keyword intent, by device |

---

## 6. Competitive KPIs

### Share of Voice (SOV)

| Attribute | Detail |
|-----------|--------|
| **Definition** | Your visibility as a percentage of total visibility across tracked keywords |
| **Formula** | (Your visibility score / Sum of all tracked competitors' visibility scores) x 100 |
| **Data Source** | ~~SEO tool |
| **Good Range** | Growing; leading in your core topic areas |
| **Warning** | Declining for 3+ consecutive months |
| **Segmentation** | By topic cluster, by competitor |

---

### Competitive Keyword Overlap

| Attribute | Detail |
|-----------|--------|
| **Definition** | Percentage of your tracked keywords where a specific competitor also ranks in the top 20 |
| **Formula** | (Keywords where both rank in top 20 / Your total tracked keywords) x 100 |
| **Data Source** | ~~SEO tool |
| **Good Range** | Context-dependent; high overlap for direct competitors is expected |
| **Warning** | New competitor appearing with high overlap indicates emerging threat |
| **Segmentation** | By competitor, by keyword group |

---

## 7. ROI and Business Impact KPIs

### SEO ROI

| Attribute | Detail |
|-----------|--------|
| **Definition** | Return on investment from SEO activities |
| **Formula** | ((Organic Revenue - SEO Investment) / SEO Investment) x 100 |
| **Data Source** | ~~analytics + internal cost tracking |
| **Good Range** | >200% annually (SEO compounds over time) |
| **Warning** | <100% after 12+ months of investment |
| **Segmentation** | By content type, by campaign |

**Note:** SEO ROI should be measured over 12+ month horizons. Short-term ROI calculations are misleading because SEO benefits compound over time.

---

### Organic Traffic Value

| Attribute | Detail |
|-----------|--------|
| **Definition** | Estimated cost to acquire equivalent traffic through paid search |
| **Formula** | Sum of (monthly organic clicks per keyword x CPC for that keyword) |
| **Data Source** | ~~SEO tool (traffic value calculation) |
| **Good Range** | Growing; significantly higher than SEO investment |
| **Warning** | Declining traffic value despite stable traffic (keywords losing CPC value) |
| **Segmentation** | By keyword group, by page |

**Interpretation:**
- Organic traffic value represents how much you would need to spend on PPC to get the same traffic.
- Useful for communicating SEO value to stakeholders who understand paid media budgets.
- A site with $50K/month organic traffic value that spends $10K/month on SEO is getting a 5:1 return.

---

## SEO/GEO Metric Definitions and Benchmarks

### Organic Search Metrics

| Metric | Definition | Good Range | Warning | Source |
|--------|-----------|-----------|---------|--------|
| Organic sessions | Visits from organic search | Growing MoM | >10% decline | ~~analytics |
| Keyword visibility | % of target keywords in top 100 | >60% | <40% | ~~SEO tool |
| Average position | Mean position across tracked keywords | <20 | >30 | ~~search console |
| Organic CTR | Clicks / impressions from search | >3% | <1.5% | ~~search console |
| Pages indexed | Pages in Google index | Growing | Dropping | ~~search console |
| Organic conversion rate | Conversions / organic sessions | >2% | <0.5% | ~~analytics |
| Non-brand organic traffic | Organic traffic minus brand searches | >50% of total organic | <30% | ~~analytics |

### GEO/AI Visibility Metrics

| Metric | Definition | Good Range | Warning | Source |
|--------|-----------|-----------|---------|--------|
| AI citation rate | % of monitored queries citing your content | >20% | <5% | ~~AI monitor |
| AI citation position | Average position in AI response citations | Top 3 sources | Not cited | ~~AI monitor |
| AI answer coverage | % of your topics appearing in AI answers | Growing | Declining | ~~AI monitor |
| Brand mention in AI | Times your brand is mentioned in AI responses | Growing | Zero | ~~AI monitor |

### Domain Authority Metrics

| Metric | Definition | Good Range | Warning | Source |
|--------|-----------|-----------|---------|--------|
| Domain Rating/Authority | Overall domain strength | Growing | Declining | ~~SEO tool |
| Referring domains | Unique domains linking to you | Growing MoM | Loss >10% MoM | ~~link database |
| Backlink growth rate | Net new backlinks per month | Positive | Negative trend | ~~link database |
| Toxic link ratio | Toxic links / total links | <5% | >10% | ~~link database |

## Reporting Templates by Audience

### Executive Report (C-Suite / Leadership)

**Focus:** Business outcomes, ROI, competitive position
**Length:** 1 page + appendix
**Frequency:** Monthly or Quarterly

| Section | Content |
|---------|---------|
| Traffic & Revenue | Organic traffic trend + attributed revenue |
| Competitive Position | Visibility share vs. top 3 competitors |
| AI Visibility | AI citation trend and coverage |
| Key Wins | Top 3 achievements with business impact |
| Risks | Top 3 concerns with proposed mitigation |
| Investment Ask | Resources needed for next period |

### Marketing Team Report

**Focus:** Channel performance, content effectiveness, technical health
**Length:** 2-3 pages
**Frequency:** Monthly

| Section | Content |
|---------|---------|
| Keyword Performance | Rankings gained/lost, new keywords discovered |
| Content Performance | Top pages by traffic, engagement, conversions |
| Technical Health | Crawl errors, speed scores, indexation |
| Backlink Profile | New links, lost links, quality assessment |
| GEO Performance | AI citation changes, new citations |
| Action Items | P0-P3 prioritized task list |

### Technical SEO Report

**Focus:** Crawlability, indexation, speed, errors
**Length:** Detailed
**Frequency:** Weekly or Bi-weekly

| Section | Content |
|---------|---------|
| Crawl Stats | Pages crawled, errors, crawl budget usage |
| Index Coverage | Indexed/excluded/errored pages |
| Core Web Vitals | LCP, CLS, INP trends |
| Error Log | New 4xx/5xx errors with resolution status |
| Schema Validation | New warnings, rich result eligibility |
| Technical Debt | Outstanding issues by priority |

## Trend Analysis Framework

### Period-Over-Period Analysis

| Comparison | Best For | Limitation |
|-----------|---------|-----------|
| Week over week (WoW) | Detecting sudden changes | Noisy, affected by day-of-week patterns |
| Month over month (MoM) | Identifying trends | Seasonal bias |
| Year over year (YoY) | Accounting for seasonality | Does not reflect recent trajectory |
| Rolling 30-day average | Smoothing noise | Lags behind real changes |

### Trend Interpretation Guidelines

| Pattern | Likely Cause | Recommended Action |
|---------|-------------|-------------------|
| Steady growth | Strategy is working | Continue, optimize high performers |
| Sudden spike then drop | Viral content or algorithm volatility | Investigate cause, build on if repeatable |
| Gradual decline | Content decay, competition, technical debt | Comprehensive audit needed |
| Flat line | Plateau — existing strategy maxed out | New content areas, new link strategies |
| Seasonal pattern | Industry/demand cycles | Plan content calendar around peaks |

## SEO Attribution Guidance

### Attribution Challenges in SEO

| Challenge | Impact | Mitigation |
|----------|--------|-----------|
| Long conversion paths | SEO rarely gets last-touch credit | Use assisted conversions report |
| Brand vs. non-brand | Brand searches inflate organic metrics | Always separate brand/non-brand |
| Cross-device journeys | Mobile search to desktop conversion | Enable cross-device tracking |
| SEO + paid overlap | Cannibalization or lift? | Test turning off paid for branded terms |
| Content assists sales | Hard to attribute | Track content touches in CRM |

