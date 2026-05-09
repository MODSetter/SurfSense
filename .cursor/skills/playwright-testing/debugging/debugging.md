# Debugging & Troubleshooting

## Table of Contents

1. [Debug Tools](#debug-tools)
2. [Trace Viewer](#trace-viewer)
3. [Identifying Flaky Tests](#identifying-flaky-tests)
4. [Debugging Network Issues](#debugging-network-issues)
5. [Debugging in CI](#debugging-in-ci)
6. [Debugging Authentication](#debugging-authentication)
7. [Debugging Screenshots](#debugging-screenshots)
8. [Common Issues](#common-issues)
9. [Logging](#logging)

## Debug Tools

### Playwright Inspector

```bash
# Run with inspector
PWDEBUG=1 npx playwright test
# Or specific test
PWDEBUG=1 npx playwright test login.spec.ts
```

Features:

- Step through test actions
- Pick locators visually
- Inspect DOM state
- Edit and re-run

### Headed Mode

```bash
# Run with visible browser
npx playwright test --headed

# Interactive debugging (headed, paused, step-through)
npx playwright test --debug
```

You can also set `slowMo` to add an `N` ms delay per action, making test execution easier to follow while debugging.

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    launchOptions: {
      slowMo: 500,
    },
  },
});
```

### UI Mode

```bash
# Interactive test runner
npx playwright test --ui
```

Features:

- Watch mode
- Test timeline
- DOM snapshots
- Network logs
- Console logs

### Debug in Code

```typescript
test("debug example", async ({ page }) => {
  await page.goto("/");

  // Pause and open inspector
  await page.pause();

  // Continue test...
  await page.click("button");
});
```

## Trace Viewer

### Enable Traces

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    trace: "on-first-retry", // Record on retry
    // trace: 'on',                 // Always record
    // trace: 'retain-on-failure',  // Keep only failures
  },
});
```

### View Traces

```bash
# Open trace file
npx playwright show-trace trace.zip

# From test-results
npx playwright show-trace test-results/test-name/trace.zip
```

### Trace Contents

- Screenshots at each action
- DOM snapshots
- Network requests/responses
- Console logs
- Action timeline
- Source code

### Programmatic Traces

```typescript
test("manual trace", async ({ page, context }) => {
  await context.tracing.start({ screenshots: true, snapshots: true });

  await page.goto("/");
  await page.click("button");

  await context.tracing.stop({ path: "trace.zip" });
});
```

## Identifying Flaky Tests

If a test fails intermittently, it's likely flaky. Quick checks:

| Behavior                               | Likely Cause                  | Next Step                              |
| -------------------------------------- | ----------------------------- | -------------------------------------- |
| Fails sometimes, passes other times    | Flaky - timing/race condition | [flaky-tests.md](flaky-tests.md)       |
| Fails only with multiple workers       | Flaky - parallelism/isolation | [flaky-tests.md](flaky-tests.md)       |
| Fails only in CI                       | Environment difference        | [CI Debugging](#debugging-in-ci) below |
| Always fails                           | Bug in test or app            | Debug with tools above                 |
| Always passes locally, always fails CI | CI-specific issue             | [ci-cd.md](../infrastructure-ci-cd/ci-cd.md)                   |

> **For flaky test detection commands, root cause analysis, and fixing strategies**, see [flaky-tests.md](flaky-tests.md).

## Debugging Network Issues

### Monitor All Requests

```typescript
test("debug network", async ({ page }) => {
  const requests: string[] = [];
  const failures: string[] = [];

  page.on("request", (req) => requests.push(`>> ${req.method()} ${req.url()}`));
  page.on("requestfinished", (req) => {
    const resp = req.response();
    requests.push(`<< ${resp?.status()} ${req.url()}`);
  });
  page.on("requestfailed", (req) => {
    failures.push(`FAILED: ${req.url()} - ${req.failure()?.errorText}`);
  });

  await page.goto("/dashboard");

  // Log summary
  console.log("Requests:", requests.length);
  if (failures.length) console.log("Failures:", failures);
});
```

### Wait for Specific API Response

When debugging network-dependent issues, wait for specific API responses instead of arbitrary timeouts.

```typescript
// Start waiting BEFORE triggering the request
const responsePromise = page.waitForResponse(
  (resp) => resp.url().includes("/api/data") && resp.status() === 200,
);
await page.getByRole("button", { name: "Load" }).click();
const response = await responsePromise;
console.log("Status:", response.status());
```

> **For comprehensive waiting patterns** (navigation, element state, network, polling), see [assertions-waiting.md](../core/assertions-waiting.md#waiting-strategies).

### Debug Slow Requests

```typescript
test("find slow requests", async ({ page }) => {
  page.on("requestfinished", (request) => {
    const timing = request.timing();
    const total = timing.responseEnd - timing.requestStart;
    if (total > 1000) {
      console.log(`SLOW (${total}ms): ${request.url()}`);
    }
  });

  await page.goto("/");
});
```

## Debugging in CI

### Simulate CI Locally

```bash
# Run in headless mode like CI
CI=true npx playwright test

# Match CI browser versions
npx playwright install --with-deps

# Run in Docker (same as CI)
docker run --rm -v $(pwd):/work -w /work \
  mcr.microsoft.com/playwright:v1.40.0-jammy \
  npx playwright test
```

### CI-Specific Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  // More artifacts in CI for debugging
  use: {
    trace: process.env.CI ? "on-first-retry" : "off",
    video: process.env.CI ? "retain-on-failure" : "off",
    screenshot: process.env.CI ? "only-on-failure" : "off",
  },

  // More retries in CI (but investigate failures!)
  retries: process.env.CI ? 2 : 0,
});
```

### Debug CI Environment

```typescript
test("CI environment check", async ({ page }, testInfo) => {
  console.log("CI:", process.env.CI);
  console.log("Project:", testInfo.project.name);
  console.log("Worker:", testInfo.workerIndex);
  console.log("Retry:", testInfo.retry);
  console.log("Base URL:", testInfo.project.use.baseURL);

  // Check viewport
  const viewport = page.viewportSize();
  console.log("Viewport:", viewport);
});
```

## Debugging Authentication

```typescript
test("debug auth", async ({ page, context }) => {
  // Inspect current storage state
  const storage = await context.storageState();
  console.log(
    "Cookies:",
    storage.cookies.map((c) => c.name),
  );

  // Check if auth cookies are present
  const cookies = await context.cookies();
  const authCookie = cookies.find((c) => c.name.includes("session"));
  console.log("Auth cookie:", authCookie ? "present" : "MISSING");

  await page.goto("/protected");

  // Check if redirected to login (auth failed)
  if (page.url().includes("/login")) {
    console.error("Auth failed - redirected to login");
    // Save state for inspection
    await context.storageState({ path: "debug-auth.json" });
  }
});
```

## Debugging Screenshots

### Compare Visual State

```typescript
test("visual debug", async ({ page }, testInfo) => {
  await page.goto("/");

  // Screenshot before action
  await page.screenshot({
    path: testInfo.outputPath("before.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Open Menu" }).click();

  // Screenshot after action
  await page.screenshot({
    path: testInfo.outputPath("after.png"),
    fullPage: true,
  });

  // Attach to report
  await testInfo.attach("before", {
    path: testInfo.outputPath("before.png"),
    contentType: "image/png",
  });
});
```

### Screenshot Specific Element

```typescript
test("element screenshot", async ({ page }) => {
  await page.goto("/");

  const element = page.getByTestId("problem-area");

  // Screenshot just the element
  await element.screenshot({ path: "element-debug.png" });

  // Highlight element in full page screenshot
  await element.evaluate((el) => (el.style.border = "3px solid red"));
  await page.screenshot({ path: "highlighted.png" });
});
```

## Common Issues

### Element Not Found

```typescript
// Debug: Check if element exists
console.log(await page.getByRole("button").count());

// Debug: Log all buttons
const buttons = await page.getByRole("button").all();
for (const button of buttons) {
  console.log(await button.textContent());
}

// Debug: Screenshot before action
await page.screenshot({ path: "debug.png" });
await page.getByRole("button").click();
```

### Timeout Issues

```typescript
// Increase timeout for slow operations
await expect(page.getByText("Loaded")).toBeVisible({ timeout: 30000 });

// Global timeout increase
test.setTimeout(60000);

// Check what's blocking
test("debug timeout", async ({ page }) => {
  await page.goto("/slow-page");

  // Log network activity
  page.on("request", (request) => console.log(">>", request.url()));
  page.on("response", (response) =>
    console.log("<<", response.url(), response.status()),
  );
});
```

### Selector Issues

```typescript
// Debug: Highlight element
await page.getByRole("button").highlight();

// Debug: Evaluate selector in browser console
// Run in Inspector console:
// playwright.locator('button').first().highlight()

// Debug: Get element info
const element = page.getByRole("button");
console.log("Count:", await element.count());
console.log("Visible:", await element.isVisible());
console.log("Enabled:", await element.isEnabled());
```

### Frame Issues

```typescript
// Debug: List all frames
for (const frame of page.frames()) {
  console.log("Frame:", frame.url());
}

// Debug: Check if element is in iframe
const frame = page.frameLocator("iframe").first();
console.log(await frame.getByRole("button").count());
```

## Logging

### Capture Browser Console

```typescript
test("with logging", async ({ page }) => {
  page.on("console", (msg) => console.log("Browser:", msg.text()));
  page.on("pageerror", (error) => console.log("Page error:", error.message));
  await page.goto("/");
});
```

> **For comprehensive console error handling** (fail on errors, allowed patterns, fixtures), see [console-errors.md](console-errors.md).

### Custom Test Attachments

```typescript
test("with attachments", async ({ page }, testInfo) => {
  // Attach screenshot to report
  const screenshot = await page.screenshot();
  await testInfo.attach("screenshot", {
    body: screenshot,
    contentType: "image/png",
  });

  // Attach logs or data
  await testInfo.attach("logs", {
    body: "Custom log data",
    contentType: "text/plain",
  });

  // Use testInfo for output paths
  const outputPath = testInfo.outputPath("debug-file.json");
});
```

## Troubleshooting Checklist

### By Symptom

| Symptom                                       | Common Causes                                                | Quick Fixes                                                         | Reference                                                                  |
| --------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Element not found**                         | Wrong selector, element not visible, in iframe, timing issue | Check locator with Inspector, wait for visibility, use frameLocator | [locators.md](../core/locators.md), [assertions-waiting.md](../core/assertions-waiting.md) |
| **Timeout errors**                            | Slow network, heavy page load, waiting for wrong condition   | Increase timeout, wait for specific response, check network tab     | [assertions-waiting.md](../core/assertions-waiting.md)                             |
| **Flaky tests**                               | Race conditions, shared state, timing dependencies           | See comprehensive flaky test guide                                  | [flaky-tests.md](flaky-tests.md)                                           |
| **Tests pass locally, fail in CI**            | Environment differences, missing dependencies, timing        | Simulate CI locally, check CI logs, verify environment vars         | [ci-cd.md](../infrastructure-ci-cd/ci-cd.md), [flaky-tests.md](flaky-tests.md)                     |
| **Slow test execution**                       | Not parallelized, heavy network calls, unnecessary waits     | Enable parallelization, mock APIs, optimize waits                   | [performance.md](../infrastructure-ci-cd/performance.md)                                           |
| **Selector works in browser but not in test** | Element not attached, wrong context, dynamic content         | Use auto-waiting, check iframe, verify element state                | [locators.md](../core/locators.md)                                                 |
| **Test fails on retry**                       | Non-deterministic data, external dependencies                | Use test data fixtures, mock external services                      | [fixtures-hooks.md](../core/fixtures-hooks.md)                                     |

### Step-by-Step Debugging Process

1. **Reproduce the issue**

   ```bash
   # Run with trace enabled
   npx playwright test tests/failing.spec.ts --trace on

   # If intermittent, run multiple times
   npx playwright test --repeat-each=10
   ```

2. **Inspect the failure**

   ```bash
   # View trace
   npx playwright show-trace test-results/path-to-trace.zip

   # Run in headed mode to watch
   npx playwright test --headed

   # Use inspector for step-by-step
   PWDEBUG=1 npx playwright test
   ```

3. **Isolate the problem**

   ```typescript
   // Add debugging points
   await page.pause();

   // Log element state
   console.log("Element count:", await page.getByRole("button").count());
   console.log("Element visible:", await page.getByRole("button").isVisible());

   // Take screenshot at failure point
   await page.screenshot({ path: "debug.png" });
   ```

4. **Check related areas**
   - Network requests: Are API calls completing? (see [Debugging Network Issues](#debugging-network-issues))
   - Timing: Is auto-waiting working correctly?
   - State: Is the test isolated? (see [flaky-tests.md](flaky-tests.md))
   - Environment: Does it work locally but fail in CI? (see [Debugging in CI](#debugging-in-ci))

5. **Apply fix and verify**
   - Fix the root cause (not just symptoms)
   - Run multiple times to confirm stability: `--repeat-each=10`
   - Check related tests aren't affected

## Related References

- **Flaky tests**: See [flaky-tests.md](flaky-tests.md) for comprehensive flaky test guide
- **Locator issues**: See [locators.md](../core/locators.md) for selector strategies
- **Waiting problems**: See [assertions-waiting.md](../core/assertions-waiting.md) for waiting patterns
- **Test isolation**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for fixtures and isolation
- **CI issues**: See [ci-cd.md](../infrastructure-ci-cd/ci-cd.md) for CI configuration
