# Schema Type Decision Tree

Guidelines for selecting the right schema types based on content, industry, and implementation priority.

---

## When to Use Which Schema

| Your Content | Primary Schema | Add If Applicable | Rich Result Eligibility |
|-------------|---------------|-------------------|----------------------|
| Blog post / article | Article | FAQ, HowTo, Speakable | Article carousel, FAQ rich result |
| Product page | Product | Review, Offer, AggregateRating | Product snippet with price/rating |
| Service page | Service | FAQ, LocalBusiness | Service snippet |
| How-to guide | HowTo | Article, FAQ | How-to rich result with steps |
| FAQ page | FAQPage | Article | FAQ accordion in SERP |
| Recipe | Recipe | Video, AggregateRating | Recipe carousel |
| Event | Event | Offer, Organization | Event snippet with date/location |
| Video | VideoObject | Article | Video carousel, key moments |
| Local business | LocalBusiness | Review, OpeningHoursSpecification | Local pack, knowledge panel |
| Person/author | Person | Organization | Knowledge panel |
| Organization | Organization | ContactPoint, Logo | Knowledge panel |
| Course | Course | Organization | Course rich result |
| Job posting | JobPosting | Organization | Google for Jobs listing |
| Breadcrumb | BreadcrumbList | (Always add alongside other schema) | Breadcrumb trail in SERP |
| Software/App | SoftwareApplication | Review, Offer | App snippet |

---

## Industry-Specific Schema Recommendations

| Industry | Essential Schema | High-Value Additions |
|----------|-----------------|---------------------|
| E-commerce | Product, BreadcrumbList, Organization | AggregateRating, FAQ, Review |
| SaaS | SoftwareApplication, FAQPage, Organization | HowTo, VideoObject, Review |
| Local Services | LocalBusiness, Service | FAQ, Review, Event |
| Publishing/Media | Article, Person, Organization | FAQ, Speakable, VideoObject |
| Education | Course, Organization | FAQ, HowTo, Event |
| Healthcare | MedicalWebPage, Organization | FAQ, Physician, MedicalClinic |
| Real Estate | RealEstateListing, Organization | LocalBusiness, FAQ |
| Restaurants | Restaurant, Menu | Review, Event, FAQ |

---

## Schema Implementation Priority

| Priority | Schema Types | Why |
|----------|-------------|-----|
| P0 -- Always | Organization, BreadcrumbList, WebSite (SearchAction) | Foundation for all sites |
| P1 -- Content | Article, FAQPage, HowTo | Direct rich result eligibility |
| P2 -- Commercial | Product, Review, AggregateRating, Offer | Revenue-impacting rich results |
| P3 -- Authority | Person, SameAs, Speakable | E-E-A-T signals, AI citation |
| P4 -- Specialized | Industry-specific types | Niche rich results |

---

## Schema Validation Quick Reference

| Issue | Impact | Fix |
|-------|--------|-----|
| Missing required property | Schema ignored by Google | Add all required fields (check schema.org) |
| Invalid date format | Warning, may lose rich result | Use ISO 8601: "2026-02-11" |
| Incorrect @type | Schema misinterpreted | Match @type exactly to schema.org |
| Self-referencing sameAs | Warning | sameAs should link to EXTERNAL profiles |
| Missing image for Article | Loses article rich result | Add image property with valid URL |
| Review without itemReviewed | Review not connected | Nest review inside Product/Service/etc. |
