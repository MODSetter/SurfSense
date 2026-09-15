# Meta Tag Code Templates

HTML code templates for Open Graph tags, Twitter cards, additional meta tags, and complete meta tag blocks.

---

## Open Graph Tags (Facebook, LinkedIn, etc.)

**Required OG Tags**:

```html
<!-- Primary Open Graph Tags -->
<meta property="og:type" content="[article/website/product]">
<meta property="og:url" content="[Full canonical URL]">
<meta property="og:title" content="[OG-optimized title - up to 60 chars]">
<meta property="og:description" content="[OG description - up to 200 chars]">
<meta property="og:image" content="[Image URL - 1200x630px recommended]">

<!-- Optional but Recommended -->
<meta property="og:site_name" content="[Website Name]">
<meta property="og:locale" content="en_US">
```

**OG Type Selection Guide**:

| Page Type | og:type |
|-----------|---------|
| Blog post | article |
| Homepage | website |
| Product | product |
| Video | video.other |
| Profile | profile |

**OG Title Considerations**:
- Can be different from title tag
- Optimize for social sharing context
- More conversational tone acceptable
- Up to 60 characters ideal

**OG Description Considerations**:
- Can be longer than meta description (up to 200 chars)
- Focus on shareability
- What would make someone click when shared?

**OG Image Requirements**:
- Recommended size: 1200x630 pixels
- Minimum size: 600x315 pixels
- Format: JPG or PNG
- Keep text to less than 20% of image
- Include branding subtly

---

## Twitter Card Tags

**Card Type Selection**:

| Card Type | Best For | Image Size |
|-----------|----------|------------|
| summary | Articles, blogs | 144x144 min |
| summary_large_image | Visual content | 300x157 min |
| player | Video/audio | 640x360 min |
| app | Mobile apps | 800x418 |

**Twitter Card Code**:

```html
<!-- Twitter Card Tags -->
<meta name="twitter:card" content="[summary_large_image/summary]">
<meta name="twitter:site" content="@[YourTwitterHandle]">
<meta name="twitter:creator" content="@[AuthorTwitterHandle]">
<meta name="twitter:title" content="[Title - 70 chars max]">
<meta name="twitter:description" content="[Description - 200 chars max]">
<meta name="twitter:image" content="[Image URL]">
<meta name="twitter:image:alt" content="[Image description for accessibility]">
```

**Twitter-Specific Considerations**:
- Shorter titles work better (under 70 chars)
- Include @mentions if relevant
- Hashtag-relevant terms can help discovery
- Test with Twitter Card Validator

---

## Additional Recommended Meta Tags

**Canonical URL** (Prevent duplicates):
```html
<link rel="canonical" href="[Preferred URL]">
```

**Robots Tag** (Indexing control):
```html
<meta name="robots" content="index, follow">
```

**Viewport** (Mobile optimization):
```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

**Author** (For articles):
```html
<meta name="author" content="[Author Name]">
```

**Language**:
```html
<html lang="en">
```

**Article-Specific** (For blog posts):
```html
<meta property="article:published_time" content="[ISO 8601 date]">
<meta property="article:modified_time" content="[ISO 8601 date]">
<meta property="article:author" content="[Author URL]">
<meta property="article:section" content="[Category]">
<meta property="article:tag" content="[Tag 1]">
```

---

## Complete Meta Tag Block Template

Copy and paste this complete meta tag block:

```html
<!-- Primary Meta Tags -->
<title>[Optimized Title]</title>
<meta name="title" content="[Optimized Title]">
<meta name="description" content="[Optimized Description]">
<link rel="canonical" href="[Canonical URL]">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="[type]">
<meta property="og:url" content="[URL]">
<meta property="og:title" content="[OG Title]">
<meta property="og:description" content="[OG Description]">
<meta property="og:image" content="[Image URL]">
<meta property="og:site_name" content="[Site Name]">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="[URL]">
<meta name="twitter:title" content="[Twitter Title]">
<meta name="twitter:description" content="[Twitter Description]">
<meta name="twitter:image" content="[Image URL]">

<!-- Additional -->
<meta name="robots" content="index, follow">
<meta name="author" content="[Author]">
```
