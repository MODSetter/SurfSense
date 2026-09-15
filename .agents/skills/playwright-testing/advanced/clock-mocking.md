# Date, Time & Clock Mocking

## Table of Contents

1. [Clock API Basics](#clock-api-basics)
2. [Fixed Time Testing](#fixed-time-testing)
3. [Time Advancement](#time-advancement)
4. [Timezone Testing](#timezone-testing)
5. [Timer Mocking](#timer-mocking)

## Clock API Basics

### Install Clock

```typescript
test("mock current time", async ({ page }) => {
  // Install clock before navigating
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });

  await page.goto("/dashboard");

  // Page sees January 15, 2025 as current date
  await expect(page.getByText("January 15, 2025")).toBeVisible();
});
```

### Clock with Fixture

```typescript
// fixtures/clock.fixture.ts
import { test as base } from "@playwright/test";

type ClockFixtures = {
  mockTime: (date: Date | string) => Promise<void>;
};

export const test = base.extend<ClockFixtures>({
  mockTime: async ({ page }, use) => {
    await use(async (date) => {
      const time = typeof date === "string" ? new Date(date) : date;
      await page.clock.install({ time });
    });
  },
});

// Usage
test("subscription expiry", async ({ page, mockTime }) => {
  await mockTime("2025-12-31T23:59:00");
  await page.goto("/subscription");

  await expect(page.getByText("Expires today")).toBeVisible();
});
```

## Fixed Time Testing

### Test Date-Dependent Features

```typescript
test("show holiday banner in December", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-12-20T10:00:00") });

  await page.goto("/");

  await expect(page.getByRole("banner", { name: /holiday/i })).toBeVisible();
});

test("no holiday banner in January", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T10:00:00") });

  await page.goto("/");

  await expect(page.getByRole("banner", { name: /holiday/i })).toBeHidden();
});
```

### Test Relative Time Display

```typescript
test("shows relative time correctly", async ({ page }) => {
  // Fix time to control "posted 2 hours ago" text
  await page.clock.install({ time: new Date("2025-06-15T14:00:00") });

  // Mock API to return post with known timestamp
  await page.route("**/api/posts/1", (route) =>
    route.fulfill({
      json: {
        id: 1,
        title: "Test Post",
        createdAt: "2025-06-15T12:00:00Z", // 2 hours before mock time
      },
    }),
  );

  await page.goto("/posts/1");

  await expect(page.getByText("2 hours ago")).toBeVisible();
});
```

### Test Date Boundaries

```typescript
test.describe("end of month billing", () => {
  test("shows billing on last day of month", async ({ page }) => {
    await page.clock.install({ time: new Date("2025-01-31T10:00:00") });
    await page.goto("/billing");

    await expect(page.getByText("Payment due today")).toBeVisible();
  });

  test("shows days remaining mid-month", async ({ page }) => {
    await page.clock.install({ time: new Date("2025-01-15T10:00:00") });
    await page.goto("/billing");

    await expect(page.getByText("16 days until payment")).toBeVisible();
  });
});
```

## Time Advancement

### Advance Time Manually

```typescript
test("session timeout warning", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
  await page.goto("/dashboard");

  // Advance 25 minutes (session timeout at 30 min)
  await page.clock.fastForward("25:00");

  await expect(page.getByText("Session expires in 5 minutes")).toBeVisible();

  // Advance 5 more minutes
  await page.clock.fastForward("05:00");

  await expect(page.getByText("Session expired")).toBeVisible();
});
```

### Pause and Resume Time

```typescript
test("countdown timer", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
  await page.goto("/sale");

  // Initial state
  await expect(page.getByText("Sale ends in 2:00:00")).toBeVisible();

  // Advance 1 hour
  await page.clock.fastForward("01:00:00");

  await expect(page.getByText("Sale ends in 1:00:00")).toBeVisible();

  // Advance past end
  await page.clock.fastForward("01:00:01");

  await expect(page.getByText("Sale ended")).toBeVisible();
});
```

### Run Pending Timers

```typescript
test("debounced search", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
  await page.goto("/search");

  await page.getByLabel("Search").fill("playwright");

  // Search is debounced by 300ms, won't fire yet
  await expect(page.getByTestId("search-results")).toBeHidden();

  // Fast forward past debounce
  await page.clock.fastForward(300);

  // Now search should execute
  await expect(page.getByTestId("search-results")).toBeVisible();
});
```

## Timezone Testing

### Test Different Timezones

```typescript
test.describe("timezone display", () => {
  test("shows correct time in PST", async ({ browser }) => {
    const context = await browser.newContext({
      timezoneId: "America/Los_Angeles",
    });
    const page = await context.newPage();

    await page.clock.install({ time: new Date("2025-01-15T17:00:00Z") }); // 5 PM UTC

    await page.goto("/schedule");

    // Should show 9 AM PST
    await expect(page.getByText("9:00 AM")).toBeVisible();

    await context.close();
  });

  test("shows correct time in JST", async ({ browser }) => {
    const context = await browser.newContext({
      timezoneId: "Asia/Tokyo",
    });
    const page = await context.newPage();

    await page.clock.install({ time: new Date("2025-01-15T17:00:00Z") }); // 5 PM UTC

    await page.goto("/schedule");

    // Should show 2 AM next day JST
    await expect(page.getByText("2:00 AM")).toBeVisible();

    await context.close();
  });
});
```

### Timezone Fixture

```typescript
// fixtures/timezone.fixture.ts
import { test as base } from "@playwright/test";

type TimezoneFixtures = {
  pageInTimezone: (timezone: string) => Promise<Page>;
};

export const test = base.extend<TimezoneFixtures>({
  pageInTimezone: async ({ browser }, use) => {
    const pages: Page[] = [];

    await use(async (timezone) => {
      const context = await browser.newContext({ timezoneId: timezone });
      const page = await context.newPage();
      pages.push(page);
      return page;
    });

    // Cleanup
    for (const page of pages) {
      await page.context().close();
    }
  },
});
```

## Timer Mocking

### Mock setInterval

```typescript
test("auto-refresh data", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });

  let apiCalls = 0;
  await page.route("**/api/data", (route) => {
    apiCalls++;
    route.fulfill({ json: { value: apiCalls } });
  });

  await page.goto("/live-data"); // Sets up 30s refresh interval

  expect(apiCalls).toBe(1); // Initial load

  // Advance 30 seconds
  await page.clock.fastForward("00:30");
  expect(apiCalls).toBe(2); // First refresh

  // Advance another 30 seconds
  await page.clock.fastForward("00:30");
  expect(apiCalls).toBe(3); // Second refresh
});
```

### Mock setTimeout Chains

```typescript
test("notification queue", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
  await page.goto("/notifications");

  // Trigger 3 notifications that show sequentially
  await page.getByRole("button", { name: "Show All" }).click();

  // First notification appears immediately
  await expect(page.getByText("Notification 1")).toBeVisible();

  // Second appears after 2 seconds
  await page.clock.fastForward("00:02");
  await expect(page.getByText("Notification 2")).toBeVisible();

  // Third appears after 2 more seconds
  await page.clock.fastForward("00:02");
  await expect(page.getByText("Notification 3")).toBeVisible();
});
```

### Test Animation Frames

```typescript
test("animation completes", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
  await page.goto("/animation-demo");

  await page.getByRole("button", { name: "Animate" }).click();

  // Animation runs for 500ms
  const element = page.getByTestId("animated-box");
  await expect(element).toHaveCSS("opacity", "0");

  // Fast forward through animation
  await page.clock.fastForward(500);

  await expect(element).toHaveCSS("opacity", "1");
});
```

## Best Practices

### Always Install Clock Before Navigation

```typescript
// Good
test("date test", async ({ page }) => {
  await page.clock.install({ time: new Date("2025-01-15") });
  await page.goto("/"); // Page loads with mocked time
});

// Bad - time already captured by page
test("date test", async ({ page }) => {
  await page.goto("/");
  await page.clock.install({ time: new Date("2025-01-15") }); // Too late!
});
```

### Use ISO Strings for Clarity

```typescript
// Good - explicit timezone
await page.clock.install({ time: new Date("2025-01-15T09:00:00Z") });

// Ambiguous - uses local timezone
await page.clock.install({ time: new Date("2025-01-15T09:00:00") });
```

## Anti-Patterns to Avoid

| Anti-Pattern                             | Problem                         | Solution                               |
| ---------------------------------------- | ------------------------------- | -------------------------------------- |
| Installing clock after navigation        | Page already captured real time | Install clock before `goto()`          |
| Hardcoded relative dates                 | Tests break over time           | Use fixed dates with clock mock        |
| Not accounting for timezone              | Tests fail in different regions | Use explicit UTC times or set timezone |
| Using `waitForTimeout` with mocked clock | Conflicts with mocked timers    | Use `fastForward` instead              |

## Related References

- **Assertions**: See [assertions-waiting.md](../core/assertions-waiting.md) for time-based assertions
- **Fixtures**: See [fixtures-hooks.md](../core/fixtures-hooks.md) for clock fixtures
