# Playwright Configuration

## Table of Contents

1. [CLI Quick Reference](#cli-quick-reference)
2. [Decision Guide](#decision-guide)
3. [Production-Ready Config](#production-ready-config)
4. [Patterns](#patterns)
5. [Anti-Patterns](#anti-patterns)
6. [Troubleshooting](#troubleshooting)
7. [Related](#related)

> **When to use**: Setting up a new project, adjusting timeouts, adding browser targets, configuring CI behavior, or managing environment-specific settings.

## CLI Quick Reference

```bash
npx playwright init                           # scaffold config + first test
npx playwright test --config=custom.config.ts # use alternate config
npx playwright test --project=chromium        # run single project
npx playwright test --reporter=html           # override reporter
npx playwright test --grep @smoke             # run tests tagged @smoke
npx playwright test --grep-invert @slow       # exclude @slow tests
npx playwright show-report                    # open last HTML report
DEBUG=pw:api npx playwright test              # verbose logging
```

## Decision Guide

### Timeout Selection

| Symptom | Setting | Default | Recommended |
|---------|---------|---------|-------------|
| Test takes too long overall | `timeout` | 30s | 30-60s (max 120s) |
| Assertion retries too long/short | `expect.timeout` | 5s | 5-10s |
| `page.goto()` or `waitForURL()` times out | `navigationTimeout` | 30s | 10-30s |
| `click()`, `fill()` time out | `actionTimeout` | 0 (unlimited) | 10-15s |
| Dev server slow to start | `webServer.timeout` | 60s | 60-180s |

### Server Management

| Scenario | Approach |
|----------|----------|
| App in same repo | `webServer` with `reuseExistingServer: !process.env.CI` |
| Separate repos | Manual start or Docker Compose |
| Testing deployed environment | No `webServer`; set `baseURL` via env |
| Multiple services | Array of `webServer` entries |

### Single vs Multi-Project

| Scenario | Approach |
|----------|----------|
| Early development | Single project (chromium only) |
| Pre-release validation | Multi-project: chromium + firefox + webkit |
| Mobile-responsive app | Add mobile projects alongside desktop |
| Auth + non-auth tests | Setup project with dependencies |
| Tight CI budget | Chromium on PRs; all browsers on main |

### globalSetup vs Setup Projects vs Fixtures

| Need | Use |
|------|-----|
| One-time DB seed | `globalSetup` |
| Shared browser auth | Setup project with `dependencies` |
| Per-test isolated state | Custom fixture via `test.extend()` |
| Cleanup after all tests | `globalTeardown` |

## Production-Ready Config

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '.env') });

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? '50%' : undefined,

  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['github']]
    : [['html', { open: 'on-failure' }]],

  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:4000',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'en-US',
    timezoneId: 'America/Los_Angeles',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] } },
    { name: 'mobile-safari', use: { ...devices['iPhone 14'] } },
  ],

  webServer: {
    command: 'npm run start',
    url: 'http://localhost:4000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
```

## Patterns

### Environment-Specific Configuration

**Use when**: Tests run against dev, staging, and production environments.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

const ENV = process.env.TEST_ENV || 'local';
dotenv.config({ path: path.resolve(__dirname, `.env.${ENV}`) });

const envConfig: Record<string, { baseURL: string; retries: number }> = {
  local:   { baseURL: 'http://localhost:4000',      retries: 0 },
  staging: { baseURL: 'https://staging.myapp.com',  retries: 2 },
  prod:    { baseURL: 'https://myapp.com',          retries: 2 },
};

export default defineConfig({
  testDir: './e2e',
  retries: envConfig[ENV].retries,
  use: { baseURL: envConfig[ENV].baseURL },
});
```

```bash
TEST_ENV=staging npx playwright test
TEST_ENV=prod npx playwright test --grep @smoke
```

### Setup Project with Dependencies

**Use when**: Tests need shared authentication state before running.

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'playwright/.auth/session.json',
      },
      dependencies: ['setup'],
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        storageState: 'playwright/.auth/session.json',
      },
      dependencies: ['setup'],
    },
  ],
});
```

```ts
// e2e/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/session.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('testuser@example.com');
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible();
  await page.context().storageState({ path: authFile });
});
```

### webServer with Build Step

**Use when**: Tests need a running application server managed by Playwright.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://localhost:4000' },
  webServer: {
    command: process.env.CI
      ? 'npm run build && npm run preview'
      : 'npm run dev',
    url: 'http://localhost:4000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NODE_ENV: 'test',
      DB_URL: process.env.DB_URL || 'postgresql://localhost:5432/testdb',
    },
  },
});
```

### globalSetup / globalTeardown

**Use when**: One-time non-browser work like seeding a database. Runs once per test run.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/setup.ts',
  globalTeardown: './e2e/teardown.ts',
});
```

```ts
// e2e/setup.ts
import { FullConfig } from '@playwright/test';

export default async function globalSetup(config: FullConfig) {
  const { execSync } = await import('child_process');
  execSync('npx prisma db seed', { stdio: 'inherit' });
  process.env.TEST_RUN_ID = `run-${Date.now()}`;
}
```

```ts
// e2e/teardown.ts
import { FullConfig } from '@playwright/test';

export default async function globalTeardown(config: FullConfig) {
  const { execSync } = await import('child_process');
  execSync('npx prisma db push --force-reset', { stdio: 'inherit' });
}
```

### Environment Variables with .env

**Use when**: Managing secrets, URLs, or feature flags without hardcoding.

```bash
# .env.example (commit this)
BASE_URL=http://localhost:4000
TEST_PASSWORD=
API_KEY=

# .env.local (gitignored)
BASE_URL=http://localhost:4000
TEST_PASSWORD=secret123
API_KEY=dev-key-abc

# .env.staging (gitignored)
BASE_URL=https://staging.myapp.com
TEST_PASSWORD=staging-pass
API_KEY=staging-key-xyz
```

```bash
# .gitignore
.env
.env.local
.env.staging
.env.production
playwright/.auth/
```

Install dotenv:

```bash
npm install -D dotenv
```

### Tag-Based Test Filtering

**Use when**: Running subsets of tests in different CI stages (PR vs nightly).

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',

  // Filter by tags in CI
  grep: process.env.CI ? /@smoke|@critical/ : undefined,
  grepInvert: process.env.CI ? /@flaky/ : undefined,
});
```

**Project-specific filtering:**

```ts
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  projects: [
    {
      name: 'smoke',
      grep: /@smoke/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'regression',
      grepInvert: /@smoke/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'critical-only',
      grep: /@critical/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

```bash
# Run specific project
npx playwright test --project=smoke
npx playwright test --project=regression
```

### Artifact Collection Strategy

| Setting | Local | CI | Reason |
|---------|-------|-----|--------|
| `trace` | `'off'` | `'on-first-retry'` | Traces are large; collect on failure only |
| `screenshot` | `'off'` | `'only-on-failure'` | Useful for CI debugging |
| `video` | `'off'` | `'retain-on-failure'` | Recording slows tests |

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: {
    trace: process.env.CI ? 'on-first-retry' : 'off',
    screenshot: process.env.CI ? 'only-on-failure' : 'off',
    video: process.env.CI ? 'retain-on-failure' : 'off',
  },
});
```

## Anti-Patterns

| Don't | Problem | Do Instead |
|-------|---------|------------|
| `timeout: 300_000` globally | Masks flaky tests; slow CI | Fix root cause; keep 30s default |
| Hardcoded URLs: `page.goto('http://localhost:4000/login')` | Breaks in other environments | Use `baseURL` + relative paths |
| All browsers on every PR | 3x CI time | Chromium on PRs; all on main |
| `trace: 'on'` always | Huge artifacts, slow uploads | `trace: 'on-first-retry'` |
| `video: 'on'` always | Massive storage; slow tests | `video: 'retain-on-failure'` |
| Config in test files: `test.use({ viewport: {...} })` everywhere | Scattered, inconsistent | Define once in project config |
| `retries: 3` locally | Hides flakiness | `retries: 0` local, `retries: 2` CI |
| No `forbidOnly` in CI | Committed `test.only` runs single test | `forbidOnly: !!process.env.CI` |
| `globalSetup` for browser auth | No browser context available | Use setup project with dependencies |
| Committing `.env` with credentials | Security risk | Commit `.env.example` only |

## Troubleshooting

### baseURL Not Working

**Cause**: Using absolute URL in `page.goto()` ignores `baseURL`.

```ts
// Wrong - ignores baseURL
await page.goto('http://localhost:4000/dashboard');

// Correct - uses baseURL
await page.goto('/dashboard');
```

### webServer Starts But Tests Get Connection Refused

**Cause**: `webServer.url` doesn't match actual server address or health check returns non-200.

```ts
webServer: {
  command: 'npm run dev',
  url: 'http://localhost:4000/api/health',  // use real endpoint
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
},
```

### Tests Pass Locally But Timeout in CI

**Cause**: CI machines are slower. Increase timeouts and reduce workers:

```ts
export default defineConfig({
  workers: process.env.CI ? '50%' : undefined,
  use: {
    navigationTimeout: process.env.CI ? 30_000 : 15_000,
    actionTimeout: process.env.CI ? 15_000 : 10_000,
  },
});
```

### "Target page, context or browser has been closed"

**Cause**: Test exceeded `timeout` and Playwright tore down browser during action.

**Fix**: Don't increase global timeout. Find slow step using trace:

```bash
npx playwright test --trace on
npx playwright show-report
```

## Related

- [test-tags.md](./test-tags.md) - tagging and filtering tests with `--grep`
- [fixtures-hooks.md](./fixtures-hooks.md) - custom fixtures for per-test state
- [test-suite-structure.md](test-suite-structure.md) - file structure and naming
- [authentication.md](../advanced/authentication.md) - setup projects for shared auth
- [projects-dependencies.md](./projects-dependencies.md) - advanced multi-project patterns
