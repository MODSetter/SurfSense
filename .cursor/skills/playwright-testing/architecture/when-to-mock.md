# Mocking Strategy: Real vs Mock Services

## Table of Contents

1. [Core Principle](#core-principle)
2. [Decision Matrix](#decision-matrix)
3. [Decision Flowchart](#decision-flowchart)
4. [Mocking Techniques](#mocking-techniques)
5. [Real Service Strategies](#real-service-strategies)
6. [Hybrid Approach: Fixture-Based Mock Control](#hybrid-approach-fixture-based-mock-control)
7. [Validating Mock Accuracy](#validating-mock-accuracy)
8. [Anti-Patterns](#anti-patterns)

> **When to use**: Deciding whether to mock API calls, intercept network requests, or hit real services in Playwright tests.

## Core Principle

**Mock at the boundary, test your stack end-to-end.** Mock third-party services you don't own (payment gateways, email providers, OAuth). Never mock your own frontend-to-backend communication. Tests should prove YOUR code works, not that third-party APIs are available.

## Decision Matrix

| Scenario | Mock? | Strategy |
| --- | --- | --- |
| Your own REST/GraphQL API | Never | Hit real API against staging or local dev |
| Your database (through your API) | Never | Seed via API or fixtures |
| Authentication (your auth system) | Mostly no | Use `storageState` to skip login in most tests |
| Stripe / payment gateway | Always | `route.fulfill()` with expected responses |
| SendGrid / email service | Always | Mock the API call, verify request payload |
| OAuth providers (Google, GitHub) | Always | Mock token exchange, test your callback handler |
| Analytics (Segment, Mixpanel) | Always | `route.abort()` or `route.fulfill()` |
| Maps / geocoding APIs | Always | Mock with static responses |
| Feature flags (LaunchDarkly) | Usually | Mock to force specific flag states |
| CDN / static assets | Never | Let them load normally |
| Flaky external dependency | CI: mock, local: real | Conditional mocking based on environment |
| Slow external dependency | Dev: mock, nightly: real | Separate test projects in config |

## Decision Flowchart

```text
Is this service part of YOUR codebase?
├── YES → Do NOT mock. Test the real integration.
│   ├── Is it slow? → Optimize the service, not the test.
│   └── Is it flaky? → Fix the service. Flaky infra is a bug.
└── NO → It's a third-party service.
    ├── Is it paid per call? → ALWAYS mock.
    ├── Is it rate-limited? → ALWAYS mock.
    ├── Is it slow or unreliable? → ALWAYS mock.
    └── Is it a complex multi-step flow? → Mock with HAR recording.
```

## Mocking Techniques

### Blocking Unwanted Requests

Block third-party scripts that slow tests and add no coverage:

```typescript
test.beforeEach(async ({ page }) => {
  await page.route('**/{analytics,tracking,segment,hotjar}.{com,io}/**', (route) => {
    route.abort();
  });
});

test('dashboard renders without tracking scripts', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
```

### Full Mock (route.fulfill)

Completely replace a third-party API response:

```typescript
test('order flow with mocked payment service', async ({ page }) => {
  await page.route('**/api/charge', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        transactionId: 'txn_mock_abc',
        status: 'completed',
      }),
    });
  });

  await page.goto('/order/confirm');
  await page.getByRole('button', { name: 'Complete Purchase' }).click();
  await expect(page.getByText('Order confirmed')).toBeVisible();
});

test('display error on payment decline', async ({ page }) => {
  await page.route('**/api/charge', (route) => {
    route.fulfill({
      status: 402,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'insufficient_funds', message: 'Card declined.' },
      }),
    });
  });

  await page.goto('/order/confirm');
  await page.getByRole('button', { name: 'Complete Purchase' }).click();
  await expect(page.getByRole('alert')).toContainText('Card declined');
});
```

### Partial Mock (Modify Responses)

Let the real API call happen but tweak the response:

```typescript
test('display low inventory warning', async ({ page }) => {
  await page.route('**/api/inventory/*', async (route) => {
    const response = await route.fetch();
    const data = await response.json();

    data.quantity = 1;
    data.lowStock = true;

    await route.fulfill({
      response,
      body: JSON.stringify(data),
    });
  });

  await page.goto('/products/widget-pro');
  await expect(page.getByText('Only 1 remaining')).toBeVisible();
});

test('inject test notification into real response', async ({ page }) => {
  await page.route('**/api/alerts', async (route) => {
    const response = await route.fetch();
    const data = await response.json();

    data.items.push({
      id: 'test-alert',
      text: 'Report generated',
      category: 'info',
    });

    await route.fulfill({
      response,
      body: JSON.stringify(data),
    });
  });

  await page.goto('/home');
  await expect(page.getByText('Report generated')).toBeVisible();
});
```

### Record and Replay (HAR Files)

For complex API sequences (OAuth flows, multi-step wizards):

**Recording:**

```typescript
test('capture API traffic for admin panel', async ({ page }) => {
  await page.routeFromHAR('tests/fixtures/admin-panel.har', {
    url: '**/api/**',
    update: true,
  });

  await page.goto('/admin');
  await page.getByRole('tab', { name: 'Reports' }).click();
  await page.getByRole('tab', { name: 'Settings' }).click();
});
```

**Replaying:**

```typescript
test('admin panel loads with recorded data', async ({ page }) => {
  await page.routeFromHAR('tests/fixtures/admin-panel.har', {
    url: '**/api/**',
    update: false,
  });

  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
});
```

**HAR maintenance:**

- Record against a known-good staging environment
- Commit `.har` files to version control
- Re-record when APIs change
- Scope HAR to specific URL patterns

## Real Service Strategies

### Local Dev Server

```typescript
// playwright.config.ts
export default defineConfig({
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  use: {
    baseURL: 'http://localhost:3000',
  },
});
```

### Staging Environment

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    baseURL: process.env.CI
      ? 'https://staging.example.com'
      : 'http://localhost:3000',
  },
});
```

### Test Containers

```typescript
// playwright.config.ts
export default defineConfig({
  webServer: {
    command: 'docker compose -f docker-compose.test.yml up --wait',
    url: 'http://localhost:3000/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  globalTeardown: './tests/global-teardown.ts',
});
```

```typescript
// tests/global-teardown.ts
import { execSync } from 'child_process';

export default function globalTeardown() {
  if (process.env.CI) {
    execSync('docker compose -f docker-compose.test.yml down -v');
  }
}
```

## Hybrid Approach: Fixture-Based Mock Control

Create fixtures that let individual tests opt into mocking specific services:

```typescript
// tests/fixtures/service-mocks.ts
import { test as base } from '@playwright/test';

type MockConfig = {
  mockPayments: boolean;
  mockNotifications: boolean;
  mockAnalytics: boolean;
};

export const test = base.extend<MockConfig>({
  mockPayments: [true, { option: true }],
  mockNotifications: [true, { option: true }],
  mockAnalytics: [true, { option: true }],

  page: async ({ page, mockPayments, mockNotifications, mockAnalytics }, use) => {
    if (mockPayments) {
      await page.route('**/api/billing/**', (route) => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'paid', id: 'inv_mock_789' }),
        });
      });
    }

    if (mockNotifications) {
      await page.route('**/api/notify', (route) => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ delivered: true }),
        });
      });
    }

    if (mockAnalytics) {
      await page.route('**/{segment,mixpanel,amplitude}.**/**', (route) => {
        route.abort();
      });
    }

    await use(page);
  },
});

export { expect } from '@playwright/test';
```

```typescript
// tests/billing.spec.ts
import { test, expect } from './fixtures/service-mocks';

test('subscription renewal sends notification', async ({ page }) => {
  await page.goto('/account/billing');
  await page.getByRole('button', { name: 'Renew Now' }).click();
  await expect(page.getByText('Subscription renewed')).toBeVisible();
});

test.describe('integration suite', () => {
  test.use({ mockPayments: false });

  test('real billing flow against test gateway', async ({ page }) => {
    await page.goto('/account/billing');
    await page.getByRole('button', { name: 'Renew Now' }).click();
    await expect(page.getByText('Subscription renewed')).toBeVisible();
  });
});
```

### Environment-Based Test Projects

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    {
      name: 'ci-fast',
      testMatch: '**/*.spec.ts',
      use: { baseURL: 'http://localhost:3000' },
    },
    {
      name: 'nightly-full',
      testMatch: '**/*.integration.spec.ts',
      use: { baseURL: 'https://staging.example.com' },
      timeout: 120_000,
    },
  ],
});
```

## Validating Mock Accuracy

Guard against mock drift from real APIs:

```typescript
test.describe('contract validation', () => {
  test('billing mock matches real API shape', async ({ request }) => {
    const realResponse = await request.post('/api/billing/charge', {
      data: { amount: 5000, currency: 'usd' },
    });
    const realBody = await realResponse.json();

    const mockBody = {
      status: 'paid',
      id: 'inv_mock_789',
    };

    expect(Object.keys(mockBody).sort()).toEqual(Object.keys(realBody).sort());

    for (const key of Object.keys(mockBody)) {
      expect(typeof mockBody[key]).toBe(typeof realBody[key]);
    }
  });
});
```

## Anti-Patterns

| Don't Do This | Problem | Do This Instead |
| --- | --- | --- |
| Mock your own API | Tests pass, app breaks. Zero integration coverage. | Hit your real API. Mock only third-party services. |
| Mock everything for speed | You test a fiction. Frontend and backend may be incompatible. | Mock only external boundaries. |
| Never mock anything | Tests are slow, flaky, fail when third parties have outages. | Mock third-party services. |
| Use outdated mocks | Mock returns different shape than real API. | Run contract validation tests. Re-record HAR files regularly. |
| Mock with `page.evaluate()` to stub fetch | Fragile, doesn't survive navigation. | Use `page.route()` which intercepts at network layer. |
| Copy-paste mocks across files | One API change requires updating many files. | Centralize mocks in fixtures. |
| Block all network and whitelist | Extremely brittle. Every new endpoint requires update. | Allow all by default. Selectively mock third-party services. |
