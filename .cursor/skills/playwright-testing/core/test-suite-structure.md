# Test Suite Structure

## Table of Contents

1. [Configuration](#configuration)
2. [E2E Tests](#e2e-tests)
3. [Component Tests](#component-tests)
4. [API Tests](#api-tests)
5. [Visual Regression Tests](#visual-regression-tests)
6. [Directory Structure](#directory-structure)
7. [Tagging & Filtering](#tagging--filtering)

### Project Setup

```bash
npm init playwright@latest
```

## Configuration

### Essential Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html"], ["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
```

## E2E Tests

Full user journey tests through the browser.

### Structure

```typescript
// tests/e2e/checkout.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Checkout Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/products");
  });

  test("complete purchase as guest", async ({ page }) => {
    // Add to cart
    await page.getByRole("button", { name: "Add to Cart" }).first().click();
    await expect(page.getByTestId("cart-count")).toHaveText("1");

    // Go to checkout
    await page.getByRole("link", { name: "Cart" }).click();
    await page.getByRole("button", { name: "Checkout" }).click();

    // Fill shipping
    await page.getByLabel("Email").fill("guest@example.com");
    await page.getByLabel("Address").fill("123 Test St");
    await page.getByRole("button", { name: "Continue" }).click();

    // Payment
    await page.getByLabel("Card Number").fill("4242424242424242");
    await page.getByRole("button", { name: "Pay Now" }).click();

    // Confirmation
    await expect(page.getByRole("heading")).toHaveText("Order Confirmed");
  });

  test("apply discount code", async ({ page }) => {
    await page.getByRole("button", { name: "Add to Cart" }).first().click();
    await page.getByRole("link", { name: "Cart" }).click();

    await page.getByLabel("Discount Code").fill("SAVE10");
    await page.getByRole("button", { name: "Apply" }).click();

    await expect(page.getByText("10% discount applied")).toBeVisible();
  });
});
```

### Best Practices

- Test critical user journeys
- Keep tests independent
- Use realistic data
- Clean up test data in teardown

## Component Tests

Test individual components in isolation using Playwright Component Testing.

```bash
npm init playwright@latest -- --ct
```

For comprehensive component testing patterns including mounting, props, events, slots, mocking, and framework-specific examples (React, Vue, Svelte), see **[component-testing.md](../testing-patterns/component-testing.md)**.

## API Tests

Test backend APIs without browser.

### API Mocking Patterns

For E2E tests that need to mock API responses:

```typescript
// Mock single endpoint
test("displays mocked users", async ({ page }) => {
  await page.route("**/api/users", (route) =>
    route.fulfill({
      status: 200,
      json: [{ id: 1, name: "Test User" }],
    })
  );

  await page.goto("/users");
  await expect(page.getByText("Test User")).toBeVisible();
});

// Mock with different responses
test("handles API errors", async ({ page }) => {
  await page.route("**/api/users", (route) =>
    route.fulfill({
      status: 500,
      json: { error: "Server error" },
    })
  );

  await page.goto("/users");
  await expect(page.getByText("Server error")).toBeVisible();
});

// Conditional mocking
test("mocks based on request", async ({ page }) => {
  await page.route("**/api/users", (route, request) => {
    if (request.method() === "GET") {
      route.fulfill({ json: [{ id: 1, name: "User" }] });
    } else {
      route.continue();
    }
  });
});

// Mock with delay (simulate slow network)
test("handles slow API", async ({ page }) => {
  await page.route("**/api/data", (route) =>
    route.fulfill({
      json: { data: "test" },
      delay: 2000, // 2 second delay
    })
  );

  await page.goto("/dashboard");
  await expect(page.getByText("Loading...")).toBeVisible();
  await expect(page.getByText("test")).toBeVisible();
});
```

For advanced patterns (GraphQL mocking, HAR recording, request modification, network throttling), see **[network-advanced.md](../advanced/network-advanced.md)**.

## Visual Regression Tests

Compare screenshots to detect visual changes.

### Basic Visual Test

```typescript
// tests/visual/homepage.spec.ts
import { test, expect } from "@playwright/test";

test("homepage visual", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveScreenshot("homepage.png");
});

test("component visual", async ({ page }) => {
  await page.goto("/components");

  const button = page.getByRole("button", { name: "Primary" });
  await expect(button).toHaveScreenshot("primary-button.png");
});
```

### Visual Test Options

```typescript
test("dashboard visual", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page).toHaveScreenshot("dashboard.png", {
    fullPage: true, // Capture entire scrollable page
    maxDiffPixels: 100, // Allow up to 100 different pixels
    maxDiffPixelRatio: 0.01, // Or 1% difference
    threshold: 0.2, // Pixel comparison threshold
    animations: "disabled", // Disable animations
    mask: [page.getByTestId("date")], // Mask dynamic content
  });
});
```

### Handling Dynamic Content

```typescript
test("page with dynamic content", async ({ page }) => {
  await page.goto("/profile");

  // Mask elements that change
  await expect(page).toHaveScreenshot("profile.png", {
    mask: [
      page.getByTestId("timestamp"),
      page.getByTestId("avatar"),
      page.getByRole("img"),
    ],
  });
});

// Or hide elements via CSS
test("page hiding dynamic elements", async ({ page }) => {
  await page.goto("/profile");

  await page.addStyleTag({
    content: `
      .dynamic-content { visibility: hidden !important; }
      [data-testid="ad-banner"] { display: none !important; }
    `,
  });

  await expect(page).toHaveScreenshot("profile-stable.png");
});
```

### Visual Test Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      maxDiffPixels: 50,
      animations: "disabled",
    },
  },
  projects: [
    {
      name: "visual-chrome",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
      testMatch: /.*visual.*\.spec\.ts/,
    },
  ],
});
```

### Update Snapshots

```bash
# Update all snapshots
npx playwright test --update-snapshots

# Update specific test
npx playwright test homepage.spec.ts --update-snapshots
```

## Directory Structure

```
tests/
├── e2e/                    # End-to-end tests
│   ├── auth.spec.ts
│   ├── checkout.spec.ts
│   └── dashboard.spec.ts
├── component/              # Component tests
│   ├── Button.spec.tsx
│   └── Modal.spec.tsx
├── api/                    # API tests
│   ├── users.spec.ts
│   └── products.spec.ts
├── visual/                 # Visual regression tests
│   └── homepage.spec.ts
├── fixtures/               # Custom fixtures
│   ├── auth.fixture.ts
│   └── api.fixture.ts
└── pages/                  # Page objects
    ├── login.page.ts
    └── dashboard.page.ts
```

## Anti-Patterns to Avoid

| Anti-Pattern                          | Problem                            | Solution                  |
| ------------------------------------- | ---------------------------------- | ------------------------- |
| Long test files                       | Hard to maintain, slow to navigate | Split by feature, use POM |
| Tests depend on execution order       | Flaky, hard to debug               | Keep tests independent    |
| Testing multiple features in one test | Hard to debug failures             | One feature per test      |

## Related References

- **Component Testing**: See [component-testing.md](../testing-patterns/component-testing.md) for comprehensive CT patterns
- **Projects**: See [projects-dependencies.md](projects-dependencies.md) for project-based filtering
- **Page Objects**: See [page-object-model.md](page-object-model.md) for organizing page interactions
- **Test Data**: See [fixtures-hooks.md](fixtures-hooks.md) for managing test data

## Tagging & Filtering

### Using Tags

```typescript
test("user login @smoke @auth", async ({ page }) => {
  // ...
});

test("checkout flow @e2e @critical", async ({ page }) => {
  // ...
});

test.describe("API tests @api", () => {
  test("create user", async ({ request }) => {
    // ...
  });
});
```

### Running Tagged Tests

```bash
# Run smoke tests
npx playwright test --grep @smoke

# Run all except slow tests
npx playwright test --grep-invert @slow

# Combine tags
npx playwright test --grep "@smoke|@critical"
```

For project-based filtering and advanced project configuration, see **[projects-dependencies.md](projects-dependencies.md)**.
