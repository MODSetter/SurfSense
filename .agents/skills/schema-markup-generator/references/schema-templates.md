# Schema.org JSON-LD Templates

Complete, copy-ready structured data templates for all major schema types. Customize the bracketed values to match your content.

## FAQPage Schema

For pages with frequently asked questions. Minimum 2 Q&A pairs required.

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "[Question text - exactly as shown on page]",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "[Complete answer text - must match visible content]"
      }
    },
    {
      "@type": "Question",
      "name": "[Question 2]",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "[Answer 2]"
      }
    },
    {
      "@type": "Question",
      "name": "[Question 3]",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "[Answer 3]"
      }
    }
  ]
}
```

**Requirements**: Questions must be complete questions, answers must be comprehensive, content must match visible page content.

---

## HowTo Schema

For step-by-step instructional content.

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "[How-to title - what will users learn]",
  "description": "[Brief description of what this tutorial teaches]",
  "image": {
    "@type": "ImageObject",
    "url": "[Main image URL]",
    "height": "[height in pixels]",
    "width": "[width in pixels]"
  },
  "totalTime": "PT[X]H[Y]M",
  "estimatedCost": {
    "@type": "MonetaryAmount",
    "currency": "USD",
    "value": "[estimated cost or 0]"
  },
  "supply": [
    {
      "@type": "HowToSupply",
      "name": "[Supply item 1]"
    },
    {
      "@type": "HowToSupply",
      "name": "[Supply item 2]"
    }
  ],
  "tool": [
    {
      "@type": "HowToTool",
      "name": "[Tool 1]"
    },
    {
      "@type": "HowToTool",
      "name": "[Tool 2]"
    }
  ],
  "step": [
    {
      "@type": "HowToStep",
      "position": 1,
      "name": "[Step 1 title]",
      "text": "[Step 1 detailed instructions]",
      "url": "[Page URL]#step1",
      "image": "[Step 1 image URL - optional]"
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "name": "[Step 2 title]",
      "text": "[Step 2 detailed instructions]",
      "url": "[Page URL]#step2",
      "image": "[Step 2 image URL - optional]"
    },
    {
      "@type": "HowToStep",
      "position": 3,
      "name": "[Step 3 title]",
      "text": "[Step 3 detailed instructions]",
      "url": "[Page URL]#step3",
      "image": "[Step 3 image URL - optional]"
    }
  ]
}
```

**Time format**: PT[X]H[Y]M where X = hours, Y = minutes. Example: PT1H30M = 1 hour 30 minutes.

---

## Article / BlogPosting / NewsArticle Schema

For blog posts, articles, and news content.

```json
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "[Article title - max 110 characters for best display]",
  "description": "[Article summary or excerpt]",
  "image": [
    "[Featured image URL - 1200px wide recommended]",
    "[Alternative image URL - 4:3 ratio]",
    "[Alternative image URL - 16:9 ratio]"
  ],
  "datePublished": "[ISO 8601 date: 2024-01-15T08:00:00+00:00]",
  "dateModified": "[ISO 8601 date - same as published if never modified]",
  "author": {
    "@type": "Person",
    "name": "[Author Full Name]",
    "url": "[Author profile URL]",
    "jobTitle": "[Author job title - optional]"
  },
  "publisher": {
    "@type": "Organization",
    "name": "[Publisher/Company Name]",
    "logo": {
      "@type": "ImageObject",
      "url": "[Publisher logo URL - max 600px wide, 60px high]",
      "width": "[width]",
      "height": "[height]"
    }
  },
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "[Canonical URL of this article]"
  },
  "articleBody": "[Full article text - optional but recommended]",
  "wordCount": "[word count - optional]"
}
```

**Type variants**: Use `Article` for general articles, `BlogPosting` for blog posts, `NewsArticle` for news content, `TechArticle` for technical documentation.

---

## Product Schema

For e-commerce product pages.

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "[Product Name]",
  "image": [
    "[Product image URL 1]",
    "[Product image URL 2]",
    "[Product image URL 3]"
  ],
  "description": "[Product description]",
  "sku": "[SKU code]",
  "mpn": "[Manufacturer Part Number - optional]",
  "brand": {
    "@type": "Brand",
    "name": "[Brand Name]"
  },
  "offers": {
    "@type": "Offer",
    "url": "[Product page URL]",
    "priceCurrency": "USD",
    "price": "[Price as number: 29.99]",
    "priceValidUntil": "[Date price is valid until: 2024-12-31]",
    "availability": "https://schema.org/InStock",
    "seller": {
      "@type": "Organization",
      "name": "[Seller/Store Name]"
    },
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {
        "@type": "MonetaryAmount",
        "value": "[shipping cost]",
        "currency": "USD"
      },
      "shippingDestination": {
        "@type": "DefinedRegion",
        "addressCountry": "US"
      }
    }
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "[4.5]",
    "reviewCount": "[89]",
    "bestRating": "5",
    "worstRating": "1"
  },
  "review": [
    {
      "@type": "Review",
      "reviewRating": {
        "@type": "Rating",
        "ratingValue": "[5]",
        "bestRating": "5"
      },
      "author": {
        "@type": "Person",
        "name": "[Reviewer Name]"
      },
      "reviewBody": "[Review text]",
      "datePublished": "[Review date: 2024-01-15]"
    }
  ]
}
```

**Availability options**: `InStock`, `OutOfStock`, `PreOrder`, `Discontinued`, `LimitedAvailability`, `OnlineOnly`, `InStoreOnly`, `SoldOut`

---

## LocalBusiness Schema

For local business pages with physical locations.

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "[Business Name]",
  "image": "[Business image or logo URL]",
  "@id": "[Business page URL]",
  "url": "[Website URL]",
  "telephone": "[Phone number: +1-555-555-5555]",
  "priceRange": "[$$$ or price range like $10-$50]",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[Street address]",
    "addressLocality": "[City]",
    "addressRegion": "[State/Province]",
    "postalCode": "[ZIP/Postal code]",
    "addressCountry": "US"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "[latitude as number: 40.7128]",
    "longitude": "[longitude as number: -74.0060]"
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00",
      "closes": "17:00"
    },
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": "Saturday",
      "opens": "10:00",
      "closes": "15:00"
    }
  ],
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "[4.5]",
    "reviewCount": "[123]"
  },
  "servesCuisine": "[Cuisine type - for restaurants only]"
}
```

**Type variants**: Use more specific types when applicable: `Restaurant`, `Store`, `AutoRepair`, `HealthAndBeautyBusiness`, `LegalService`, etc.

---

## Organization Schema

For brand/company homepage.

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[Organization Name]",
  "url": "[Website URL]",
  "logo": "[Logo URL - recommended 112x112px or larger]",
  "description": "[Company description]",
  "sameAs": [
    "[Facebook URL]",
    "[Twitter URL]",
    "[LinkedIn URL]",
    "[Instagram URL]",
    "[YouTube URL]"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "[Phone number]",
    "contactType": "customer service",
    "email": "[Email address]",
    "availableLanguage": ["English", "Spanish"],
    "areaServed": "US"
  },
  "founder": {
    "@type": "Person",
    "name": "[Founder name - optional]"
  },
  "foundingDate": "[YYYY-MM-DD - optional]",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[Street address]",
    "addressLocality": "[City]",
    "addressRegion": "[State]",
    "postalCode": "[ZIP]",
    "addressCountry": "US"
  }
}
```

---

## BreadcrumbList Schema

For navigation breadcrumbs.

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "[Homepage URL]"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "[Category Name]",
      "item": "[Category URL]"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "[Subcategory Name]",
      "item": "[Subcategory URL]"
    },
    {
      "@type": "ListItem",
      "position": 4,
      "name": "[Current Page Name]",
      "item": "[Current Page URL]"
    }
  ]
}
```

**Important**: Position numbers must be sequential starting from 1. Last item should be the current page.

---

## VideoObject Schema

For video content.

```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "[Video title]",
  "description": "[Video description]",
  "thumbnailUrl": "[Video thumbnail URL - minimum 160x90px]",
  "uploadDate": "[ISO 8601 date: 2024-01-15T08:00:00+00:00]",
  "duration": "PT[X]M[Y]S",
  "contentUrl": "[Video file URL]",
  "embedUrl": "[Video embed URL]",
  "interactionStatistic": {
    "@type": "InteractionCounter",
    "interactionType": { "@type": "WatchAction" },
    "userInteractionCount": "[view count]"
  }
}
```

**Duration format**: PT[X]M[Y]S where X = minutes, Y = seconds. Example: PT5M30S = 5 minutes 30 seconds.

---

## Event Schema

For events, conferences, concerts, etc.

```json
{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "[Event Name]",
  "description": "[Event description]",
  "image": "[Event image URL]",
  "startDate": "[ISO 8601 date: 2024-06-15T19:00:00-05:00]",
  "endDate": "[ISO 8601 date: 2024-06-15T22:00:00-05:00]",
  "eventStatus": "https://schema.org/EventScheduled",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "location": {
    "@type": "Place",
    "name": "[Venue Name]",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "[Street address]",
      "addressLocality": "[City]",
      "addressRegion": "[State]",
      "postalCode": "[ZIP]",
      "addressCountry": "US"
    }
  },
  "offers": {
    "@type": "Offer",
    "url": "[Ticket purchase URL]",
    "price": "[ticket price]",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "validFrom": "[Sale start date]"
  },
  "organizer": {
    "@type": "Organization",
    "name": "[Organizer name]",
    "url": "[Organizer website]"
  }
}
```

**Event status options**: `EventScheduled`, `EventCancelled`, `EventPostponed`, `EventRescheduled`, `EventMovedOnline`

**Attendance mode**: `OfflineEventAttendanceMode`, `OnlineEventAttendanceMode`, `MixedEventAttendanceMode`

---

## Course Schema

For online courses and educational content.

```json
{
  "@context": "https://schema.org",
  "@type": "Course",
  "name": "[Course Name]",
  "description": "[Course description]",
  "provider": {
    "@type": "Organization",
    "name": "[Provider name]",
    "sameAs": "[Provider URL]"
  },
  "offers": {
    "@type": "Offer",
    "category": "Paid",
    "price": "[price]",
    "priceCurrency": "USD"
  },
  "hasCourseInstance": {
    "@type": "CourseInstance",
    "courseMode": "online",
    "courseWorkload": "PT[X]H",
    "instructor": {
      "@type": "Person",
      "name": "[Instructor name]"
    }
  }
}
```

---

## Recipe Schema

For cooking recipes.

```json
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "[Recipe name]",
  "image": "[Recipe image URL]",
  "author": {
    "@type": "Person",
    "name": "[Author name]"
  },
  "datePublished": "[ISO 8601 date]",
  "description": "[Recipe description]",
  "prepTime": "PT[X]M",
  "cookTime": "PT[X]M",
  "totalTime": "PT[X]M",
  "recipeYield": "[Servings: e.g., '4 servings']",
  "recipeCategory": "[Category: e.g., 'Dinner']",
  "recipeCuisine": "[Cuisine: e.g., 'Italian']",
  "keywords": "[comma, separated, keywords]",
  "nutrition": {
    "@type": "NutritionInformation",
    "calories": "[calories per serving]"
  },
  "recipeIngredient": [
    "[Ingredient 1 with quantity]",
    "[Ingredient 2 with quantity]",
    "[Ingredient 3 with quantity]"
  ],
  "recipeInstructions": [
    {
      "@type": "HowToStep",
      "text": "[Step 1 instructions]"
    },
    {
      "@type": "HowToStep",
      "text": "[Step 2 instructions]"
    }
  ],
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "[4.5]",
    "reviewCount": "[number of reviews]"
  }
}
```

---

## SoftwareApplication Schema

For software, apps, and tools.

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "[Software name]",
  "operatingSystem": "[Windows, macOS, iOS, Android, Web]",
  "applicationCategory": "BusinessApplication",
  "offers": {
    "@type": "Offer",
    "price": "[price or 0 for free]",
    "priceCurrency": "USD"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "[4.5]",
    "reviewCount": "[number of reviews]"
  },
  "screenshot": "[Screenshot URL - optional]",
  "softwareVersion": "[version number]",
  "fileSize": "[file size with units: e.g., '50MB']",
  "datePublished": "[Release date]",
  "downloadUrl": "[Download URL - optional]"
}
```

---

## Multiple Schema Types (Combined Array)

To include multiple schema types on one page, wrap them in an array:

```html
<script type="application/ld+json">
[
  {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "[Article title]",
    "author": {
      "@type": "Person",
      "name": "[Author]"
    }
  },
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "[Question]",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "[Answer]"
        }
      }
    ]
  },
  {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": "[URL]"
      }
    ]
  }
]
</script>
```

---

## Implementation Notes

- Always validate schema at https://validator.schema.org/ and https://search.google.com/test/rich-results
- Remove bracketed placeholders and replace with actual content
- Use absolute URLs, not relative paths
- Dates must be in ISO 8601 format
- Schema must match visible page content (Google policy requirement)
- No trailing commas in JSON (invalid syntax)
