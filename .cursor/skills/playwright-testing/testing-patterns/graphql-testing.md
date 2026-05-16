# GraphQL Testing

## Table of Contents

1. [Patterns](#patterns)
2. [Anti-Patterns](#anti-patterns)
3. [Troubleshooting](#troubleshooting)

> **When to use**: Testing GraphQL APIs — queries, mutations, variables, and error handling.

## Patterns

### Basic Query with Variables

All GraphQL requests go through `POST` to a single endpoint. Send `query`, `variables`, and optionally `operationName` in the JSON body.

```typescript
import { test, expect } from "@playwright/test";

const GQL_ENDPOINT = "/graphql";

test("query with variables", async ({ request }) => {
  const resp = await request.post(GQL_ENDPOINT, {
    data: {
      query: `
        query FetchItem($id: ID!) {
          item(id: $id) {
            id
            title
            price
            reviews { id rating }
          }
        }
      `,
      variables: { id: "101" },
    },
  });

  expect(resp.ok()).toBeTruthy();
  const { data, errors } = await resp.json();

  // GraphQL returns 200 even on errors — always check both
  expect(errors).toBeUndefined();
  expect(data.item).toMatchObject({
    id: "101",
    title: expect.any(String),
    price: expect.any(Number),
  });
  expect(data.item.reviews).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: expect.any(String),
        rating: expect.any(Number),
      }),
    ])
  );
});
```

### Mutations

```typescript
import { test, expect } from "@playwright/test";

const GQL_ENDPOINT = "/graphql";

test("mutation creates resource", async ({ request }) => {
  const resp = await request.post(GQL_ENDPOINT, {
    data: {
      query: `
        mutation AddItem($input: ItemInput!) {
          addItem(input: $input) {
            id
            title
            status
          }
        }
      `,
      variables: {
        input: {
          title: "New Widget",
          price: 15.0,
          status: "DRAFT",
        },
      },
    },
  });

  const { data, errors } = await resp.json();
  expect(errors).toBeUndefined();
  expect(data.addItem).toMatchObject({
    id: expect.any(String),
    title: "New Widget",
    status: "DRAFT",
  });
});
```

### Validation Errors

```typescript
import { test, expect } from "@playwright/test";

const GQL_ENDPOINT = "/graphql";

test("handles validation errors", async ({ request }) => {
  const resp = await request.post(GQL_ENDPOINT, {
    data: {
      query: `
        mutation AddItem($input: ItemInput!) {
          addItem(input: $input) { id }
        }
      `,
      variables: { input: { title: "" } },
    },
  });

  const { data, errors } = await resp.json();
  expect(errors).toBeDefined();
  expect(errors.length).toBeGreaterThan(0);
  expect(errors[0].message).toContain("title");
  expect(errors[0].extensions?.code).toBe("BAD_USER_INPUT");
});
```

### Authorization Errors

```typescript
import { test, expect } from "@playwright/test";

const GQL_ENDPOINT = "/graphql";

test("handles authorization errors", async ({ request }) => {
  const resp = await request.post(GQL_ENDPOINT, {
    data: {
      query: `
        query AdminDashboard {
          adminMetrics { revenue activeUsers }
        }
      `,
    },
  });

  const { data, errors } = await resp.json();
  expect(errors).toBeDefined();
  expect(errors[0].extensions?.code).toBe("UNAUTHORIZED");
  expect(data?.adminMetrics).toBeNull();
});
```

### Authenticated GraphQL Fixture

```typescript
// fixtures/graphql-fixtures.ts
import { test as base, expect, APIRequestContext } from "@playwright/test";

type GraphQLFixtures = {
  gqlClient: APIRequestContext;
  adminGqlClient: APIRequestContext;
};

export const test = base.extend<GraphQLFixtures>({
  gqlClient: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
      extraHTTPHeaders: {
        Authorization: `Bearer ${process.env.API_TOKEN}`,
        "Content-Type": "application/json",
      },
    });
    await use(ctx);
    await ctx.dispose();
  },

  adminGqlClient: async ({ playwright }, use) => {
    const loginCtx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
    });
    const loginResp = await loginCtx.post("/graphql", {
      data: {
        query: `
          mutation Login($email: String!, $password: String!) {
            login(email: $email, password: $password) { token }
          }
        `,
        variables: {
          email: process.env.ADMIN_EMAIL,
          password: process.env.ADMIN_PASSWORD,
        },
      },
    });
    const { data } = await loginResp.json();
    
    if (!data?.login?.token) {
      throw new Error(`Admin login failed: status ${loginResp.status()}, response: ${JSON.stringify(data)}`);
    }
    
    await loginCtx.dispose();

    const ctx = await playwright.request.newContext({
      baseURL: "https://api.myapp.io",
      extraHTTPHeaders: {
        Authorization: `Bearer ${data.login.token}`,
        "Content-Type": "application/json",
      },
    });
    await use(ctx);
    await ctx.dispose();
  },
});

export { expect };
```

### GraphQL Helper Function

```typescript
// utils/graphql.ts
import { APIRequestContext, expect } from "@playwright/test";

export async function gqlQuery<T = any>(
  request: APIRequestContext,
  query: string,
  variables?: Record<string, any>
): Promise<{ data: T; errors?: any[] }> {
  const resp = await request.post("/graphql", {
    data: { query, variables },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

export async function gqlMutation<T = any>(
  request: APIRequestContext,
  mutation: string,
  variables?: Record<string, any>
): Promise<{ data: T; errors?: any[] }> {
  return gqlQuery<T>(request, mutation, variables);
}
```

```typescript
// tests/api/items.spec.ts
import { test, expect } from "@playwright/test";
import { gqlQuery, gqlMutation } from "../../utils/graphql";

test("fetch and update item", async ({ request }) => {
  const { data: fetchData } = await gqlQuery(
    request,
    `query GetItem($id: ID!) { item(id: $id) { id title } }`,
    { id: "101" }
  );
  expect(fetchData.item.title).toBeDefined();

  const { data: updateData, errors } = await gqlMutation(
    request,
    `mutation UpdateItem($id: ID!, $title: String!) {
      updateItem(id: $id, title: $title) { id title }
    }`,
    { id: "101", title: "Updated Title" }
  );
  expect(errors).toBeUndefined();
  expect(updateData.updateItem.title).toBe("Updated Title");
});
```

## Anti-Patterns

| Don't Do This | Problem | Do This Instead |
| --- | --- | --- |
| Check only `response.ok()` | GraphQL returns 200 even on errors — `errors` array is the real signal | Always check both `data` and `errors` in the response body |
| Ignore `errors` array | Validation and auth errors appear in `errors`, not HTTP status | Destructure and assert: `expect(errors).toBeUndefined()` |
| Hardcode query strings inline everywhere | Duplicated queries are hard to maintain | Extract queries to constants or use a helper function |
| Skip variable validation | Invalid variables cause cryptic server errors | Validate input shape before sending |

## Troubleshooting

### GraphQL returns 200 but data is null

**Cause**: GraphQL servers return HTTP 200 even when the query has errors. The actual error is in the `errors` array.

**Fix**: Always destructure and check both `data` and `errors`.

```typescript
const { data, errors } = await resp.json();
if (errors) {
  console.error("GraphQL errors:", JSON.stringify(errors, null, 2));
}
expect(errors).toBeUndefined();
expect(data.item).toBeDefined();
```

### "Cannot query field X on type Y"

**Cause**: The field doesn't exist in the schema, or you're querying the wrong type.

**Fix**: Verify the schema. Use introspection or check your GraphQL IDE for available fields.

```typescript
// Introspection query to debug schema
const { data } = await request.post("/graphql", {
  data: {
    query: `{ __type(name: "Item") { fields { name type { name } } } }`,
  },
});
console.log(data.__type.fields);
```

### Variables not being applied

**Cause**: Variable names in the query don't match the `variables` object keys, or types don't match.

**Fix**: Ensure variable names match exactly (case-sensitive) and types align with the schema.

```typescript
// Wrong: variable name mismatch
const resp = await request.post("/graphql", {
  data: {
    query: `query GetItem($itemId: ID!) { item(id: $itemId) { id } }`,
    variables: { id: "101" }, // Should be { itemId: "101" }
  },
});

// Correct
const resp = await request.post("/graphql", {
  data: {
    query: `query GetItem($itemId: ID!) { item(id: $itemId) { id } }`,
    variables: { itemId: "101" },
  },
});
```
