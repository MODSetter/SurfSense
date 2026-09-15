# Test Annotations & Organization

## Table of Contents

1. [Skip Annotations](#skip-annotations)
2. [Fixme & Fail Annotations](#fixme--fail-annotations)
3. [Slow Tests](#slow-tests)
4. [Test Steps](#test-steps)
5. [Custom Annotations](#custom-annotations)
6. [Conditional Annotations](#conditional-annotations)

## Skip Annotations

### Basic Skip

```typescript
// Skip unconditionally
test.skip("feature not implemented", async ({ page }) => {
  // This test won't run
});

// Skip with reason
test("payment flow", async ({ page }) => {
  test.skip(true, "Payment gateway in maintenance");
  // Test body won't execute
});
```

### Conditional Skip

```typescript
test("webkit-specific feature", async ({ page, browserName }) => {
  test.skip(browserName !== "webkit", "This feature only works in WebKit");

  await page.goto("/webkit-feature");
});

test("production only", async ({ page }) => {
  test.skip(process.env.ENV !== "production", "Only runs against production");

  await page.goto("/prod-feature");
});
```

### Skip by Platform

```typescript
test("windows-specific", async ({ page }) => {
  test.skip(process.platform !== "win32", "Windows only");
});

test("not on CI", async ({ page }) => {
  test.skip(!!process.env.CI, "Skipped in CI environment");
});
```

### Skip Describe Block

```typescript
test.describe("Admin features", () => {
  test.skip(
    ({ browserName }) => browserName === "firefox",
    "Firefox admin bug",
  );

  test("admin dashboard", async ({ page }) => {
    // Skipped in Firefox
  });

  test("admin settings", async ({ page }) => {
    // Skipped in Firefox
  });
});
```

## Fixme & Fail Annotations

### Fixme - Known Issues

```typescript
// Mark test as needing fix (skips the test)
test.fixme("broken after refactor", async ({ page }) => {
  // Test won't run but is tracked
});

// Conditional fixme
test("flaky on CI", async ({ page }) => {
  test.fixme(!!process.env.CI, "Investigate CI flakiness - ticket #123");

  await page.goto("/flaky-feature");
});
```

### Fail - Expected Failures

```typescript
// Test is expected to fail (runs but expects failure)
test("known bug", async ({ page }) => {
  test.fail();

  await page.goto("/buggy-page");
  // If this passes, the test fails (bug was fixed!)
  await expect(page.getByText("Working")).toBeVisible();
});

// Conditional fail
test("fails on webkit", async ({ page, browserName }) => {
  test.fail(browserName === "webkit", "WebKit rendering bug #456");

  await page.goto("/render-test");
  await expect(page.getByTestId("element")).toHaveCSS("width", "100px");
});
```

### Difference Between Skip, Fixme, Fail

| Annotation     | Runs? | Use Case                         |
| -------------- | ----- | -------------------------------- |
| `test.skip()`  | No    | Feature not applicable           |
| `test.fixme()` | No    | Known bug, needs investigation   |
| `test.fail()`  | Yes   | Expected to fail, tracking a bug |

## Slow Tests

### Mark Slow Tests

```typescript
// Triple the default timeout
test("large data import", async ({ page }) => {
  test.slow();

  await page.goto("/import");
  await page.setInputFiles("#file", "large-file.csv");
  await page.getByRole("button", { name: "Import" }).click();

  await expect(page.getByText("Import complete")).toBeVisible();
});

// Conditional slow
test("video processing", async ({ page, browserName }) => {
  test.slow(browserName === "webkit", "WebKit video processing is slow");

  await page.goto("/video-editor");
});
```

### Custom Timeout

```typescript
test("very long operation", async ({ page }) => {
  // Set specific timeout (in milliseconds)
  test.setTimeout(120000); // 2 minutes

  await page.goto("/long-operation");
});

// Timeout for describe block
test.describe("Integration tests", () => {
  test.describe.configure({ timeout: 60000 });

  test("test 1", async ({ page }) => {
    // Has 60 second timeout
  });
});
```

## Test Steps

### Basic Steps

```typescript
test("checkout flow", async ({ page }) => {
  await test.step("Add item to cart", async () => {
    await page.goto("/products");
    await page.getByRole("button", { name: "Add to Cart" }).click();
  });

  await test.step("Go to checkout", async () => {
    await page.getByRole("link", { name: "Cart" }).click();
    await page.getByRole("button", { name: "Checkout" }).click();
  });

  await test.step("Fill shipping info", async () => {
    await page.getByLabel("Address").fill("123 Test St");
    await page.getByLabel("City").fill("Test City");
  });

  await test.step("Complete payment", async () => {
    await page.getByLabel("Card").fill("4242424242424242");
    await page.getByRole("button", { name: "Pay" }).click();
  });

  await expect(page.getByText("Order confirmed")).toBeVisible();
});
```

### Nested Steps

```typescript
test("user registration", async ({ page }) => {
  await test.step("Fill registration form", async () => {
    await page.goto("/register");

    await test.step("Personal info", async () => {
      await page.getByLabel("Name").fill("John Doe");
      await page.getByLabel("Email").fill("john@example.com");
    });

    await test.step("Security", async () => {
      await page.getByLabel("Password").fill("SecurePass123");
      await page.getByLabel("Confirm Password").fill("SecurePass123");
    });
  });

  await test.step("Submit and verify", async () => {
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page.getByText("Welcome")).toBeVisible();
  });
});
```

### Steps with Return Values

```typescript
test("verify order", async ({ page }) => {
  const orderId = await test.step("Create order", async () => {
    await page.goto("/checkout");
    await page.getByRole("button", { name: "Place Order" }).click();

    // Return value from step
    return await page.getByTestId("order-id").textContent();
  });

  await test.step("Verify order details", async () => {
    await page.goto(`/orders/${orderId}`);
    await expect(page.getByText(`Order #${orderId}`)).toBeVisible();
  });
});
```

### Step in Page Object

```typescript
// pages/checkout.page.ts
export class CheckoutPage {
  async fillShippingInfo(address: string, city: string) {
    await test.step("Fill shipping information", async () => {
      await this.page.getByLabel("Address").fill(address);
      await this.page.getByLabel("City").fill(city);
    });
  }

  async completePayment(cardNumber: string) {
    await test.step("Complete payment", async () => {
      await this.page.getByLabel("Card").fill(cardNumber);
      await this.page.getByRole("button", { name: "Pay" }).click();
    });
  }
}
```

## Custom Annotations

### Add Annotations

```typescript
test("important feature", async ({ page }, testInfo) => {
  // Add custom annotation
  testInfo.annotations.push({
    type: "priority",
    description: "high",
  });

  testInfo.annotations.push({
    type: "ticket",
    description: "JIRA-123",
  });

  await page.goto("/feature");
});
```

### Annotation Fixture

```typescript
// fixtures/annotations.fixture.ts
import { test as base, TestInfo } from "@playwright/test";

type AnnotationFixtures = {
  annotate: {
    ticket: (id: string) => void;
    priority: (level: "low" | "medium" | "high") => void;
    owner: (name: string) => void;
  };
};

export const test = base.extend<AnnotationFixtures>({
  annotate: async ({}, use, testInfo) => {
    await use({
      ticket: (id) => {
        testInfo.annotations.push({ type: "ticket", description: id });
      },
      priority: (level) => {
        testInfo.annotations.push({ type: "priority", description: level });
      },
      owner: (name) => {
        testInfo.annotations.push({ type: "owner", description: name });
      },
    });
  },
});

// Usage
test("critical feature", async ({ page, annotate }) => {
  annotate.ticket("JIRA-456");
  annotate.priority("high");
  annotate.owner("Alice");

  await page.goto("/critical");
});
```

### Read Annotations in Reporter

```typescript
// reporters/annotation-reporter.ts
import { Reporter, TestCase, TestResult } from "@playwright/test/reporter";

class AnnotationReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult) {
    const ticket = test.annotations.find((a) => a.type === "ticket");
    const priority = test.annotations.find((a) => a.type === "priority");

    if (ticket) {
      console.log(`Test linked to: ${ticket.description}`);
    }

    if (priority?.description === "high" && result.status === "failed") {
      console.log(`HIGH PRIORITY FAILURE: ${test.title}`);
    }
  }
}

export default AnnotationReporter;
```

## Conditional Annotations

### Annotation Helper

```typescript
// helpers/test-annotations.ts
import { test } from "@playwright/test";

export function skipInCI(reason = "Skipped in CI") {
  test.skip(!!process.env.CI, reason);
}

export function skipInBrowser(browser: string, reason: string) {
  test.beforeEach(({ browserName }) => {
    test.skip(browserName === browser, reason);
  });
}

export function onlyInEnv(env: string) {
  test.skip(process.env.ENV !== env, `Only runs in ${env}`);
}
```

```typescript
// tests/feature.spec.ts
import { skipInCI, onlyInEnv } from "../helpers/test-annotations";

test("local only feature", async ({ page }) => {
  skipInCI("Uses local resources");

  await page.goto("/local-feature");
});

test("production check", async ({ page }) => {
  onlyInEnv("production");

  await page.goto("/prod-only");
});
```

### Describe-Level Conditions

```typescript
test.describe("Mobile features", () => {
  test.beforeEach(({ isMobile }) => {
    test.skip(!isMobile, "Mobile only tests");
  });

  test("touch gestures", async ({ page }) => {
    // Only runs on mobile
  });
});

test.describe("Desktop features", () => {
  test.beforeEach(({ isMobile }) => {
    test.skip(isMobile, "Desktop only tests");
  });

  test("hover interactions", async ({ page }) => {
    // Only runs on desktop
  });
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                | Problem                | Solution                         |
| --------------------------- | ---------------------- | -------------------------------- |
| Skipping without reason     | Hard to track why      | Always provide description       |
| Too many skipped tests      | Test debt accumulates  | Review and clean up regularly    |
| Using skip instead of fixme | Loses intent           | Use fixme for bugs, skip for N/A |
| Not using steps             | Hard to debug failures | Group logical actions in steps   |

## Related References

- **Test Tags**: See [test-tags.md](test-tags.md) for tagging and filtering tests with `--grep`
- **Test Organization**: See [test-suite-structure.md](test-suite-structure.md) for structuring tests
- **Debugging**: See [debugging.md](../debugging/debugging.md) for troubleshooting
