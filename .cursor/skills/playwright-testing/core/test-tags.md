# Test Tags

## Table of Contents

1. [Basic Tagging](#basic-tagging)
2. [Tagging Describe Blocks](#tagging-describe-blocks)
3. [Running Tagged Tests](#running-tagged-tests)
4. [Filtering by Tags](#filtering-by-tags)
5. [Configuration-Based Filtering](#configuration-based-filtering)
6. [Tag Organization Patterns](#tag-organization-patterns)
7. [Common Tag Categories](#common-tag-categories)
8. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
9. [Related References](#related-references)

## Basic Tagging

### Tag via Details Object

```typescript
import { test, expect } from "@playwright/test";

test(
  "test login page",
  {
    tag: "@fast",
  },
  async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading")).toBeVisible();
  }
);

test(
  "test dashboard",
  {
    tag: "@slow",
  },
  async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByTestId("charts")).toBeVisible();
  }
);
```

### Tag via Title (not recommended)

```typescript
test("test full report @slow", async ({ page }) => {
  await page.goto("/reports/full");
  await expect(page.getByText("Report loaded")).toBeVisible();
});

test("quick validation @fast @smoke", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
});
```

## Tagging Describe Blocks

### Tag All Tests in Group

```typescript
test.describe(
  "report tests",
  {
    tag: "@report",
  },
  () => {
    test("test report header", async ({ page }) => {
      // Inherits @report tag
    });

    test("test report footer", async ({ page }) => {
      // Inherits @report tag
    });
  }
);
```

### Combine Group and Test Tags

```typescript
test.describe(
  "admin features",
  {
    tag: "@admin",
  },
  () => {
    test("admin dashboard", async ({ page }) => {
      // Has @admin tag
    });

    test(
      "admin settings",
      {
        tag: ["@slow", "@critical"],
      },
      async ({ page }) => {
        // Has @admin, @slow, @critical tags
      }
    );
  }
);
```

## Running Tagged Tests

### Run Tests with Specific Tag

```bash
# Run all @fast tests
npx playwright test --grep @fast
```

### Exclude Tests with Tag

```bash
# Run all tests except @slow
npx playwright test --grep-invert @slow
```

## Filtering by Tags

### Logical OR (Either Tag)

```bash
# Run tests with @fast OR @smoke
npx playwright test --grep "@fast|@smoke"
```

### Logical AND (Both Tags)

```bash
# Run tests with both @fast AND @critical
npx playwright test --grep "(?=.*@fast)(?=.*@critical)"
```

### Complex Patterns

```bash
# Run @e2e tests that are also @critical
npx playwright test --grep "(?=.*@e2e)(?=.*@critical)"

# Run @api tests excluding @slow
npx playwright test --grep "@api" --grep-invert "@slow"
```

## Configuration-Based Filtering

### Filter in playwright.config.ts

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  grep: /@smoke/,
  grepInvert: /@flaky/,
});
```

### Project-Specific Tags

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  projects: [
    {
      name: "smoke",
      grep: /@smoke/,
    },
    {
      name: "regression",
      grepInvert: /@smoke/,
    },
    {
      name: "critical-only",
      grep: /@critical/,
    },
  ],
});
```

### Environment-Based Filtering

```typescript
import { defineConfig } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  grep: isCI ? /@smoke|@critical/ : undefined,
  grepInvert: isCI ? /@flaky/ : undefined,
});
```

## Tag Organization Patterns

### By Test Type

```typescript
// Smoke tests - quick validation
test("homepage loads", { tag: "@smoke" }, async ({ page }) => {});
test("login works", { tag: "@smoke" }, async ({ page }) => {});

// Regression tests - comprehensive
test("full checkout flow", { tag: "@regression" }, async ({ page }) => {});
test("all payment methods", { tag: "@regression" }, async ({ page }) => {});

// E2E tests - user journeys
test("complete user journey", { tag: "@e2e" }, async ({ page }) => {});
```

### By Priority

```typescript
test(
  "payment processing",
  {
    tag: ["@critical", "@p0"],
  },
  async ({ page }) => {}
);

test(
  "user preferences",
  {
    tag: ["@p1"],
  },
  async ({ page }) => {}
);

test(
  "theme customization",
  {
    tag: ["@p2"],
  },
  async ({ page }) => {}
);
```

### By Feature Area

```typescript
test.describe(
  "authentication",
  {
    tag: "@auth",
  },
  () => {
    test("login @smoke", async ({ page }) => {});
    test("logout", async ({ page }) => {});
    test("password reset @slow", async ({ page }) => {});
  }
);

test.describe(
  "payments",
  {
    tag: "@payments",
  },
  () => {
    test("credit card @critical", async ({ page }) => {});
    test("paypal @critical", async ({ page }) => {});
  }
);
```

## Common Tag Categories

| Category        | Tags                                          | Purpose                       |
| --------------- | --------------------------------------------- | ----------------------------- |
| **Speed**       | `@fast`, `@slow`                              | Execution time classification |
| **Priority**    | `@critical`, `@p0`, `@p1`, `@p2`              | Business importance           |
| **Type**        | `@smoke`, `@regression`, `@e2e`               | Test suite categorization     |
| **Feature**     | `@auth`, `@payments`, `@settings`             | Feature area grouping         |
| **Pipeline**    | `@pr`, `@nightly`, `@release`                 | CI/CD execution timing        |
| **Status**      | `@flaky`, `@wip`, `@quarantine`               | Test health tracking          |
| **Environment** | `@local`, `@staging`, `@prod`                 | Target environment            |
| **Team**        | `@team-frontend`, `@team-backend`, `@team-qa` | Team assignment               |

## Anti-Patterns to Avoid

| Anti-Pattern             | Problem                  | Solution                                       |
| ------------------------ | ------------------------ | ---------------------------------------------- |
| Too many tags per test   | Hard to maintain         | Limit to 2-3 relevant tags                     |
| Inconsistent naming      | Confusing filtering      | Establish naming conventions                   |
| Missing `@` prefix       | Tags won't match filters | Always prefix with `@`                         |
| Overlapping tag meanings | Ambiguous categorization | Define clear tag semantics                     |
| Not using tags           | Can't selectively run    | Tag by type, priority, or feature              |
| Tags in test title       | Hard to parse/filter     | Use the details object for tags, not the title |

## Related References

- **Test Organization**: See [test-suite-structure.md](test-suite-structure.md) for structuring tests
- **Annotations**: See [annotations.md](annotations.md) for skip, fixme, fail, slow
- **CI/CD Integration**: See [ci-cd.md](../infrastructure-ci-cd/ci-cd.md) for pipeline setup
