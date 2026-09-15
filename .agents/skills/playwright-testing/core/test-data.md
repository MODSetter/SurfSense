# Test Data Factories & Generators

This file covers **reusable test data builders** (factories, Faker, data generators). For related topics:

- **Per-test database fixtures** (isolation, transaction rollback): See [fixtures-hooks.md](fixtures-hooks.md#database-fixtures)
- **One-time database setup** (migrations, snapshots): See [global-setup.md](global-setup.md#database-patterns)

## Table of Contents

1. [Factory Pattern](#factory-pattern)
2. [Faker Integration](#faker-integration)
3. [Data-Driven Testing](#data-driven-testing)
4. [Test Data Fixtures](#test-data-fixtures)
5. [Database Seeding](#database-seeding)

## Factory Pattern

### Basic Factory

```typescript
// factories/user.factory.ts
interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "user" | "guest";
  createdAt: Date;
}

let userIdCounter = 0;

export function createUser(overrides: Partial<User> = {}): User {
  userIdCounter++;
  return {
    id: `user-${userIdCounter}`,
    email: `user${userIdCounter}@test.com`,
    name: `Test User ${userIdCounter}`,
    role: "user",
    createdAt: new Date(),
    ...overrides,
  };
}

// Usage
const user = createUser();
const admin = createUser({ role: "admin", name: "Admin User" });
```

### Factory with Traits

```typescript
// factories/product.factory.ts
interface Product {
  id: string;
  name: string;
  price: number;
  stock: number;
  category: string;
  featured: boolean;
}

type ProductTrait = "outOfStock" | "featured" | "expensive" | "sale";

const traits: Record<ProductTrait, Partial<Product>> = {
  outOfStock: { stock: 0 },
  featured: { featured: true },
  expensive: { price: 999.99 },
  sale: { price: 9.99 },
};

let productIdCounter = 0;

export function createProduct(
  overrides: Partial<Product> = {},
  ...traitNames: ProductTrait[]
): Product {
  productIdCounter++;

  const appliedTraits = traitNames.reduce(
    (acc, trait) => ({ ...acc, ...traits[trait] }),
    {},
  );

  return {
    id: `prod-${productIdCounter}`,
    name: `Product ${productIdCounter}`,
    price: 29.99,
    stock: 100,
    category: "General",
    featured: false,
    ...appliedTraits,
    ...overrides,
  };
}

// Usage
const product = createProduct();
const featuredProduct = createProduct({}, "featured");
const saleItem = createProduct({ name: "Sale Item" }, "sale", "featured");
const soldOut = createProduct({}, "outOfStock");
```

### Factory with Relationships

```typescript
// factories/order.factory.ts
import { createUser, User } from "./user.factory";
import { createProduct, Product } from "./product.factory";

interface OrderItem {
  product: Product;
  quantity: number;
}

interface Order {
  id: string;
  user: User;
  items: OrderItem[];
  total: number;
  status: "pending" | "paid" | "shipped" | "delivered";
}

let orderIdCounter = 0;

export function createOrder(overrides: Partial<Order> = {}): Order {
  orderIdCounter++;

  const user = overrides.user ?? createUser();
  const items = overrides.items ?? [{ product: createProduct(), quantity: 1 }];
  const total = items.reduce(
    (sum, item) => sum + item.product.price * item.quantity,
    0,
  );

  return {
    id: `order-${orderIdCounter}`,
    user,
    items,
    total,
    status: "pending",
    ...overrides,
  };
}

// Usage
const order = createOrder();
const bigOrder = createOrder({
  items: [
    { product: createProduct({ price: 100 }), quantity: 5 },
    { product: createProduct({ price: 50 }), quantity: 2 },
  ],
});
```

## Faker Integration

### Setup Faker

```bash
npm install -D @faker-js/faker
```

```typescript
// factories/faker-user.factory.ts
import { faker } from "@faker-js/faker";

interface User {
  id: string;
  email: string;
  name: string;
  avatar: string;
  address: {
    street: string;
    city: string;
    country: string;
    zipCode: string;
  };
}

export function createFakeUser(overrides: Partial<User> = {}): User {
  return {
    id: faker.string.uuid(),
    email: faker.internet.email(),
    name: faker.person.fullName(),
    avatar: faker.image.avatar(),
    address: {
      street: faker.location.streetAddress(),
      city: faker.location.city(),
      country: faker.location.country(),
      zipCode: faker.location.zipCode(),
    },
    ...overrides,
  };
}
```

### Seeded Faker for Reproducibility

```typescript
import { faker } from "@faker-js/faker";

// Set seed for reproducible data
faker.seed(12345);

export function createDeterministicUser(): User {
  return {
    id: faker.string.uuid(),
    email: faker.internet.email(),
    name: faker.person.fullName(),
    // Same seed = same data every time
  };
}

// Or seed per test
test("user profile", async ({ page }) => {
  faker.seed(42); // Reset seed for this test
  const user = createFakeUser();
  // user will always have the same data
});
```

### Faker Fixture

```typescript
// fixtures/faker.fixture.ts
import { test as base } from "@playwright/test";
import { faker } from "@faker-js/faker";

type FakerFixtures = {
  fake: typeof faker;
};

export const test = base.extend<FakerFixtures>({
  fake: async ({}, use, testInfo) => {
    // Seed based on test name for reproducibility
    faker.seed(testInfo.title.length);
    await use(faker);
  },
});

// Usage
test("create user with fake data", async ({ page, fake }) => {
  await page.goto("/signup");

  await page.getByLabel("Name").fill(fake.person.fullName());
  await page.getByLabel("Email").fill(fake.internet.email());
  await page.getByLabel("Password").fill(fake.internet.password());

  await page.getByRole("button", { name: "Sign Up" }).click();
});
```

## Data-Driven Testing

### test.each with Arrays

```typescript
const loginScenarios = [
  { email: "user@example.com", password: "pass123", expected: "Dashboard" },
  { email: "admin@example.com", password: "admin123", expected: "Admin Panel" },
  {
    email: "invalid@example.com",
    password: "wrong",
    expected: "Invalid credentials",
  },
];

for (const { email, password, expected } of loginScenarios) {
  test(`login with ${email}`, async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page.getByText(expected)).toBeVisible();
  });
}
```

### Parameterized Tests

```typescript
// data/checkout-scenarios.ts
export const checkoutScenarios = [
  {
    name: "standard shipping",
    shipping: "standard",
    expectedDays: "5-7 business days",
    expectedCost: "$5.99",
  },
  {
    name: "express shipping",
    shipping: "express",
    expectedDays: "2-3 business days",
    expectedCost: "$14.99",
  },
  {
    name: "overnight shipping",
    shipping: "overnight",
    expectedDays: "Next business day",
    expectedCost: "$29.99",
  },
];
```

```typescript
import { checkoutScenarios } from "./data/checkout-scenarios";

test.describe("shipping options", () => {
  for (const scenario of checkoutScenarios) {
    test(`checkout with ${scenario.name}`, async ({ page }) => {
      await page.goto("/checkout");

      await page.getByLabel(scenario.shipping, { exact: false }).check();

      await expect(page.getByText(scenario.expectedDays)).toBeVisible();
      await expect(page.getByText(scenario.expectedCost)).toBeVisible();
    });
  }
});
```

### CSV/JSON Data Source

```typescript
import fs from "fs";

interface TestCase {
  input: string;
  expected: string;
}

// Load test data from JSON
const testCases: TestCase[] = JSON.parse(
  fs.readFileSync("./data/search-tests.json", "utf-8"),
);

test.describe("search functionality", () => {
  for (const { input, expected } of testCases) {
    test(`search for "${input}"`, async ({ page }) => {
      await page.goto("/search");
      await page.getByLabel("Search").fill(input);
      await page.getByLabel("Search").press("Enter");

      await expect(page.getByText(expected)).toBeVisible();
    });
  }
});
```

## Test Data Fixtures

### Fixture with Factory

```typescript
// fixtures/data.fixture.ts
import { test as base } from "@playwright/test";
import { createUser, User } from "../factories/user.factory";
import { createProduct, Product } from "../factories/product.factory";

type DataFixtures = {
  testUser: User;
  testProducts: Product[];
};

export const test = base.extend<DataFixtures>({
  testUser: async ({}, use) => {
    const user = createUser({ name: "E2E Test User" });
    await use(user);
  },

  testProducts: async ({}, use) => {
    const products = [
      createProduct({ name: "Test Product 1" }),
      createProduct({ name: "Test Product 2" }),
      createProduct({ name: "Test Product 3" }),
    ];
    await use(products);
  },
});

// Usage
test("add product to cart", async ({ page, testUser, testProducts }) => {
  // Mock API with test data
  await page.route("**/api/user", (route) => route.fulfill({ json: testUser }));
  await page.route("**/api/products", (route) =>
    route.fulfill({ json: testProducts }),
  );

  await page.goto("/products");
  await expect(page.getByText(testProducts[0].name)).toBeVisible();
});
```

## Database Seeding

### API-Based Seeding

```typescript
// fixtures/seed.fixture.ts
import { test as base, APIRequestContext } from "@playwright/test";
import { createUser } from "../factories/user.factory";

type SeedFixtures = {
  seedUser: (overrides?: Partial<User>) => Promise<User>;
  cleanupUsers: string[];
};

export const test = base.extend<SeedFixtures>({
  cleanupUsers: [],

  seedUser: async ({ request, cleanupUsers }, use) => {
    await use(async (overrides = {}) => {
      const userData = createUser(overrides);

      const response = await request.post("/api/test/users", {
        data: userData,
      });
      const user = await response.json();

      cleanupUsers.push(user.id);
      return user;
    });
  },

  // Cleanup after test
  cleanupUsers: async ({ request }, use) => {
    const userIds: string[] = [];
    await use(userIds);

    // Delete all created users
    for (const id of userIds) {
      await request.delete(`/api/test/users/${id}`);
    }
  },
});

// Usage
test("user profile page", async ({ page, seedUser }) => {
  const user = await seedUser({ name: "John Doe" });

  await page.goto(`/users/${user.id}`);
  await expect(page.getByText("John Doe")).toBeVisible();
});
```

### Transaction Rollback Seeding

```typescript
// fixtures/db.fixture.ts
export const test = base.extend<{}, { db: DbTransaction }>({
  db: [
    async ({}, use) => {
      const client = await pool.connect();
      await client.query("BEGIN");

      await use({
        query: (sql: string, params?: any[]) => client.query(sql, params),
        seed: async (table: string, data: object) => {
          const keys = Object.keys(data);
          const values = Object.values(data);
          const placeholders = keys.map((_, i) => `$${i + 1}`);

          const result = await client.query(
            `INSERT INTO ${table} (${keys.join(", ")}) VALUES (${placeholders.join(", ")}) RETURNING *`,
            values,
          );
          return result.rows[0];
        },
      });

      await client.query("ROLLBACK");
      client.release();
    },
    { scope: "test" },
  ],
});
```

## Anti-Patterns to Avoid

| Anti-Pattern                    | Problem                         | Solution                   |
| ------------------------------- | ------------------------------- | -------------------------- |
| Hardcoded test data             | Brittle, repetitive             | Use factories              |
| Random data without seed        | Non-reproducible failures       | Seed faker per test        |
| Shared mutable test data        | Tests interfere with each other | Create fresh data per test |
| Manual data creation everywhere | Duplication, maintenance burden | Centralize in factories    |

## Related References

- **Fixtures**: See [fixtures-hooks.md](fixtures-hooks.md) for fixture patterns
- **API Testing**: See [test-suite-structure.md](test-suite-structure.md) for API mocking
