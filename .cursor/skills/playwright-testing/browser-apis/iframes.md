# iFrame Testing

## Table of Contents

1. [Basic iFrame Access](#basic-iframe-access)
2. [Cross-Origin iFrames](#cross-origin-iframes)
3. [Nested iFrames](#nested-iframes)
4. [Dynamic iFrames](#dynamic-iframes)
5. [iFrame Navigation](#iframe-navigation)
6. [Common Patterns](#common-patterns)

## Basic iFrame Access

### Using frameLocator

```typescript
// Access iframe by selector
const frame = page.frameLocator("iframe#payment");
await frame.getByRole("button", { name: "Pay" }).click();

// Access by name attribute
const namedFrame = page.frameLocator('iframe[name="checkout"]');
await namedFrame.getByLabel("Card number").fill("4242424242424242");

// Access by title
const titledFrame = page.frameLocator('iframe[title="Payment Form"]');

// Access by src (partial match)
const srcFrame = page.frameLocator('iframe[src*="stripe.com"]');
```

### Frame vs FrameLocator

```typescript
// frameLocator - for locator-based operations (recommended)
const frameLocator = page.frameLocator("#my-iframe");
await frameLocator.getByRole("button").click();

// frame() - for Frame object operations (navigation, evaluation)
const frame = page.frame({ name: "my-frame" });
if (frame) {
  await frame.goto("https://example.com");
  const title = await frame.title();
}

// Get all frames
const frames = page.frames();
for (const f of frames) {
  console.log("Frame URL:", f.url());
}
```

### Waiting for iFrame Content

```typescript
// Wait for iframe to load
const frame = page.frameLocator("#dynamic-iframe");

// Wait for element inside iframe
await expect(frame.getByRole("heading")).toBeVisible({ timeout: 10000 });

// Wait for iframe src to change
await page.waitForFunction(() => {
  const iframe = document.querySelector("iframe#my-frame") as HTMLIFrameElement;
  return iframe?.src.includes("loaded");
});
```

## Cross-Origin iFrames

### Accessing Cross-Origin Content

```typescript
// Cross-origin iframes work seamlessly with frameLocator
const thirdPartyFrame = page.frameLocator('iframe[src*="third-party.com"]');

// Interact with elements inside cross-origin iframe
await thirdPartyFrame.getByRole("textbox").fill("test@example.com");
await thirdPartyFrame.getByRole("button", { name: "Submit" }).click();

// Wait for cross-origin iframe to be ready
await expect(thirdPartyFrame.locator("body")).toBeVisible();
```

### Payment Provider iFrames (Stripe, PayPal)

```typescript
test("Stripe payment iframe", async ({ page }) => {
  await page.goto("/checkout");

  // Stripe uses multiple iframes for each field
  const cardFrame = page
    .frameLocator('iframe[name*="__privateStripeFrame"]')
    .first();

  // Wait for Stripe to initialize
  await expect(cardFrame.locator('[placeholder="Card number"]')).toBeVisible({
    timeout: 15000,
  });

  // Fill card details
  await cardFrame
    .locator('[placeholder="Card number"]')
    .fill("4242424242424242");
  await cardFrame.locator('[placeholder="MM / YY"]').fill("12/30");
  await cardFrame.locator('[placeholder="CVC"]').fill("123");
});
```

### Handling OAuth in iFrames

```typescript
test("OAuth iframe flow", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in with Google" }).click();

  // If OAuth opens in iframe instead of popup
  const oauthFrame = page.frameLocator('iframe[src*="accounts.google.com"]');

  // Wait for OAuth form
  await expect(oauthFrame.getByLabel("Email")).toBeVisible({ timeout: 10000 });
  await oauthFrame.getByLabel("Email").fill("test@gmail.com");
});
```

## Nested iFrames

### Accessing Nested Frames

```typescript
// Parent iframe contains child iframe
const parentFrame = page.frameLocator("#outer-frame");
const childFrame = parentFrame.frameLocator("#inner-frame");

// Interact with deeply nested content
await childFrame.getByRole("button", { name: "Submit" }).click();

// Multiple levels of nesting
const level1 = page.frameLocator("#level1");
const level2 = level1.frameLocator("#level2");
const level3 = level2.frameLocator("#level3");
await level3.getByText("Deep content").click();
```

### Finding Elements Across Frame Hierarchy

```typescript
// Helper to search all frames for an element
async function findInAnyFrame(
  page: Page,
  selector: string,
): Promise<Locator | null> {
  // Check main page first
  const mainCount = await page.locator(selector).count();
  if (mainCount > 0) return page.locator(selector);

  // Check all frames
  for (const frame of page.frames()) {
    const count = await frame.locator(selector).count();
    if (count > 0) {
      return frame.locator(selector);
    }
  }
  return null;
}

test("find element in any frame", async ({ page }) => {
  await page.goto("/complex-page");
  const element = await findInAnyFrame(page, '[data-testid="submit-btn"]');
  if (element) await element.click();
});
```

## Dynamic iFrames

### iFrames Created at Runtime

```typescript
test("handle dynamically created iframe", async ({ page }) => {
  await page.goto("/dashboard");

  // Click button that creates iframe
  await page.getByRole("button", { name: "Open Widget" }).click();

  // Wait for iframe to appear in DOM
  await page.waitForSelector("iframe#widget-frame");

  // Now access the frame
  const widgetFrame = page.frameLocator("#widget-frame");
  await expect(widgetFrame.getByText("Widget Loaded")).toBeVisible();
});
```

### iFrames with Changing src

```typescript
test("iframe src changes", async ({ page }) => {
  await page.goto("/multi-step");

  const frame = page.frameLocator("#step-frame");

  // Step 1
  await expect(frame.getByText("Step 1")).toBeVisible();
  await frame.getByRole("button", { name: "Next" }).click();

  // Wait for iframe to reload with new content
  await expect(frame.getByText("Step 2")).toBeVisible({ timeout: 10000 });
  await frame.getByRole("button", { name: "Next" }).click();

  // Step 3
  await expect(frame.getByText("Step 3")).toBeVisible({ timeout: 10000 });
});
```

### Lazy-Loaded iFrames

```typescript
test("lazy loaded iframe", async ({ page }) => {
  await page.goto("/page-with-lazy-iframe");

  // Scroll to trigger lazy load
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

  // Wait for iframe to load
  const lazyFrame = page.frameLocator("#lazy-iframe");
  await expect(lazyFrame.locator("body")).not.toBeEmpty({ timeout: 15000 });

  // Interact with content
  await lazyFrame.getByRole("button").click();
});
```

## iFrame Navigation

### Navigating Within iFrame

```typescript
test("iframe internal navigation", async ({ page }) => {
  await page.goto("/app");

  // Get frame object for navigation control
  const frame = page.frame({ name: "content-frame" });
  if (!frame) throw new Error("Frame not found");

  // Navigate within iframe
  await frame.goto("https://embedded-app.com/page2");

  // Wait for navigation
  await frame.waitForURL("**/page2");

  // Verify content
  await expect(frame.getByRole("heading")).toHaveText("Page 2");
});
```

### Handling Frame Navigation Events

```typescript
test("track iframe navigation", async ({ page }) => {
  const navigations: string[] = [];

  // Listen to frame navigation
  page.on("framenavigated", (frame) => {
    if (frame.parentFrame()) {
      // This is an iframe navigation
      navigations.push(frame.url());
    }
  });

  await page.goto("/with-iframe");
  await page
    .frameLocator("#nav-frame")
    .getByRole("link", { name: "Page 2" })
    .click();

  // Verify navigation occurred
  expect(navigations.some((url) => url.includes("page2"))).toBe(true);
});
```

## Common Patterns

### iFrame Fixture

```typescript
// fixtures.ts
import { test as base, FrameLocator } from "@playwright/test";

export const test = base.extend<{ paymentFrame: FrameLocator }>({
  paymentFrame: async ({ page }, use) => {
    await page.goto("/checkout");

    // Wait for payment iframe to be ready
    const frame = page.frameLocator('iframe[src*="payment"]');
    await expect(frame.locator("body")).toBeVisible({ timeout: 15000 });

    await use(frame);
  },
});

// test file
test("complete payment", async ({ paymentFrame }) => {
  await paymentFrame.getByLabel("Card").fill("4242424242424242");
  await paymentFrame.getByRole("button", { name: "Pay" }).click();
});
```

### Debugging iFrame Issues

```typescript
test("debug iframe content", async ({ page }) => {
  await page.goto("/page-with-iframes");

  // List all frames
  console.log("All frames:");
  for (const frame of page.frames()) {
    console.log(`  - ${frame.name() || "(unnamed)"}: ${frame.url()}`);
  }

  // Screenshot specific iframe content
  const frame = page.frame({ name: "target-frame" });
  if (frame) {
    const body = frame.locator("body");
    await body.screenshot({ path: "iframe-content.png" });
  }

  // Get iframe HTML for debugging
  const frameContent = page.frameLocator("#my-frame");
  const html = await frameContent.locator("body").innerHTML();
  console.log("iFrame HTML:", html.substring(0, 500));
});
```

### Handling iFrame Load Failures

```typescript
test("handle iframe load failure", async ({ page }) => {
  await page.goto("/page-with-unreliable-iframe");

  const frame = page.frameLocator("#unreliable-frame");

  try {
    // Try to interact with iframe content
    await expect(frame.getByRole("button")).toBeVisible({ timeout: 5000 });
    await frame.getByRole("button").click();
  } catch (error) {
    // Fallback: refresh iframe
    await page.evaluate(() => {
      const iframe = document.querySelector(
        "#unreliable-frame",
      ) as HTMLIFrameElement;
      if (iframe) iframe.src = iframe.src;
    });

    // Retry
    await expect(frame.getByRole("button")).toBeVisible({ timeout: 10000 });
    await frame.getByRole("button").click();
  }
});
```

### Mocking iFrame Content

```typescript
test("mock iframe response", async ({ page }) => {
  // Intercept iframe src request
  await page.route("**/embedded-widget**", (route) => {
    route.fulfill({
      contentType: "text/html",
      body: `
        <!DOCTYPE html>
        <html>
          <body>
            <h1>Mocked Widget</h1>
            <button>Mocked Button</button>
          </body>
        </html>
      `,
    });
  });

  await page.goto("/page-with-widget");

  const frame = page.frameLocator("#widget-frame");
  await expect(frame.getByRole("heading")).toHaveText("Mocked Widget");
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                          | Problem                           | Solution                                           |
| ------------------------------------- | --------------------------------- | -------------------------------------------------- |
| Using `page.frame()` for interactions | Less reliable than frameLocator   | Use `page.frameLocator()` for element interactions |
| Hardcoding iframe index               | Fragile if DOM order changes      | Use name, id, or src attribute selectors           |
| Not waiting for iframe load           | Race conditions                   | Wait for element inside iframe to be visible       |
| Assuming same-origin                  | Cross-origin has different timing | Always wait for iframe content explicitly          |
| Ignoring nested iframes               | Element not found                 | Chain frameLocator calls for nested frames         |

## Related References

- **Locators**: See [locators.md](../core/locators.md) for selector strategies
- **Third-party services**: See [third-party.md](../advanced/third-party.md) for payment iframe patterns
- **Debugging**: See [debugging.md](../debugging/debugging.md) for troubleshooting iframe issues
