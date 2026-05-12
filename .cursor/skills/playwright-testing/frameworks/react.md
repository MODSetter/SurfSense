# React Application Testing

## Table of Contents

1. [Patterns](#patterns)
2. [Setup](#setup)
3. [Framework Tips](#framework-tips)
4. [Anti-Patterns](#anti-patterns)
5. [Related](#related)

> **When to use**: Testing React apps built with Vite, Create React App, or custom bundlers. Covers E2E testing, component testing, React Router navigation, form libraries, portals, error boundaries, and context/state verification.
> **Prerequisites**: [configuration.md](../core/configuration.md), [locators.md](../core/locators.md)

## Patterns

### Testing Context and Global State

**Use when**: Verifying React context (theme, auth, locale) and state management (Redux, Zustand) produce correct UI changes.
**Avoid when**: You want to assert on raw state objects—test the UI, not internal state.

```typescript
import { test, expect } from '@playwright/test';

test.describe('theme switching', () => {
  test('toggle applies dark mode across pages', async ({ page }) => {
    await page.goto('/preferences');

    const root = page.locator('html');
    await expect(root).not.toHaveClass(/dark-mode/);

    await page.getByRole('switch', { name: 'Enable dark theme' }).click();
    await expect(root).toHaveClass(/dark-mode/);

    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page.locator('html')).toHaveClass(/dark-mode/);
  });
});

test.describe('cart state persistence', () => {
  test('item count updates globally', async ({ page }) => {
    await page.goto('/catalog');

    const badge = page.getByTestId('cart-badge');

    await page.getByRole('listitem')
      .filter({ hasText: 'Wireless Headphones' })
      .getByRole('button', { name: 'Add' })
      .click();
    await expect(badge).toHaveText('1');

    await page.getByRole('link', { name: 'Contact' }).click();
    await expect(badge).toHaveText('1');
  });
});

test.describe('auth state', () => {
  test('login updates header across components', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('link', { name: 'Login' })).toBeVisible();

    await page.getByRole('link', { name: 'Login' }).click();
    await page.getByLabel('Username').fill('testuser');
    await page.getByLabel('Password').fill('secret123');
    await page.getByRole('button', { name: 'Submit' }).click();

    await expect(page.getByRole('link', { name: 'Login' })).toBeHidden();
    await expect(page.getByText('testuser')).toBeVisible();
  });
});
```

### React Router Navigation

**Use when**: Testing client-side routing with React Router v6+—route transitions, URL parameters, protected routes, browser history.
**Avoid when**: Server-side routing (Next.js App Router—see [nextjs.md](nextjs.md)).

```typescript
import { test, expect } from '@playwright/test';

test.describe('client routing', () => {
  test('navigation preserves SPA state', async ({ page }) => {
    await page.goto('/');

    await page.evaluate(() => {
      (window as any).__spaMarker = 'active';
    });

    await page.getByRole('link', { name: 'Inventory' }).click();
    await page.waitForURL('/inventory');

    const marker = await page.evaluate(() => (window as any).__spaMarker);
    expect(marker).toBe('active');
  });

  test('query params filter content', async ({ page }) => {
    await page.goto('/items?type=books');

    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible();

    await page.getByRole('link', { name: 'Music' }).click();
    await page.waitForURL('/items?type=music');

    await expect(page.getByRole('heading', { name: 'Music' })).toBeVisible();
  });

  test('nested routes render layouts', async ({ page }) => {
    await page.goto('/account/security');

    await expect(page.getByRole('heading', { name: 'Account' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Security', level: 2 })).toBeVisible();

    await page.getByRole('link', { name: 'Privacy' }).click();
    await page.waitForURL('/account/privacy');

    await expect(page.getByRole('heading', { name: 'Account' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Privacy', level: 2 })).toBeVisible();
  });

  test('history navigation works', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Inventory' }).click();
    await page.waitForURL('/inventory');
    await page.getByRole('link', { name: 'Help' }).click();
    await page.waitForURL('/help');

    await page.goBack();
    await expect(page).toHaveURL(/\/inventory/);

    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
  });

  test('protected route redirects', async ({ page }) => {
    await page.goto('/admin/users');

    await expect(page).toHaveURL(/\/login/);
  });

  test('unknown route shows 404', async ({ page }) => {
    await page.goto('/nonexistent-path');

    await expect(page.getByRole('heading', { name: 'Not Found' })).toBeVisible();
  });
});
```

### Testing Hooks Through UI

**Use when**: Verifying custom hooks produce correct UI behavior—Playwright cannot call hooks directly.
**Avoid when**: Hook logic is pure computation—use unit tests instead.

```typescript
import { test, expect } from '@playwright/test';

test.describe('useDebounce via SearchBox', () => {
  test('batches rapid input', async ({ page }) => {
    await page.goto('/search');

    const apiCalls: string[] = [];
    await page.route('**/api/query*', async (route) => {
      apiCalls.push(route.request().url());
      await route.continue();
    });

    await page.getByRole('textbox', { name: 'Search' }).pressSequentially('testing', {
      delay: 40,
    });

    await expect(page.getByRole('listitem')).toHaveCount(3);
    expect(apiCalls.length).toBeLessThanOrEqual(2);
  });
});

test.describe('usePagination via DataGrid', () => {
  test('page controls work', async ({ page }) => {
    await page.goto('/records');

    await expect(page.getByText('Page 1 of 10')).toBeVisible();

    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page.getByText('Page 2 of 10')).toBeVisible();

    await page.getByRole('button', { name: 'Previous' }).click();
    await expect(page.getByText('Page 1 of 10')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });
});
```

### Form Libraries (React Hook Form, Formik)

**Use when**: Testing forms built with react-hook-form or Formik—Playwright interacts with DOM, form library is transparent.

```typescript
import { test, expect } from '@playwright/test';

test.describe('signup form', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/signup');
  });

  test('validation on empty submit', async ({ page }) => {
    await page.getByRole('button', { name: 'Register' }).click();

    await expect(page.getByText('Email required')).toBeVisible();
    await expect(page.getByText('Password required')).toBeVisible();
  });

  test('inline validation on blur', async ({ page }) => {
    const email = page.getByLabel('Email');
    await email.fill('invalid');
    await email.blur();

    await expect(page.getByText('Invalid email format')).toBeVisible();
  });

  test('password strength indicator', async ({ page }) => {
    const pwd = page.getByLabel('Password', { exact: true });

    await pwd.fill('weak');
    await expect(page.getByText('Minimum 8 characters')).toHaveClass(/invalid/);

    await pwd.fill('StrongPass1!');
    await expect(page.getByText('Minimum 8 characters')).toHaveClass(/valid/);
  });

  test('successful submission redirects', async ({ page }) => {
    await page.getByLabel('Name').fill('Alice');
    await page.getByLabel('Email').fill('alice@test.com');
    await page.getByLabel('Password', { exact: true }).fill('Secure123!');
    await page.getByLabel('Confirm').fill('Secure123!');
    await page.getByLabel('Accept terms').check();

    await page.getByRole('button', { name: 'Register' }).click();

    await page.waitForURL('/welcome');
    await expect(page.getByText('Hello, Alice')).toBeVisible();
  });

  test('submit button disabled during request', async ({ page }) => {
    await page.route('**/api/signup', async (route) => {
      await new Promise((r) => setTimeout(r, 800));
      await route.fulfill({ status: 201, json: { id: 1 } });
    });

    await page.getByLabel('Name').fill('Bob');
    await page.getByLabel('Email').fill('bob@test.com');
    await page.getByLabel('Password', { exact: true }).fill('Secure123!');
    await page.getByLabel('Confirm').fill('Secure123!');
    await page.getByLabel('Accept terms').check();

    await page.getByRole('button', { name: 'Register' }).click();

    await expect(page.getByRole('button', { name: /Registering|Loading/ })).toBeDisabled();
  });
});
```

### Portals (Modals, Tooltips, Dropdowns)

**Use when**: Testing components rendered via `ReactDOM.createPortal()`—modals, dialogs, tooltips, menus. These render outside parent DOM but Playwright sees the full document.

```typescript
import { test, expect } from '@playwright/test';

test.describe('portal components', () => {
  test('modal interaction', async ({ page }) => {
    await page.goto('/items');

    await page.getByRole('button', { name: 'Remove' }).first().click();

    const dialog = page.getByRole('dialog', { name: 'Confirm removal' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();

    await dialog.getByRole('button', { name: 'Remove' }).click();
    await expect(dialog).toBeHidden();
  });

  test('escape closes modal', async ({ page }) => {
    await page.goto('/items');
    await page.getByRole('button', { name: 'Remove' }).first().click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
  });

  test('tooltip on hover', async ({ page }) => {
    await page.goto('/panel');

    await page.getByRole('button', { name: 'Help' }).hover();
    await expect(page.getByRole('tooltip')).toBeVisible();

    await page.mouse.move(0, 0);
    await expect(page.getByRole('tooltip')).toBeHidden();
  });

  test('dropdown menu', async ({ page }) => {
    await page.goto('/panel');

    await page.getByRole('button', { name: 'Actions' }).click();

    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();

    await menu.getByRole('menuitem', { name: 'Rename' }).click();
    await expect(menu).toBeHidden();
  });

  test('toast auto-dismisses', async ({ page }) => {
    await page.goto('/preferences');

    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Preferences saved')).toBeVisible();

    await expect(page.getByText('Preferences saved')).toBeHidden({ timeout: 8000 });
  });
});
```

### Error Boundaries

**Use when**: Verifying error boundaries catch rendering errors and show fallback UI.
**Avoid when**: Testing error handling in event handlers or async code—error boundaries only catch render errors.

```typescript
import { test, expect } from '@playwright/test';

test.describe('error boundary', () => {
  test('shows fallback on crash', async ({ page }) => {
    await page.route('**/api/widgets', (route) => {
      route.fulfill({
        status: 200,
        json: { widgets: null },
      });
    });

    await page.goto('/panel');

    await expect(page.getByText('Something went wrong')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(page.getByRole('navigation')).toBeVisible();
  });

  test('retry recovers component', async ({ page }) => {
    let calls = 0;
    await page.route('**/api/widgets', (route) => {
      calls++;
      if (calls === 1) {
        route.fulfill({ status: 200, json: { widgets: null } });
      } else {
        route.fulfill({ status: 200, json: { widgets: [{ id: 1, name: 'Chart' }] } });
      }
    });

    await page.goto('/panel');

    await expect(page.getByText('Something went wrong')).toBeVisible();

    await page.getByRole('button', { name: 'Retry' }).click();

    await expect(page.getByText('Something went wrong')).toBeHidden();
    await expect(page.getByText('Chart')).toBeVisible();
  });
});
```

### Component Testing (Experimental)

**Use when**: Testing complex interactive components in isolation—data tables, form wizards, rich editors. Needs real browser but not full app.
**Avoid when**: Component depends heavily on backend data or routing—use E2E instead.

```typescript
// playwright-ct.config.ts
import { defineConfig, devices } from '@playwright/experimental-ct-react';

export default defineConfig({
  testDir: './tests/components',
  testMatch: '**/*.ct.ts',
  use: {
    trace: 'on-first-retry',
    ctPort: 3100,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

```typescript
// tests/components/Stepper.ct.ts
import { test, expect } from '@playwright/experimental-ct-react';
import Stepper from '../../src/components/Stepper';

test('increments on click', async ({ mount }) => {
  const component = await mount(<Stepper initial={0} />);

  await expect(component.getByText('Value: 0')).toBeVisible();
  await component.getByRole('button', { name: '+' }).click();
  await expect(component.getByText('Value: 1')).toBeVisible();
});

test('fires onChange callback', async ({ mount }) => {
  const values: number[] = [];
  const component = await mount(
    <Stepper initial={0} onChange={(v) => values.push(v)} />
  );

  await component.getByRole('button', { name: '+' }).click();
  await component.getByRole('button', { name: '+' }).click();

  expect(values).toEqual([1, 2]);
});

test('respects min boundary', async ({ mount }) => {
  const component = await mount(<Stepper initial={0} min={0} />);

  await expect(component.getByRole('button', { name: '-' })).toBeDisabled();
});
```

## Setup

### E2E Config (Vite)

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
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'mobile', use: { ...devices['iPhone 14'] } },
  ],

  webServer: {
    command: process.env.CI ? 'npm run build && npx vite preview --port 5173' : 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

### CRA vs Vite Differences

| Aspect | Create React App | Vite |
|---|---|---|
| Default port | `3000` | `5173` |
| Build output | `build/` | `dist/` |
| Serve production | `npx serve -s build -l 3000` | `npx vite preview --port 5173` |
| Env var prefix | `REACT_APP_*` | `VITE_*` |

## Framework Tips

### Strict Mode Double Effects

React Strict Mode runs effects twice in development. Tests should be resilient:

- Don't assert exact API call counts in dev mode
- Run against production build for call count assertions, or account for double invocations

### Suspense and Lazy Components

```typescript
test('lazy route loads content', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('link', { name: 'Analytics' }).click();

  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible();
});
```

### Detecting Memory Leaks

```typescript
test('no unmounted state warnings', async ({ page }) => {
  const warnings: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'warning' && msg.text().includes('unmounted')) {
      warnings.push(msg.text());
    }
  });

  await page.goto('/panel');
  await page.getByRole('link', { name: 'Settings' }).click();
  await page.goBack();
  await page.getByRole('link', { name: 'Profile' }).click();

  expect(warnings).toEqual([]);
});
```

## Anti-Patterns

| Don't | Problem | Do Instead |
|---|---|---|
| `page.evaluate(() => store.getState())` | Couples tests to implementation | Assert on UI: `expect(badge).toHaveText('3')` |
| Import components in E2E tests | E2E runs in Node, not browser | Use `@playwright/experimental-ct-react` for components |
| `page.waitForTimeout(500)` after state changes | Timing varies across machines | `expect(locator).toHaveText('value')` auto-retries |
| `page.locator('.MuiButton-root')` | Class names change between versions | `page.getByRole('button', { name: 'Submit' })` |
| Test every component with CT | Overhead for simple components | CT for complex widgets, unit tests for logic, E2E for flows |
| Skip keyboard navigation tests | Accessibility regressions common | Test Tab, Enter, Escape, Arrow interactions |
| Assert on `__REACT_FIBER__` internals | Not stable across versions | Only interact with rendered DOM |

## Related

- [locators.md](../core/locators.md) — locator strategies for any React component library
- [assertions-waiting.md](../core/assertions-waiting.md) — auto-waiting for React state changes
- [forms-validation.md](../testing-patterns/forms-validation.md) — form testing patterns
- [component-testing.md](../testing-patterns/component-testing.md) — in-depth component testing
- [test-architecture.md](../architecture/test-architecture.md) — E2E vs component vs unit decisions
- [nextjs.md](nextjs.md) — Next.js-specific patterns for SSR
