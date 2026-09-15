# Debugging and Managing Flaky Tests

## Table of Contents

1. [Understanding Flakiness Types](#understanding-flakiness-types)
2. [Detection and Reproduction](#detection-and-reproduction)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Fixing Strategies by Type](#fixing-strategies-by-type)
5. [CI-Specific Flakiness](#ci-specific-flakiness)
6. [Quarantine and Management](#quarantine-and-management)
7. [Prevention Strategies](#prevention-strategies)

## Understanding Flakiness Types

### Categories of Flakiness

Most flaky tests fall into distinct categories requiring different remediation:

| Category                    | Symptoms                        | Common Causes                                          |
| --------------------------- | ------------------------------- | ------------------------------------------------------ |
| **UI-driven**               | Element not found, click missed | Missing waits, animations, dynamic rendering           |
| **Environment-driven**      | CI-only failures                | Slower CPU, memory limits, cold browser starts         |
| **Data/parallelism-driven** | Fails with multiple workers     | Shared backend data, reused accounts, state collisions |
| **Test-suite-driven**       | Fails when run with other tests | Leaked state, shared fixtures, order dependencies      |

### Flakiness Decision Tree

```
Test fails intermittently
├─ Fails locally too?
│  ├─ YES → Timing/async issue → Check waits and assertions
│  └─ NO → CI-specific → Check environment differences
│
├─ Fails only with multiple workers?
│  └─ YES → Parallelism issue → Check data isolation
│
├─ Fails only when run after specific tests?
│  └─ YES → State leak → Check fixtures and cleanup
│
└─ Fails randomly regardless of conditions?
   └─ External dependency → Check network/API stability
```

## Detection and Reproduction

### Confirming Flakiness

```bash
# Run test multiple times to confirm instability
npx playwright test tests/checkout.spec.ts --repeat-each=20

# Run with single worker to isolate parallelism issues
npx playwright test --workers=1

# Run in CI-like conditions locally
CI=true npx playwright test --repeat-each=10
```

### Reproduction Strategies

```typescript
// playwright.config.ts - Enable artifacts for flaky test investigation
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: "on-first-retry", // Capture trace on retry
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
```

### Identify Flaky Tests Programmatically

```typescript
// Track test results across runs
test.afterEach(async ({}, testInfo) => {
  if (testInfo.retry > 0 && testInfo.status === "passed") {
    console.warn(`FLAKY: ${testInfo.title} passed on retry ${testInfo.retry}`);
    // Log to your tracking system
  }
});
```

## Root Cause Analysis

### Event Logging for Race Conditions

Add comprehensive event logging to expose timing issues:

```typescript
test.beforeEach(async ({ page }) => {
  page.on("console", (msg) =>
    console.log(`CONSOLE [${msg.type()}]:`, msg.text()),
  );
  page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));
  page.on("requestfailed", (req) =>
    console.error(`REQUEST FAILED: ${req.url()}`),
  );
});
```

> **For comprehensive console error handling** (fail on errors, allowed patterns, fixtures), see [console-errors.md](console-errors.md).

### Network Timing Analysis

```typescript
// Capture slow or failed requests
test.beforeEach(async ({ page }) => {
  const slowRequests: string[] = [];

  page.on("requestfinished", (request) => {
    const timing = request.timing();
    const duration = timing.responseEnd - timing.requestStart;
    if (duration > 2000) {
      slowRequests.push(`${request.url()} took ${duration}ms`);
    }
  });

  page.on("requestfailed", (request) => {
    console.error(`Failed: ${request.url()} - ${request.failure()?.errorText}`);
  });
});
```

### Trace Analysis

```bash
# View trace from failed CI run
npx playwright show-trace path/to/trace.zip

# Generate trace for specific test
npx playwright test tests/flaky.spec.ts --trace on
```

## Fixing Strategies by Type

### UI-Driven Flakiness

**Problem: Element not ready when action executes**

```typescript
// ❌ BAD: No wait for element state
await page.click("#submit");
await page.fill("#username", "test"); // Element may not be ready

// ✅ GOOD: Actions + assertions pattern (auto-waiting built-in)
await page.getByRole("button", { name: "Submit" }).click();
await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
```

**Problem: Animations or transitions interfere**

```typescript
// ❌ BAD: Click during animation
await page.click(".menu-item");

// ✅ GOOD: Wait for animation to complete
await page.getByRole("menuitem", { name: "Settings" }).click();
await expect(page.getByRole("dialog")).toBeVisible();
// Or disable animations entirely
await page.emulateMedia({ reducedMotion: "reduce" });
```

**Problem: Brittle selectors**

```typescript
// ❌ BAD: Fragile CSS chain
await page.click("div.container > div:nth-child(2) > button.btn-primary");

// ✅ GOOD: Semantic selectors
await page.getByRole("button", { name: "Continue" }).click();
await page.getByTestId("checkout-button").click();
await page.getByLabel("Email address").fill("test@example.com");
```

### Async/Timing Flakiness

**Problem: Race between test and application**

```typescript
// ❌ BAD: Arbitrary sleep
await page.click("#load-data");
await page.waitForTimeout(3000); // Hope data loads in 3s

// ✅ GOOD: Wait for specific condition
await page.click("#load-data");
await expect(page.locator(".data-row")).toHaveCount(10, { timeout: 10000 });

// ✅ BETTER: Wait for network response, then assert
const responsePromise = page.waitForResponse(
  (r) =>
    r.url().includes("/api/data") &&
    r.request().method() === "GET" &&
    r.ok(),
);
await page.click("#load-data");
await responsePromise;
await expect(page.locator(".data-row")).toHaveCount(10);
```

> **For comprehensive waiting strategies** (navigation, element state, network, polling with `toPass()`), see [assertions-waiting.md](assertions-waiting.md#waiting-strategies).

**Problem: Complex async state**

```typescript
// Custom wait for application-specific conditions
await page.waitForFunction(() => {
  const app = (window as any).__APP_STATE__;
  return app?.isReady && !app?.isLoading;
});

// Wait for multiple conditions
await Promise.all([
  page.waitForResponse("**/api/user"),
  page.waitForResponse("**/api/settings"),
  page.getByRole("button", { name: "Load" }).click(),
]);
```

### Data/Parallelism-Driven Flakiness

**Problem: Tests share backend data**

```typescript
// ❌ BAD: All workers use same user
const testUser = { email: "test@example.com", password: "pass123" };

// ✅ GOOD: Unique data per worker
import { test as base } from "@playwright/test";

export const test = base.extend<
  {},
  { testUser: { email: string; id: string } }
>({
  testUser: [
    async ({}, use, workerInfo) => {
      const email = `test-${workerInfo.workerIndex}-${Date.now()}@example.com`;
      const user = await createTestUser(email);
      await use(user);
      await deleteTestUser(user.id);
    },
    { scope: "worker" },
  ],
});
```

**Problem: Shared storageState across workers**

```typescript
// ❌ BAD: All workers share same auth state
use: {
  storageState: '.auth/user.json',
}

// ✅ GOOD: Per-worker auth state
export const test = base.extend<{}, { workerStorageState: string }>({
  workerStorageState: [
    async ({ browser }, use, workerInfo) => {
      const id = workerInfo.workerIndex;
      const fileName = `.auth/user-${id}.json`;

      if (!fs.existsSync(fileName)) {
        const page = await browser.newPage({ storageState: undefined });
        await authenticateUser(page, `worker${id}@test.com`);
        await page.context().storageState({ path: fileName });
        await page.close();
      }

      await use(fileName);
    },
    { scope: "worker" },
  ],
});
```

### Test-Suite-Driven Flakiness (State Leaks)

**Problem: Tests affect each other**

```typescript
// ❌ BAD: Module-level state persists across tests
let sharedPage: Page;

test.beforeAll(async ({ browser }) => {
  sharedPage = await browser.newPage(); // Shared across tests!
});

// ✅ GOOD: Use Playwright's default isolation (fresh context per test)
test("first test", async ({ page }) => {
  // Fresh page for this test
});

test("second test", async ({ page }) => {
  // Fresh page for this test
});
```

**Problem: Fixture cleanup not happening**

```typescript
// ✅ GOOD: Proper fixture with cleanup
export const test = base.extend<{ tempFile: string }>({
  tempFile: async ({}, use) => {
    const file = `/tmp/test-${Date.now()}.json`;
    fs.writeFileSync(file, "{}");

    await use(file);

    // Cleanup always runs, even on failure
    if (fs.existsSync(file)) {
      fs.unlinkSync(file);
    }
  },
});
```

## CI-Specific Flakiness

### Why Tests Fail Only in CI

| CI Condition       | Impact                                | Solution                                             |
| ------------------ | ------------------------------------- | ---------------------------------------------------- |
| Slower CPU         | Actions complete later than expected  | Use auto-waiting, not timeouts                       |
| Cold browser start | No cached assets, slower initial load | Add explicit waits for first navigation              |
| Headless mode      | Different rendering behavior          | Test locally in headless mode                        |
| Shared runners     | Resource contention                   | Reduce parallelism or use dedicated runners          |
| Network latency    | API calls slower                      | Mock external APIs, increase timeouts for real calls |

### Simulating CI Locally

```bash
# Run headless with CI environment variable
CI=true npx playwright test

# Limit CPU (Linux/Mac)
cpulimit -l 50 -- npx playwright test

# Run in Docker matching CI environment
docker run -it --rm \
  -v $(pwd):/work \
  -w /work \
  mcr.microsoft.com/playwright:v1.40.0-jammy \
  npx playwright test
```

### Consistent Viewport and Scale

```typescript
// playwright.config.ts - Match CI rendering exactly
export default defineConfig({
  use: {
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  },
});
```

### Network Stubbing for External APIs

```typescript
// Eliminate external API flakiness
test.beforeEach(async ({ page }) => {
  // Stub unstable third-party APIs
  await page.route("**/api.analytics.com/**", (route) =>
    route.fulfill({ body: "" }),
  );
  await page.route("**/api.payment-provider.com/**", (route) =>
    route.fulfill({ json: { status: "ok" } }),
  );
});

// Test-specific stub
test("checkout with payment", async ({ page }) => {
  await page.route("**/api/payment", (route) =>
    route.fulfill({ json: { success: true, transactionId: "test-123" } }),
  );
  // Test proceeds with deterministic response
});
```

## Quarantine and Management

### Quarantine Pattern

```typescript
// playwright.config.ts - Separate flaky tests
export default defineConfig({
  projects: [
    {
      name: "stable",
      testIgnore: ["**/*.flaky.spec.ts"],
    },
    {
      name: "quarantine",
      testMatch: ["**/*.flaky.spec.ts"],
      retries: 3,
    },
  ],
});
```

### Annotation-Based Quarantine

```typescript
// Mark flaky tests with annotations
test("intermittent checkout issue", async ({ page }, testInfo) => {
  testInfo.annotations.push({
    type: "flaky",
    description: "Investigating payment API timing - JIRA-1234",
  });

  // Test implementation
});

// Skip flaky test conditionally
test("known CI flaky", async ({ page }) => {
  test.skip(!!process.env.CI, "Flaky in CI - investigating JIRA-5678");
  // Test implementation
});
```

## Prevention Strategies

### Test Burn-In

```bash
# Run new tests many times before merging
npx playwright test tests/new-feature.spec.ts --repeat-each=50

# Run in parallel to expose race conditions
npx playwright test tests/new-feature.spec.ts --repeat-each=20 --workers=4
```

### Isolation Checklist

```typescript
// ✅ Each test should be self-contained
test.describe("User profile", () => {
  test("can update name", async ({ page, testUser }) => {
    // Uses unique testUser fixture
    // No dependency on other tests
    // Cleanup handled by fixture
  });

  test("can update email", async ({ page, testUser }) => {
    // Independent of "can update name"
    // Own testUser, own state
  });
});
```

### Defensive Assertions

```typescript
// ❌ BAD: Single point of failure
await expect(page.locator(".items")).toHaveCount(5);

// ✅ GOOD: Progressive assertions that help diagnose
await expect(page.locator(".items-container")).toBeVisible();
await expect(page.locator(".loading")).not.toBeVisible();
await expect(page.locator(".items")).toHaveCount(5);
```

### Retry Budget

```typescript
// playwright.config.ts - Limit retries to avoid masking issues
export default defineConfig({
  retries: process.env.CI ? 2 : 0, // Only retry in CI
  expect: {
    timeout: 10000, // Reasonable assertion timeout
  },
  timeout: 60000, // Test timeout
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                              | Problem                             | Solution                                       |
| ----------------------------------------- | ----------------------------------- | ---------------------------------------------- |
| `waitForTimeout()` as primary wait        | Arbitrary, hides real timing issues | Use auto-waiting assertions                    |
| Increasing global timeout to "fix" flakes | Masks root cause, slows all tests   | Find and fix actual timing issue               |
| Retrying until pass                       | Hides systemic problems             | Fix root cause, use retries for diagnosis only |
| Shared test data across workers           | Race conditions, collisions         | Isolate data per worker                        |
| Testing real external APIs                | Network variability                 | Mock external dependencies                     |
| Module-level mutable state                | Leaks between tests                 | Use fixtures with proper cleanup               |
| Ignoring flaky tests                      | Problem compounds over time         | Quarantine and track for fixing                |

## Related References

- **Debugging**: See [debugging.md](debugging.md) for trace viewer and inspector
- **Fixtures**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for worker-scoped isolation
- **Performance**: See [performance.md](../infrastructure-ci-cd/performance.md) for parallel execution patterns
- **Assertions**: See [assertions-waiting.md](../core/assertions-waiting.md) for auto-waiting patterns
- **Global Setup**: See [global-setup.md](../core/global-setup.md) for setup vs fixtures decision
