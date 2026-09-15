# Assertions & Waiting

## Table of Contents

1. [Web-First Assertions](#web-first-assertions)
2. [Generic Assertions](#generic-assertions)
3. [Soft Assertions](#soft-assertions)
4. [Waiting Strategies](#waiting-strategies)
5. [Polling & Retrying](#polling--retrying)
6. [Custom Matchers](#custom-matchers)

## Web-First Assertions

Auto-retry until condition is met or timeout. Always prefer these over generic assertions.

### Locator Assertions

```typescript
import { expect } from "@playwright/test";

// Visibility
await expect(page.getByRole("button")).toBeVisible();
await expect(page.getByRole("button")).toBeHidden();
await expect(page.getByRole("button")).not.toBeVisible();

// Enabled/Disabled
await expect(page.getByRole("button")).toBeEnabled();
await expect(page.getByRole("button")).toBeDisabled();

// Text content
await expect(page.getByRole("heading")).toHaveText("Welcome");
await expect(page.getByRole("heading")).toHaveText(/welcome/i);
await expect(page.getByRole("heading")).toContainText("Welcome");

// Count
await expect(page.getByRole("listitem")).toHaveCount(5);

// Attributes
await expect(page.getByRole("link")).toHaveAttribute("href", "/home");
await expect(page.getByRole("img")).toHaveAttribute("alt", /logo/i);

// CSS
await expect(page.getByRole("button")).toHaveClass(/primary/);
await expect(page.getByRole("button")).toHaveCSS("color", "rgb(0, 0, 255)");

// Input values
await expect(page.getByLabel("Email")).toHaveValue("user@example.com");
await expect(page.getByLabel("Email")).toBeEmpty();

// Focus
await expect(page.getByLabel("Email")).toBeFocused();

// Checked state
await expect(page.getByRole("checkbox")).toBeChecked();
await expect(page.getByRole("checkbox")).not.toBeChecked();

// Editable state
await expect(page.getByLabel("Name")).toBeEditable();
```

### Page Assertions

```typescript
// URL
await expect(page).toHaveURL("/dashboard");
await expect(page).toHaveURL(/\/dashboard/);

// Title
await expect(page).toHaveTitle("Dashboard - MyApp");
await expect(page).toHaveTitle(/dashboard/i);
```

### Response Assertions

```typescript
const response = await page.request.get("/api/users");
await expect(response).toBeOK();
await expect(response).not.toBeOK();
```

## Generic Assertions

Use for non-UI values. Do NOT retry - execute immediately.

```typescript
// Equality
expect(value).toBe(5);
expect(object).toEqual({ name: "Test" });
expect(array).toContain("item");

// Truthiness
expect(value).toBeTruthy();
expect(value).toBeFalsy();
expect(value).toBeNull();
expect(value).toBeUndefined();
expect(value).toBeDefined();

// Numbers
expect(value).toBeGreaterThan(5);
expect(value).toBeLessThanOrEqual(10);
expect(value).toBeCloseTo(5.5, 1);

// Strings
expect(string).toMatch(/pattern/);
expect(string).toContain("substring");

// Arrays/Objects
expect(array).toHaveLength(3);
expect(object).toHaveProperty("key", "value");

// Exceptions
expect(() => fn()).toThrow();
expect(() => fn()).toThrow("error message");
await expect(asyncFn()).rejects.toThrow();
```

## Soft Assertions

Continue test execution after failure, report all failures at end.

```typescript
test("check multiple elements", async ({ page }) => {
  await page.goto("/dashboard");

  // Won't stop on first failure
  await expect.soft(page.getByRole("heading")).toHaveText("Dashboard");
  await expect.soft(page.getByRole("button", { name: "Save" })).toBeEnabled();
  await expect.soft(page.getByText("Welcome")).toBeVisible();

  // Test continues; all failures reported at end
});
```

### Soft Assertions with Early Exit

```typescript
test("check form", async ({ page }) => {
  await expect.soft(page.getByRole("form")).toBeVisible();

  // Exit early if form not visible (pointless to check fields)
  if (expect.soft.hasFailures()) {
    return;
  }

  await expect.soft(page.getByLabel("Name")).toBeVisible();
  await expect.soft(page.getByLabel("Email")).toBeVisible();
});
```

## Waiting Strategies

### Auto-Waiting (Default)

Actions automatically wait for:

- Element to be attached to DOM
- Element to be visible
- Element to be stable (no animations)
- Element to be enabled
- Element to receive events

```typescript
// These auto-wait
await page.click("button");
await page.fill("input", "text");
await page.getByRole("button").click();
```

### Wait for Navigation

```typescript
// Wait for URL change
await page.waitForURL("/dashboard");
await page.waitForURL(/\/dashboard/);

// Wait for navigation after action
await Promise.all([
  page.waitForURL("**/dashboard"),
  page.click('a[href="/dashboard"]'),
]);

// Or without Promise.all
const urlPromise = page.waitForURL("**/dashboard");
await page.click("a");
await urlPromise;
```

### Wait for Network

```typescript
// Wait for specific response
const responsePromise = page.waitForResponse("**/api/users");
await page.click("button");
const response = await responsePromise;
expect(response.status()).toBe(200);

// Wait for request
const requestPromise = page.waitForRequest("**/api/submit");
await page.click("button");
const request = await requestPromise;

// Wait for no network activity
await page.waitForLoadState("networkidle");
```

### Wait for Element State

```typescript
// Wait for element to appear
await page.getByRole("dialog").waitFor({ state: "visible" });

// Wait for element to disappear
await page.getByText("Loading...").waitFor({ state: "hidden" });

// Wait for element to be attached
await page.getByTestId("result").waitFor({ state: "attached" });

// Wait for element to be detached
await page.getByTestId("modal").waitFor({ state: "detached" });
```

### Wait for Function

```typescript
// Wait for arbitrary condition
await page.waitForFunction(() => {
  return document.querySelector(".loaded") !== null;
});

// With arguments
await page.waitForFunction(
  (selector) => document.querySelector(selector)?.textContent === "Ready",
  ".status",
);
```

## Polling & Retrying

### toPass() for Polling

Retry until block passes or times out:

```typescript
await expect(async () => {
  const response = await page.request.get("/api/status");
  expect(response.status()).toBe(200);

  const data = await response.json();
  expect(data.ready).toBe(true);
}).toPass({
  intervals: [1000, 2000, 5000], // Retry intervals
  timeout: 30000,
});
```

### expect.poll()

Poll a function until assertion passes:

```typescript
// Poll API until condition met
await expect
  .poll(
    async () => {
      const response = await page.request.get("/api/job/123");
      return (await response.json()).status;
    },
    {
      intervals: [1000, 2000, 5000],
      timeout: 30000,
    },
  )
  .toBe("completed");

// Poll DOM value
await expect.poll(() => page.getByTestId("counter").textContent()).toBe("10");
```

## Custom Matchers

```typescript
// playwright.config.ts or fixtures
import { expect } from "@playwright/test";

expect.extend({
  async toHaveDataLoaded(page: Page) {
    const locator = page.getByTestId("data-container");
    let pass = false;
    let message = "";

    try {
      await expect(locator).toBeVisible();
      await expect(locator).not.toContainText("Loading");
      pass = true;
    } catch (e) {
      message = `Expected data to be loaded but found loading state`;
    }

    return { pass, message: () => message };
  },
});

// Extend TypeScript types
declare global {
  namespace PlaywrightTest {
    interface Matchers<R> {
      toHaveDataLoaded(): Promise<R>;
    }
  }
}

// Usage
await expect(page).toHaveDataLoaded();
```

## Timeouts

### Configure Timeouts

```typescript
// playwright.config.ts
export default defineConfig({
  timeout: 30000, // Test timeout
  expect: {
    timeout: 5000, // Assertion timeout
  },
});

// Per-test timeout
test("long test", async ({ page }) => {
  test.setTimeout(60000);
  // ...
});

// Per-assertion timeout
await expect(page.getByRole("button")).toBeVisible({ timeout: 10000 });
```

## Best Practices

| Do                             | Don't                          |
| ------------------------------ | ------------------------------ |
| Use web-first assertions       | Use generic assertions for DOM |
| Let auto-waiting work          | Add unnecessary explicit waits |
| Use `toPass()` for polling     | Write manual retry loops       |
| Configure appropriate timeouts | Use `waitForTimeout()`         |
| Check specific conditions      | Wait for arbitrary time        |

## Anti-Patterns to Avoid

| Anti-Pattern                                              | Problem                       | Solution                                     |
| --------------------------------------------------------- | ----------------------------- | -------------------------------------------- |
| `await page.waitForTimeout(5000)`                         | Slow, flaky, arbitrary timing | Use auto-waiting or `waitForResponse`        |
| `await new Promise(resolve => setTimeout(resolve, 1000))` | Same as above                 | Use `waitForResponse` or element state waits |
| Generic assertions on DOM elements                        | No auto-retry, flaky          | Use web-first assertions with `expect()`     |

## Related References

- **Debugging timeout issues**: See [debugging.md](../debugging/debugging.md) for troubleshooting
- **Fixing flaky tests**: See [debugging.md](../debugging/debugging.md) for race condition solutions
- **Network interception**: See [test-suite-structure.md](test-suite-structure.md) for API mocking
