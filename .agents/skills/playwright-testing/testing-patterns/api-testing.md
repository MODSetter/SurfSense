# API Testing

## Table of Contents

1. [Patterns](#patterns)
2. [Decision Guide](#decision-guide)
3. [Anti-Patterns](#anti-patterns)
4. [Troubleshooting](#troubleshooting)

> **When to use**: Testing REST APIs directly — validating endpoints, seeding test data, or verifying backend behavior without browser overhead.
> **See also**: [graphql-testing.md](graphql-testing.md) for GraphQL-specific patterns.

## Patterns

### Request Fixtures for Authenticated Clients

**Use when**: Multiple tests need an authenticated API client with shared configuration.
**Avoid when**: A single test makes one-off API calls — use the built-in `request` fixture directly.

```typescript
// fixtures/api-fixtures.ts
import { test as base, expect, APIRequestContext } from "@playwright/test";

type ApiFixtures = {
  authApi: APIRequestContext;
  adminApi: APIRequestContext;
};

export const test = base.extend<ApiFixtures>({
  authApi: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
      extraHTTPHeaders: {
        Authorization: `Bearer ${process.env.API_TOKEN}`,
        Accept: "application/json",
      },
    });
    await use(ctx);
    await ctx.dispose();
  },

  adminApi: async ({ playwright }, use) => {
    const loginCtx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
    });
    const loginResp = await loginCtx.post("/auth/login", {
      data: {
        email: process.env.ADMIN_EMAIL,
        password: process.env.ADMIN_PASSWORD,
      },
    });
    expect(loginResp.ok()).toBeTruthy();
    const { token } = await loginResp.json();
    await loginCtx.dispose();

    const ctx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
      extraHTTPHeaders: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    await use(ctx);
    await ctx.dispose();
  },
});

export { expect };
```

```typescript
// tests/api/admin.spec.ts
import { test, expect } from "../../fixtures/api-fixtures";

test("admin retrieves all accounts", async ({ adminApi }) => {
  const resp = await adminApi.get("/admin/accounts");
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.accounts.length).toBeGreaterThan(0);
});
```

### CRUD Operations

**Use when**: Making HTTP requests — GET, POST, PUT, PATCH, DELETE with headers, query params, and bodies.
**Avoid when**: You need to test browser-rendered responses (redirects, cookies with `HttpOnly`).

```typescript
import { test, expect } from "@playwright/test";

test("full CRUD cycle", async ({ request }) => {
  // GET with query params
  const listResp = await request.get("/api/items", {
    params: { page: 1, limit: 10, category: "tools" },
  });
  expect(listResp.ok()).toBeTruthy();

  // POST with JSON body
  const createResp = await request.post("/api/items", {
    data: {
      title: "Hammer",
      price: 19.99,
      category: "tools",
    },
  });
  expect(createResp.status()).toBe(201);
  const created = await createResp.json();

  // PUT — full replacement
  const putResp = await request.put(`/api/items/${created.id}`, {
    data: {
      title: "Claw Hammer",
      price: 24.99,
      category: "tools",
    },
  });
  expect(putResp.ok()).toBeTruthy();

  // PATCH — partial update
  const patchResp = await request.patch(`/api/items/${created.id}`, {
    data: { price: 22.5 },
  });
  expect(patchResp.ok()).toBeTruthy();
  const patched = await patchResp.json();
  expect(patched.price).toBe(22.5);

  // DELETE
  const delResp = await request.delete(`/api/items/${created.id}`);
  expect(delResp.status()).toBe(204);

  // Verify deletion
  const getDeleted = await request.get(`/api/items/${created.id}`);
  expect(getDeleted.status()).toBe(404);
});

test("form-urlencoded body", async ({ request }) => {
  const resp = await request.post("/oauth/token", {
    form: {
      grant_type: "client_credentials",
      client_id: "my-client",
      client_secret: "secret-value",
    },
  });
  expect(resp.ok()).toBeTruthy();
  const token = await resp.json();
  expect(token).toHaveProperty("access_token");
});
```

### Dedicated API Project Configuration

**Use when**: Writing dedicated API test suites that do not need a browser.

```typescript
// playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  projects: [
    {
      name: "api",
      testDir: "./tests/api",
      use: {
        baseURL: "https://api.myapp.io",
        extraHTTPHeaders: { Accept: "application/json" },
      },
    },
    {
      name: "e2e",
      testDir: "./tests/e2e",
      use: {
        baseURL: "https://myapp.io",
        browserName: "chromium",
      },
    },
  ],
});
```

### Response Assertions

**Use when**: Validating response status, headers, and body structure.
**Avoid when**: Never skip these — every API test should assert on status and body.

```typescript
import { test, expect } from "@playwright/test";

test("comprehensive response validation", async ({ request }) => {
  const resp = await request.get("/api/items/101");

  // Status code — always check first
  expect(resp.status()).toBe(200);
  expect(resp.ok()).toBeTruthy();

  // Headers
  expect(resp.headers()["content-type"]).toContain("application/json");
  expect(resp.headers()["cache-control"]).toMatch(/max-age=\d+/);

  const item = await resp.json();

  // Exact match on known fields
  expect(item.id).toBe(101);
  expect(item.title).toBe("Widget");

  // Partial match — ignore fields you don't care about
  expect(item).toMatchObject({
    id: 101,
    title: "Widget",
    status: expect.stringMatching(/^(active|inactive|archived)$/),
  });

  // Type checks
  expect(item).toMatchObject({
    id: expect.any(Number),
    title: expect.any(String),
    createdAt: expect.any(String),
    tags: expect.any(Array),
  });

  // Array content
  expect(item.tags).toEqual(expect.arrayContaining(["featured"]));
  expect(item.tags).not.toContain("deprecated");

  // Nested object
  expect(item.metadata).toMatchObject({
    views: expect.any(Number),
    rating: expect.any(Number),
  });

  // Date format
  expect(new Date(item.createdAt).toISOString()).toBe(item.createdAt);
});

test("list response structure", async ({ request }) => {
  const resp = await request.get("/api/items");
  const body = await resp.json();

  expect(body.items).toHaveLength(10);

  for (const item of body.items) {
    expect(item).toMatchObject({
      id: expect.any(Number),
      title: expect.any(String),
      price: expect.any(Number),
    });
  }

  expect(body.pagination).toEqual({
    page: 1,
    limit: 10,
    total: expect.any(Number),
    totalPages: expect.any(Number),
  });
});
```

### API Data Seeding

**Use when**: E2E tests need specific data to exist before running. API seeding is 10-100x faster than UI-based setup.
**Avoid when**: The test specifically validates the creation flow through the UI.

```typescript
import { test as base, expect } from "@playwright/test";

type SeedFixtures = {
  seedAccount: { id: number; email: string; password: string };
  seedWorkspace: { id: number; name: string };
};

export const test = base.extend<SeedFixtures>({
  seedAccount: async ({ request }, use) => {
    const email = `account-${Date.now()}@test.io`;
    const password = "SecurePass123!";

    const resp = await request.post("/api/accounts", {
      data: { name: "Test Account", email, password },
    });
    expect(resp.ok()).toBeTruthy();
    const account = await resp.json();

    await use({ id: account.id, email, password });

    // Cleanup
    await request.delete(`/api/accounts/${account.id}`);
  },

  seedWorkspace: async ({ request, seedAccount }, use) => {
    const resp = await request.post("/api/workspaces", {
      data: { name: `Workspace ${Date.now()}`, ownerId: seedAccount.id },
    });
    expect(resp.ok()).toBeTruthy();
    const workspace = await resp.json();

    await use({ id: workspace.id, name: workspace.name });

    await request.delete(`/api/workspaces/${workspace.id}`);
  },
});

export { expect };
```

```typescript
// tests/e2e/workspace-dashboard.spec.ts
import { test, expect } from "../../fixtures/seed-fixtures";

test("user sees workspace on dashboard", async ({
  page,
  seedAccount,
  seedWorkspace,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(seedAccount.email);
  await page.getByLabel("Password").fill(seedAccount.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("/dashboard");
  await expect(
    page.getByRole("heading", { name: seedWorkspace.name })
  ).toBeVisible();
});
```

### Error Response Testing

**Use when**: Every API has error paths — test them. A missing 401 test today is a security hole tomorrow.

```typescript
import { test, expect } from "@playwright/test";

test.describe("Error responses", () => {
  test("400 — validation error with details", async ({ request }) => {
    const resp = await request.post("/api/items", {
      data: { title: "", price: -5 },
    });
    expect(resp.status()).toBe(400);

    const body = await resp.json();
    expect(body).toMatchObject({
      error: "Validation Error",
      details: expect.any(Array),
    });
    expect(body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          field: "title",
          message: expect.any(String),
        }),
        expect.objectContaining({
          field: "price",
          message: expect.any(String),
        }),
      ])
    );
  });

  test("401 — missing authentication", async ({ request }) => {
    const resp = await request.get("/api/protected/resource", {
      headers: { Authorization: "" },
    });
    expect(resp.status()).toBe(401);
    const body = await resp.json();
    expect(body.error).toMatch(/unauthorized|unauthenticated/i);
  });

  test("403 — insufficient permissions", async ({ request }) => {
    const resp = await request.delete("/api/admin/items/1");
    expect(resp.status()).toBe(403);
    const body = await resp.json();
    expect(body.error).toMatch(/forbidden|insufficient permissions/i);
  });

  test("404 — resource not found", async ({ request }) => {
    const resp = await request.get("/api/items/999999");
    expect(resp.status()).toBe(404);
    const body = await resp.json();
    expect(body).toMatchObject({ error: expect.stringMatching(/not found/i) });
  });

  test("409 — conflict on duplicate", async ({ request }) => {
    const sku = `SKU-${Date.now()}`;
    await request.post("/api/items", { data: { title: "First", sku } });

    const resp = await request.post("/api/items", {
      data: { title: "Duplicate", sku },
    });
    expect(resp.status()).toBe(409);
  });

  test("422 — unprocessable entity", async ({ request }) => {
    const resp = await request.post("/api/orders", {
      data: { items: [] },
    });
    expect(resp.status()).toBe(422);
    const body = await resp.json();
    expect(body.error).toContain("at least one item");
  });

  test("429 — rate limiting", async ({ request }) => {
    const responses = await Promise.all(
      Array.from({ length: 50 }, () =>
        request.get("/api/search", { params: { q: "test" } })
      )
    );
    const rateLimited = responses.filter((r) => r.status() === 429);
    expect(rateLimited.length).toBeGreaterThan(0);
    expect(rateLimited[0].headers()["retry-after"]).toBeDefined();
  });
});
```

### File Upload via API

**Use when**: Testing file upload endpoints with multipart form data.
**Avoid when**: You need to test the browser file picker dialog — use `page.setInputFiles()` instead.

```typescript
import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

test("upload file via multipart", async ({ request }) => {
  const filePath = path.resolve("tests/fixtures/report.pdf");

  const resp = await request.post("/api/documents/upload", {
    multipart: {
      file: {
        name: "report.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(filePath),
      },
      description: "Monthly report",
      category: "reports",
    },
  });

  expect(resp.status()).toBe(201);
  const body = await resp.json();
  expect(body).toMatchObject({
    id: expect.any(String),
    filename: "report.pdf",
    mimeType: "application/pdf",
    size: expect.any(Number),
    url: expect.stringMatching(/^https:\/\//),
  });
});

test("rejects oversized files", async ({ request }) => {
  const largeBuffer = Buffer.alloc(11 * 1024 * 1024); // 11MB

  const resp = await request.post("/api/documents/upload", {
    multipart: {
      file: {
        name: "large-file.bin",
        mimeType: "application/octet-stream",
        buffer: largeBuffer,
      },
    },
  });

  expect(resp.status()).toBe(413);
});
```

### Chained API Calls

**Use when**: Testing multi-step workflows — create, read, update, delete sequences; order flows; state machine transitions.
**Avoid when**: You can test each endpoint in isolation and the interactions are trivial.

```typescript
import { test, expect } from "@playwright/test";

test("complete order workflow", async ({ request }) => {
  // Step 1: Create a product
  const productResp = await request.post("/api/products", {
    data: { name: "Gadget", price: 49.99, stock: 50 },
  });
  expect(productResp.status()).toBe(201);
  const product = await productResp.json();

  // Step 2: Create a cart
  const cartResp = await request.post("/api/carts", {
    data: { items: [{ productId: product.id, quantity: 3 }] },
  });
  expect(cartResp.status()).toBe(201);
  const cart = await cartResp.json();
  expect(cart.total).toBe(149.97);

  // Step 3: Checkout
  const orderResp = await request.post("/api/orders", {
    data: {
      cartId: cart.id,
      shippingAddress: {
        street: "456 Main Ave",
        city: "Metropolis",
        zip: "54321",
      },
    },
  });
  expect(orderResp.status()).toBe(201);
  const order = await orderResp.json();
  expect(order.status).toBe("pending");
  expect(order.items).toHaveLength(1);

  // Step 4: Verify order in list
  const ordersResp = await request.get("/api/orders");
  const orders = await ordersResp.json();
  expect(orders.items.map((o: any) => o.id)).toContain(order.id);

  // Step 5: Verify stock decreased
  const updatedProduct = await (
    await request.get(`/api/products/${product.id}`)
  ).json();
  expect(updatedProduct.stock).toBe(47);

  // Cleanup
  await request.delete(`/api/orders/${order.id}`);
  await request.delete(`/api/products/${product.id}`);
});

test("state machine transitions — publish workflow", async ({ request }) => {
  const createResp = await request.post("/api/articles", {
    data: { title: "Draft Article", body: "Content here." },
  });
  const article = await createResp.json();
  expect(article.status).toBe("draft");

  // Submit for review
  const reviewResp = await request.patch(`/api/articles/${article.id}/status`, {
    data: { status: "in_review" },
  });
  expect(reviewResp.ok()).toBeTruthy();
  expect((await reviewResp.json()).status).toBe("in_review");

  // Approve
  const approveResp = await request.patch(
    `/api/articles/${article.id}/status`,
    {
      data: { status: "published" },
    }
  );
  expect(approveResp.ok()).toBeTruthy();
  expect((await approveResp.json()).status).toBe("published");

  // Cannot revert to draft from published
  const revertResp = await request.patch(`/api/articles/${article.id}/status`, {
    data: { status: "draft" },
  });
  expect(revertResp.status()).toBe(422);

  await request.delete(`/api/articles/${article.id}`);
});

test("API + E2E hybrid — seed via API, verify in browser", async ({
  request,
  page,
}) => {
  const resp = await request.post("/api/products", {
    data: {
      name: `Hybrid Product ${Date.now()}`,
      price: 35.0,
      published: true,
    },
  });
  const product = await resp.json();

  await page.goto("/products");
  await expect(page.getByRole("heading", { name: product.name })).toBeVisible();
  await expect(page.getByText("$35.00")).toBeVisible();

  await request.delete(`/api/products/${product.id}`);
});
```

### Schema Validation with Zod

**Use when**: Verifying API responses match a contract — field types, required fields, value constraints.
**Avoid when**: You only need to check one or two specific fields — use `toMatchObject` instead.

```typescript
import { test, expect } from "@playwright/test";
import { z } from "zod";

const ItemSchema = z.object({
  id: z.number().positive(),
  title: z.string().min(1),
  price: z.number().nonnegative(),
  status: z.enum(["active", "inactive", "archived"]),
  createdAt: z.string().datetime(),
  metadata: z.object({
    views: z.number().int().nonnegative(),
    rating: z.number().min(0).max(5).nullable(),
  }),
});

const PaginatedItemsSchema = z.object({
  items: z.array(ItemSchema),
  pagination: z.object({
    page: z.number().int().positive(),
    limit: z.number().int().positive(),
    total: z.number().int().nonnegative(),
  }),
});

test("GET /api/items matches schema", async ({ request }) => {
  const resp = await request.get("/api/items");
  expect(resp.ok()).toBeTruthy();

  const body = await resp.json();
  const result = PaginatedItemsSchema.safeParse(body);

  if (!result.success) {
    throw new Error(
      `Schema validation failed:\n${result.error.issues
        .map((i) => `  ${i.path.join(".")}: ${i.message}`)
        .join("\n")}`
    );
  }
});
```

## Decision Guide

| Scenario                                         | Use API Tests               | Use E2E Tests                  | Why                                                                |
| ------------------------------------------------ | --------------------------- | ------------------------------ | ------------------------------------------------------------------ |
| Validate response status/body/headers            | Yes                         | No                             | No browser needed; 10-100x faster                                  |
| Test business logic (calculations, rules)        | Yes                         | No                             | API tests isolate backend logic from UI                            |
| Verify form submission creates correct data      | Seed via API, submit via UI | Yes                            | UI test validates the form; API check confirms persistence         |
| Test error messages shown to user                | No                          | Yes                            | Error rendering is a UI concern                                    |
| Validate pagination, filtering, sorting          | Yes                         | Maybe both                     | API test for correctness; E2E test only if the UI logic is complex |
| Seed test data for E2E tests                     | Yes (fixture)               | No                             | API seeding is fast and reliable                                   |
| Test auth flows (login/logout/RBAC)              | Yes for token/session logic | Yes for UI flow                | Both matter: API protects resources, UI guides users               |
| Verify file upload processing                    | Yes                         | Only if testing file picker UI | API test validates backend processing                              |
| Contract/schema regression testing               | Yes                         | No                             | Schema tests run in milliseconds                                   |
| Test third-party webhook handling                | Yes                         | No                             | Webhooks are API-to-API; no UI involved                            |
| Verify redirect behavior after action            | No                          | Yes                            | Redirects are browser/navigation concerns                          |
| Test real-time updates (WebSocket + API trigger) | API triggers                | E2E verifies                   | Seed via API, observe in browser                                   |

## Anti-Patterns

| Don't Do This                                        | Problem                                                                                | Do This Instead                                                   |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Use E2E tests to validate pure API responses         | Slow, flaky, launches a browser for no reason                                          | Use `request` fixture — no browser, direct HTTP                   |
| Ignore `response.status()`                           | A 500 with a fallback body can pass all body assertions                                | Always assert status first: `expect(response.status()).toBe(200)` |
| Skip response header checks                          | Missing `Content-Type`, `Cache-Control`, CORS headers cause production bugs            | Assert critical headers                                           |
| Only test the happy path                             | Real users trigger 400, 401, 403, 404, 409, 422 — every one needs a test               | Dedicate a `describe` block to error responses                    |
| Hardcode IDs in API tests                            | Tests break when database is reset or IDs are reassigned                               | Create resources in the test, use returned IDs                    |
| Share mutable state between tests                    | Tests that depend on execution order are flaky and cannot run in parallel              | Each test creates and cleans up its own data                      |
| Parse `response.text()` then `JSON.parse()` manually | Playwright's `response.json()` handles this and throws clear errors on non-JSON        | Use `await response.json()`                                       |
| Forget cleanup after creating resources              | Test pollution: subsequent tests may see stale data or hit unique constraints          | Use fixtures with teardown or explicit `delete` calls             |
| Use `page.request` when you don't need a page        | `page.request` shares cookies with the browser context, which may cause auth confusion | Use the standalone `request` fixture for pure API tests           |

## Troubleshooting

### "Request failed: connect ECONNREFUSED 127.0.0.1:3000"

**Cause**: The API server is not running, or `baseURL` points to the wrong host/port.

**Fix**: Verify the server is running before tests. Use `webServer` in config to start it automatically.

```typescript
// playwright.config.ts
export default defineConfig({
  webServer: {
    command: "npm run start:api",
    url: "http://localhost:3000/api/health",
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: "http://localhost:3000" },
});
```

### "response.json() failed — body is not valid JSON"

**Cause**: The endpoint returned HTML (error page), plain text, or an empty body instead of JSON.

**Fix**: Check `response.status()` first — a 500 or 302 often returns HTML. Log `await response.text()` to see the actual body. Verify the `Accept: application/json` header is set.

```typescript
const resp = await request.get("/api/endpoint");
if (!resp.ok()) {
  console.error(`Status: ${resp.status()}, Body: ${await resp.text()}`);
}
const body = await resp.json();
```

### "401 Unauthorized" when using `request` fixture

**Cause**: The built-in `request` fixture does not carry browser cookies or auth tokens automatically.

**Fix**: Set `extraHTTPHeaders` in config or create a custom authenticated fixture. If you need cookies from a browser login, use `page.request` instead.

```typescript
// Option A: config-level headers
export default defineConfig({
  use: {
    extraHTTPHeaders: { Authorization: `Bearer ${process.env.API_TOKEN}` },
  },
});

// Option B: per-request headers
const resp = await request.get("/api/resource", {
  headers: { Authorization: `Bearer ${token}` },
});

// Option C: use page.request to inherit browser cookies
test("API call with browser auth", async ({ page }) => {
  await page.goto("/login");
  // ... login via UI ...
  const resp = await page.request.get("/api/profile");
  expect(resp.ok()).toBeTruthy();
});
```

### Tests pass locally but fail in CI

**Cause**: Different environments, database state, or missing environment variables.

**Fix**: Use `process.env` for secrets and base URLs. Run database seeds or migrations in `globalSetup`. Use unique identifiers (timestamps, UUIDs) for test data. Check that the CI `baseURL` matches the deployed service.
