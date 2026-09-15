# Fixtures & Hooks

## Table of Contents

1. [Built-in Fixtures](#built-in-fixtures)
2. [Custom Fixtures](#custom-fixtures)
3. [Fixture Scopes](#fixture-scopes)
4. [Hooks](#hooks)
5. [Authentication Patterns](#authentication-patterns)
6. [Database Fixtures](#database-fixtures)

## Built-in Fixtures

### Core Fixtures

```typescript
test("example", async ({
  page, // Isolated page instance
  context, // Browser context (cookies, localStorage)
  browser, // Browser instance
  browserName, // 'chromium', 'firefox', or 'webkit'
  request, // API request context
}) => {
  // Each test gets fresh instances
});
```

### Request Fixture

```typescript
test("API call", async ({ request }) => {
  const response = await request.get("/api/users");
  await expect(response).toBeOK();

  const users = await response.json();
  expect(users).toHaveLength(5);
});
```

## Custom Fixtures

### Basic Custom Fixture

```typescript
// fixtures.ts
import { test as base } from "@playwright/test";

// Declare fixture types
type MyFixtures = {
  todoPage: TodoPage;
  apiClient: ApiClient;
};

export const test = base.extend<MyFixtures>({
  // Fixture with setup and teardown
  todoPage: async ({ page }, use) => {
    const todoPage = new TodoPage(page);
    await todoPage.goto();

    await use(todoPage); // Test runs here

    // Teardown (optional)
    await todoPage.clearTodos();
  },

  // Simple fixture
  apiClient: async ({ request }, use) => {
    await use(new ApiClient(request));
  },
});

export { expect } from "@playwright/test";
```

### Fixture with Options

```typescript
type Options = {
  defaultUser: { email: string; password: string };
};

type Fixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<Options & Fixtures>({
  // Define option with default
  defaultUser: [
    { email: "test@example.com", password: "pass123" },
    { option: true },
  ],

  // Use option in fixture
  authenticatedPage: async ({ page, defaultUser }, use) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(defaultUser.email);
    await page.getByLabel("Password").fill(defaultUser.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await use(page);
  },
});

// Override in config
export default defineConfig({
  use: {
    defaultUser: { email: "admin@example.com", password: "admin123" },
  },
});
```

### Automatic Fixtures

```typescript
export const test = base.extend<{}, { setupDb: void }>({
  // Auto-fixture runs for every test without explicit usage
  setupDb: [
    async ({}, use) => {
      await seedDatabase();
      await use();
      await cleanDatabase();
    },
    { auto: true },
  ],
});
```

## Fixture Scopes

### Test Scope (Default)

Created fresh for each test:

```typescript
test.extend({
  page: async ({ browser }, use) => {
    const page = await browser.newPage();
    await use(page);
    await page.close();
  },
});
```

### Worker Scope

Shared across tests in the same worker (each worker gets its own instance; tests in different workers do not share it):

```typescript
type WorkerFixtures = {
  sharedAccount: Account;
};

export const test = base.extend<{}, WorkerFixtures>({
  sharedAccount: [
    async ({ browser }, use) => {
      // Expensive setup - runs once per worker
      const account = await createTestAccount();
      await use(account);
      await deleteTestAccount(account);
    },
    { scope: "worker" },
  ],
});
```

### Isolate test data between parallel workers

When tests in different workers touch the same backend or DB (e.g. same user, same tenant), they can collide and cause flaky failures. Use `testInfo.workerIndex` (or `process.env.TEST_WORKER_INDEX`) in a worker-scoped fixture to create unique data per worker:

```typescript
import { test as baseTest } from "@playwright/test";

type WorkerFixtures = {
  dbUserName: string;
};

export const test = baseTest.extend<{}, WorkerFixtures>({
  dbUserName: [
    async ({}, use, testInfo) => {
      const userName = `user-${testInfo.workerIndex}`;
      await createUserInTestDatabase(userName);
      await use(userName);
      await deleteUserFromTestDatabase(userName);
    },
    { scope: "worker" },
  ],
});
```

Then each worker uses a distinct user (e.g. `user-1`, `user-2`), so parallel workers do not overwrite each other’s data.

## Hooks

### beforeEach / afterEach

```typescript
test.beforeEach(async ({ page }) => {
  // Runs before each test in file
  await page.goto("/");
});

test.afterEach(async ({ page }, testInfo) => {
  // Runs after each test
  if (testInfo.status !== "passed") {
    await page.screenshot({ path: `failed-${testInfo.title}.png` });
  }
});
```

### beforeAll / afterAll

```typescript
test.beforeAll(async ({ browser }) => {
  // Runs once before all tests in file
  // Note: Cannot use page fixture here
});

test.afterAll(async () => {
  // Runs once after all tests in file
});
```

### Describe-Level Hooks

```typescript
test.describe("User Management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/users");
  });

  test("can list users", async ({ page }) => {
    // Starts at /users
  });

  test("can add user", async ({ page }) => {
    // Starts at /users
  });
});
```

## Authentication Patterns

### Global Setup with Storage State

```typescript
// auth.setup.ts
import { test as setup, expect } from "@playwright/test";

const authFile = ".auth/user.json";

setup("authenticate", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.TEST_EMAIL!);
  await page.getByLabel("Password").fill(process.env.TEST_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await page.context().storageState({ path: authFile });
});
```

```typescript
// playwright.config.ts
export default defineConfig({
  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],
});
```

### Multiple Auth States

```typescript
// auth.setup.ts
setup("admin auth", async ({ page }) => {
  await login(page, "admin@example.com", "adminpass");
  await page.context().storageState({ path: ".auth/admin.json" });
});

setup("user auth", async ({ page }) => {
  await login(page, "user@example.com", "userpass");
  await page.context().storageState({ path: ".auth/user.json" });
});
```

```typescript
// playwright.config.ts
projects: [
  {
    name: "admin tests",
    testMatch: /.*admin.*\.spec\.ts/,
    use: { storageState: ".auth/admin.json" },
    dependencies: ["setup"],
  },
  {
    name: "user tests",
    testMatch: /.*user.*\.spec\.ts/,
    use: { storageState: ".auth/user.json" },
    dependencies: ["setup"],
  },
];
```

### Auth Fixture

```typescript
// fixtures/auth.fixture.ts
export const test = base.extend<{ adminPage: Page; userPage: Page }>({
  adminPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: ".auth/admin.json",
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },

  userPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: ".auth/user.json",
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});
```

## Database Fixtures

This section covers **per-test database fixtures** (isolation, transaction rollback). For related topics:

- **Test data factories** (builders, Faker): See [test-data.md](test-data.md)
- **One-time database setup** (migrations, snapshots): See [global-setup.md](global-setup.md#database-patterns)

### Transaction Rollback Pattern

```typescript
import { test as base } from "@playwright/test";
import { db } from "../db";

export const test = base.extend<{ dbTransaction: Transaction }>({
  dbTransaction: async ({}, use) => {
    const transaction = await db.beginTransaction();

    await use(transaction);

    await transaction.rollback(); // Clean slate for next test
  },
});
```

### Seed Data Fixture

```typescript
type TestData = {
  testUser: User;
  testProducts: Product[];
};

export const test = base.extend<TestData>({
  testUser: async ({}, use) => {
    const user = await db.users.create({
      email: `test-${Date.now()}@example.com`,
      name: "Test User",
    });

    await use(user);

    await db.users.delete(user.id);
  },

  testProducts: async ({ testUser }, use) => {
    const products = await db.products.createMany([
      { name: "Product A", ownerId: testUser.id },
      { name: "Product B", ownerId: testUser.id },
    ]);

    await use(products);

    await db.products.deleteMany(products.map((p) => p.id));
  },
});
```

## Fixture Tips

| Tip                | Explanation                                 |
| ------------------ | ------------------------------------------- |
| Fixtures are lazy  | Only created when used                      |
| Compose fixtures   | Use other fixtures as dependencies          |
| Keep setup minimal | Do heavy lifting in worker-scoped fixtures  |
| Clean up resources | Use teardown in fixtures, not afterEach     |
| Avoid shared state | Each fixture instance should be independent |

## Anti-Patterns to Avoid

| Anti-Pattern                              | Problem                                                    | Solution                                                                                                                                                                              |
| ----------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared mutable state between tests        | Race conditions, order dependencies                        | Use fixtures for isolation                                                                                                                                                            |
| Global variables in tests                 | Tests depend on execution order                            | Use fixtures or beforeEach for setup                                                                                                                                                  |
| Not cleaning up test data                 | Tests interfere with each other                            | Use fixtures with teardown or database transactions                                                                                                                                   |
| Shared `page` or `context` in `beforeAll` | State leak between tests; flaky when tests run in parallel | Use default one-context-per-test, or `beforeEach` + fresh page; if serial is required, prefer `test.describe.configure({ mode: 'serial' })` and document that isolation is sacrificed |
| Backend/DB state shared across workers    | Tests in different workers collide on same data            | Use worker-scoped fixture with `testInfo.workerIndex` to create unique data per worker                                                                                                |

## Related References

- **Page Objects with fixtures**: See [page-object-model.md](page-object-model.md) for POM patterns
- **Test organization**: See [test-suite-structure.md](test-suite-structure.md) for test structure
- **Debugging fixture issues**: See [debugging.md](../debugging/debugging.md) for troubleshooting
