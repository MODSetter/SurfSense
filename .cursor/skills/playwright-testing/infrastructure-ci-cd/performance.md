# Performance & Parallelization

## Table of Contents

1. [Parallel Execution](#parallel-execution)
2. [Sharding](#sharding)
3. [Test Optimization](#test-optimization)
4. [Network Optimization](#network-optimization)
5. [Isolation and Parallel Execution](#isolation-and-parallel-execution)
6. [Resource Management](#resource-management)
7. [Benchmarking](#benchmarking)

## Parallel Execution

### Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  // Run test files in parallel
  fullyParallel: true,

  // Number of worker processes
  workers: process.env.CI ? 1 : undefined, // undefined = half CPU cores

  // Or explicit count
  // workers: 4,
  // workers: '50%', // Percentage of CPU cores
});
```

### Serial Execution When Needed

```typescript
// Entire file serial
test.describe.configure({ mode: "serial" });

test.describe("Sequential Tests", () => {
  test("first", async ({ page }) => {
    // Runs first
  });

  test("second", async ({ page }) => {
    // Runs after first
  });
});
```

```typescript
// Single describe block serial
test.describe("Parallel Tests", () => {
  test("a", async () => {}); // Parallel
  test("b", async () => {}); // Parallel
});

test.describe.serial("Serial Tests", () => {
  test("c", async () => {}); // Serial
  test("d", async () => {}); // Serial
});
```

### Parallel Projects

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
```

```bash
# Run all projects in parallel
npx playwright test

# Run specific project
npx playwright test --project=chromium
```

## Sharding

### Basic Sharding

```bash
# Split tests across 4 machines
# Machine 1:
npx playwright test --shard=1/4

# Machine 2:
npx playwright test --shard=2/4

# Machine 3:
npx playwright test --shard=3/4

# Machine 4:
npx playwright test --shard=4/4
```

### Sharding Strategy

Tests are distributed evenly by file. For optimal sharding:

- Keep test files similar in size
- Use `fullyParallel: true` for even distribution
- Balance slow tests across files

### CI Sharding Pattern

```yaml
# GitHub Actions
jobs:
  test:
    strategy:
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - run: npx playwright test --shard=${{ matrix.shard }}/4
```

> **For comprehensive CI sharding** (blob reports, merging sharded results, full workflows), see [ci-cd.md](ci-cd.md#sharding).

## Test Optimization

### Reuse Authentication

Avoid logging in for every test. Use setup projects with storage state to authenticate once and reuse the session.

> **For authentication patterns** (storage state, multiple auth states, setup projects), see [fixtures-hooks.md](fixtures-hooks.md#authentication-patterns).

### Reuse Page State (serial only — trade-off with isolation)

Sharing a single page/context across tests with `beforeAll`/`afterAll` is **not recommended** for most suites: it breaks test isolation, causes state leak between tests, and makes failures harder to debug. Prefer a fresh `page` per test (Playwright default). Use shared page only when you explicitly need serial execution and accept no isolation.

```typescript
// ⚠️ Serial only, no isolation: state from one test leaks into the next.
// Prefer test.describe.configure({ mode: 'serial' }) + fresh page per test, or beforeEach + page.goto().
test.describe.configure({ mode: "serial" });
test.describe("Dashboard", () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: ".auth/user.json",
    });
    page = await context.newPage();
    await page.goto("/dashboard");
  });

  test.afterAll(async () => {
    await page?.close();
  });

  test("shows stats", async () => {
    await expect(page.getByTestId("stats")).toBeVisible();
  });

  test("shows chart", async () => {
    await expect(page.getByTestId("chart")).toBeVisible();
  });
});
```

### Lazy Navigation

```typescript
// Bad: Navigate in every test
test("check header", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("heading")).toBeVisible();
});

test("check footer", async ({ page }) => {
  await page.goto("/products");
  await expect(page.getByRole("contentinfo")).toBeVisible();
});

// Good: Share navigation
test.describe("Products Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/products");
  });

  test("check header", async ({ page }) => {
    await expect(page.getByRole("heading")).toBeVisible();
  });

  test("check footer", async ({ page }) => {
    await expect(page.getByRole("contentinfo")).toBeVisible();
  });
});
```

### Skip Unnecessary Setup

```typescript
// Use test.skip for conditional execution
test("admin feature", async ({ page }) => {
  test.skip(!process.env.ADMIN_ENABLED, "Admin features disabled");
  // ...
});

// Use test.fixme for known broken tests
test.fixme("broken feature", async ({ page }) => {
  // Skipped but tracked
});
```

## Network Optimization

### Mock APIs

```typescript
test.beforeEach(async ({ page }) => {
  // Mock slow/heavy endpoints
  await page.route("**/api/analytics", (route) =>
    route.fulfill({ json: { views: 1000 } }),
  );

  await page.route("**/api/recommendations", (route) =>
    route.fulfill({ json: [] }),
  );
});
```

### Block Unnecessary Resources

```typescript
test.beforeEach(async ({ page }) => {
  // Block analytics, ads, tracking
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (
      url.includes("google-analytics") ||
      url.includes("facebook") ||
      url.includes("hotjar")
    ) {
      return route.abort();
    }
    return route.continue();
  });
});
```

### Block Resource Types

```typescript
// Block images and fonts for faster tests
await page.route("**/*", (route) => {
  const resourceType = route.request().resourceType();
  if (["image", "font", "stylesheet"].includes(resourceType)) {
    return route.abort();
  }
  return route.continue();
});
```

### Cache API Responses

```typescript
const apiCache = new Map<string, object>();

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();

    if (apiCache.has(url)) {
      return route.fulfill({ json: apiCache.get(url) });
    }

    const response = await route.fetch();
    const json = await response.json();
    apiCache.set(url, json);
    return route.fulfill({ json });
  });
});
```

## Isolation and Parallel Execution

### Default: one context per test

Playwright gives each test its own browser context (and page). That gives isolation: no shared cookies, storage, or DOM between tests, so failures don’t carry over and you can run tests in any order or in parallel. Keep this default unless you have a clear reason to share state.

### Avoiding state leak in parallel runs

- **Do not** rely on shared mutable state (e.g. a single `page` or `context` in `beforeAll`) when tests can run in parallel. State from one test can leak into another and cause flaky, order-dependent failures.
- Use **fixtures** for setup/teardown and **`beforeEach`** for per-test navigation so each test gets a fresh page or a clean slate.
- For **backend or DB state** shared across tests, isolate per worker so parallel workers don’t collide. Use a worker-scoped fixture and `testInfo.workerIndex` (or `process.env.TEST_WORKER_INDEX`) to create unique data per worker (e.g. unique user or DB prefix). See [fixtures-hooks.md](../core/fixtures-hooks.md) for worker-scoped fixtures and [debugging.md](../debugging/debugging.md) for debugging flaky parallel runs.

### Debugging flaky parallel runs

If a test is flaky only with multiple workers:

1. **Reproduce**: Run with default workers and `--repeat-each=10` (or `--repeat-each=100 --max-failures=1`).
2. **Confirm parallel-specific**: Run with `--workers=1`. If the failure disappears, the cause is likely shared state or non-isolated backend/DB data.
3. **Fix**: Remove shared page/context; use per-test fixtures and `beforeEach`; isolate test data per worker with `workerIndex` in a worker-scoped fixture.

Workers are restarted after a test failure so subsequent tests in that worker get a clean environment; fixing isolation still prevents the initial flakiness.

## Resource Management

### Browser Contexts

```typescript
// Recommended: One context per test (default) — full isolation
test("isolated test", async ({ page }) => {
  // Fresh context automatically
});

// Manual context for specific needs
test("multiple tabs", async ({ browser }) => {
  const context = await browser.newContext();
  const page1 = await context.newPage();
  const page2 = await context.newPage();

  // Clean up
  await context.close();
});
```

### Memory Management

```typescript
// playwright.config.ts
export default defineConfig({
  // Limit concurrent workers
  workers: 2,

  // Limit parallel tests per worker
  use: {
    // Lower memory usage
    launchOptions: {
      args: ["--disable-dev-shm-usage"],
    },
  },
});
```

### Timeouts

```typescript
// playwright.config.ts
export default defineConfig({
  // Global test timeout
  timeout: 30000,

  // Assertion timeout
  expect: {
    timeout: 5000,
  },

  // Navigation timeout
  use: {
    navigationTimeout: 15000,
    actionTimeout: 10000,
  },
});
```

## Benchmarking

### Measure Test Duration

```typescript
test("performance test", async ({ page }, testInfo) => {
  const startTime = Date.now();

  await page.goto("/");

  const loadTime = Date.now() - startTime;
  console.log(`Page load: ${loadTime}ms`);

  // Add to test report
  testInfo.annotations.push({
    type: "performance",
    description: `Load time: ${loadTime}ms`,
  });
});
```

### Performance Metrics

```typescript
test("collect metrics", async ({ page }) => {
  await page.goto("/");

  const metrics = await page.evaluate(() => ({
    // Navigation timing
    loadTime:
      performance.timing.loadEventEnd - performance.timing.navigationStart,
    domContentLoaded:
      performance.timing.domContentLoadedEventEnd -
      performance.timing.navigationStart,

    // Performance entries
    resources: performance.getEntriesByType("resource").length,

    // Memory (Chrome only)
    // @ts-ignore
    memory: performance.memory?.usedJSHeapSize,
  }));

  console.log("Metrics:", metrics);
  expect(metrics.loadTime).toBeLessThan(3000);
});
```

### Lighthouse Integration

```typescript
import { playAudit } from "playwright-lighthouse";

test("lighthouse audit", async ({ page }) => {
  await page.goto("/");

  const audit = await playAudit({
    page,
    thresholds: {
      performance: 80,
      accessibility: 90,
      "best-practices": 80,
      seo: 80,
    },
    port: 9222,
  });

  expect(audit.lhr.categories.performance.score * 100).toBeGreaterThanOrEqual(
    80,
  );
});
```

## Performance Checklist

| Optimization                   | Impact     |
| ------------------------------ | ---------- |
| Enable `fullyParallel`         | High       |
| Reuse authentication           | High       |
| Mock heavy APIs                | High       |
| Block tracking scripts         | Medium     |
| Use sharding in CI             | High       |
| Reduce workers if memory-bound | Medium     |
| Cache API responses            | Medium     |
| Skip unnecessary tests         | Low-Medium |

## Related References

- **CI/CD sharding**: See [ci-cd.md](ci-cd.md) for CI configuration
- **Test organization**: See [test-suite-structure.md](../core/test-suite-structure.md) for structuring tests
- **Fixtures for reuse**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for authentication patterns
