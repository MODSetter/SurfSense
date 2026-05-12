# Choosing Test Types: E2E, Component, or API

## Table of Contents

1. [Decision Matrix](#decision-matrix)
2. [API Tests](#api-tests)
3. [Component Tests](#component-tests)
4. [E2E Tests](#e2e-tests)
5. [Layering Test Types](#layering-test-types)
6. [Common Mistakes](#common-mistakes)
7. [Related](#related)

> **When to use**: Deciding which test type to write for a feature. Ask: "What's the cheapest test that gives confidence this works?"

## Decision Matrix

| Scenario                    | Recommended Type | Rationale                                     |
| --------------------------- | ---------------- | --------------------------------------------- |
| Login / auth flow           | E2E              | Cross-page, cookies, redirects, session state |
| Form submission             | Component        | Isolated validation logic, error states       |
| CRUD operations             | API              | Data integrity matters more than UI           |
| Search with results UI      | Component + API  | API for query logic; component for rendering  |
| Cross-page navigation       | E2E              | Routing, history, deep linking                |
| API error handling          | API              | Status codes, error shapes, edge cases        |
| UI error feedback           | Component        | Toast, banner, inline error rendering         |
| Accessibility               | Component        | ARIA roles, keyboard nav per-component        |
| Responsive layout           | Component        | Viewport-specific rendering without full app  |
| API contract validation     | API              | Response shapes, headers, auth                |
| WebSocket/real-time         | E2E              | Requires full browser environment             |
| Payment / checkout          | E2E              | Multi-step, third-party iframes               |
| Onboarding wizard           | E2E              | Multi-step, state persists across pages       |
| Widget behavior             | Component        | Toggle, accordion, date picker, modal         |
| Permissions / authorization | API              | Role-based access is backend logic            |

## API Tests

**Ideal for**:

- CRUD operations (create, read, update, delete)
- Input validation and error responses (400, 422)
- Permission and authorization checks
- Data integrity and business rules
- API contract verification
- Edge cases expensive to reproduce through UI
- Test data setup/teardown for E2E tests

**Avoid for**:

- Testing how errors display to users
- Browser-specific behavior (cookies, redirects)
- Visual layout or responsive design
- Flows requiring JavaScript execution or DOM interaction
- Third-party iframe interactions

```typescript
import { test, expect } from "@playwright/test";

test.describe("Products API", () => {
  let token: string;

  test.beforeAll(async ({ request }) => {
    const res = await request.post("/api/auth/token", {
      data: { email: "manager@shop.io", password: "mgr-secret" },
    });
    token = (await res.json()).accessToken;
  });

  test("creates product with valid payload", async ({ request }) => {
    const res = await request.post("/api/products", {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "Widget Pro", sku: "WGT-100", price: 29.99 },
    });

    expect(res.status()).toBe(201);
    const product = await res.json();
    expect(product).toMatchObject({ name: "Widget Pro", sku: "WGT-100" });
    expect(product).toHaveProperty("id");
  });

  test("rejects duplicate SKU with 409", async ({ request }) => {
    const res = await request.post("/api/products", {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "Duplicate", sku: "WGT-100", price: 19.99 },
    });

    expect(res.status()).toBe(409);
    expect((await res.json()).message).toContain("already exists");
  });

  test("returns 422 for missing required fields", async ({ request }) => {
    const res = await request.post("/api/products", {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: "Incomplete" },
    });

    expect(res.status()).toBe(422);
    const err = await res.json();
    expect(err.errors).toContainEqual(
      expect.objectContaining({ field: "sku" })
    );
  });

  test("staff role cannot delete products", async ({ request }) => {
    const staffLogin = await request.post("/api/auth/token", {
      data: { email: "staff@shop.io", password: "staff-pass" },
    });
    const staffToken = (await staffLogin.json()).accessToken;

    const res = await request.delete("/api/products/123", {
      headers: { Authorization: `Bearer ${staffToken}` },
    });

    expect(res.status()).toBe(403);
  });

  test("lists products with pagination", async ({ request }) => {
    const res = await request.get("/api/products", {
      headers: { Authorization: `Bearer ${token}` },
      params: { page: "1", limit: "20" },
    });

    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.items).toBeInstanceOf(Array);
    expect(body.items.length).toBeLessThanOrEqual(20);
    expect(body).toHaveProperty("totalCount");
  });
});
```

## Component Tests

**Ideal for**:

- Form validation (required fields, format rules, error messages)
- Interactive widgets (modals, dropdowns, accordions, date pickers)
- Conditional rendering (show/hide, loading states, empty states)
- Accessibility per-component (ARIA attributes, keyboard navigation)
- Responsive layout at different viewports
- Visual states (hover, focus, disabled, selected)

**Avoid for**:

- Testing routing or navigation between pages
- Flows requiring real cookies, sessions, or server-side state
- Data persistence or API contract validation
- Third-party iframe interactions
- Anything requiring multiple pages or browser contexts

```typescript
import { test, expect } from "@playwright/experimental-ct-react";
import { ContactForm } from "../src/components/ContactForm";

test.describe("ContactForm component", () => {
  test("displays validation errors on empty submit", async ({ mount }) => {
    const component = await mount(<ContactForm onSubmit={() => {}} />);

    await component.getByRole("button", { name: "Send message" }).click();

    await expect(component.getByText("Name is required")).toBeVisible();
    await expect(component.getByText("Email is required")).toBeVisible();
  });

  test("rejects malformed email", async ({ mount }) => {
    const component = await mount(<ContactForm onSubmit={() => {}} />);

    await component.getByLabel("Name").fill("Alex");
    await component.getByLabel("Email").fill("invalid-email");
    await component.getByLabel("Message").fill("Hello");
    await component.getByRole("button", { name: "Send message" }).click();

    await expect(component.getByText("Enter a valid email")).toBeVisible();
  });

  test("invokes onSubmit with form data", async ({ mount }) => {
    const submissions: Array<{ name: string; email: string; message: string }> =
      [];
    const component = await mount(
      <ContactForm onSubmit={(data) => submissions.push(data)} />
    );

    await component.getByLabel("Name").fill("Alex");
    await component.getByLabel("Email").fill("alex@company.org");
    await component.getByLabel("Message").fill("Inquiry about pricing");
    await component.getByRole("button", { name: "Send message" }).click();

    expect(submissions).toHaveLength(1);
    expect(submissions[0]).toEqual({
      name: "Alex",
      email: "alex@company.org",
      message: "Inquiry about pricing",
    });
  });

  test("disables button during submission", async ({ mount }) => {
    const component = await mount(
      <ContactForm onSubmit={() => {}} submitting={true} />
    );

    await expect(
      component.getByRole("button", { name: "Sending..." })
    ).toBeDisabled();
  });

  test("associates labels with inputs for accessibility", async ({ mount }) => {
    const component = await mount(<ContactForm onSubmit={() => {}} />);

    await expect(
      component.getByRole("textbox", { name: "Name" })
    ).toBeVisible();
    await expect(
      component.getByRole("textbox", { name: "Email" })
    ).toBeVisible();
  });
});
```

## E2E Tests

**Ideal for**:

- Critical user flows that generate revenue (checkout, signup)
- Authentication flows (login, SSO, MFA, password reset)
- Multi-page workflows where state carries across navigation
- Flows involving third-party iframes (payment widgets)
- Smoke tests validating the entire stack
- Real-time collaboration requiring multiple browser contexts

**Avoid for**:

- Testing every form validation permutation
- CRUD operations where UI is a thin wrapper
- Verifying individual component states
- Testing API response shapes or error codes
- Responsive layout at every breakpoint
- Edge cases that only affect the backend

```typescript
import { test, expect } from "@playwright/test";

test.describe("subscription flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.request.post("/api/test/seed-account", {
      data: { plan: "free", email: "subscriber@demo.io" },
    });
    await page.goto("/account/upgrade");
  });

  test("upgrades to premium plan", async ({ page }) => {
    await test.step("select plan", async () => {
      await expect(
        page.getByRole("heading", { name: "Choose Your Plan" })
      ).toBeVisible();
      await page.getByRole("button", { name: "Select Premium" }).click();
    });

    await test.step("enter billing details", async () => {
      await page.getByLabel("Cardholder name").fill("Sam Johnson");
      await page.getByLabel("Billing address").fill("456 Oak Ave");
      await page.getByLabel("City").fill("Seattle");
      await page.getByRole("combobox", { name: "State" }).selectOption("WA");
      await page.getByLabel("Postal code").fill("98101");
      await page.getByRole("button", { name: "Continue" }).click();
    });

    await test.step("complete payment", async () => {
      const paymentFrame = page.frameLocator('iframe[title="Secure Payment"]');
      await paymentFrame.getByLabel("Card number").fill("5555555555554444");
      await paymentFrame.getByLabel("Expiry").fill("09/29");
      await paymentFrame.getByLabel("CVV").fill("456");
      await page.getByRole("button", { name: "Subscribe now" }).click();
    });

    await test.step("verify success", async () => {
      await page.waitForURL("**/account/subscription/success**");
      await expect(
        page.getByRole("heading", { name: "Welcome to Premium" })
      ).toBeVisible();
      await expect(page.getByText(/Subscription #\d+/)).toBeVisible();
    });
  });
});
```

## Layering Test Types

Effective test suites combine all three types. Example for an "inventory management" feature:

### API Layer (60% of tests)

Cover every backend logic permutation. Cheap to run and maintain.

```
tests/api/inventory.spec.ts
  - creates item with valid data (201)
  - rejects duplicate SKU (409)
  - rejects invalid quantity format (422)
  - rejects missing required fields (422)
  - warehouse-staff cannot delete items (403)
  - unauthenticated request returns 401
  - lists items with pagination
  - filters items by category
  - updates item stock level
  - archives an item
  - prevents archiving items with pending orders
```

### Component Layer (30% of tests)

Cover every visual state and interaction.

```
tests/components/InventoryForm.spec.tsx
  - shows validation errors on empty submit
  - shows inline error for invalid SKU format
  - disables submit while saving
  - calls onSubmit with form data
  - resets form after successful save

tests/components/InventoryTable.spec.tsx
  - renders item rows from props
  - shows empty state when no items
  - handles archive confirmation modal
  - sorts by column header click
  - shows stock level badges with correct colors
```

### E2E Layer (10% of tests)

Cover only critical paths proving full stack works.

```
tests/e2e/inventory.spec.ts
  - manager creates item and sees it in list
  - manager updates item stock level
  - warehouse-staff cannot access admin settings
```

### Execution Profile

For this feature:

- **11 API tests** — ~2 seconds total, no browser
- **10 component tests** — ~5 seconds total, real browser but no server
- **3 E2E tests** — ~15 seconds total, full stack

Total: 24 tests, ~22 seconds. API tests catch most regressions. Component tests catch UI bugs. E2E tests prove wiring works. If E2E fails but API and component pass, the problem is in integration (routing, state management, API client).

## Common Mistakes

| Anti-Pattern                              | Problem                                                  | Better Approach                                                |
| ----------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------- |
| E2E for every validation rule             | 30-second browser test for something API covers in 200ms | API test for validation, one component test for error display  |
| No API tests, all E2E                     | Slow suite, flaky from UI timing, hard to diagnose       | API tests for data/logic, E2E for critical paths only          |
| Component tests mocking everything        | Tests pass but app broken because mocks drift            | Mock only external boundaries; API tests verify real contracts |
| Same assertion in API, component, AND E2E | Triple maintenance cost                                  | Each layer tests what it uniquely verifies                     |
| E2E creating test data via UI             | 2-minute test where 90 seconds is setup                  | Seed via API in `beforeEach`, test actual flow                 |
| Testing third-party behavior              | Testing that Stripe validates cards (Stripe's job)       | Mock Stripe; trust their contract                              |
| Skipping API layer                        | Can't tell if bug is frontend or backend                 | API tests isolate backend; component tests isolate frontend    |
| One giant E2E for entire feature          | 5-minute test failing somewhere with no clear cause      | Focused E2E per critical path; use `test.step()`               |

## Related

- [test-suite-structure.md](../core/test-suite-structure.md) — file structure and naming
- [api-testing.md](../testing-patterns/api-testing.md) — Playwright's `request` API for HTTP testing
- [component-testing.md](../testing-patterns/component-testing.md) — setting up component tests
- [authentication.md](../advanced/authentication.md) — auth flow patterns with `storageState`
- [when-to-mock.md](when-to-mock.md) — when to mock vs hit real services
- [pom-vs-fixtures.md](pom-vs-fixtures.md) — organizing shared test logic
