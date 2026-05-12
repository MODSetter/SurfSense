# Organizing Reusable Test Code

## Table of Contents

1. [Pattern Comparison](#pattern-comparison)
2. [Selection Flowchart](#selection-flowchart)
3. [Page Objects](#page-objects)
4. [Custom Fixtures](#custom-fixtures)
5. [Helper Functions](#helper-functions)
6. [Combined Project Structure](#combined-project-structure)
7. [Anti-Patterns](#anti-patterns)

Use all three patterns together. Most projects benefit from a hybrid approach:

- **Page objects** for UI interaction (pages/components with 5+ interactions)
- **Custom fixtures** for test infrastructure (auth state, database, API clients, anything with lifecycle)
- **Helper functions** for stateless utilities (generate data, format values, simple waits)

If only using one pattern, choose **custom fixtures** — they handle setup/teardown, compose well, and Playwright is built around them.

## Pattern Comparison

| Aspect | Page Objects | Custom Fixtures | Helper Functions |
|---|---|---|---|
| **Purpose** | Encapsulate UI interactions | Provide resources with setup/teardown | Stateless utilities |
| **Lifecycle** | Manual (constructor/methods) | Built-in (`use()` with automatic teardown) | None |
| **Composability** | Constructor injection or fixture wiring | Depend on other fixtures | Call other functions |
| **Best for** | Pages with many reused interactions | Resources needing setup AND teardown | Simple logic with no side effects |

## Selection Flowchart

```text
What kind of reusable code?
|
+-- Interacts with browser page/component?
|   |
|   +-- Has 5+ interactions (fill, click, navigate, assert)?
|   |   +-- YES: Used in 3+ test files?
|   |   |   +-- YES --> PAGE OBJECT
|   |   |   +-- NO --> Inline or small helper
|   |   +-- NO --> HELPER FUNCTION
|   |
|   +-- Needs setup before AND cleanup after test?
|       +-- YES --> CUSTOM FIXTURE
|       +-- NO --> PAGE OBJECT method or HELPER
|
+-- Manages resource with lifecycle (create/destroy)?
|   +-- Examples: auth state, DB connection, API client, test user
|   +-- YES --> CUSTOM FIXTURE (always)
|
+-- Stateless utility? (no browser, no side effects)
|   +-- Examples: random email, format date, build URL, parse response
|   +-- YES --> HELPER FUNCTION
|
+-- Not sure?
    +-- Start with HELPER FUNCTION
    +-- Promote to PAGE OBJECT when interactions grow
    +-- Promote to FIXTURE when lifecycle needed
```

## Page Objects

Best for pages/components with 5+ interactions appearing in 3+ test files.

```typescript
// page-objects/booking.page.ts
import { type Page, type Locator, expect } from '@playwright/test';

export class BookingPage {
  readonly page: Page;
  readonly dateField: Locator;
  readonly guestCount: Locator;
  readonly roomType: Locator;
  readonly reserveBtn: Locator;
  readonly totalPrice: Locator;

  constructor(page: Page) {
    this.page = page;
    this.dateField = page.getByLabel('Check-in date');
    this.guestCount = page.getByLabel('Guests');
    this.roomType = page.getByLabel('Room type');
    this.reserveBtn = page.getByRole('button', { name: 'Reserve' });
    this.totalPrice = page.getByTestId('total-price');
  }

  async goto() {
    await this.page.goto('/booking');
  }

  async fillDetails(opts: { date: string; guests: number; room: string }) {
    await this.dateField.fill(opts.date);
    await this.guestCount.fill(String(opts.guests));
    await this.roomType.selectOption(opts.room);
  }

  async reserve() {
    await this.reserveBtn.click();
    await this.page.waitForURL('**/confirmation');
  }

  async expectPrice(amount: string) {
    await expect(this.totalPrice).toHaveText(amount);
  }
}
```

```typescript
// tests/booking/reservation.spec.ts
import { test, expect } from '@playwright/test';
import { BookingPage } from '../page-objects/booking.page';

test('complete reservation with standard room', async ({ page }) => {
  const booking = new BookingPage(page);
  await booking.goto();
  await booking.fillDetails({ date: '2026-03-15', guests: 2, room: 'standard' });
  await booking.reserve();
  await expect(page.getByText('Reservation confirmed')).toBeVisible();
});
```

**Page object principles:**
- One class per logical page/component, not per URL
- Constructor takes `Page`
- Locators as `readonly` properties in constructor
- Methods represent user intent (`reserve`, `fillDetails`), not low-level clicks
- Navigation methods (`goto`) belong on the page object

## Custom Fixtures

Best for resources needing setup before and teardown after tests — auth state, database connections, API clients, test users.

```typescript
// fixtures/base.fixture.ts
import { test as base, expect } from '@playwright/test';
import { BookingPage } from '../page-objects/booking.page';
import { generateMember } from '../helpers/data';

type Fixtures = {
  bookingPage: BookingPage;
  member: { email: string; password: string; id: string };
  loggedInPage: import('@playwright/test').Page;
};

export const test = base.extend<Fixtures>({
  bookingPage: async ({ page }, use) => {
    await use(new BookingPage(page));
  },

  member: async ({ request }, use) => {
    const data = generateMember();
    const res = await request.post('/api/test/members', { data });
    const member = await res.json();
    await use(member);
    await request.delete(`/api/test/members/${member.id}`);
  },

  loggedInPage: async ({ page, member }, use) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(member.email);
    await page.getByLabel('Password').fill(member.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL('/dashboard');
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

```typescript
// tests/dashboard/overview.spec.ts
import { test, expect } from '../../fixtures/base.fixture';

test('member sees dashboard widgets', async ({ loggedInPage }) => {
  await expect(loggedInPage.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(loggedInPage.getByTestId('stats-widget')).toBeVisible();
});

test('new member sees welcome prompt', async ({ loggedInPage, member }) => {
  await expect(loggedInPage.getByText(`Welcome, ${member.email}`)).toBeVisible();
});
```

**Fixture principles:**
- Use `test.extend()` — never module-level variables
- `use()` callback separates setup from teardown
- Teardown runs even if test fails
- Fixtures compose: one can depend on another
- Fixtures are lazy: created only when requested
- Wrap page objects in fixtures for lifecycle management

## Helper Functions

Best for stateless utilities — generating test data, formatting values, building URLs, parsing responses.

```typescript
// helpers/data.ts
import { randomUUID } from 'node:crypto';

export function generateEmail(prefix = 'user'): string {
  return `${prefix}-${Date.now()}-${randomUUID().slice(0, 8)}@test.local`;
}

export function generateMember(overrides: Partial<Member> = {}): Member {
  return {
    email: generateEmail(),
    password: 'SecurePass456!',
    name: 'Test Member',
    ...overrides,
  };
}

interface Member {
  email: string;
  password: string;
  name: string;
}

export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
```

```typescript
// helpers/assertions.ts
import { type Page, expect } from '@playwright/test';

export async function expectNotification(page: Page, message: string): Promise<void> {
  const notification = page.getByRole('alert').filter({ hasText: message });
  await expect(notification).toBeVisible();
  await expect(notification).toBeHidden({ timeout: 10000 });
}
```

```typescript
// tests/settings/account.spec.ts
import { test, expect } from '@playwright/test';
import { generateEmail } from '../../helpers/data';
import { expectNotification } from '../../helpers/assertions';

test('update account email', async ({ page }) => {
  const newEmail = generateEmail('updated');
  await page.goto('/settings/account');
  await page.getByLabel('Email').fill(newEmail);
  await page.getByRole('button', { name: 'Save' }).click();
  await expectNotification(page, 'Account updated');
  await expect(page.getByLabel('Email')).toHaveValue(newEmail);
});
```

**Helper principles:**
- Pure functions with no side effects
- No browser state — take `page` as parameter if needed
- Promote to fixture if setup/teardown needed
- Promote to page object if many page interactions grow
- Keep small and focused

## Combined Project Structure

```text
tests/
+-- fixtures/
|   +-- auth.fixture.ts
|   +-- db.fixture.ts
|   +-- base.fixture.ts
+-- page-objects/
|   +-- login.page.ts
|   +-- booking.page.ts
|   +-- components/
|       +-- data-table.component.ts
+-- helpers/
|   +-- data.ts
|   +-- assertions.ts
+-- e2e/
|   +-- auth/
|   |   +-- login.spec.ts
|   +-- booking/
|       +-- reservation.spec.ts
playwright.config.ts
```

**Layer responsibilities:**

| Layer | Pattern | Responsibility |
|---|---|---|
| **Test file** | `test()` | Describes behavior, orchestrates layers |
| **Fixtures** | `test.extend()` | Resource lifecycle — setup, provide, teardown |
| **Page objects** | Classes | UI interaction — navigation, actions, locators |
| **Helpers** | Functions | Utilities — data generation, formatting, assertions |

## Anti-Patterns

### Page object managing resources

```typescript
// BAD: page object handling API calls and database
class LoginPage {
  async createUser() { /* API call */ }
  async deleteUser() { /* API call */ }
  async signIn(email: string, password: string) { /* UI */ }
}
```

Resource lifecycle belongs in fixtures where teardown is guaranteed. Keep only `signIn` in the page object.

### Locator-only page objects

```typescript
// BAD: no methods, just locators
class LoginPage {
  emailInput = this.page.getByLabel('Email');
  passwordInput = this.page.getByLabel('Password');
  submitBtn = this.page.getByRole('button', { name: 'Sign in' });
  constructor(private page: Page) {}
}
```

Add intent-revealing methods or skip the page object entirely.

### Monolithic fixtures

```typescript
// BAD: one fixture doing everything
test.extend({
  everything: async ({ page, request }, use) => {
    const user = await createUser(request);
    const products = await seedProducts(request, 50);
    await setupPayment(request, user.id);
    await page.goto('/dashboard');
    await use({ user, products, page });
    // massive teardown...
  },
});
```

Break into small, composable fixtures. Each fixture does one thing.

### Helpers with side effects

```typescript
// BAD: module-level state
let createdUserId: string;

export async function createTestUser(request: APIRequestContext) {
  const res = await request.post('/api/users', { data: { email: 'test@example.com' } });
  const user = await res.json();
  createdUserId = user.id; // shared across tests!
  return user;
}
```

Module-level state leaks between parallel tests. If it has side effects and needs cleanup, make it a fixture.

### Over-abstracting simple operations

```typescript
// BAD: helper for one-liner
export async function clickButton(page: Page, name: string) {
  await page.getByRole('button', { name }).click();
}
```

Only abstract when there is real duplication (3+ usages) or complexity (5+ interactions).
