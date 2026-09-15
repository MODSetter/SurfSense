# Next.js Testing Patterns

## Table of Contents

1. [Setup](#setup)
2. [App Router Patterns](#app-router-patterns)
3. [Pages Router Patterns](#pages-router-patterns)
4. [Dynamic Routes](#dynamic-routes)
5. [API Routes](#api-routes)
6. [Middleware Testing](#middleware-testing)
7. [Hydration Testing](#hydration-testing)
8. [next/image Testing](#nextimage-testing)
9. [NextAuth.js Authentication](#nextauthjs-authentication)
10. [Tips](#tips)
11. [Anti-Patterns](#anti-patterns)
12. [Related](#related)

> **When to use**: Testing Next.js applications with App Router, Pages Router, API routes, middleware, SSR, dynamic routes, and server components.
> **Prerequisites**: [configuration.md](../core/configuration.md), [locators.md](../core/locators.md)

## Setup

### Configuration with webServer

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? '50%' : undefined,

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 14'] } },
  ],

  webServer: {
    command: process.env.CI
      ? 'npm run build && npm run start'
      : 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NODE_ENV: process.env.CI ? 'production' : 'test',
    },
  },
});
```

### Environment Variables

Next.js loads `.env.test` when `NODE_ENV=test`:

```bash
# .env.test (commit this)
NEXT_PUBLIC_API_URL=http://localhost:3000/api
DATABASE_URL=postgresql://localhost:5432/test_db

# .env.test.local (gitignored)
NEXTAUTH_SECRET=test-secret-local
```

## App Router Patterns

### Server Component Content

```typescript
test('renders server component content', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Welcome', level: 1 })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
});
```

### Loading States with Streaming

```typescript
test('loading state during data streaming', async ({ page }) => {
  await page.route('**/api/stats', async (route) => {
    await new Promise((r) => setTimeout(r, 2000));
    await route.continue();
  });

  await page.goto('/dashboard');

  await expect(page.getByRole('progressbar')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByRole('progressbar')).toBeHidden();
});
```

### Nested Layouts

```typescript
test('layouts persist across navigation', async ({ page }) => {
  await page.goto('/dashboard/analytics');

  const sidebar = page.getByRole('navigation', { name: 'Dashboard' });
  await expect(sidebar).toBeVisible();

  await sidebar.getByRole('link', { name: 'Settings' }).click();
  await page.waitForURL('/dashboard/settings');

  await expect(sidebar).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
});
```

## Pages Router Patterns

### SSR with getServerSideProps

```typescript
test('page with getServerSideProps renders data', async ({ page }) => {
  await page.goto('/blog');

  await expect(page.getByRole('heading', { name: 'Blog', level: 1 })).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(10);
  await expect(page.getByRole('article').first()).toContainText(/\w+/);
});
```

### Static Generation with getStaticProps

```typescript
test('static page shows pre-rendered content', async ({ page }) => {
  await page.goto('/about');

  await expect(page.getByRole('heading', { name: 'About Us' })).toBeVisible();
  await expect(page.getByText('Founded in 2020')).toBeVisible();
});
```

## Dynamic Routes

### Slug Parameters

```typescript
test('dynamic [slug] renders correct content', async ({ page }) => {
  await page.goto('/blog/testing-guide');

  await expect(page.getByRole('heading', { level: 1 })).toContainText('Testing Guide');
  await expect(page.getByText('Page not found')).toBeHidden();
});

test('non-existent slug shows 404', async ({ page }) => {
  const response = await page.goto('/blog/nonexistent-post');

  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', { name: '404' })).toBeVisible();
});
```

### Catch-All Routes

```typescript
test('catch-all handles nested paths', async ({ page }) => {
  await page.goto('/docs/getting-started/installation');
  await expect(page.getByRole('heading', { name: 'Installation' })).toBeVisible();

  await page.goto('/docs/api/configuration');
  await expect(page.getByRole('heading', { name: 'Configuration' })).toBeVisible();
});
```

### Query Parameters

```typescript
test('query parameters filter content', async ({ page }) => {
  await page.goto('/products?category=electronics&sort=price-asc');

  await expect(page.getByRole('heading', { name: 'Electronics' })).toBeVisible();

  const prices = await page.getByTestId('product-price').allTextContents();
  const numericPrices = prices.map((p) => parseFloat(p.replace('$', '')));
  expect(numericPrices).toEqual([...numericPrices].sort((a, b) => a - b));
});
```

## API Routes

### Direct API Testing

```typescript
test('GET /api/products returns list', async ({ request }) => {
  const response = await request.get('/api/products');

  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.products).toBeInstanceOf(Array);
  expect(body.products[0]).toHaveProperty('id');
  expect(body.products[0]).toHaveProperty('name');
});

test('POST /api/products creates item', async ({ request }) => {
  const response = await request.post('/api/products', {
    data: { name: 'Test Product', price: 29.99 },
  });

  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.product.name).toBe('Test Product');
});

test('POST /api/products validates fields', async ({ request }) => {
  const response = await request.post('/api/products', {
    data: { name: '' },
  });

  expect(response.status()).toBe(400);
  const body = await response.json();
  expect(body.error).toContainEqual(expect.objectContaining({ field: 'price' }));
});
```

### API Through UI

```typescript
test('form submission calls API', async ({ page }) => {
  await page.goto('/products/new');

  await page.getByLabel('Product name').fill('Widget');
  await page.getByLabel('Price').fill('19.99');
  await page.getByRole('button', { name: 'Create product' }).click();

  await expect(page.getByText('Product created successfully')).toBeVisible();
  await page.waitForURL('/products/**');
});
```

## Middleware Testing

### Auth Redirects

```typescript
test('unauthenticated user redirected to login', async ({ page }) => {
  await page.goto('/dashboard');

  expect(page.url()).toContain('/login');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
});

test('redirect preserves return URL', async ({ page }) => {
  await page.goto('/dashboard/settings');

  const url = new URL(page.url());
  expect(url.pathname).toBe('/login');
  expect(url.searchParams.get('callbackUrl') || url.searchParams.get('returnTo'))
    .toContain('/dashboard/settings');
});
```

### Security Headers

```typescript
test('middleware sets security headers', async ({ page }) => {
  const response = await page.goto('/');

  const headers = response!.headers();
  expect(headers['x-frame-options']).toBe('DENY');
  expect(headers['x-content-type-options']).toBe('nosniff');
});
```

### Locale Rewrites

```typescript
test('middleware rewrites based on locale', async ({ page, context }) => {
  await context.setExtraHTTPHeaders({
    'Accept-Language': 'fr-FR,fr;q=0.9',
  });

  await page.goto('/');

  await expect(page.getByText('Bienvenue')).toBeVisible();
});
```

## Hydration Testing

### Console Error Detection

```typescript
test('no hydration errors in console', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Get started' }).click();

  const hydrationErrors = consoleErrors.filter(
    (e) =>
      e.includes('Hydration') ||
      e.includes('hydration') ||
      e.includes('did not match')
  );
  expect(hydrationErrors).toEqual([]);
});
```

### Interactive Elements After Hydration

```typescript
test('interactive elements work after hydration', async ({ page }) => {
  await page.goto('/');

  const counter = page.getByTestId('counter-value');
  await expect(counter).toHaveText('0');

  await page.getByRole('button', { name: 'Increment' }).click();
  await expect(counter).toHaveText('1');
});
```

## next/image Testing

```typescript
test('hero image loads with srcset', async ({ page }) => {
  await page.goto('/');

  const heroImage = page.getByRole('img', { name: 'Hero banner' });
  await expect(heroImage).toBeVisible();

  const srcset = await heroImage.getAttribute('srcset');
  expect(srcset).toBeTruthy();
  expect(srcset).toContain('w=');

  const loading = await heroImage.getAttribute('loading');
  expect(loading).not.toBe('lazy');
});

test('offscreen images lazy load', async ({ page }) => {
  await page.goto('/gallery');

  const offscreenImage = page.getByRole('img', { name: 'Gallery item 20' });

  await offscreenImage.scrollIntoViewIfNeeded();
  await expect(offscreenImage).toBeVisible();

  const naturalWidth = await offscreenImage.evaluate(
    (img: HTMLImageElement) => img.naturalWidth
  );
  expect(naturalWidth).toBeGreaterThan(0);
});
```

## NextAuth.js Authentication

### Setup Project

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'authenticated',
      use: { storageState: 'playwright/.auth/user.json' },
      dependencies: ['setup'],
    },
    { name: 'unauthenticated', testMatch: '**/*.unauth.spec.ts' },
  ],
});
```

### Auth Setup

```typescript
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/user.json';

setup('authenticate via credentials', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();

  await page.waitForURL('/dashboard');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

  await page.context().storageState({ path: authFile });
});
```

### Authenticated Tests

```typescript
test('authenticated user sees dashboard', async ({ page }) => {
  await page.goto('/dashboard');

  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('test@example.com')).toBeVisible();
});
```

## Tips

### Dev Server vs Production Build

| Scenario | Command | Trade-off |
|---|---|---|
| Local development | `npm run dev` | Fast iteration, no production behavior |
| CI pipeline | `npm run build && npm run start` | Tests real production bundle |

### Turbopack

```typescript
webServer: {
  command: process.env.CI
    ? 'npm run build && npm run start'
    : 'npx next dev --turbopack',
  url: 'http://localhost:3000',
  reuseExistingServer: !process.env.CI,
},
```

### Multiple webServer Entries

```typescript
webServer: [
  {
    command: 'npm run dev:api',
    url: 'http://localhost:4000/health',
    reuseExistingServer: !process.env.CI,
  },
  {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
],
```

## Anti-Patterns

| Don't Do This | Problem | Do This Instead |
|---|---|---|
| `await page.waitForTimeout(3000)` | Arbitrary waits are fragile | `await page.waitForURL('/path')` or `await expect(locator).toBeVisible()` |
| Test `getServerSideProps` directly | Depends on req/res context | Navigate to page and verify rendered output |
| Mock your own API routes | Hides real API bugs | Let real API handle requests; mock only external services |
| `page.goto('http://localhost:3000/path')` | Breaks when port changes | Use `page.goto('/path')` with `baseURL` |
| Run `npm run build` locally for every test | Extremely slow | Use `npm run dev` locally with `reuseExistingServer: true` |
| Test `next/image` by checking exact URLs | Paths change between dev/prod | Assert on `alt`, visibility, `naturalWidth > 0`, `srcset` |
| Test server actions by calling as functions | Server actions need Next.js runtime | Trigger through UI (forms, buttons) |

## Related

- [configuration.md](../core/configuration.md) -- Playwright configuration including `webServer`
- [authentication.md](../advanced/authentication.md) -- authentication setup and `storageState`
- [api-testing.md](../testing-patterns/api-testing.md) -- testing API routes with `request` context
- [react.md](react.md) -- React patterns for Next.js client components
